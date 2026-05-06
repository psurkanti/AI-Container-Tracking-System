from __future__ import annotations

import logging

import pandas as pd

from llm_engine.explainer import AIExplainer
from pipelines.profiling import profile_dataframe
from pipelines.self_heal import apply_self_healing
from validation.checks import compute_quality_score, run_quality_checks
from validation.schema import SchemaDriftDetector

logger = logging.getLogger(__name__)


class QualityPipeline:
    def __init__(self) -> None:
        self.explainer = AIExplainer()
        self.schema_detector = SchemaDriftDetector()

    def run_checks(self, df: pd.DataFrame, include_ai: bool = False, self_heal: bool = False) -> dict:
        working_df = df.copy()
        fixes_applied = []
        if self_heal:
            working_df, fixes_applied = apply_self_healing(working_df)

        profiling = profile_dataframe(working_df)
        issues = run_quality_checks(working_df)
        score = compute_quality_score(working_df, issues)

        if include_ai:
            issues = self.explainer.enrich_issues(issues)

        logger.info(
            "Quality checks completed",
            extra={
                "event": "validation",
                "issues_found": len(issues),
                "fixes_applied": len(fixes_applied),
            },
        )

        return {
            "data_quality_score": score,
            "issues": issues,
            "profiling": profiling,
            "fixes_applied": fixes_applied,
            "dataframe": working_df,
        }

    def detect_schema_drift(self, df: pd.DataFrame) -> dict:
        return self.schema_detector.detect(df)
