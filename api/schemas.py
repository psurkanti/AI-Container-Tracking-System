from __future__ import annotations

from typing import Any
from typing import Optional

from pydantic import BaseModel, Field


class SourceInput(BaseModel):
    file_path: Optional[str] = Field(default=None, description="Absolute or project-relative CSV path")


class QualityCheckInput(SourceInput):
    self_heal: bool = False


class GenericResponse(BaseModel):
    status: str = "success"
    payload: dict[str, Any]
