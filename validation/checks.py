from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

CRITICAL_NULL_COLUMNS = ["qc_status", "eta_date", "supplier_name"]
DATE_COLUMNS = ["eta_date", "arrival_date", "warehouse_delivery_date"]
OUTLIER_COLUMNS = ["gross_weight", "cbm", "invoice_value"]
REQUIRED_TRACKING_COLUMNS = [
    "container_number",
    "po_number",
    "part_number",
    "supplier_name",
    "qty_ordered",
    "qty_loaded",
    "qty_received",
    "container_status",
    "qc_status",
    "eta_date",
    "arrival_date",
    "warehouse_delivery_date",
]


@dataclass
class Issue:
    type: str
    column: str | None = None
    entity: str | None = None
    count: int = 1
    severity: str = "medium"
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _safe_series(df: pd.DataFrame, col: str) -> pd.Series:
    return df[col] if col in df.columns else pd.Series(dtype=float)


def run_quality_checks(df: pd.DataFrame) -> list[dict]:
    issues: list[Issue] = []

    for col in REQUIRED_TRACKING_COLUMNS:
        if col not in df.columns:
            issues.append(
                Issue(
                    type="missing_column",
                    column=col,
                    count=1,
                    severity="high",
                    details={"rule": "required container tracking column is missing"},
                )
            )

    for col in CRITICAL_NULL_COLUMNS:
        if col in df.columns:
            missing_count = int(df[col].isna().sum())
            if missing_count:
                issues.append(Issue(type="missing_value", column=col, count=missing_count, severity="high"))

    for col in REQUIRED_TRACKING_COLUMNS:
        if col in df.columns:
            missing_count = int(df[col].isna().sum())
            if missing_count:
                issues.append(
                    Issue(
                        type="missing_value",
                        column=col,
                        count=missing_count,
                        severity="high",
                        details={"rule": "required tracking field should not be null"},
                    )
                )

    if {"qty_loaded", "qty_ordered"}.issubset(df.columns):
        mismatch = (df["qty_loaded"] != df["qty_ordered"]).fillna(False)
        mismatch_count = int(mismatch.sum())
        if mismatch_count:
            issues.append(
                Issue(
                    type="data_mismatch",
                    column="qty_loaded",
                    count=mismatch_count,
                    severity="high",
                    details={"rule": "qty_loaded must equal qty_ordered"},
                )
            )

    if {"qty_received", "qty_loaded"}.issubset(df.columns):
        over_received = (df["qty_received"] > df["qty_loaded"]).fillna(False)
        over_received_count = int(over_received.sum())
        if over_received_count:
            issues.append(
                Issue(
                    type="data_mismatch",
                    column="qty_received",
                    count=over_received_count,
                    severity="high",
                    details={"rule": "qty_received cannot exceed qty_loaded"},
                )
            )

    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    if {"arrival_date", "eta_date"}.issubset(df.columns):
        invalid_arrival = (df["arrival_date"] < df["eta_date"]).fillna(False)
        invalid_arrival_count = int(invalid_arrival.sum())
        if invalid_arrival_count:
            issues.append(
                Issue(
                    type="date_issue",
                    column="arrival_date",
                    count=invalid_arrival_count,
                    details={"rule": "arrival_date should not be before eta_date"},
                )
            )

    if {"warehouse_delivery_date", "arrival_date"}.issubset(df.columns):
        invalid_wh = (df["warehouse_delivery_date"] < df["arrival_date"]).fillna(False)
        invalid_wh_count = int(invalid_wh.sum())
        if invalid_wh_count:
            issues.append(
                Issue(
                    type="date_issue",
                    column="warehouse_delivery_date",
                    count=invalid_wh_count,
                    details={"rule": "warehouse_delivery_date should not be before arrival_date"},
                )
            )

    for col in OUTLIER_COLUMNS:
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            std = df[col].std(ddof=0)
            if std and not np.isnan(std):
                z_scores = (df[col] - df[col].mean()) / std
                outliers = z_scores.abs() > 3
                outlier_count = int(outliers.sum())
                if outlier_count:
                    issues.append(Issue(type="outlier", column=col, count=outlier_count, severity="medium"))

    if "container_number" in df.columns:
        duplicate_container = df["container_number"].duplicated(keep=False)
        dup_count = int(duplicate_container.sum())
        if dup_count:
            issues.append(Issue(type="duplicate", column="container_number", count=dup_count, severity="high"))

    if {"po_number", "part_number"}.issubset(df.columns):
        duplicate_combo = df.duplicated(subset=["po_number", "part_number"], keep=False)
        combo_count = int(duplicate_combo.sum())
        if combo_count:
            issues.append(
                Issue(type="duplicate", column="po_number+part_number", count=combo_count, severity="high")
            )

    return [item.to_dict() for item in issues]


def compute_quality_score(df: pd.DataFrame, issues: list[dict]) -> float:
    if df.empty:
        return 0.0

    row_count = len(df)
    weighted_impact = 0.0
    severity_weight = {"low": 0.5, "medium": 1.0, "high": 2.0}

    for issue in issues:
        count = issue.get("count", 1)
        severity = issue.get("severity", "medium")
        weighted_impact += (count / row_count) * 100 * severity_weight.get(severity, 1.0)

    score = max(0.0, 100.0 - weighted_impact)
    return round(score, 2)
