# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations
from typing import Any

def dump(v: Any) -> Any:
    if hasattr(v, "to_dict"):
        return v.to_dict()
    if isinstance(v, list):
        return [dump(x) for x in v]
    if isinstance(v, dict):
        return {k: dump(x) for k, x in v.items() if x is not None}
    return v

class User:
    __slots__ = ('id', 'is_bot', 'first_name', 'username')
    def __init__(self, id: int, is_bot: bool, first_name: str, username: str|None = None) -> None:
        self.id = id
        self.is_bot = is_bot
        self.first_name = first_name
        self.username = username

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": dump(self.id),
            "is_bot": dump(self.is_bot),
            "first_name": dump(self.first_name),
            "username": dump(self.username),
        }

class Chat:
    __slots__ = ('id', 'type', 'title', 'username')
    def __init__(self, id: int, type: str, title: str|None = None, username: str|None = None) -> None:
        self.id = id
        self.type = type
        self.title = title
        self.username = username

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": dump(self.id),
            "type": dump(self.type),
            "title": dump(self.title),
            "username": dump(self.username),
        }

class Message:
    __slots__ = ('message_id', 'date', 'chat', 'text')
    def __init__(self, message_id: int, date: int, chat: Chat, text: str|None = None) -> None:
        self.message_id = message_id
        self.date = date
        self.chat = chat
        self.text = text

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": dump(self.message_id),
            "date": dump(self.date),
            "chat": dump(self.chat),
            "text": dump(self.text),
        }

__all__ = ['User', 'Chat', 'Message']
