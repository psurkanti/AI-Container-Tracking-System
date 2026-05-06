from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd


class ReportGenerator:
    def __init__(self, output_dir: str = "reporting/output") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, payload: dict, dataframe: pd.DataFrame) -> dict:
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        json_path = self.output_dir / f"quality_report_{stamp}.json"
        csv_path = self.output_dir / f"cleaned_data_{stamp}.csv"
        html_path = self.output_dir / f"quality_report_{stamp}.html"

        json_path.write_text(json.dumps(payload, indent=2, default=str))
        dataframe.to_csv(csv_path, index=False)

        html = self._to_html(payload)
        html_path.write_text(html)

        return {
            "json_report": str(json_path),
            "csv_report": str(csv_path),
            "html_report": str(html_path),
        }

    def _to_html(self, payload: dict) -> str:
        issues = payload.get("issues", [])
        issue_rows = "".join(
            f"<tr><td>{i.get('type')}</td><td>{i.get('column')}</td><td>{i.get('count')}</td>"
            f"<td>{i.get('explanation','')}</td><td>{i.get('suggested_fix','')}</td></tr>"
            for i in issues
        )

        return f"""
        <html>
          <head><title>Data Quality Report</title></head>
          <body>
            <h1>Self-Healing Supply Chain Data Quality Report</h1>
            <p><strong>Score:</strong> {payload.get('data_quality_score')}</p>
            <h2>Issues</h2>
            <table border="1" cellpadding="6" cellspacing="0">
              <tr><th>Type</th><th>Column</th><th>Count</th><th>Explanation</th><th>Suggested Fix</th></tr>
              {issue_rows}
            </table>
          </body>
        </html>
        """
