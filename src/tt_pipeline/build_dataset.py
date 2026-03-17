from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from .annotation_loader import load_annotations
from .video_features import extract_motion_features


def _resolve_video_path(videos_dir: Path, video_token: str) -> Path | None:
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
    n_frames: int,
) -> pd.DataFrame:
    segments = load_annotations(csv_dir=csv_dir, xml_dir=xml_dir)
    rows = []

    for seg in tqdm(segments, desc="Extracting segment features"):
        video_path = _resolve_video_path(videos_dir=videos_dir, video_token=seg.video)
        if video_path is None:
            continue

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

    df = pd.DataFrame(rows)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Build stroke feature dataset from annotations.")
    parser.add_argument("--videos-dir", type=Path, required=True)
    parser.add_argument("--csv-dir", type=Path, required=True)
    parser.add_argument("--xml-dir", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--n-frames", type=int, default=24)
    args = parser.parse_args()

    df = build_feature_table(
        videos_dir=args.videos_dir,
        csv_dir=args.csv_dir,
        xml_dir=args.xml_dir,
        output_csv=args.output_csv,
        n_frames=args.n_frames,
    )
    print(f"Saved {len(df)} rows to {args.output_csv}")


if __name__ == "__main__":
    main()
