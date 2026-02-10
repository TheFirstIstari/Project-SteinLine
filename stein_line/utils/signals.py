"""Helper utilities for safe Qt Signal emission.

Provide a single `safe_emit` function that attempts to call
`signal_obj.emit(*args)` and falls back to logging/stderr when
emitting isn't possible (prevents AttributeError crashes).
"""
from typing import Any

def safe_emit(signal_obj: Any, *args: Any) -> None:
    try:
        signal_obj.emit(*args)
        return
    except Exception:
        try:
            import logging
            logging.warning("Signal emit failed for %s with args %s", getattr(signal_obj, '__name__', str(signal_obj)), args)
        except Exception:
            try:
                import sys
                sys.stderr.write(f"Signal emit fallback: {args}\n")
            except Exception:
                pass
