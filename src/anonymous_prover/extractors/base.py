"""Base extractor with shared utilities."""

from __future__ import annotations

import logging
import os
import re

from .stream_parsers import StreamJsonParser, StreamMetrics

logger = logging.getLogger(__name__)


class BaseExtractor:
    """Common helpers shared by all result extractors."""

    @staticmethod
    def _derive_task_name(task_path: str) -> str:
        """Derive a human-friendly task name from a file path.

        Strips the directory prefix and ``.lean`` extension, and removes any
        ``_Generated`` suffix that was appended during workspace setup.
        """
        basename = os.path.splitext(os.path.basename(task_path))[0]
        basename = re.sub(r"_Generated$", "", basename)
        return basename

    @staticmethod
    def _parse_stream(stream_path: str, *, fallback_model: str = "") -> StreamMetrics:
        """Create a :class:`StreamJsonParser` and parse *stream_path*."""
        parser = StreamJsonParser()
        return parser.parse(stream_path, fallback_model=fallback_model)
