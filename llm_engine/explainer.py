from __future__ import annotations

from llm_engine.client import LLMClient


class AIExplainer:
    def __init__(self) -> None:
        self.client = LLMClient()

    def enrich_issues(self, issues: list[dict]) -> list[dict]:
        enriched = []
        for issue in issues:
            ai_text = self.client.explain_issue(issue)
            merged = {
                **issue,
                "explanation": ai_text["explanation"],
                "impact": ai_text["impact"],
                "suggested_fix": ai_text["suggested_fix"],
            }
            enriched.append(merged)
        return enriched
