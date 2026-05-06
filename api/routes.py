from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from pipelines.ingestion import DataIngestionService
from pipelines.quality_pipeline import QualityPipeline
from pipelines.tracking import (
    list_all_latest_statuses,
    list_customer_parts_in_container,
    list_tracking_by_authorized_pairs,
    lookup_container_tracking,
)
from reporting.generator import ReportGenerator
from utils.auth import User, auth_service
from utils.config import settings
from validation.drift import detect_statistical_drift

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["data-quality"])
ingestor = DataIngestionService(settings.uploads_dir)
pipeline = QualityPipeline()
report_generator = ReportGenerator(settings.reports_dir)


def _customer_data_scope(df: pd.DataFrame, user: User) -> pd.DataFrame:
    """Keep only rows owned by this customer when the dataset provides ownership columns."""
    uname = user.username.strip().lower()
    if "username" in df.columns:
        return df[df["username"].astype(str).str.strip().str.lower() == uname].copy()

    labels = user.csv_customer_names or []
    if labels and "customer_name" in df.columns:
        low = {str(x).strip().lower() for x in labels if str(x).strip()}
        if low:
            mask = df["customer_name"].astype(str).str.strip().str.lower().isin(low)
            return df.loc[mask].copy()

    return df.copy()


def _resolve_file_path(file_path: str) -> str:
    path = Path(file_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return str(path)


def _get_default_data_path() -> str:
    uploads_dir = Path(settings.uploads_dir)
    if uploads_dir.exists():
        csv_files = sorted(uploads_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        if csv_files:
            return str(csv_files[0])
    fallback = Path("data") / "sample_container_data.csv"
    return str(Path.cwd() / fallback)


async def _load_df(file_path: Optional[str], file: Optional[UploadFile]):
    if file is not None:
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="Only CSV upload is supported")
        saved = await ingestor.save_upload(file)
        return ingestor.load_dataframe(saved)
    if file_path:
        resolved = _resolve_file_path(file_path)
        try:
            return ingestor.load_from_path(resolved)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    # Default to latest uploaded CSV for customer/admin runtime convenience.
    return ingestor.load_from_path(_get_default_data_path())


@router.post("/upload-data")
async def upload_data(
    auth_token: str = Form(...),
    file: UploadFile = File(...),
):
    try:
        user = auth_service.get_user_by_token(auth_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can upload data")

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV upload is supported")

    saved = await ingestor.save_upload(file)
    df = ingestor.load_dataframe(saved)
    result = pipeline.run_checks(df, include_ai=False, self_heal=False)
    return {
        "status": "success",
        "saved_path": str(saved),
        "profiling": result["profiling"],
    }


@router.post("/auth/login")
async def login(
    username: str = Form(...),
    password: str = Form(...),
):
    try:
        payload = auth_service.login(username=username, password=password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"status": "success", "payload": payload}


@router.post("/run-quality-checks")
async def run_quality_checks(
    file_path: Optional[str] = Form(default=None),
    self_heal: bool = Form(default=False),
    file: Optional[UploadFile] = File(default=None),
):
    df = await _load_df(file_path=file_path, file=file)
    result = pipeline.run_checks(df, include_ai=False, self_heal=self_heal)
    return {"status": "success", "payload": {k: v for k, v in result.items() if k != "dataframe"}}


@router.post("/detect-drift")
async def detect_drift(
    file_path: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
):
    df = await _load_df(file_path=file_path, file=file)
    schema_drift = pipeline.detect_schema_drift(df)
    drift_result = {"schema": schema_drift}

    baseline_path = Path("data") / "baseline.csv"
    if baseline_path.exists():
        reference_df = ingestor.load_dataframe(baseline_path)
        drift_result["statistical"] = detect_statistical_drift(reference_df, df)
    else:
        drift_result["statistical"] = {
            "evidently_enabled": False,
            "result": "Baseline data/baseline.csv not found; skipping statistical drift",
        }

    return {"status": "success", "payload": drift_result}


@router.post("/explain-issues")
async def explain_issues(
    file_path: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
):
    df = await _load_df(file_path=file_path, file=file)
    result = pipeline.run_checks(df, include_ai=True, self_heal=False)
    return {"status": "success", "payload": {k: v for k, v in result.items() if k != "dataframe"}}


@router.post("/suggest-fixes")
async def suggest_fixes(
    file_path: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
):
    df = await _load_df(file_path=file_path, file=file)
    result = pipeline.run_checks(df, include_ai=True, self_heal=False)
    suggestions = [
        {
            "type": i.get("type"),
            "column": i.get("column"),
            "suggested_fix": i.get("suggested_fix", "Review source and correct."),
        }
        for i in result["issues"]
    ]
    return {"status": "success", "payload": {"suggested_fixes": suggestions}}


@router.post("/generate-report")
async def generate_report(
    file_path: Optional[str] = Form(default=None),
    self_heal: bool = Form(default=False),
    file: Optional[UploadFile] = File(default=None),
):
    df = await _load_df(file_path=file_path, file=file)
    result = pipeline.run_checks(df, include_ai=True, self_heal=self_heal)
    report_payload = {k: v for k, v in result.items() if k != "dataframe"}
    report_paths = report_generator.generate(report_payload, result["dataframe"])
    logger.info("Report generated", extra={"event": "reporting", "source": report_paths["json_report"]})
    return {"status": "success", "payload": report_payload, "reports": report_paths}


@router.post("/track-container")
async def track_container(
    auth_token: str = Form(...),
    part_number: str = Form(...),
    tracking_pin: str = Form(...),
    file_path: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
):
    try:
        user = auth_service.get_user_by_token(auth_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    if user.role == "customer":
        df = await _load_df(file_path=file_path, file=file)
        df = _customer_data_scope(df, user)
        allowed_parts = user.allowed_part_numbers or ([user.allowed_part_number] if user.allowed_part_number else [])
        allowed_pins = user.allowed_tracking_pins or ([user.allowed_tracking_pin] if user.allowed_tracking_pin else [])
        if allowed_parts and part_number.strip().lower() not in {p.strip().lower() for p in allowed_parts if p}:
            raise HTTPException(status_code=403, detail="Customer is not authorized for this part number")
        if allowed_pins and tracking_pin.strip().lower() not in {p.strip().lower() for p in allowed_pins if p}:
            raise HTTPException(status_code=403, detail="Customer is not authorized for this tracking pin")
    else:
        df = await _load_df(file_path=file_path, file=file)
    try:
        tracking_details = lookup_container_tracking(df, part_number=part_number, tracking_pin=tracking_pin)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "success", "payload": tracking_details}


@router.post("/my-parts-status")
async def my_parts_status(
    auth_token: str = Form(...),
    file_path: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
):
    try:
        user = auth_service.get_user_by_token(auth_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    if user.role != "customer":
        raise HTTPException(status_code=403, detail="This endpoint is for customer role only")

    allowed_parts = user.allowed_part_numbers or ([user.allowed_part_number] if user.allowed_part_number else [])
    allowed_pins = user.allowed_tracking_pins or ([user.allowed_tracking_pin] if user.allowed_tracking_pin else [])

    df = await _load_df(file_path=file_path, file=file)
    df = _customer_data_scope(df, user)
    records = list_tracking_by_authorized_pairs(
        df=df,
        allowed_part_numbers=allowed_parts,
        allowed_tracking_pins=allowed_pins,
    )
    return {"status": "success", "payload": {"records": records, "count": len(records)}}


@router.post("/customer/search-my-parts")
async def customer_search_my_parts(
    auth_token: str = Form(...),
    part_query: str = Form(...),
    file_path: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
):
    """Part-number search restricted to this customer's rows only (same rules as /my-parts-status)."""
    try:
        user = auth_service.get_user_by_token(auth_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    if user.role != "customer":
        raise HTTPException(status_code=403, detail="This endpoint is for customer role only")

    allowed_parts = user.allowed_part_numbers or ([user.allowed_part_number] if user.allowed_part_number else [])
    allowed_pins = user.allowed_tracking_pins or ([user.allowed_tracking_pin] if user.allowed_tracking_pin else [])

    df = await _load_df(file_path=file_path, file=file)
    df = _customer_data_scope(df, user)
    records = list_tracking_by_authorized_pairs(
        df=df,
        allowed_part_numbers=allowed_parts,
        allowed_tracking_pins=allowed_pins,
    )

    q = part_query.strip().lower()
    if not q:
        raise HTTPException(status_code=400, detail="Enter a part number to search")
    filtered = [r for r in records if q in str(r.get("part_number", "")).strip().lower()]
    return {"status": "success", "payload": {"records": filtered, "count": len(filtered)}}


@router.post("/customer/track-by-part")
async def customer_track_by_part(
    auth_token: str = Form(...),
    part_number: str = Form(...),
    file_path: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
):
    try:
        user = auth_service.get_user_by_token(auth_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    if user.role != "customer":
        raise HTTPException(status_code=403, detail="This endpoint is for customer role only")

    allowed_parts = user.allowed_part_numbers or ([user.allowed_part_number] if user.allowed_part_number else [])
    allowed_pins = user.allowed_tracking_pins or ([user.allowed_tracking_pin] if user.allowed_tracking_pin else [])

    if part_number.strip().lower() not in {p.strip().lower() for p in allowed_parts if p}:
        raise HTTPException(status_code=403, detail="Customer is not authorized for this part number")

    df = await _load_df(file_path=file_path, file=file)
    df = _customer_data_scope(df, user)
    records = list_tracking_by_authorized_pairs(
        df=df,
        allowed_part_numbers=allowed_parts,
        allowed_tracking_pins=allowed_pins,
    )
    part_records = [r for r in records if str(r.get("part_number", "")).strip().lower() == part_number.strip().lower()]
    if not part_records:
        raise HTTPException(status_code=404, detail="No tracking record found for this part number")
    return {"status": "success", "payload": part_records[0]}


@router.post("/admin/all-parts-status")
async def admin_all_parts_status(
    auth_token: str = Form(...),
    file_path: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
):
    try:
        user = auth_service.get_user_by_token(auth_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can access all parts status")

    df = await _load_df(file_path=file_path, file=file)
    records = list_all_latest_statuses(df)
    return {"status": "success", "payload": {"records": records, "count": len(records)}}


@router.post("/admin/customers/list")
async def admin_list_customers(auth_token: str = Form(...)):
    try:
        user = auth_service.get_user_by_token(auth_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can manage customers")
    return {"status": "success", "payload": {"customers": auth_service.list_customers()}}


@router.post("/admin/customers/upsert")
async def admin_upsert_customer(
    auth_token: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    allowed_part_numbers: str = Form(...),
    allowed_tracking_pins: str = Form(...),
):
    try:
        user = auth_service.get_user_by_token(auth_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can manage customers")
    try:
        payload = auth_service.upsert_customer(
            username=username.strip(),
            password=password,
            allowed_part_numbers=[x.strip() for x in allowed_part_numbers.split(",")],
            allowed_tracking_pins=[x.strip() for x in allowed_tracking_pins.split(",")],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "success", "payload": payload}


@router.post("/admin/customers/delete")
async def admin_delete_customer(
    auth_token: str = Form(...),
    username: str = Form(...),
):
    try:
        user = auth_service.get_user_by_token(auth_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can manage customers")
    try:
        auth_service.delete_customer(username.strip())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "success", "payload": {"deleted": username.strip()}}


@router.post("/admin/manual-entry")
async def admin_manual_entry(
    auth_token: str = Form(...),
    container_number: str = Form(...),
    po_number: str = Form(...),
    part_number: str = Form(...),
    supplier_name: str = Form(...),
    qty_ordered: float = Form(...),
    qty_loaded: float = Form(...),
    qty_received: float = Form(...),
    container_status: str = Form(...),
    eta_date: str = Form(...),
    arrival_date: str = Form(...),
    estimated_arrival_date: str = Form(...),
    destination: str = Form(...),
    tracking_pin: str = Form(...),
    qc_status: str = Form("Pending"),
    warehouse_delivery_date: str = Form(""),
    pallet_count: float = Form(0),
    gross_weight: float = Form(0),
    cbm: float = Form(0),
    invoice_value: float = Form(0),
    duty_amount: float = Form(0),
    target_file_path: str = Form("data/sample_container_data.csv"),
):
    try:
        user = auth_service.get_user_by_token(auth_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can add manual data")

    target_path = Path(_resolve_file_path(target_file_path))
    target_path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
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
        "tracking_pin",
        "current_location",
        "last_arrived_location",
        "estimated_arrival_date",
        "destination",
    ]

    row = {
        "container_number": container_number,
        "po_number": po_number,
        "part_number": part_number,
        "supplier_name": supplier_name,
        "qty_ordered": qty_ordered,
        "qty_loaded": qty_loaded,
        "qty_received": qty_received,
        "qc_status": qc_status,
        "container_status": container_status,
        "eta_date": eta_date,
        "arrival_date": arrival_date,
        "warehouse_delivery_date": warehouse_delivery_date or arrival_date,
        "pallet_count": pallet_count,
        "gross_weight": gross_weight,
        "cbm": cbm,
        "invoice_value": invoice_value,
        "duty_amount": duty_amount,
        "tracking_pin": tracking_pin,
        "current_location": destination,
        "last_arrived_location": destination,
        "estimated_arrival_date": estimated_arrival_date,
        "destination": destination,
    }

    if target_path.exists():
        existing = pd.read_csv(target_path)
        for col in columns:
            if col not in existing.columns:
                existing[col] = ""
        updated = pd.concat([existing[columns], pd.DataFrame([row], columns=columns)], ignore_index=True)
    else:
        updated = pd.DataFrame([row], columns=columns)

    updated.to_csv(target_path, index=False)
    return {"status": "success", "payload": {"saved_to": str(target_path), "record": row}}


@router.post("/public/track-container")
async def public_track_container(
    part_number: str = Form(...),
    tracking_pin: str = Form(...),
    file_path: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
):
    df = await _load_df(file_path=file_path, file=file)
    try:
        tracking_details = lookup_container_tracking(df, part_number=part_number, tracking_pin=tracking_pin)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "success", "payload": tracking_details}


@router.post("/public/track-qc-status")
async def public_track_qc_status(
    part_number: str = Form(...),
    tracking_pin: str = Form(...),
    file_path: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
):
    df = await _load_df(file_path=file_path, file=file)
    try:
        tracking_details = lookup_container_tracking(df, part_number=part_number, tracking_pin=tracking_pin)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "status": "success",
        "payload": {
            "part_number": tracking_details.get("part_number"),
            "tracking_pin": tracking_details.get("tracking_pin"),
            "container_number": tracking_details.get("container_number"),
            "qc_status": tracking_details.get("qc_status"),
        },
    }


@router.post("/customer/container-parts")
async def customer_container_parts(
    auth_token: str = Form(...),
    container_number: str = Form(...),
    file_path: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
):
    try:
        user = auth_service.get_user_by_token(auth_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if user.role != "customer":
        raise HTTPException(status_code=403, detail="This endpoint is for customer role only")

    allowed_parts = user.allowed_part_numbers or ([user.allowed_part_number] if user.allowed_part_number else [])
    df = await _load_df(file_path=file_path, file=file)
    df = _customer_data_scope(df, user)
    records = list_customer_parts_in_container(df, container_number=container_number, allowed_part_numbers=allowed_parts)
    return {"status": "success", "payload": {"records": records, "count": len(records)}}


@router.post("/customer/container-qc-status")
async def customer_container_qc_status(
    auth_token: str = Form(...),
    container_number: str = Form(...),
    file_path: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
):
    try:
        user = auth_service.get_user_by_token(auth_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if user.role != "customer":
        raise HTTPException(status_code=403, detail="This endpoint is for customer role only")

    allowed_parts = user.allowed_part_numbers or ([user.allowed_part_number] if user.allowed_part_number else [])
    df = await _load_df(file_path=file_path, file=file)
    df = _customer_data_scope(df, user)
    records = list_customer_parts_in_container(df, container_number=container_number, allowed_part_numbers=allowed_parts)
    qc_records = [
        {
            "container_number": rec.get("container_number"),
            "part_number": rec.get("part_number"),
            "tracking_pin": rec.get("tracking_pin"),
            "arrival_date": rec.get("arrival_date"),
            "destination": rec.get("destination"),
            "qc_status": rec.get("qc_status"),
        }
        for rec in records
    ]
    return {"status": "success", "payload": {"records": qc_records, "count": len(qc_records)}}
