# AI Powered Supply Chain Container Tracking System

Production-ready FastAPI system focused on container shipment tracking using part number and tracking pin lookups.

## Roles and login
- Admin login can upload shipment CSV files.
- Customer login can only track assigned `part_number` + `tracking_pin`.
- Customer login can view multiple assigned parts with QC status.
- Tracking response includes `qc_status`.

Default demo users:
- Admin: `admin` / `admin123`
- Customer: `customer_prt_a` / `customer123`
- Additional sample customer: `customer_prt_x` / `customer456`
- User access is configured in `data/customer_access.json`. **Do not commit real passwords.** Copy `data/customer_access.example.json` → `customer_access.json` locally and customize.

UI pages:
- Admin page: `/admin`
- Customer page: `/customer`

## Features
- CSV ingestion via upload or file path
- Automated profiling (shape, dtypes, nulls, uniqueness, stats)
- Data quality checks (missing values, mismatch rules, date sequence, outliers, duplicates)
- Schema drift detection and optional Evidently drift
- AI issue explanation and fix recommendations via OpenAI/Azure OpenAI-compatible endpoint
- Optional self-healing actions
- JSON + CSV + HTML reporting
- Structured JSON logging

## Run locally
```bash
cd /Users/pavithrareddy/projects/data-quality-ai-system
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Environment variables
- `OPENAI_API_KEY` (optional; fallback explanations used if omitted)
- `OPENAI_BASE_URL` (optional; set for Azure/OpenAI-compatible endpoints)
- `OPENAI_MODEL` (default `gpt-4o-mini`)

## API Endpoints
- `POST /auth/login` (form: `username`, `password`)
- `POST /upload-data` (multipart form: `auth_token`, `file`; admin only)
- `POST /run-quality-checks` (multipart form with either `file_path` or `file`, optional `self_heal`)
- `POST /detect-drift` (multipart form with either `file_path` or `file`)
- `POST /explain-issues` (multipart form with either `file_path` or `file`)
- `POST /suggest-fixes` (multipart form with either `file_path` or `file`)
- `POST /generate-report` (multipart form with either `file_path` or `file`, optional `self_heal`)
- `POST /track-container` (multipart form with `part_number`, `tracking_pin`, and either `file_path` or `file`)
- `POST /my-parts-status` (multipart form: `auth_token`, and either `file_path` or `file`; customer view)
- `POST /admin/all-parts-status` (multipart form: `auth_token`, and either `file_path` or `file`; admin view)
- `POST /customer/track-by-part` (multipart form: `auth_token`, `part_number`, and source input; customer view)

## Example response snippet
```json
{
  "data_quality_score": 78,
  "issues": [
    {
      "type": "missing_value",
      "column": "qc_status",
      "count": 12,
      "explanation": "QC status is missing for some containers which may delay approvals.",
      "suggested_fix": "Fill with 'Pending' or verify from QC team"
    }
  ]
}
```
