"""Strict API schema base classes."""
from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Reject undeclared fields and normalize surrounding string whitespace."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
