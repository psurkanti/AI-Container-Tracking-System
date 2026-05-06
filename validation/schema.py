from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


EXPECTED_COLUMNS = [
    "container_number",
    "po_number",
    "part_number",
    "supplier_name",
    "qty_ordered",
    "qty_loaded",
    "qty_received",
    "qc_status",
    "container_status",
    "eta_date",
    "arrival_date",
    "warehouse_delivery_date",
    "pallet_count",
    "gross_weight",
    "cbm",
    "invoice_value",
    "duty_amount",
]


class SchemaDriftDetector:
    def __init__(self, baseline_file: str = "data/schema_baseline.json") -> None:
        self.baseline_file = Path(baseline_file)
        self.baseline_file.parent.mkdir(parents=True, exist_ok=True)

    def infer_schema(self, df: pd.DataFrame) -> dict:
        return {"columns": list(df.columns), "dtypes": {c: str(df[c].dtype) for c in df.columns}}

    def detect(self, df: pd.DataFrame) -> dict:
        current = self.infer_schema(df)
        if not self.baseline_file.exists():
            self.baseline_file.write_text(json.dumps(current, indent=2))
            return {"drift_detected": False, "details": "Baseline schema initialized"}

        baseline = json.loads(self.baseline_file.read_text())
        baseline_cols = set(baseline.get("columns", []))
        current_cols = set(current["columns"])

        added = sorted(list(current_cols - baseline_cols))
        removed = sorted(list(baseline_cols - current_cols))
        dtype_changes = []
        for col in baseline_cols & current_cols:
            old = baseline["dtypes"].get(col)
            new = current["dtypes"].get(col)
            if old != new:
                dtype_changes.append({"column": col, "baseline": old, "current": new})

        required_missing = [c for c in EXPECTED_COLUMNS if c not in current_cols]

        drift_detected = bool(added or removed or dtype_changes or required_missing)
        return {
            "drift_detected": drift_detected,
            "added_columns": added,
            "removed_columns": removed,
            "dtype_changes": dtype_changes,
            "required_columns_missing": required_missing,
        }
