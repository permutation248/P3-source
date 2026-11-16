"""Collector factory."""

from __future__ import annotations

from .default import DefaultCollector


def create_collector(**kwargs):
    """Create the default result collector."""
    return DefaultCollector(**kwargs)
