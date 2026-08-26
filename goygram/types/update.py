# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

from typing import Any


class UpdateObj:
    __slots__ = ("src", "raw", "app", "type")

    def __init__(self, src: str, raw: dict[str, Any], app: Any) -> None:
        self.src = src
        self.raw = raw
        self.app = app
        update = raw.get("raw_update")
        nested = update.get("_") if isinstance(update, dict) else None
        source = raw.get("raw")
        source_type = source.get("_") if isinstance(source, dict) else None
        self.type = str(raw.get("update_type") or raw.get("_") or nested or source_type or "unknown")

    @property
    def update_type(self) -> str:
        return self.type

    def get(self, key: str, default: Any = None) -> Any:
        if key == "update_type":
            return self.type
        return self.raw.get(key, default)

    def __getitem__(self, key: str) -> Any:
        if key == "update_type":
            return self.type
        return self.raw[key]

    def __getattr__(self, name: str) -> Any:
        if name == "update_type":
            return self.type
        try:
            return self.raw[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def to_dict(self) -> dict[str, Any]:
        return self.raw
