# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

import json
import secrets
from typing import Any


class Obj:
    src: str
    raw: dict[str, Any]
    app: Any
    id: int | None
    chat_id: int | str | None
    from_id: int | None
    msg_id: int | None
    kind: str

    def __init__(self, src: str, raw: dict[str, Any], app: Any) -> None:
        self.src = src
        self.raw = raw
        self.app = app
        kind = raw.get("kind")
        if kind == "cb" or kind == "inline":
            self.id = raw.get("query_id")
        else:
            self.id = raw.get("msg_id") or raw.get("query_id") or raw.get("poll_id") or raw.get("id")
        self.chat_id = raw.get("chat_id")
        self.from_id = raw.get("from_id")
        self.msg_id = raw.get("msg_id")
        self.kind = raw.get("kind", raw.get("update_type", "msg"))
        self.match = None

    @property
    def text(self) -> str:
        return str(self.raw.get("text", ""))

    @property
    def data(self) -> Any:
        return self.raw.get("data")

    @property
    def query(self) -> Any:
        return self.raw.get("query")

    @property
    def cmd(self) -> str | None:
        return self.raw.get("cmd")

    @property
    def args(self) -> Any:
        return self.raw.get("args")

    @property
    def is_me(self) -> bool:
        return bool(self.raw.get("is_me", False))

    @property
    def update_type(self) -> str:
        return str(self.raw.get("update_type") or self.raw.get("_") or self.kind)

    @property
    def inline_message_id(self) -> Any:
        return self.raw.get("inline_message_id")

    @property
    def old(self) -> Any:
        return self.raw.get("old_status", self.raw.get("old"))

    @property
    def new(self) -> Any:
        return self.raw.get("new_status", self.raw.get("new"))

    @property
    def user_id(self) -> Any:
        return self.raw.get("user_id")

    @property
    def closed(self) -> Any:
        return self.raw.get("is_closed", False)

    @property
    def question(self) -> Any:
        return self.raw.get("question", "")

    @property
    def offset(self) -> Any:
        return self.raw.get("offset", "")

    @property
    def chat_type(self) -> Any:
        v = self.raw.get("chat_type")
        if v is None:
            chat = self.raw.get("chat")
            if isinstance(chat, dict):
                return chat.get("type")
        return v

    @property
    def location(self) -> Any:
        return self.raw.get("location")

    @property
    def words(self) -> list[str]:
        return self.text.split()

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    @property
    def urls(self) -> list[str]:
        raw = self.raw.get("entities") or []
        out = []
        for ent in raw:
            if isinstance(ent, dict) and ent.get("type") == "url":
                off = int(ent.get("offset", 0))
                ln = int(ent.get("length", 0))
                out.append(self.text[off:off + ln])
        return out

    @property
    def entities(self) -> list[dict[str, Any]]:
        v = self.raw.get("entities")
        return v if isinstance(v, list) else []

    @property
    def has_text(self) -> bool:
        return bool(self.text.strip())

    @property
    def html_text(self) -> str:
        from goygram.sugar import parse_entities_html
        return parse_entities_html(self.text, self.entities)

    @property
    def caption(self) -> str:
        return str(self.raw.get("caption", "") or "")

    @property
    def is_private(self) -> bool:
        return self.chat_type == "private"

    @property
    def is_group(self) -> bool:
        return self.chat_type in ("group", "supergroup")

    @property
    def chat_title(self) -> str | None:
        chat = self.raw.get("chat")
        if isinstance(chat, dict):
            return chat.get("title") or chat.get("first_name") or chat.get("username")
        return None

    @property
    def username(self) -> str | None:
        chat = self.raw.get("chat")
        if isinstance(chat, dict):
            return chat.get("username")
        return None

    @property
    def file_size(self) -> int | None:
        from goygram.filters import _msize
        try:
            return int(_msize(self))
        except (TypeError, ValueError):
            return None

    @property
    def file_name(self) -> str | None:
        raw = self.raw
        for key in ("document", "video", "audio", "voice", "animation", "video_note"):
            v = raw.get(key)
            if isinstance(v, dict) and v.get("file_name"):
                return v["file_name"]
        return None

    @property
    def mime(self) -> str | None:
        raw = self.raw
        for key in ("document", "video", "audio", "voice", "animation", "video_note"):
            v = raw.get(key)
            if isinstance(v, dict) and v.get("mime_type"):
                return v["mime_type"]
        return None

    @property
    def media_type(self) -> str | None:
        from goygram.filters import _mkey
        return _mkey(self)

    @property
    def is_media(self) -> bool:
        return self.media_type is not None

    @property
    def date_ts(self) -> int | None:
        v = self.raw.get("date")
        return int(v) if v is not None else None

    @property
    def edit_date_ts(self) -> int | None:
        v = self.raw.get("edit_date")
        return int(v) if v is not None else None

    @property
    def is_reply(self) -> bool:
        return bool(self.raw.get("reply_to_message"))

    @property
    def reply_msg(self) -> "Obj | None":
        r = self.raw.get("reply_to_message")
        if isinstance(r, dict):
            return Obj(self.src, r, self.app)
        return None

    @property
    def args_list(self) -> list[str]:
        a = self.raw.get("args")
        if isinstance(a, str):
            return a.split() if a else []
        if isinstance(a, list):
            return [str(x) for x in a]
        return []

    @property
    def command_name(self) -> str | None:
        return self.cmd

    @property
    def full_name(self) -> str:
        first = self._value("first_name")
        last = self._value("last_name")
        if first is None or last is None:
            chat = self.raw.get("chat")
            if isinstance(chat, dict):
                if first is None:
                    first = chat.get("first_name") or chat.get("title")
                if last is None:
                    last = chat.get("last_name")
        parts = [p for p in (first, last) if p]
        return " ".join(str(p) for p in parts) if parts else ""

    @property
    def mention(self) -> str:
        name = self.full_name or str(self.from_id or self.chat_id)
        uid = self.from_id if self.from_id is not None else self.chat_id
        return f'<a href="tg://user?id={uid}">{name}</a>'

    @property
    def ago(self) -> str:
        from datetime import datetime, timezone

        ts = self.raw.get("date")
        if ts is None:
            return ""
        delta = datetime.now(tz=timezone.utc).timestamp() - float(ts)
        if delta < 0:
            delta = 0.0
        m, s = divmod(int(delta), 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)
        if d:
            return f"{d}d"
        if h:
            return f"{h}h"
        if m:
            return f"{m}m"
        return f"{s}s"

    async def ask(self, prompt: str | None = None, timeout: float = 60.0, filt: Any = None, user_id: int | None = None, from_me: bool = False) -> "Obj | None":
        if prompt:
            await self.reply(prompt)
        uid = user_id
        if uid is None and from_me:
            uid = getattr(self.app, "self_id", None)
        if uid is None:
            uid = self.from_id
        return await self.app.conv_wait(self.chat_id, user_id=uid, filt=filt, timeout=timeout)

    async def copy_to(self, chat_id: int | str, **kw: Any) -> Any:
        return await self.app.copy_msg(self.chat_id, self.msg_id, to=chat_id, **kw)

    async def typing(self) -> None:
        await self.app.send_action(self.chat_id, "typing")

    async def get_chat(self, **kw: Any) -> Any:
        return await self.app.get_chat(self.chat_id, via=self.src, **kw)

    async def get_sender(self, **kw: Any) -> Any:
        return await self.app.get_user(self.from_id, via=self.src, **kw)

    async def mark_read(self) -> Any:
        return await self.app.mark_read(self.chat_id, self.msg_id)

    def _value(self, key: str, default: Any = None) -> Any:
        if key in self.raw:
            return self.raw[key]
        source = self.raw.get("raw")
        if isinstance(source, dict):
            if key in source:
                return source[key]
            for name in ("message", "edited_message", "channel_post", "edited_channel_post"):
                obj = source.get(name)
                if isinstance(obj, dict) and key in obj:
                    return obj[key]
        update = self.raw.get("raw_update")
        if isinstance(update, dict):
            obj = update.get("message")
            if isinstance(obj, dict) and key in obj:
                return obj[key]
            if key in update:
                return update[key]
        return default

    def get(self, key: str, default: Any = None) -> Any:
        return self._value(key, default)

    def __getitem__(self, key: str) -> Any:
        value = self._value(key)
        if value is None and key not in self.raw:
            raise KeyError(key)
        return value

    def __getattr__(self, name: str) -> Any:
        key = "from" if name == "from_user" else name
        value = self._value(key)
        if value is None:
            raise AttributeError(name)
        return value

    def to_dict(self) -> dict[str, Any]:
        return self.raw

    async def respond(self, text: str, **kw: Any) -> Any:
        return await self.app.send_msg(self.chat_id, text, via=self.src, **kw)

    async def answer(self, text: str | None = None, alert: bool = False, url: str | None = None, cache_time: int = 0, results: list[dict[str, Any]] | None = None, **kw: Any) -> Any:
        if self.kind == "inline" and results is not None:
            if self.id is None:
                return None
            if self.src == "mt" or self.app.bot is None:
                if self.app.mt is None:
                    raise RuntimeError("mt net is not configured")
                data: dict[str, Any] = {
                    "query_id": int(self.id),
                    "gallery": bool(kw.pop("gallery", False)),
                    "private": bool(kw.pop("is_personal", True)),
                    "cache_time": int(cache_time),
                }
                next_offset = kw.pop("next_offset", None)
                if next_offset:
                    data["next_offset"] = next_offset
                data["results"] = results
                return await self.app.mt_req("messages.setInlineBotResults", **data)
            data = {
                "inline_query_id": str(self.id),
                "results": results,
                "cache_time": kw.pop("cache_time", cache_time),
                "is_personal": kw.pop("is_personal", True),
            }
            for opt in ("next_offset", "button", "switch_pm_text", "switch_pm_parameter"):
                if opt in kw:
                    data[opt] = kw.pop(opt)
            data.update(kw)
            return await self.app.bot_req("answerInlineQuery", **data)
        if self.id is None:
            return None
        if self.src == "mt" or self.app.bot is None:
            if self.app.mt is None:
                raise RuntimeError("mt net is not configured")
            return await self.app.mt_req(
                "messages.setBotCallbackAnswer",
                query_id=int(self.id),
                message=text,
                alert=bool(alert),
                url=url,
                cache_time=int(cache_time),
            )
        return await self.app.bot_req("answerCallbackQuery", callback_query_id=str(self.id), text=text, show_alert=alert, url=url, cache_time=cache_time)

    async def edit(self, text: str, kbd: Any | None = None, **kw: Any) -> Any:
        if self.src == "mt" or (self.app is not None and self.app.bot is None):
            if self.app is None or self.app.mt is None:
                raise RuntimeError("mt net is not configured")
            data = dict(kw)
            if kbd is not None:
                data["reply_markup"] = kbd
            inline_mid = self.inline_message_id
            if inline_mid is not None:
                id_field = inline_mid if isinstance(inline_mid, dict) else {"_": "inputBotInlineMessageID", "raw": inline_mid} if isinstance(inline_mid, (str, bytes)) else None
                if id_field is None:
                    return None
                return await self.app.mt_req("messages.editInlineBotMessage", id=id_field, message=text, **data)
            if self.chat_id is None or self.msg_id is None:
                return None
            return await self.app.mt_req("messages.editMessage", peer=self.chat_id, id=int(self.msg_id), message=text, **data)
        if self.app is None or self.app.bot is None:
            raise RuntimeError("bot net is not configured")
        data = dict(kw)
        if kbd is not None:
            data["reply_markup"] = kbd.to_dict() if hasattr(kbd, "to_dict") else kbd
        if self.chat_id is None or self.msg_id is None:
            if self.inline_message_id is None:
                return None
            return await self.app.bot_req("editMessageText", inline_message_id=self.inline_message_id, text=text, **data)
        return await self.app.bot_req("editMessageText", chat_id=self.chat_id, message_id=int(self.msg_id), text=text, **data)

    async def reply(self, txt: str, kbd: Any | None = None, topic_id: int | None = None, link_options: Any | None = None, **kw: Any) -> Any:
        from goygram import ext as rx
        if self.chat_id is None:
            return None
        if self.src == "bot" and self.app.bot is not None:
            data = dict(kw)
            if self.id is not None:
                data["reply_parameters"] = {"message_id": self.id}
            if kbd is not None:
                self._kbd(data, kbd)
            if topic_id is not None:
                data["message_thread_id"] = topic_id
            if link_options is not None:
                data["link_preview_options"] = link_options.to_dict() if hasattr(link_options, "to_dict") else link_options
            return await self.app.bot_req("sendMessage", chat_id=self.chat_id, text=txt, **data)
        if self.app.mt is not None:
            data = dict(kw)
            peer = await self.app.mt.resolve_peer(self.chat_id)
            if self.id is not None:
                data["reply_to"] = bytes(rx.serialize_constructor('inputReplyToMessage',
                    json.dumps({'reply_to_msg_id': int(self.id)})))
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

    def _kbd(self, data: dict[str, Any], kbd: Any) -> None:
        data["reply_markup"] = kbd.to_dict() if hasattr(kbd, "to_dict") else kbd

    async def forward_to(self, chat_id: int | str, *, via: str | None = None, **kw: Any) -> Any:
        if self.chat_id is None or self.id is None:
            return None
        if self.src == "bot":
            return await self.app.bot_req("forwardMessage", chat_id=chat_id, from_chat_id=self.chat_id, message_id=int(self.id), **kw)
        from_peer = await self.app.mt.resolve_peer(self.chat_id)
        to_peer = await self.app.mt.resolve_peer(self.app.raw_chat(chat_id))
        return await self.app.mt_req("messages.forwardMessages", from_peer=from_peer, to_peer=to_peer, id=[int(self.id)], random_id=[secrets.randbits(63)], **kw)

    async def pin(self, *, disable_notification: bool = False, **kw: Any) -> Any:
        if self.chat_id is None or self.id is None:
            return None
        if self.src == "bot":
            return await self.app.bot_req("pinChatMessage", chat_id=self.chat_id, message_id=int(self.id), disable_notification=disable_notification, **kw)
        peer = await self.app.mt.resolve_peer(self.chat_id)
        return await self.app.mt_req("messages.updatePinnedMessage", peer=peer, id=int(self.id), silent=disable_notification, **kw)

    async def unpin(self, **kw: Any) -> Any:
        if self.chat_id is None or self.id is None:
            return None
        if self.src == "bot":
            return await self.app.bot_req("unpinChatMessage", chat_id=self.chat_id, message_id=int(self.id), **kw)
        peer = await self.app.mt.resolve_peer(self.chat_id)
        return await self.app.mt_req("messages.updatePinnedMessage", peer=peer, id=int(self.id), unpin=True, **kw)

    async def react(self, reaction: Any, **kw: Any) -> Any:
        if self.chat_id is None or self.id is None:
            return None
        if self.src == "bot":
            return await self.app.bot_req("setMessageReaction", chat_id=self.chat_id, message_id=int(self.id), reaction=reaction, **kw)
        peer = await self.app.mt.resolve_peer(self.chat_id)
        return await self.app.mt_req("messages.sendReaction", peer=peer, msg_id=int(self.id), reaction=reaction, **kw)

    async def download(self, destination: str | None = None) -> Any:
        if self.src != "bot":
            raise RuntimeError("MTProto media download requires an upload.getFile location")
        media = self.get("document") or self.get("video") or self.get("audio") or self.get("voice") or self.get("animation") or self.get("video_note") or self.get("photo")
        if isinstance(media, list):
            media = media[-1] if media else None
        file_id = media.get("file_id") if isinstance(media, dict) else None
        if not file_id:
            raise ValueError("message has no downloadable Bot API file_id")
        return await self.app.download_file(file_id, destination)

    def net(self) -> Any:
        if self.src == "bot":
            if self.app.bot is None:
                raise RuntimeError("bot net is not configured")
            return self.app.bot
        if self.app.mt is None:
            raise RuntimeError("mt net is not configured")
        return self.app.mt

    async def delete(self) -> Any:
        if self.chat_id is None or self.id is None:
            return None
        if self.src == "bot" and self.app.bot is not None:
            return await self.app.bot_req("deleteMessage", chat_id=self.chat_id, message_id=self.id)
        if self.app.mt is not None:
            return await self.app.mt_req("messages.deleteMessages", id=[int(self.id)], revoke=True)
        return None

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
        result: dict[str, Any] = {
            "type": "article",
            "id": result_id,
            "title": title,
            "input_message_content": message,
        }
        if kbd is not None:
            markup = kbd.to_dict() if hasattr(kbd, "to_dict") else kbd
            if isinstance(markup, list):
                markup = {"inline_keyboard": markup}
            result["reply_markup"] = markup
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
