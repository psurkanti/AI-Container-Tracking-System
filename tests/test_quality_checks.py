import pandas as pd

from validation.checks import compute_quality_score, run_quality_checks


def test_quality_checks_detect_multiple_issues():
    df = pd.DataFrame(
        {
            "container_number": ["CON1", "CON1"],
            "po_number": ["PO1", "PO1"],
            "part_number": ["P1", "P1"],
            "supplier_name": [None, "ABC"],
            "qty_ordered": [10, 10],
            "qty_loaded": [9, 10],
            "qty_received": [10, 11],
            "qc_status": [None, "Approved"],
            "eta_date": ["2025-01-03", "2025-01-04"],
            "arrival_date": ["2025-01-02", "2025-01-03"],
            "warehouse_delivery_date": ["2025-01-01", "2025-01-02"],
            "gross_weight": [100.0, 10000.0],
            "cbm": [1.0, 20.0],
            "invoice_value": [1000.0, 90000.0],
            "duty_amount": [100.0, 200.0],
        }
    )

    issues = run_quality_checks(df)
    assert any(i["type"] == "missing_value" for i in issues)
    assert any(i["type"] == "data_mismatch" for i in issues)
    assert any(i["type"] == "date_issue" for i in issues)
    assert any(i["type"] == "duplicate" for i in issues)

    score = compute_quality_score(df, issues)
    assert score < 100
