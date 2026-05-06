from __future__ import annotations

import pandas as pd


def _clean(value):
    if pd.isna(value):
        return None
    return value


def _fmt_date(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.date().strftime("%m/%d/%Y")
    text = str(value)
    try:
        if " " in text:
            return pd.to_datetime(text.split(" ")[0], errors="coerce").strftime("%m/%d/%Y")
        return pd.to_datetime(text, errors="coerce").strftime("%m/%d/%Y")
    except Exception:
        return text


def lookup_container_tracking(df: pd.DataFrame, part_number: str, tracking_pin: str) -> dict:
    working = df.copy()
    if "tracking_pin" not in working.columns:
        if "container_number" in working.columns:
            working["tracking_pin"] = working["container_number"].astype(str)
        else:
            raise ValueError("tracking_pin column is missing and container_number fallback is unavailable")

    mask = (
        working["part_number"].astype(str).str.strip().str.lower() == part_number.strip().lower()
    ) & (working["tracking_pin"].astype(str).str.strip().str.lower() == tracking_pin.strip().lower())

    matches = working[mask]
    if matches.empty:
        raise ValueError("No tracking record found for the provided part number and tracking pin")

    # Use latest event based on arrival/warehouse date when available.
    for col in ("warehouse_delivery_date", "arrival_date", "eta_date"):
        if col in matches.columns:
            matches[col] = pd.to_datetime(matches[col], errors="coerce")
    if "warehouse_delivery_date" in matches.columns:
        matches = matches.sort_values(by="warehouse_delivery_date", ascending=False, na_position="last")
    elif "arrival_date" in matches.columns:
        matches = matches.sort_values(by="arrival_date", ascending=False, na_position="last")

    row = {k: _clean(v) for k, v in matches.iloc[0].to_dict().items()}
    estimated_arrival = row.get("estimated_arrival_date") or row.get("eta_date")
    return {
        "tracking_pin": str(row.get("tracking_pin", "")),
        "container_number": row.get("container_number"),
        "po_number": row.get("po_number"),
        "part_number": row.get("part_number"),
        "supplier_name": row.get("supplier_name"),
        "qty_ordered": row.get("qty_ordered"),
        "qty_loaded": row.get("qty_loaded"),
        "qty_received": row.get("qty_received"),
        "qc_status": row.get("qc_status"),
        "container_status": row.get("container_status"),
        "current_location": row.get("current_location", "Location not provided"),
        "last_arrived_location": row.get("last_arrived_location", row.get("warehouse_delivery_date")),
        "eta_date": _fmt_date(row.get("eta_date")),
        "estimated_arrival_date": _fmt_date(estimated_arrival),
        "arrival_date": _fmt_date(row.get("arrival_date")),
        "warehouse_delivery_date": _fmt_date(row.get("warehouse_delivery_date")),
    }


def list_tracking_by_authorized_pairs(
    df: pd.DataFrame,
    allowed_part_numbers: list[str],
    allowed_tracking_pins: list[str],
) -> list[dict]:
    if "tracking_pin" not in df.columns and "container_number" in df.columns:
        df = df.copy()
        df["tracking_pin"] = df["container_number"].astype(str)

    if "tracking_pin" not in df.columns:
        raise ValueError("tracking_pin column is missing and container_number fallback is unavailable")

    allowed_parts = {p.strip().lower() for p in allowed_part_numbers if p}
    allowed_pins = {p.strip().lower() for p in allowed_tracking_pins if p}

    if not allowed_parts or not allowed_pins:
        return []

    subset = df[
        df["part_number"].astype(str).str.strip().str.lower().isin(allowed_parts)
        & df["tracking_pin"].astype(str).str.strip().str.lower().isin(allowed_pins)
    ].copy()

    if subset.empty:
        return []

    for col in ("warehouse_delivery_date", "arrival_date", "eta_date"):
        if col in subset.columns:
            subset[col] = pd.to_datetime(subset[col], errors="coerce")

    sort_cols = ["part_number", "tracking_pin"]
    ascending = [True, True]
    if "warehouse_delivery_date" in subset.columns:
        sort_cols.append("warehouse_delivery_date")
        ascending.append(False)
    if "arrival_date" in subset.columns:
        sort_cols.append("arrival_date")
        ascending.append(False)
    subset = subset.sort_values(by=sort_cols, ascending=ascending, na_position="last")
    latest = subset.drop_duplicates(subset=["part_number", "tracking_pin"], keep="first")

    records = []
    for _, row in latest.iterrows():
        cleaned = {k: _clean(v) for k, v in row.to_dict().items()}
        destination = (
            cleaned.get("destination")
            or cleaned.get("last_arrived_location")
            or cleaned.get("current_location")
            or cleaned.get("warehouse_delivery_date")
        )
        records.append(
            {
                "tracking_pin": str(cleaned.get("tracking_pin", "")),
                "container_number": cleaned.get("container_number"),
                "po_number": cleaned.get("po_number"),
                "part_number": cleaned.get("part_number"),
                "supplier_name": cleaned.get("supplier_name"),
                "qty_ordered": cleaned.get("qty_ordered"),
                "qty_loaded": cleaned.get("qty_loaded"),
                "qty_received": cleaned.get("qty_received"),
                "quantity_arriving": cleaned.get("quantity_arriving"),
                "qc_status": cleaned.get("qc_status"),
                "container_status": cleaned.get("container_status"),
                "current_location": cleaned.get("current_location", "Location not provided"),
                "destination": destination,
                "estimated_arrival_date": _fmt_date(cleaned.get("estimated_arrival_date") or cleaned.get("eta_date")),
                "eta_date": _fmt_date(cleaned.get("eta_date")),
                "arrival_date": _fmt_date(cleaned.get("arrival_date")),
                "warehouse_delivery_date": _fmt_date(cleaned.get("warehouse_delivery_date")),
            }
        )
    return records


def list_all_latest_statuses(df: pd.DataFrame) -> list[dict]:
    if "tracking_pin" not in df.columns and "container_number" in df.columns:
        df = df.copy()
        df["tracking_pin"] = df["container_number"].astype(str)
    if "tracking_pin" not in df.columns:
        raise ValueError("tracking_pin column is missing and container_number fallback is unavailable")

    subset = df.copy()
    for col in ("warehouse_delivery_date", "arrival_date", "eta_date"):
        if col in subset.columns:
            subset[col] = pd.to_datetime(subset[col], errors="coerce")

    sort_cols = ["part_number", "tracking_pin"]
    ascending = [True, True]
    if "warehouse_delivery_date" in subset.columns:
        sort_cols.append("warehouse_delivery_date")
        ascending.append(False)
    if "arrival_date" in subset.columns:
        sort_cols.append("arrival_date")
        ascending.append(False)
    subset = subset.sort_values(by=sort_cols, ascending=ascending, na_position="last")
    latest = subset.drop_duplicates(subset=["part_number", "tracking_pin"], keep="first")

    records = []
    for _, row in latest.iterrows():
        cleaned = {k: _clean(v) for k, v in row.to_dict().items()}
        records.append(
            {
                "tracking_pin": str(cleaned.get("tracking_pin", "")),
                "container_number": cleaned.get("container_number"),
                "po_number": cleaned.get("po_number"),
                "part_number": cleaned.get("part_number"),
                "supplier_name": cleaned.get("supplier_name"),
                "qty_ordered": cleaned.get("qty_ordered"),
                "qty_loaded": cleaned.get("qty_loaded"),
                "qty_received": cleaned.get("qty_received"),
                "qc_status": cleaned.get("qc_status"),
                "container_status": cleaned.get("container_status"),
                "current_location": cleaned.get("current_location", "Location not provided"),
                "eta_date": _fmt_date(cleaned.get("eta_date")),
                "arrival_date": _fmt_date(cleaned.get("arrival_date")),
                "warehouse_delivery_date": _fmt_date(cleaned.get("warehouse_delivery_date")),
            }
        )
    return records


def list_customer_parts_in_container(
    df: pd.DataFrame,
    container_number: str,
    allowed_part_numbers: list[str],
) -> list[dict]:
    if "container_number" not in df.columns:
        raise ValueError("container_number column is required")
    if "part_number" not in df.columns:
        raise ValueError("part_number column is required")

    working = df.copy()
    if "tracking_pin" not in working.columns and "container_number" in working.columns:
        working["tracking_pin"] = working["container_number"].astype(str)

    allowed_parts = {p.strip().lower() for p in allowed_part_numbers if p}
    container_key = container_number.strip().lower()
    subset = working[
        working["container_number"].astype(str).str.strip().str.lower().eq(container_key)
        & working["part_number"].astype(str).str.strip().str.lower().isin(allowed_parts)
    ].copy()
    if subset.empty:
        return []

    for col in ("warehouse_delivery_date", "arrival_date", "eta_date"):
        if col in subset.columns:
            subset.loc[:, col] = pd.to_datetime(subset[col], errors="coerce")

    sort_cols = ["part_number"]
    ascending = [True]
    if "warehouse_delivery_date" in subset.columns:
        sort_cols.append("warehouse_delivery_date")
        ascending.append(False)
    if "arrival_date" in subset.columns:
        sort_cols.append("arrival_date")
        ascending.append(False)
    subset = subset.sort_values(by=sort_cols, ascending=ascending, na_position="last")
    latest = subset.drop_duplicates(subset=["part_number"], keep="first")

    records = []
    for _, row in latest.iterrows():
        cleaned = {k: _clean(v) for k, v in row.to_dict().items()}
        destination = (
            cleaned.get("destination")
            or cleaned.get("last_arrived_location")
            or cleaned.get("current_location")
            or cleaned.get("warehouse_delivery_date")
        )
        records.append(
            {
                "container_number": cleaned.get("container_number"),
                "part_number": cleaned.get("part_number"),
                "tracking_pin": str(cleaned.get("tracking_pin", "")),
                "container_status": cleaned.get("container_status"),
                "qty_ordered": cleaned.get("qty_ordered"),
                "qty_loaded": cleaned.get("qty_loaded"),
                "qty_received": cleaned.get("qty_received"),
                "current_location": cleaned.get("current_location", "Location not provided"),
                "estimated_arrival_date": _fmt_date(cleaned.get("estimated_arrival_date") or cleaned.get("eta_date")),
                "eta_date": _fmt_date(cleaned.get("eta_date")),
                "arrival_date": _fmt_date(cleaned.get("arrival_date")),
                "destination": destination,
                "qc_status": cleaned.get("qc_status"),
            }
        )
    return records
