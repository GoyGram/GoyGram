# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

from typing import Any


class InlineObj:
    __slots__ = ("src", "raw", "app", "id", "from_id", "query", "offset", "chat_type", "location")

    def __init__(self, src: str, raw: dict[str, Any], app: Any) -> None:
        self.src = src
        self.raw = raw
        self.app = app
        self.id = raw.get("query_id")
        self.from_id = raw.get("from_id")
        self.query = raw.get("query", "")
        self.offset = raw.get("offset", "")
        self.chat_type = raw.get("chat_type")
        self.location = raw.get("location")

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def __getattr__(self, name: str) -> Any:
        try:
            return self.raw[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def to_dict(self) -> dict[str, Any]:
        return self.raw

    async def answer(
        self,
        results: list[dict[str, Any]],
        *,
        cache_time: int = 0,
        is_personal: bool = True,
        next_offset: str | None = None,
        button: dict[str, Any] | None = None,
        switch_pm_text: str | None = None,
        switch_pm_parameter: str | None = None,
    ) -> Any:
        if self.id is None:
            return None
        if self.app.bot is None:
            raise RuntimeError("bot net is not configured")
        data: dict[str, Any] = {
            "inline_query_id": str(self.id),
            "results": results,
            "cache_time": cache_time,
            "is_personal": is_personal,
        }
        if next_offset is not None:
            data["next_offset"] = next_offset
        if button is not None:
            data["button"] = button
        if switch_pm_text is not None:
            data["switch_pm_text"] = switch_pm_text
        if switch_pm_parameter is not None:
            data["switch_pm_parameter"] = switch_pm_parameter
        return await self.app.bot_req("answerInlineQuery", **data)

    @staticmethod
    def article(
        result_id: str,
        title: str,
        text: str,
        *,
        description: str | None = None,
        parse_mode: str | None = None,
        kbd: Any | None = None,
        url: str | None = None,
        hide_url: bool | None = None,
        thumb_url: str | None = None,
        thumb_width: int | None = None,
        thumb_height: int | None = None,
    ) -> dict[str, Any]:
        message: dict[str, Any] = {"message_text": text}
        if parse_mode is not None:
            message["parse_mode"] = parse_mode
        if kbd is not None:
            message["reply_markup"] = kbd.to_dict() if hasattr(kbd, "to_dict") else kbd
        result: dict[str, Any] = {
            "type": "article",
            "id": result_id,
            "title": title,
            "input_message_content": message,
        }
        if description is not None:
            result["description"] = description
        if url is not None:
            result["url"] = url
        if hide_url is not None:
            result["hide_url"] = hide_url
        if thumb_url is not None:
            result["thumb_url"] = thumb_url
        if thumb_width is not None:
            result["thumb_width"] = thumb_width
        if thumb_height is not None:
            result["thumb_height"] = thumb_height
        return result
