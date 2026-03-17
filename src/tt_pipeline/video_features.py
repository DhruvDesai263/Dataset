from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def sample_frame_ids(start_frame: int, end_frame: int, n_frames: int) -> np.ndarray:
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
