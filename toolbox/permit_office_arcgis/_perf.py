"""Lightweight perf instrumentation gated on the PERMIT_OFFICE_PERF env var.

Both ``perf_session`` and ``perf_block`` are no-ops unless ``PERMIT_OFFICE_PERF``
is set to a truthy value, so normal tool runs pay nothing for the wrapping.

When enabled, blocks compose into a nested tree: an outer ``perf_session`` (or
top-level ``perf_block``) collects child blocks beneath it and emits a single
line summary through the same ArcGIS messages channel as the rest of the
toolbox.

Example output (with PERMIT_OFFICE_PERF=1)::

    [PERF] turn=approve total=7.612 (writes=1.180 rebuild=6.205 (sel=0.082 remove=0.621 add=5.314 refresh=0.188))
"""

from __future__ import annotations

import contextlib
import functools
import os
import threading
import time

from .messages import _log


PERF_ENV = "PERMIT_OFFICE_PERF"

_state = threading.local()
_override = None  # None defers to env var; True/False forces the gate.


def set_enabled(value):
    """Force-enable or force-disable the perf gate; pass None to revert to env."""

    global _override
    _override = None if value is None else bool(value)


def perf_enabled():
    """Return True when perf logging is on, via runtime override or env var."""

    if _override is not None:
        return _override
    return os.environ.get(PERF_ENV, "") not in ("", "0", "false", "False", "no", "No")


class _PerfBlock:
    """One node in the perf tree; records its own elapsed and any children."""

    __slots__ = ("name", "children", "_start", "elapsed")

    def __init__(self, name):
        self.name = name
        self.children = []
        self._start = time.perf_counter()
        self.elapsed = 0.0

    def stop(self):
        self.elapsed = time.perf_counter() - self._start

    def summary(self):
        if not self.children:
            return f"{self.name}={self.elapsed:.3f}"
        parts = " ".join(child.summary() for child in self.children)
        return f"{self.name}={self.elapsed:.3f} ({parts})"


def _stack():
    stack = getattr(_state, "stack", None)
    if stack is None:
        stack = []
        _state.stack = stack
    return stack


@contextlib.contextmanager
def perf_block(name, messages=None):
    """Record elapsed time for a named code block.

    When this block is the outermost one and ``messages`` is provided, the
    summary line (including any nested children) is emitted on exit.
    """

    if not perf_enabled():
        yield None
        return
    stack = _stack()
    block = _PerfBlock(name)
    if stack:
        stack[-1].children.append(block)
    stack.append(block)
    try:
        yield block
    finally:
        stack.pop()
        block.stop()
        if not stack and messages is not None:
            _log(messages, "PERF", block.summary())


def perf_session(name, messages):
    """Alias for ``perf_block`` intended to mark a top-level turn boundary."""

    return perf_block(name, messages)


def perf_traced(name):
    """Decorator that wraps a function call in a ``perf_block(name)``.

    Cheaper to apply than indenting an entire function body. Pays a single
    no-op context manager per call when ``PERMIT_OFFICE_PERF`` is off.
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            with perf_block(name):
                return fn(*args, **kwargs)
        return wrapper

    return decorator
