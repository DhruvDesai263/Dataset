from __future__ import annotations

from pathlib import Path

from src.tt_pipeline.build_dataset import build_feature_table
from src.tt_pipeline.train_baseline import train_model


if __name__ == "__main__":
    root = Path(__file__).parent
    videos_dir = root / "data" / "raw_videos"
    csv_dir = root / "data" / "annotations" / "csv"
    xml_dir = root / "data" / "annotations" / "xml"
    outputs = root / "outputs"

    features_csv = outputs / "stroke_features.csv"
    model_out = outputs / "stroke_classifier.joblib"
    report_out = outputs / "classification_report.json"

    df = build_feature_table(
        videos_dir=videos_dir,
        csv_dir=csv_dir,
        xml_dir=xml_dir,
        output_csv=features_csv,
        n_frames=24,
    )

    print(f"Prepared features for {len(df)} stroke segments")

    if len(df) >= 20 and df["label"].nunique() >= 2:
        report = train_model(features_csv, model_out, report_out)
        print(f"Macro F1: {report['macro avg']['f1-score']:.4f}")
    else:
        print("Not enough data to train robustly. Add more labeled segments.")
