"""Base class for JSON contract models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Rejects unknown fields so contract drift fails loudly."""

    model_config = ConfigDict(extra="forbid")
