from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ManualUpdate(BaseModel):
    windows: list[dict[str, Any]] = Field(min_length=1, max_length=20)
