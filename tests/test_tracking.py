import pandas as pd

from pipelines.tracking import lookup_container_tracking


def test_tracking_lookup_by_part_and_pin():
    df = pd.DataFrame(
        {
            "container_number": ["CON0119"],
            "po_number": ["PO1001"],
            "part_number": ["PRT-A"],
            "supplier_name": ["Supplier A"],
            "qty_ordered": [100],
            "qty_loaded": [95],
            "qty_received": [90],
            "qc_status": ["Pending"],
            "container_status": ["In Transit"],
            "eta_date": ["2026-05-10"],
            "arrival_date": ["2026-05-09"],
            "warehouse_delivery_date": ["2026-05-12"],
            "tracking_pin": ["PIN-1234"],
            "current_location": ["Singapore Hub"],
            "last_arrived_location": ["Shanghai Port"],
        }
    )

    result = lookup_container_tracking(df, part_number="PRT-A", tracking_pin="PIN-1234")
    assert result["container_number"] == "CON0119"
    assert result["part_number"] == "PRT-A"
    assert result["container_status"] == "In Transit"
    assert result["current_location"] == "Singapore Hub"
