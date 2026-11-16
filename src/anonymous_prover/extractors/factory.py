"""Extractor factory."""

from __future__ import annotations

from .default import DefaultExtractor


def create_extractor(**kwargs):
    """Create the default result extractor."""
    return DefaultExtractor(**kwargs)
