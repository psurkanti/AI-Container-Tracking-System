from __future__ import annotations

from typing import Any

import pandas as pd


def detect_statistical_drift(reference: pd.DataFrame, current: pd.DataFrame) -> dict[str, Any]:
    """Optional Evidently integration; returns graceful fallback when unavailable."""
    try:
        from evidently import ColumnMapping
        from evidently.report import Report
        from evidently.metric_preset import DataDriftPreset

        report = Report(metrics=[DataDriftPreset()])
        mapping = ColumnMapping()
        report.run(reference_data=reference, current_data=current, column_mapping=mapping)
        result = report.as_dict()
        return {"evidently_enabled": True, "result": result}
    except Exception as exc:
        return {
            "evidently_enabled": False,
            "result": "Evidently not configured or drift execution failed.",
            "error": str(exc),
        }
