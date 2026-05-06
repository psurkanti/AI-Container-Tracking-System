from __future__ import annotations

import pandas as pd


def apply_self_healing(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    fixes: list[dict] = []
    healed = df.copy()

    lowered = {col: col.strip().lower() for col in healed.columns}
    if any(orig != norm for orig, norm in lowered.items()):
        healed.rename(columns=lowered, inplace=True)
        fixes.append({"action": "normalize_column_names", "count": len(lowered)})

    if "qc_status" in healed.columns:
        missing = int(healed["qc_status"].isna().sum())
        if missing:
            healed["qc_status"] = healed["qc_status"].fillna("Pending")
            fixes.append({"action": "fill_missing_qc_status", "count": missing, "value": "Pending"})

    if "supplier_name" in healed.columns:
        missing = int(healed["supplier_name"].isna().sum())
        if missing:
            healed["supplier_name"] = healed["supplier_name"].fillna("Unknown Supplier")
            fixes.append({"action": "fill_missing_supplier", "count": missing})

    before = len(healed)
    if "container_number" in healed.columns:
        healed = healed.drop_duplicates(subset=["container_number"], keep="first")
    if {"po_number", "part_number"}.issubset(healed.columns):
        healed = healed.drop_duplicates(subset=["po_number", "part_number"], keep="first")
    removed = before - len(healed)
    if removed > 0:
        fixes.append({"action": "remove_duplicates", "count": removed})

    return healed, fixes
