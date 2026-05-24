# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

import secrets
from typing import Any


class MsgObj:
    __slots__ = ("src", "raw", "app", "id", "chat_id", "from_id", "text", "is_me")

    src: str
    raw: dict[str, Any]
    app: Any
    id: int | None
    chat_id: int | str | None
    from_id: int | None
    text: str
    is_me: bool

    def __init__(self, src: str, raw: dict[str, Any], app: Any) -> None:
        self.src = src
        self.raw = raw
        self.app = app
        self.id = raw.get("msg_id")
        self.chat_id = raw.get("chat_id")
        self.from_id = raw.get("from_id")
        self.text = str(raw.get("text", ""))
        self.is_me = bool(raw.get("is_me", False))

    @property
    def msg_id(self) -> int | None:
        return self.id

    def net(self) -> Any:
        if self.src == "bot":
            if self.app.bot is None:
                raise RuntimeError("bot net is not configured")
            return self.app.bot
        if self.app.mt is None:
            raise RuntimeError("mt net is not configured")
        return self.app.mt

    def _resolve_peer(self, chat_id):
        c = self.app.mt.codec
        if isinstance(chat_id, int):
            if chat_id > 0:
                return c.input_peer_user(chat_id, 0)
            raw = -chat_id
            if raw > 1000000000000:
                return c.input_peer_channel(raw - 1000000000000, 0)
            return c.input_peer_chat(raw)
        return c.input_peer_self()

    async def reply(self, txt: str, kbd: Any | None = None, topic_id: int | None = None, link_options: Any | None = None, **kw: Any) -> Any:
        if self.chat_id is None:
            return None
        if self.src == "bot" and self.app.bot is not None:
            data = dict(kw)
            if self.id is not None:
                data["reply_parameters"] = {"message_id": self.id}
            if kbd is not None:
                data["reply_markup"] = kbd.to_dict() if hasattr(kbd, "to_dict") else kbd
            if topic_id is not None:
                data["message_thread_id"] = topic_id
            if link_options is not None:
                data["link_preview_options"] = link_options.to_dict() if hasattr(link_options, "to_dict") else link_options
            return await self.app.bot_req("sendMessage", chat_id=self.chat_id, text=txt, **data)
        if self.app.mt is not None:
            data = dict(kw)
            peer = self._resolve_peer(self.chat_id)
            if self.id is not None:
                data["reply_to"] = self.app.mt.codec.input_reply_to_message(int(self.id))
            if kbd is not None:
                data["kbd"] = kbd
            if link_options is not None:
                data["link_options"] = link_options
            return await self.app.mt_req("messages.sendMessage",
                peer=peer,
                message=txt,
                random_id=secrets.randbits(63),
                **data)
        return None

    async def delete(self) -> Any:
        if self.chat_id is None or self.id is None:
            return None
        if self.src == "bot" and self.app.bot is not None:
            return await self.app.bot_req("deleteMessage", chat_id=self.chat_id, message_id=self.id)
        if self.app.mt is not None:
            return await self.app.mt_req("messages.deleteMessages", id=[int(self.id)], revoke=True)
        return None
