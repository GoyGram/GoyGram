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

    def url(self, text: str, url: str, **kw: Any) -> KbdBuilder:
        return self.btn(text, url=url, **kw)

    def cb(self, text: str, data: str, **kw: Any) -> KbdBuilder:
        return self.btn(text, callback_data=data, **kw)

    def copy(self, text: str, copy_text: str, **kw: Any) -> KbdBuilder:
        return self.btn(text, copy_text=copy_text, **kw)

    def switch(self, text: str, query: str = "", current: bool = False, **kw: Any) -> KbdBuilder:
        if current:
            return self.btn(text, switch_inline_query_current_chat=query, **kw)
        return self.btn(text, switch_inline_query=query, **kw)

    def web(self, text: str, url: str, **kw: Any) -> KbdBuilder:
        return self.btn(text, web_app={"url": url}, **kw)

    def row(self) -> KbdBuilder:
        if self._rows[-1]:
            self._rows.append([])
        return self

    def add(self, *rows: list[dict[str, Any]]) -> KbdBuilder:
        for r in rows:
            if r:
                self._rows[-1].extend(r)
                self._rows.append([])
        if self._rows and not self._rows[-1]:
            self._rows.pop()
        return self

    def line(self, *buttons: dict[str, Any]) -> KbdBuilder:
        for b in buttons:
            self._rows[-1].append(b)
        self._rows.append([])
        return self

    def join(self, other: "KbdBuilder") -> KbdBuilder:
        rows = other.build().get("inline_keyboard", []) if other._kind == "inline" else []
        for r in rows:
            self._rows.append(list(r))
        return self

    def __len__(self) -> int:
        return sum(len(r) for r in self._rows)

    def __bool__(self) -> bool:
        return any(bool(r) for r in self._rows)

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


def kbd_to_tl(kbd: Any) -> dict[str, Any] | None:
    from goygram import ext as rx
    import json as _json

    def ser(ctor: str, fields: dict[str, Any]) -> str:
        return rx.serialize_constructor(ctor, _json.dumps(fields)).hex()

    def btn_type(b: dict[str, Any]) -> str:
        if b.get("callback_data") is not None:
            return ser("inlineButtonTypeCallback", {"data": str(b["callback_data"]).encode().hex()})
        if b.get("url") is not None:
            return ser("inlineButtonTypeUrl", {"url": str(b["url"])})
        if b.get("web_app") is not None:
            return ser("inlineButtonTypeWebView", {"url": str(b["web_app"].get("url", ""))})
        if b.get("switch_inline_query") is not None:
            return ser("inlineButtonTypeSwitchInline", {"query": str(b["switch_inline_query"])})
        if b.get("switch_inline_query_current_chat") is not None:
            return ser("inlineButtonTypeSwitchInline", {"query": str(b["switch_inline_query_current_chat"]), "same_peer": True})
        if b.get("copy_text") is not None:
            return ser("inlineButtonTypeCopy", {"copy_text": str(b["copy_text"])})
        return ser("inlineButtonTypeCallback", {"data": b.get("callback_data") or "noop"})

    def btn(b: Any) -> str:
        if isinstance(b, dict) and b.get("_") == "keyboardInlineButton":
            return ser("keyboardInlineButton", {"text": str(b.get("text", "")), "type": b.get("type")})
        d = b.to_dict() if hasattr(b, "to_dict") else dict(b) if isinstance(b, dict) else {"text": str(b)}
        fields: dict[str, Any] = {"text": str(d.get("text", "")), "type": btn_type(d)}
        icon = d.get("icon_custom_emoji_id")
        if icon is not None:
            fields["style"] = ser("keyboardButtonStyle", {"icon": int(icon)})
        return ser("keyboardInlineButton", fields)

    def reply_btn(b: dict[str, Any]) -> dict[str, Any]:
        t: dict[str, Any] = {"_": "buttonTypeDefault"}
        if b.get("request_contact"):
            t = {"_": "buttonTypeRequestPhone"}
        elif b.get("request_location"):
            t = {"_": "buttonTypeRequestGeoLocation"}
        elif b.get("request_poll"):
            t = {"_": "buttonTypeRequestPoll"}
        out = {"_": "keyboardButton", "text": str(b.get("text", "")), "type": t}
        return out

    if isinstance(kbd, KbdBuilder):
        kbd = kbd.build()
    if not isinstance(kbd, dict):
        return None
    if kbd.get("_") in {"replyInlineMarkup", "replyKeyboardMarkup", "replyKeyboardHide", "replyForceReply"}:
        return kbd
    rows_raw = kbd.get("inline_keyboard")
    if rows_raw is None:
        rows_raw = kbd.get("keyboard")
        if rows_raw is None:
            return None
        return {
            "_": "replyKeyboardMarkup",
            "rows": [
                {
                    "_": "keyboardButtonRow",
                    "buttons": [
                        b if isinstance(b, dict) and b.get("_") else reply_btn(dict(b) if isinstance(b, dict) else {"text": str(b)})
                        for b in row
                    ],
                }
                for row in rows_raw
                if isinstance(row, (list, tuple))
            ],
            "resize": bool(kbd.get("resize_keyboard", kbd.get("resize"))),
            "single_use": bool(kbd.get("single_use")),
            "selective": bool(kbd.get("selective")),
            "persistent": bool(kbd.get("persistent")),
        }
    rows = [
        ser("keyboardInlineButtonRow", {"buttons": [btn(b) for b in row]})
        for row in rows_raw
        if isinstance(row, (list, tuple))
    ]
    return {"_": "replyInlineMarkup", "rows": rows}
