# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

from typing import Any


class KbdBuilder:
    __slots__ = ("_kind", "_opts", "_rows")

    def __init__(self, kind: str = "inline", **opts: Any) -> None:
        self._kind = kind
        self._opts = opts
        self._rows: list[list[dict[str, Any]]] = [[]]

    def btn(self, text: str, **kw: Any) -> KbdBuilder:
        btn: dict[str, Any] = {"text": text, **kw}
        self._rows[-1].append(btn)
        return self

    def row(self) -> KbdBuilder:
        if self._rows[-1]:
            self._rows.append([])
        return self

    def build(self) -> dict[str, Any]:
        rows = [r for r in self._rows if r]
        if self._kind == "inline":
            return {"inline_keyboard": rows}
        if self._kind == "reply":
            out: dict[str, Any] = {"keyboard": rows}
            out.update(self._opts)
            return out
        if self._kind == "force":
            out = {"force_reply": True}
            out.update(self._opts)
            return out
        if self._kind == "remove":
            out = {"remove_keyboard": True}
            out.update(self._opts)
            return out
        return {}

    def to_dict(self) -> dict[str, Any]:
        return self.build()
