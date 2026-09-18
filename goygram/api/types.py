# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations
from typing import Any

_ATOM = {type(None), bool, int, float, str, bytes, bytearray, memoryview}


def dump(v: Any) -> Any:
    t = type(v)
    if t in _ATOM:
        return v
    if t is dict:
        return {k: dump(x) for k, x in v.items() if x is not None}
    if t is list or t is tuple:
        return [dump(x) for x in v]
    fn = getattr(t, "to_dict", None)
    if fn is not None:
        return dump(fn(v))
    return v


class User:
    __slots__ = ('id', 'is_bot', 'first_name', 'username')
    def __init__(self, id: int, is_bot: bool, first_name: str, username: str|None = None) -> None:
        self.id = id
        self.is_bot = is_bot
        self.first_name = first_name
        self.username = username

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "is_bot": self.is_bot, "first_name": self.first_name, "username": self.username}


class Chat:
    __slots__ = ('id', 'type', 'title', 'username')
    def __init__(self, id: int, type: str, title: str|None = None, username: str|None = None) -> None:
        self.id = id
        self.type = type
        self.title = title
        self.username = username

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "type": self.type, "title": self.title, "username": self.username}


class Message:
    __slots__ = ('message_id', 'date', 'chat', 'text')
    def __init__(self, message_id: int, date: int, chat: Chat, text: str|None = None) -> None:
        self.message_id = message_id
        self.date = date
        self.chat = chat
        self.text = text

    def to_dict(self) -> dict[str, Any]:
        return {"message_id": self.message_id, "date": self.date, "chat": dump(self.chat), "text": self.text}


__all__ = ['dump', 'User', 'Chat', 'Message']
