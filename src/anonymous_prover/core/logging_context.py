"""Per-experiment logging context utilities."""

from __future__ import annotations

import contextvars
import logging
import threading

_LOCK = threading.Lock()
_INSTALLED = False

_EXPERIMENT_TAG: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "anonymous_experiment_tag",
    default=None,
)


def install_experiment_record_factory() -> None:
    """Install a LogRecordFactory that injects ``experiment_tag``."""
    global _INSTALLED
    if _INSTALLED:
        return
    with _LOCK:
        if _INSTALLED:
            return
        old_factory = logging.getLogRecordFactory()

        def _factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.experiment_tag = _EXPERIMENT_TAG.get()
            return record

        logging.setLogRecordFactory(_factory)
        _INSTALLED = True


def set_experiment_tag(tag: str | None):
    """Set current experiment tag and return context token."""
    return _EXPERIMENT_TAG.set(tag)


def reset_experiment_tag(token) -> None:
    """Reset previously set experiment tag token."""
    _EXPERIMENT_TAG.reset(token)


class ExperimentTagFilter(logging.Filter):
    """Allow only records matching one experiment tag."""

    def __init__(self, tag: str) -> None:
        super().__init__()
        self._tag = tag

    def filter(self, record: logging.LogRecord) -> bool:
        return getattr(record, "experiment_tag", None) == self._tag
