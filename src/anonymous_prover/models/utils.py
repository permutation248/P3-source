"""Shared utilities for ORM models."""

from __future__ import annotations

import json
from typing import Any, Optional


def parse_json_field(val: Optional[str]) -> Any:
    """Parse a JSON TEXT column value, returning the original on failure."""
    if val is None:
        return None
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return val
