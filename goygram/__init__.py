# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from importlib.metadata import PackageNotFoundError, version as pkg_version

from .client import GoyGram
from .errors import StopPropagation
from .session import Session

__all__ = ["GoyGram", "Session", "StopPropagation"]

try:
    __version__ = pkg_version("goygram")
except PackageNotFoundError:
    __version__ = "0.0.0"
