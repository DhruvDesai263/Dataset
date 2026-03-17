from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


FEATURE_COLUMNS = [
    "flow_mag_mean",
    "flow_mag_std",
    "diff_mean",
    "diff_std",
    "duration_frames",
]


def train_model(features_csv: Path, model_out: Path, report_out: Path, random_state: int = 42) -> dict:
    df = pd.read_csv(features_csv)
    if df.empty:
        raise ValueError("Feature CSV is empty. Build dataset first.")

    missing = [c for c in FEATURE_COLUMNS + ["label"] if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    X = df[FEATURE_COLUMNS]
    y = df["label"]

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

    model.fit(X_train, y_train)
    preds = model.predict(X_test)

    report = classification_report(y_test, preds, output_dict=True, zero_division=0)

    model_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_out)
    with report_out.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Train baseline stroke classifier.")
    parser.add_argument("--features-csv", type=Path, required=True)
    parser.add_argument("--model-out", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    report = train_model(
        features_csv=args.features_csv,
        model_out=args.model_out,
        report_out=args.report_out,
        random_state=args.random_state,
    )
    print(f"Saved model: {args.model_out}")
    print(f"Saved report: {args.report_out}")
    print(f"Macro F1: {report['macro avg']['f1-score']:.4f}")


if __name__ == "__main__":
    main()
