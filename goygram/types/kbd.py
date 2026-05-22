# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

from typing import Any


class Btn:
    __slots__ = ("text", "data", "url")

    def __init__(self, text: str, data: str | None = None, url: str | None = None) -> None:
        self.text = text
        self.data = data
        self.url = url

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"text": self.text}
        if self.data is not None:
            out["callback_data"] = self.data
        if self.url is not None:
            out["url"] = self.url
        return out


class InlineKbd:
    __slots__ = ("rows",)

    def __init__(self) -> None:
        self.rows: list[list[Btn]] = []

    def add_btn(self, text: str, data: str | None = None, url: str | None = None, row: int = -1) -> "InlineKbd":
        btn = Btn(text, data, url)
        if row < 0 or row >= len(self.rows):
            self.rows.append([btn])
            return self
        self.rows[row].append(btn)
        return self

    def add_row(self, *btns: Btn) -> "InlineKbd":
        self.rows.append(list(btns))
        return self

    def to_dict(self) -> dict[str, Any]:
        return {"inline_keyboard": [[x.to_dict() for x in row] for row in self.rows]}


class ReplyKbd:
    __slots__ = ("rows", "resize", "once")

    def __init__(self, resize: bool = True, once: bool = False) -> None:
        self.rows: list[list[Btn]] = []
        self.resize = resize
        self.once = once

    def add_btn(self, text: str, row: int = -1) -> "ReplyKbd":
        btn = Btn(text)
        if row < 0 or row >= len(self.rows):
            self.rows.append([btn])
            return self
        self.rows[row].append(btn)
        return self

    def add_row(self, *btns: Btn) -> "ReplyKbd":
        self.rows.append(list(btns))
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "keyboard": [[{"text": x.text} for x in row] for row in self.rows],
            "resize_keyboard": self.resize,
            "one_time_keyboard": self.once,
        }


class ForceReply:
    __slots__ = ("selective", "placeholder")

    def __init__(self, selective: bool = False, placeholder: str | None = None) -> None:
        self.selective = selective
        self.placeholder = placeholder

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"force_reply": True, "selective": self.selective}
        if self.placeholder is not None:
            out["input_field_placeholder"] = self.placeholder
        return out


class ReplyGone:
    __slots__ = ("selective",)

    def __init__(self, selective: bool = False) -> None:
        self.selective = selective

    def to_dict(self) -> dict[str, Any]:
        return {"remove_keyboard": True, "selective": self.selective}


class LinkOpts:
    __slots__ = ("disabled", "url", "small", "large", "above")

    def __init__(
        self,
        disabled: bool = False,
        url: str | None = None,
        small: bool = False,
        large: bool = False,
        above: bool = False,
    ) -> None:
        self.disabled = disabled
        self.url = url
        self.small = small
        self.large = large
        self.above = above

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.disabled:
            out["is_disabled"] = True
        if self.url is not None:
            out["url"] = self.url
        if self.small:
            out["prefer_small_media"] = True
        if self.large:
            out["prefer_large_media"] = True
        if self.above:
            out["show_above_text"] = True
        return out
