from __future__ import annotations

from typing import Any


class UpdateObj:
    __slots__ = ("src", "raw", "app", "type")

    def __init__(self, src: str, raw: dict[str, Any], app: Any) -> None:
        self.src = src
        self.raw = raw
        self.app = app
        self.type = str(raw.get("update_type") or raw.get("_") or "unknown")
