from fastapi.testclient import TestClient

import api.routes as routes
from main import app
from utils.auth import User


def test_customer_can_only_track_assigned_part_and_pin():
    client = TestClient(app)

    login = client.post(
        "/auth/login",
        data={"username": "customer_prt_a", "password": "customer123"},
    )
    assert login.status_code == 200
    token = login.json()["payload"]["access_token"]

    ok = client.post(
        "/track-container",
        data={
            "auth_token": token,
            "file_path": "data/sample_container_data.csv",
            "part_number": "PRT-A",
            "tracking_pin": "CON0119",
        },
    )
    assert ok.status_code == 200
    assert "qc_status" in ok.json()["payload"]

    forbidden = client.post(
        "/track-container",
        data={
            "auth_token": token,
            "file_path": "data/sample_container_data.csv",
            "part_number": "PRT-Z",
            "tracking_pin": "CON0119",
        },
    )
    assert forbidden.status_code == 403


def test_customer_cannot_upload_data():
    client = TestClient(app)

    login = client.post(
        "/auth/login",
        data={"username": "customer_prt_a", "password": "customer123"},
    )
    token = login.json()["payload"]["access_token"]

    upload = client.post(
        "/upload-data",
        data={"auth_token": token},
        files={"file": ("data.csv", "a,b\n1,2\n", "text/csv")},
    )
    assert upload.status_code == 403


def test_customer_can_view_multiple_parts_qc_status():
    client = TestClient(app)
    login = client.post(
        "/auth/login",
        data={"username": "customer_prt_a", "password": "customer123"},
    )
    token = login.json()["payload"]["access_token"]

    multi = client.post(
        "/my-parts-status",
        data={"auth_token": token, "file_path": "data/sample_container_data.csv"},
    )
    assert multi.status_code == 200
    payload = multi.json()["payload"]
    assert "records" in payload


def test_customer_track_by_part_endpoint():
    client = TestClient(app)
    login = client.post(
        "/auth/login",
        data={"username": "customer_prt_a", "password": "customer123"},
    )
    token = login.json()["payload"]["access_token"]

    result = client.post(
        "/customer/track-by-part",
        data={
            "auth_token": token,
            "file_path": "data/sample_container_data.csv",
            "part_number": "PRT-B",
        },
    )
    assert result.status_code == 200
    assert result.json()["payload"]["part_number"] == "PRT-B"


def test_customer_container_view_shows_only_allowed_parts():
    client = TestClient(app)
    login = client.post(
        "/auth/login",
        data={"username": "customer_prt_a", "password": "customer123"},
    )
    token = login.json()["payload"]["access_token"]

    resp = client.post(
        "/customer/container-parts",
        data={
            "auth_token": token,
            "file_path": "data/sample_container_data.csv",
            "container_number": "CON0119",
        },
    )
    assert resp.status_code == 200
    records = resp.json()["payload"]["records"]
    parts = {r["part_number"] for r in records}
    assert "PRT-A" in parts
    assert "PRT-X" not in parts


def test_customer_part_search_returns_only_own_customer_rows(tmp_path, monkeypatch):
    """Shared part + container in CSV: rows must be split by customer_name when configured."""
    iso = tmp_path / "isolation.csv"
    iso.write_text(
        "customer_name,tracking_pin,container_number,part_number,po_number,"
        "qty_ordered,qty_loaded,qty_received,qc_status,container_status,"
        "eta_date,arrival_date,destination,supplier_name\n"
        "Alpha Party,CONE1,CONE1,PART-SHARED,PO1,1,1,,Pending,Sea,2026-01-01,2026-01-02,Dest-A,SupA\n"
        "Bravo Party,CONE1,CONE1,PART-SHARED,PO2,2,2,,Pending,Sea,2026-01-01,2026-01-03,Dest-B,SupB\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        routes.auth_service,
        "get_user_by_token",
        lambda _t: User(
            username="u_test",
            password="p",
            role="customer",
            allowed_part_numbers=["PART-SHARED"],
            allowed_tracking_pins=["CONE1"],
            csv_customer_names=["Alpha Party"],
        ),
    )

    client = TestClient(app)
    r = client.post(
        "/customer/search-my-parts",
        data={
            "auth_token": "any-token",
            "part_query": "PART",
            "file_path": str(iso),
        },
    )
    assert r.status_code == 200
    recs = r.json()["payload"]["records"]
    assert len(recs) == 1
    assert recs[0]["destination"] == "Dest-A"
