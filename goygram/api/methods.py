# Copyleft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations
from typing import Any
from goygram.api.types import *

def dump(v: Any) -> Any:
    if hasattr(v, "to_dict"):
        return v.to_dict()
    if isinstance(v, list):
        return [dump(x) for x in v]
    if isinstance(v, dict):
        return {k: dump(x) for k, x in v.items() if x is not None}
    return v

class BotAPI:
    __slots__ = ("net",)
    def __init__(self, net: Any) -> None:
        self.net = net

    async def call(self, meth: str, **kw: Any) -> Any:
        return await self.net.req(meth, dump(kw))

    def __getattr__(self, name: str) -> Any:
        async def dyn(**kw: Any) -> Any:
            parts = name.split("_")
            meth = parts[0] + "".join(x[:1].upper() + x[1:] for x in parts[1:])
            return await self.call(meth, **kw)
        return dyn

    async def get_me(self) -> User:
        data: dict[str, Any] = {}
        return await self.net.req("getMe", data)

    async def send_message(self, chat_id: int|str, text: str, parse_mode: str|None = None, reply_parameters: dict[str,Any]|None = None, reply_markup: InlineKeyboardMarkup|ReplyKeyboardMarkup|dict[str,Any]|None = None, message_thread_id: int|None = None) -> Message:
        data: dict[str, Any] = {}
        if chat_id is not None:
            data["chat_id"] = dump(chat_id)
        if text is not None:
            data["text"] = dump(text)
        if parse_mode is not None:
            data["parse_mode"] = dump(parse_mode)
        if reply_parameters is not None:
            data["reply_parameters"] = dump(reply_parameters)
        if reply_markup is not None:
            data["reply_markup"] = dump(reply_markup)
        if message_thread_id is not None:
            data["message_thread_id"] = dump(message_thread_id)
        return await self.net.req("sendMessage", data)

    async def edit_message_text(self, text: str, chat_id: int|str|None = None, message_id: int|None = None, inline_message_id: str|None = None, reply_markup: InlineKeyboardMarkup|dict[str,Any]|None = None) -> Message|bool:
        data: dict[str, Any] = {}
        if text is not None:
            data["text"] = dump(text)
        if chat_id is not None:
            data["chat_id"] = dump(chat_id)
        if message_id is not None:
            data["message_id"] = dump(message_id)
        if inline_message_id is not None:
            data["inline_message_id"] = dump(inline_message_id)
        if reply_markup is not None:
            data["reply_markup"] = dump(reply_markup)
        return await self.net.req("editMessageText", data)

    async def delete_message(self, chat_id: int|str, message_id: int) -> bool:
        data: dict[str, Any] = {}
        if chat_id is not None:
            data["chat_id"] = dump(chat_id)
        if message_id is not None:
            data["message_id"] = dump(message_id)
        return await self.net.req("deleteMessage", data)

__all__ = ["BotAPI"]
