from __future__ import annotations

from typing import Any
from typing import Optional

from pydantic import BaseModel, Field


class QualityIssue(BaseModel):
    type: str
    column: Optional[str] = None
    entity: Optional[str] = None
    count: int = 1
    severity: str = "medium"
    details: dict[str, Any] = Field(default_factory=dict)
    explanation: Optional[str] = None
    suggested_fix: Optional[str] = None


class QualityResult(BaseModel):
    data_quality_score: float
    issues: list[QualityIssue]
    profiling: dict[str, Any]
    fixes_applied: list[dict[str, Any]] = Field(default_factory=list)
