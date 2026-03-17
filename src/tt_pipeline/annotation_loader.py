from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable

import pandas as pd
from lxml import etree

from .models import StrokeSegment


_IDLE_LABELS = {"idle", "none", "background", "rest", "ready"}
_LABEL_ALIASES = {
    "serev": "serve",
}


def _norm_label(value: object) -> str:
    label = str(value).strip().lower()
    return _LABEL_ALIASES.get(label, label)


def _norm_video_name(value: str) -> str:
    p = Path(str(value).strip())
    return p.name


def _to_int(value: object) -> int:
    return int(float(value))


def _extract_video_from_cvat_meta(root: etree._Element, fallback_stem: str) -> str:
    task_name = root.findtext(".//meta//task//name")
    if task_name and task_name.strip():
        return _norm_video_name(task_name.strip())
    return fallback_stem


def _build_segments_from_frame_labels(df: pd.DataFrame) -> list[StrokeSegment]:
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
            # Common exported schema: one CSV per video with no explicit video column.
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
    tree = etree.parse(str(xml_path))
    root = tree.getroot()

    segments: list[StrokeSegment] = []

    # Handle CVAT 1.1 track schema first.
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
