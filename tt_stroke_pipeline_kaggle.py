"""
Table Tennis Stroke Pipeline - All-in-One Kaggle Notebook Version

This file combines all components of the stroke detection pipeline:
- Models (StrokeSegment dataclass)
- Annotation loading (CSV + XML parsing, including CVAT format)
- Video feature extraction (optical flow + frame difference)
- Dataset building (feature table generation)
- Model training (Random Forest classifier)

Usage in Kaggle:
1. Upload your data to /kaggle/input/stroke-data/
   Structure: raw_videos/, annotations/csv/, annotations/xml/
2. Run: python tt_stroke_pipeline_kaggle.py
3. Outputs saved to /kaggle/output/
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
import pandas as pd
from lxml import etree
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from tqdm import tqdm

try:
    import joblib
except ImportError:
    from sklearn.externals import joblib


# ============================================================================
# MODELS: Stroke Segment Data Structure
# ============================================================================

@dataclass(frozen=True)
class StrokeSegment:
    """Represents a single stroke interval in a video."""
    video: str
    label: str
    start_frame: int
    end_frame: int

    @property
    def duration_frames(self) -> int:
        return max(0, self.end_frame - self.start_frame + 1)


# ============================================================================
# ANNOTATION LOADING: CSV and XML Parsers
# ============================================================================

_IDLE_LABELS = {"idle", "none", "background", "rest", "ready"}
_LABEL_ALIASES = {
    "serev": "serve",
}


def _norm_label(value: object) -> str:
    """Normalize label: lowercase and apply aliases (e.g., serev -> serve)."""
    label = str(value).strip().lower()
    return _LABEL_ALIASES.get(label, label)


def _norm_video_name(value: str) -> str:
    """Extract filename from video path."""
    p = Path(str(value).strip())
    return p.name


def _to_int(value: object) -> int:
    """Convert value to int via float (handles "123.0" style strings)."""
    return int(float(value))


def _extract_video_from_cvat_meta(root: etree._Element, fallback_stem: str) -> str:
    """Extract video name from CVAT XML metadata."""
    task_name = root.findtext(".//meta//task//name")
    if task_name and task_name.strip():
        return _norm_video_name(task_name.strip())
    return fallback_stem


def _build_segments_from_frame_labels(df: pd.DataFrame) -> list[StrokeSegment]:
    """Convert frame-level labels to contiguous stroke segments."""
    segments: list[StrokeSegment] = []
    for video_name, group in df.groupby("video"):
        g = group.sort_values("frame")
        current_label = None
        start_frame = None
        prev_frame = None

        for row in g.itertuples(index=False):
            frame = _to_int(row.frame)
            label = str(row.label).strip().lower()
            if label in _IDLE_LABELS:
                label = "idle"

            if current_label is None:
                current_label = label
                start_frame = frame
                prev_frame = frame
                continue

            is_contiguous = frame == (prev_frame + 1)
            if label == current_label and is_contiguous:
                prev_frame = frame
                continue

            if current_label != "idle":
                segments.append(
                    StrokeSegment(
                        video=video_name,
                        label=current_label,
                        start_frame=start_frame,
                        end_frame=prev_frame,
                    )
                )
            current_label = label
            start_frame = frame
            prev_frame = frame

        if current_label is not None and current_label != "idle":
            segments.append(
                StrokeSegment(
                    video=video_name,
                    label=current_label,
                    start_frame=start_frame,
                    end_frame=prev_frame,
                )
            )
    return segments


def _load_single_csv(csv_path: Path) -> list[StrokeSegment]:
    """Load stroke annotations from CSV."""
    df = pd.read_csv(csv_path)
    if df.empty:
        return []

    df.columns = [c.strip().lower() for c in df.columns]
    if "video" not in df.columns:
        if "video_path" in df.columns:
            df["video"] = df["video_path"]
        elif "filename" in df.columns:
            df["video"] = df["filename"]
        elif "video_name" in df.columns:
            df["video"] = df["video_name"]
        elif "stroke_id" in df.columns:
            df["video"] = csv_path.stem
        else:
            raise ValueError(f"{csv_path.name}: missing video/video_path/filename column")

    df["video"] = df["video"].map(_norm_video_name)

    if "stroke_type" in df.columns and "label" not in df.columns:
        df["label"] = df["stroke_type"]

    if {"start_frame", "end_frame", "label"}.issubset(df.columns):
        out: list[StrokeSegment] = []
        for row in df.itertuples(index=False):
            out.append(
                StrokeSegment(
                    video=row.video,
                    label=_norm_label(row.label),
                    start_frame=_to_int(row.start_frame),
                    end_frame=_to_int(row.end_frame),
                )
            )
        return out

    if {"frame", "label"}.issubset(df.columns):
        return _build_segments_from_frame_labels(df[["video", "frame", "label"]])

    if {"start_time", "end_time", "label", "fps"}.issubset(df.columns):
        out: list[StrokeSegment] = []
        for row in df.itertuples(index=False):
            fps = float(row.fps)
            out.append(
                StrokeSegment(
                    video=row.video,
                    label=_norm_label(row.label),
                    start_frame=_to_int(float(row.start_time) * fps),
                    end_frame=_to_int(float(row.end_time) * fps),
                )
            )
        return out

    raise ValueError(
        f"{csv_path.name}: unsupported CSV schema. Expected columns including either "
        "(video,start_frame,end_frame,label) or (video,frame,label) or "
        "(video,start_time,end_time,label,fps)."
    )


def _extract_label_from_cvat_track(track: etree._Element) -> str:
    """Extract the most common stroke_type from CVAT track boxes."""
    labels: list[str] = []

    for box in track.findall("box"):
        outside = box.attrib.get("outside", "0")
        if outside == "1":
            continue
        for attr in box.findall("attribute"):
            name = str(attr.attrib.get("name", "")).strip().lower()
            if name in {"stroke_type", "label", "class", "name"} and attr.text:
                labels.append(_norm_label(attr.text))

    if labels:
        return Counter(labels).most_common(1)[0][0]
    return _norm_label(track.attrib.get("label", "stroke"))


def _extract_xml_segments(xml_path: Path) -> list[StrokeSegment]:
    """Load stroke annotations from XML (supports CVAT 1.1 and generic formats)."""
    tree = etree.parse(str(xml_path))
    root = tree.getroot()

    segments: list[StrokeSegment] = []

    # Handle CVAT 1.1 track schema first
    tracks = root.findall(".//track")
    if tracks:
        default_video = _extract_video_from_cvat_meta(root=root, fallback_stem=xml_path.stem)
        for track in tracks:
            boxes = track.findall("box")
            if not boxes:
                continue

            frames = []
            for box in boxes:
                outside = box.attrib.get("outside", "0")
                if outside == "1":
                    continue
                frame = box.attrib.get("frame")
                if frame is None:
                    continue
                frames.append(_to_int(frame))

            if not frames:
                continue

            segments.append(
                StrokeSegment(
                    video=_norm_video_name(default_video),
                    label=_extract_label_from_cvat_track(track),
                    start_frame=min(frames),
                    end_frame=max(frames),
                )
            )
        if segments:
            return segments

    # Fallback: generic XML parsing
    candidate_tags = ["stroke", "segment", "action", "event", "annotation"]

    nodes: list[etree._Element] = []
    for tag in candidate_tags:
        nodes.extend(root.findall(f".//{tag}"))

    for node in nodes:
        attrs = {k.lower(): v for k, v in node.attrib.items()}
        video = attrs.get("video") or attrs.get("video_name") or attrs.get("filename")
        label = attrs.get("label") or attrs.get("class") or attrs.get("name")

        start_frame = attrs.get("start_frame") or attrs.get("start") or attrs.get("begin")
        end_frame = attrs.get("end_frame") or attrs.get("end") or attrs.get("finish")

        if video is None:
            video_node = node.find("video") or node.find("filename")
            if video_node is not None and video_node.text:
                video = video_node.text

        if label is None:
            label_node = node.find("label") or node.find("class") or node.find("name")
            if label_node is not None and label_node.text:
                label = label_node.text

        if start_frame is None:
            sf_node = node.find("start_frame") or node.find("start") or node.find("begin")
            if sf_node is not None and sf_node.text:
                start_frame = sf_node.text

        if end_frame is None:
            ef_node = node.find("end_frame") or node.find("end") or node.find("finish")
            if ef_node is not None and ef_node.text:
                end_frame = ef_node.text

        if not all([video, label, start_frame, end_frame]):
            continue

        segments.append(
            StrokeSegment(
                video=_norm_video_name(video),
                label=_norm_label(label),
                start_frame=_to_int(start_frame),
                end_frame=_to_int(end_frame),
            )
        )

    return segments


def load_annotations(csv_dir: Path, xml_dir: Path) -> list[StrokeSegment]:
    """Load all annotations from CSV and XML directories."""
    all_segments: list[StrokeSegment] = []

    for csv_path in sorted(csv_dir.glob("*.csv")):
        all_segments.extend(_load_single_csv(csv_path))

    for xml_path in sorted(xml_dir.glob("*.xml")):
        all_segments.extend(_extract_xml_segments(xml_path))

    dedup = {(s.video, s.label, s.start_frame, s.end_frame): s for s in all_segments}
    segments = list(dedup.values())
    segments.sort(key=lambda x: (x.video, x.start_frame, x.end_frame, x.label))
    return segments


def to_dataframe(segments: Iterable[StrokeSegment]) -> pd.DataFrame:
    """Convert stroke segments to DataFrame."""
    rows = [
        {
            "video": s.video,
            "label": s.label,
            "start_frame": s.start_frame,
            "end_frame": s.end_frame,
            "duration_frames": s.duration_frames,
        }
        for s in segments
    ]
    return pd.DataFrame(rows)


# ============================================================================
# VIDEO FEATURE EXTRACTION: Optical Flow + Frame Difference
# ============================================================================

def sample_frame_ids(start_frame: int, end_frame: int, n_frames: int) -> np.ndarray:
    """Sample n_frames uniformly from [start_frame, end_frame]."""
    start_frame = max(0, int(start_frame))
    end_frame = max(start_frame, int(end_frame))
    if n_frames <= 1:
        return np.array([start_frame], dtype=np.int32)
    return np.linspace(start_frame, end_frame, n_frames, dtype=np.int32)


def extract_motion_features(
    video_path: Path,
    start_frame: int,
    end_frame: int,
    n_frames: int = 24,
) -> dict[str, float]:
    """Extract motion features (optical flow + frame difference) from video segment."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    frame_ids = sample_frame_ids(start_frame, end_frame, n_frames)
    gray_frames: list[np.ndarray] = []

    for fid in frame_ids:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(fid))
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_frames.append(gray)

    cap.release()

    if len(gray_frames) < 2:
        return {
            "flow_mag_mean": 0.0,
            "flow_mag_std": 0.0,
            "diff_mean": 0.0,
            "diff_std": 0.0,
            "duration_frames": float(max(0, end_frame - start_frame + 1)),
        }

    flow_mags = []
    diffs = []

    for i in range(1, len(gray_frames)):
        prev = gray_frames[i - 1]
        curr = gray_frames[i]

        flow = cv2.calcOpticalFlowFarneback(
            prev,
            curr,
            None,
            pyr_scale=0.5,
            levels=3,
            winsize=15,
            iterations=3,
            poly_n=5,
            poly_sigma=1.2,
            flags=0,
        )
        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        flow_mags.append(float(np.mean(mag)))

        diff = cv2.absdiff(prev, curr)
        diffs.append(float(np.mean(diff)))

    return {
        "flow_mag_mean": float(np.mean(flow_mags)),
        "flow_mag_std": float(np.std(flow_mags)),
        "diff_mean": float(np.mean(diffs)),
        "diff_std": float(np.std(diffs)),
        "duration_frames": float(max(0, end_frame - start_frame + 1)),
    }


# ============================================================================
# DATASET BUILDING: Feature Table Generation
# ============================================================================

def _resolve_video_path(videos_dir: Path, video_token: str) -> Path | None:
    """Resolve video file by name, stem, or case-insensitive match."""
    direct = videos_dir / video_token
    if direct.exists():
        return direct

    stem = Path(video_token).stem
    matches = sorted(videos_dir.glob(f"{stem}.*"))
    if matches:
        return matches[0]

    lower_stem = stem.lower()
    for p in videos_dir.iterdir():
        if p.is_file() and p.stem.lower() == lower_stem:
            return p
    return None


def build_feature_table(
    videos_dir: Path,
    csv_dir: Path,
    xml_dir: Path,
    output_csv: Path,
    n_frames: int = 24,
) -> pd.DataFrame:
    """Build feature table from videos and annotations."""
    segments = load_annotations(csv_dir=csv_dir, xml_dir=xml_dir)
    rows = []

    for seg in tqdm(segments, desc="Extracting segment features"):
        video_path = _resolve_video_path(videos_dir=videos_dir, video_token=seg.video)
        if video_path is None:
            print(f"  Warning: Video not found for {seg.video}, skipping")
            continue

        try:
            features = extract_motion_features(
                video_path=video_path,
                start_frame=seg.start_frame,
                end_frame=seg.end_frame,
                n_frames=n_frames,
            )
            row = {
                "video": video_path.name,
                "label": seg.label,
                "start_frame": seg.start_frame,
                "end_frame": seg.end_frame,
            }
            row.update(features)
            rows.append(row)
        except Exception as e:
            print(f"  Error processing {seg.video}: {e}")
            continue

    df = pd.DataFrame(rows)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False)
    print(f"Saved {len(df)} features to {output_csv}")
    return df


# ============================================================================
# MODEL TRAINING: Random Forest Classifier
# ============================================================================

FEATURE_COLUMNS = [
    "flow_mag_mean",
    "flow_mag_std",
    "diff_mean",
    "diff_std",
    "duration_frames",
]


def train_model(
    features_csv: Path,
    model_out: Path,
    report_out: Path,
    random_state: int = 42,
) -> dict:
    """Train Random Forest classifier on extracted features."""
    df = pd.read_csv(features_csv)
    if df.empty:
        raise ValueError("Feature CSV is empty. Build dataset first.")

    missing = [c for c in FEATURE_COLUMNS + ["label"] if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    X = df[FEATURE_COLUMNS]
    y = df["label"]

    if len(y.unique()) < 2:
        print(f"Warning: Only {len(y.unique())} class(es) in data. Training may be unstable.")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=random_state,
        stratify=y,
    )

    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=300,
                    max_depth=None,
                    random_state=random_state,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    print(f"Training on {len(X_train)} samples, testing on {len(X_test)} samples")
    model.fit(X_train, y_train)
    preds = model.predict(X_test)

    report = classification_report(y_test, preds, output_dict=True, zero_division=0)

    model_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_out)
    with report_out.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Saved model to {model_out}")
    print(f"Saved report to {report_out}")
    return report


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main(
    input_dir: Path = Path("/kaggle/input/stroke-data"),
    output_dir: Path = Path("/kaggle/output"),
    n_frames: int = 24,
):
    """
    Run the full stroke detection pipeline.

    Parameters:
    -----------
    input_dir : Path
        Root input directory containing subdirs: raw_videos, annotations/csv, annotations/xml
    output_dir : Path
        Output directory for features, model, and report
    n_frames : int
        Number of frames to sample per stroke segment
    """
    # Setup paths
    videos_dir = input_dir / "raw_videos"
    csv_dir = input_dir / "annotations" / "csv"
    xml_dir = input_dir / "annotations" / "xml"

    features_csv = output_dir / "stroke_features.csv"
    model_out = output_dir / "stroke_classifier.joblib"
    report_out = output_dir / "classification_report.json"

    # Validate input directories
    for d in [videos_dir, csv_dir, xml_dir]:
        if not d.exists():
            print(f"Warning: {d} does not exist. Creating as empty.")
            d.mkdir(parents=True, exist_ok=True)

    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("TABLE TENNIS STROKE DETECTION PIPELINE")
    print("=" * 80)

    # Step 1: Build feature table
    print("\n[1/2] Building feature table from annotations and videos...")
    df = build_feature_table(
        videos_dir=videos_dir,
        csv_dir=csv_dir,
        xml_dir=xml_dir,
        output_csv=features_csv,
        n_frames=n_frames,
    )

    print(f"\nExtracted {len(df)} stroke features")
    if len(df) > 0:
        print(f"Classes: {df['label'].unique()}")
        print(f"\nFeature statistics:\n{df[FEATURE_COLUMNS].describe()}")

    # Step 2: Train classifier (if enough data)
    if len(df) >= 20 and df["label"].nunique() >= 2:
        print("\n[2/2] Training Random Forest classifier...")
        report = train_model(features_csv, model_out, report_out)
        macro_f1 = report.get("macro avg", {}).get("f1-score", 0.0)
        print(f"\nMacro F1-Score: {macro_f1:.4f}")
    else:
        min_samples = max(20, df["label"].nunique() * 2)
        print(f"\n[2/2] Skipping training: need at least {min_samples} samples and 2+ classes")
        print(f"       (have {len(df)} samples, {df['label'].nunique()} classes)")

    print("\n" + "=" * 80)
    print("Pipeline completed!")
    print("=" * 80)


if __name__ == "__main__":
    # For local testing, you can override paths:
    # main(
    #     input_dir=Path("./data"),
    #     output_dir=Path("./outputs"),
    # )

    # Default: use Kaggle paths
    main()
