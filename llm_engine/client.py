from __future__ import annotations

from typing import Any

from openai import OpenAI

from utils.config import settings


class LLMClient:
    def __init__(self) -> None:
        self.enabled = bool(settings.openai_api_key)
        self.client = None
        if self.enabled:
            self.client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)

    def explain_issue(self, issue: dict[str, Any]) -> dict[str, str]:
        if not self.enabled or self.client is None:
            return self._fallback_response(issue)

        prompt = (
            "You are a supply chain data governance expert. "
            "Given a data quality issue JSON, provide concise plain-English explanation and actionable fix. "
            "Respond strictly as JSON with keys: explanation, impact, suggested_fix.\n"
            f"Issue: {issue}"
        )

        response = self.client.responses.create(
            model=settings.openai_model,
            input=prompt,
            temperature=0.2,
        )

        text_output = response.output_text.strip()
        return self._parse_json_like_response(text_output, issue)

    def _parse_json_like_response(self, text: str, issue: dict[str, Any]) -> dict[str, str]:
        import json

        try:
            parsed = json.loads(text)
            if all(k in parsed for k in ("explanation", "impact", "suggested_fix")):
                return {
                    "explanation": parsed["explanation"],
                    "impact": parsed["impact"],
                    "suggested_fix": parsed["suggested_fix"],
                }
        except Exception:
            pass
        return self._fallback_response(issue)

    def _fallback_response(self, issue: dict[str, Any]) -> dict[str, str]:
        issue_type = issue.get("type", "data_issue")
        column = issue.get("column", "column")
        count = issue.get("count", 1)
        if issue_type == "missing_value":
            return {
                "explanation": f"{count} records are missing values in {column}, which reduces shipment visibility.",
                "impact": "Missing operational fields can delay approvals and downstream planning.",
                "suggested_fix": f"Backfill {column} using trusted source rules; default qc_status to 'Pending' when appropriate.",
            }
        if issue_type == "data_mismatch":
            return {
                "explanation": f"Quantity inconsistency detected in {column}; ordered, loaded, and received values do not align.",
                "impact": "Mismatched quantities can cause inventory discrepancies and invoice disputes.",
                "suggested_fix": "Route records to exception queue for manual verification against packing and receiving logs.",
            }
        if issue_type == "date_issue":
            return {
                "explanation": f"Date sequence issue in {column}; timeline events are out of order.",
                "impact": "Invalid dates can skew ETA reliability metrics and operational SLAs.",
                "suggested_fix": "Validate date chronology and correct based on carrier milestones.",
            }
        if issue_type == "duplicate":
            return {
                "explanation": f"Duplicate records found for {column}, risking double-counting.",
                "impact": "Duplicates inflate shipment and financial metrics.",
                "suggested_fix": "De-duplicate using business keys and retain the most trustworthy record.",
            }
        if issue_type == "outlier":
            return {
                "explanation": f"Unusual values detected in {column} compared to normal historical range.",
                "impact": "Outliers may indicate data entry errors or exceptional cases requiring review.",
                "suggested_fix": "Set threshold-based alerts and verify anomalous records with source documents.",
            }
        return {
            "explanation": f"Issue detected in {column}.",
            "impact": "Data quality issue may impact planning and governance reporting.",
            "suggested_fix": "Review record lineage and correct at source.",
        }
