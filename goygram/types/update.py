# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

from typing import Any


class UpdateObj:
    __slots__ = ("src", "raw", "app", "type")

    def __init__(self, src: str, raw: dict[str, Any], app: Any) -> None:
        self.src = src
        self.raw = raw
        self.app = app
        self.type = str(raw.get("update_type") or raw.get("_") or "unknown")

    @property
    def update_type(self) -> str:
        return self.type

    def get(self, key: str, default: Any = None) -> Any:
        if key == "update_type":
            return self.type
        return self.raw.get(key, default)
