"""Comparator factory."""

from __future__ import annotations

from .default import DefaultComparator


def create_comparator(**kwargs):
    """Create the default result comparator."""
    return DefaultComparator(**kwargs)
