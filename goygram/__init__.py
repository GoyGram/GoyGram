# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

from .client import GoyGram
from .errors import StopPropagation
from .session import Session

__all__ = ["GoyGram", "Session", "StopPropagation"]


def __getattr__(name: str) -> str:
    if name != "__version__":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib.metadata import PackageNotFoundError, version
    try:
        value = version("goygram")
    except PackageNotFoundError:
        value = "0.0.0"
    globals()[name] = value
    return value
