# Table Tennis Stroke Pipeline (CSV + XML + Raw Video)

This project ingests annotation files (`.csv` and `.xml`) plus raw videos, builds stroke-level features, and trains a baseline stroke classifier.

## Expected data layout

Place files like this:

- `data/raw_videos/*.mp4` (or `.avi`, `.mov`, etc.)
- `data/annotations/csv/*.csv`
- `data/annotations/xml/*.xml`

Video names inside annotations should match actual filenames in `data/raw_videos`.

## Supported CSV schemas

The parser accepts one of these schemas:

1. `video,start_frame,end_frame,label`
2. `video,frame,label` (frame-level labels; pipeline converts to stroke segments)
3. `video,start_time,end_time,label,fps`

It also accepts `video_path` or `filename` instead of `video`.

For CVAT-style exported CSV like `TTVideo_1.csv`:

- `stroke_type` is treated as label
- if no video column exists, the filename stem (for example `TTVideo_1`) is used
- common typo `serev` is normalized to `serve`

## Supported XML schema patterns

The parser looks for tags such as `stroke`, `segment`, `action`, `event`, `annotation` and attributes/children like:

- `video` / `video_name` / `filename`
- `label` / `class` / `name`
- `start_frame` / `start` / `begin`
- `end_frame` / `end` / `finish`

If your XML format is different, update `src/tt_pipeline/annotation_loader.py` accordingly.

CVAT XML 1.1 is supported directly:

- reads `<track label="stroke">` with nested `<box frame="..." outside="...">`
- uses active boxes (`outside=0`) to compute `start_frame` and `end_frame`
- reads stroke class from box attributes such as `stroke_type`

## Setup

```bash
pip install -r requirements.txt
```

## Run end-to-end

```bash
python run_pipeline.py
```

## Outputs

- `outputs/stroke_features.csv`
- `outputs/stroke_classifier.joblib`
- `outputs/classification_report.json`

## Notes

- This is a strong baseline with motion features (optical flow + frame difference).
- Next upgrade: add pose-based features and temporal deep models for better stroke discrimination.
