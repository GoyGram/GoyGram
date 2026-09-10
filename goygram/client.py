# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

import asyncio
import hashlib
import secrets
import signal
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Literal

from goygram.api.methods import BotAPI
from goygram.core.bus import Bus
from goygram.core.disp import Disp
from goygram.core.fsm import FSMEngine
from goygram.types.obj import Obj
from goygram.logging import get_logger
from goygram.security import bootstrap_session
from goygram.filters import Filter
from goygram.dc_fetcher import get_dynamic_dc_config, pick_dc_endpoint
from goygram.utils import print_methods

Fn = Callable[["Obj"], Awaitable[Any]]
CbFn = Fn
PollFn = Fn
MemFn = Fn
InlineFn = Fn

_SEND_METHODS = {
    "photo": "sendPhoto",
    "document": "sendDocument",
    "audio": "sendAudio",
    "video": "sendVideo",
    "voice": "sendVoice",
    "sticker": "sendSticker",
    "animation": "sendAnimation",
    "video_note": "sendVideoNote",
}

_MIME_GUESS = {
    "photo": "image/jpeg",
    "audio": "audio/mpeg",
    "video": "video/mp4",
    "voice": "audio/ogg",
    "sticker": "image/webp",
    "animation": "video/mp4",
    "document": "application/octet-stream",
}

_MIME_EXT = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif",
    ".mp4": "video/mp4", ".mkv": "video/x-matroska", ".webm": "video/webm", ".mov": "video/quicktime",
    ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".opus": "audio/opus", ".wav": "audio/wav", ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".pdf": "application/pdf", ".zip": "application/zip", ".tar": "application/x-tar", ".gz": "application/gzip",
    ".txt": "text/plain", ".md": "text/markdown", ".json": "application/json", ".xml": "application/xml",
    ".py": "text/x-python", ".js": "text/javascript", ".html": "text/html", ".css": "text/css",
    ".apk": "application/vnd.android.package-archive", ".so": "application/x-sharedlib",
}


def _guess_mime(source: Any, kind: str) -> str:
    name = ""
    if isinstance(source, (str, Path)):
        name = str(source)
    elif isinstance(source, dict):
        name = str(source.get("name", ""))
    elif hasattr(source, "name"):
        name = str(source.name)
    dot = name.rfind(".")
    if dot > 0:
        ext = name[dot:].lower()
        if ext in _MIME_EXT:
            return _MIME_EXT[ext]
    return _MIME_GUESS.get(kind, "application/octet-stream")


def _find_ctor(payload: Any, ctor: str) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        if payload.get("_") == ctor:
            return payload
        for v in payload.values():
            found = _find_ctor(v, ctor)
            if found is not None:
                return found
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            found = _find_ctor(item, ctor)
            if found is not None:
                return found
    return None


async def _call(fn: Callable[..., Any], *args: Any, **kw: Any) -> Any:
    out = fn(*args, **kw)
    if asyncio.iscoroutinefunction(fn) or asyncio.iscoroutine(out):
        return await out
    return out


class _UsingCtx:
    __slots__ = ("app", "which", "prev")

    def __init__(self, app: "AppCore", which: str) -> None:
        self.app = app
        self.which = which
        self.prev = app.default_transport

    async def __aenter__(self) -> "AppCore":
        self.prev = self.app.default_transport
        self.app.use(self.which)
        return self.app

    async def __aexit__(self, *exc: Any) -> None:
        self.app.default_transport = self.prev


class _HandlerGroup:
    __slots__ = ("app", "name", "_members")

    def __init__(self, app: "AppCore", name: str) -> None:
        self.app = app
        self.name = name
        self._members: dict[str, list[Fn]] = {
            "hook": [], "edit_hook": [], "cb_hook": [], "inline_hook": [],
            "poll_hook": [], "member_hook": [], "update_hook": [],
        }

    _names = {
        "on_msg": "hook", "on_edit": "edit_hook", "on_cb": "cb_hook",
        "on_inline": "inline_hook", "on_poll": "poll_hook", "on_member": "member_hook",
        "on_update": "update_hook",
    }

    def __getattr__(self, item: str) -> Any:
        if item.startswith("_"):
            raise AttributeError(item)
        key = self._names.get(item)
        if key is None:
            raise AttributeError(item)
        target = self._members[key]

        def _wrap(fn: Fn) -> Fn:
            if isinstance(fn, Filter):
                raise TypeError("pass filters via filt= keyword")
            target.append(fn)
            host = getattr(self.app, key)
            host.append(fn)
            return fn

        return _wrap

    def disable(self) -> None:
        for hooks in self._members.values():
            for fn in hooks:
                for host in self._hosts():
                    try:
                        host.remove(fn)
                    except ValueError:
                        pass

    def enable(self) -> None:
        for key, hooks in self._members.items():
            host = getattr(self.app, key)
            for fn in hooks:
                if fn not in host:
                    host.append(fn)

    def clear(self) -> None:
        self.disable()
        for hooks in self._members.values():
            hooks.clear()

    def _hosts(self) -> list[list[Fn]]:
        return [getattr(self.app, key) for key in self._members]


class _HistoryIter:
    __slots__ = ("app", "chat_id", "limit", "batch", "via", "_offset_id", "_left", "_buf", "_started")

    def __init__(self, app: "AppCore", chat_id: int | str, limit: int, batch: int, via: str | None) -> None:
        self.app = app
        self.chat_id = chat_id
        self.limit = int(limit) if limit and int(limit) > 0 else 0
        self.batch = max(1, min(int(batch), 100))
        self.via = via
        self._offset_id = 0
        self._left = self.limit
        self._buf: list[Any] = []
        self._started = False

    def __aiter__(self) -> "_HistoryIter":
        return self

    async def _fetch(self) -> list[Any]:
        app = self.app
        tr = app.via(self.chat_id, self.via)
        if tr != "mt":
            raise RuntimeError("iter_history requires the mtproto transport")
        peer = await app.mt.resolve_peer(app.raw_chat(self.chat_id))
        raw = await app.mt_req(
            "messages.getHistory",
            peer=peer,
            offset_id=self._offset_id,
            offset_date=0,
            add_offset=0,
            limit=min(self.batch, self._left) if self._left else self.batch,
            max_id=0,
            min_id=0,
            hash=0,
        )
        res = raw.get("result", raw) if isinstance(raw, dict) else {}
        msgs = res.get("messages") if isinstance(res, dict) else None
        return list(msgs) if isinstance(msgs, list) else []

    async def __anext__(self) -> Any:
        if self._buf:
            item = self._buf.pop(0)
            if self._left:
                self._left -= 1
            return item
        if self._left == 0 and self.limit:
            raise StopAsyncIteration
        msgs = await self._fetch()
        if not msgs:
            raise StopAsyncIteration
        self._started = True
        for m in msgs:
            mid = m.get("id") if isinstance(m, dict) else None
            if mid is not None:
                self._offset_id = int(mid)
        self._buf = list(msgs)
        item = self._buf.pop(0)
        if self._left:
            self._left -= 1
        return item


class _DialogIter:
    __slots__ = ("app", "limit", "batch", "folder", "_offset_date", "_offset_id", "_left", "_buf", "_started")

    def __init__(self, app: "AppCore", limit: int, batch: int, folder: int) -> None:
        self.app = app
        self.limit = int(limit) if limit and int(limit) > 0 else 0
        self.batch = max(1, min(int(batch), 100))
        self.folder = folder
        self._offset_date = 0
        self._offset_id = 0
        self._left = self.limit
        self._buf: list[Any] = []
        self._started = False

    def __aiter__(self) -> "_DialogIter":
        return self

    async def _fetch(self) -> list[Any]:
        app = self.app
        if app.mt is None:
            raise RuntimeError("iter_dialogs requires the mtproto transport")
        raw = await app.mt_req(
            "messages.getDialogs",
            offset_date=self._offset_date,
            offset_id=self._offset_id,
            offset_peer={"_": "inputPeerEmpty"},
            limit=min(self.batch, self._left) if self._left else self.batch,
            hash=0,
        )
        res = raw.get("result", raw) if isinstance(raw, dict) else {}
        dialogs = res.get("dialogs") if isinstance(res, dict) else None
        if dialogs is None and isinstance(res, dict):
            dialogs = [x for x in res.get("chats", []) + res.get("users", []) if isinstance(x, dict)]
        return list(dialogs) if isinstance(dialogs, list) else []

    async def __anext__(self) -> Any:
        if self._buf:
            item = self._buf.pop(0)
            if self._left:
                self._left -= 1
            return item
        if self._left == 0 and self.limit:
            raise StopAsyncIteration
        dialogs = await self._fetch()
        if not dialogs:
            raise StopAsyncIteration
        self._started = True
        for d in dialogs:
            if isinstance(d, dict):
                top = d.get("top_message")
                if top is not None:
                    self._offset_id = int(top)
        self._buf = list(dialogs)
        item = self._buf.pop(0)
        if self._left:
            self._left -= 1
        return item


@dataclass(frozen=True, slots=True)
class BotCfg:
    token: str
    timeout: int = 25
    base: str = "https://api.telegram.org"
    webhook_url: str | None = None
    webhook_host: str = "127.0.0.1"
    webhook_port: int = 8080
    webhook_path: str = "/telegram/webhook"
    webhook_secret_token: str | None = None
    webhook_max_body: int = 1024 * 1024
    webhook_drop_pending_updates: bool = False
    offset_path: str | None = None


@dataclass(frozen=True, slots=True)
class MtCfg:
    host: str
    port: int
    key: bytes | None = None
    iv: bytes | None = None


@dataclass(frozen=True, slots=True)
class AppCfg:
    bot: BotCfg | None = None
    mt: MtCfg | None = None
    bus_max: int = 0


class AppCore:
    def __init__(
        self,
        cfg: AppCfg,
        api_id: int | str | None = None,
        api_hash: str | None = None,
        session_name: str = "default",
        *,
        session: Any | None = None,
        default_transport: str = "auto",
        proxy: str | None = None,
        app_name: str | None = None,
        app_version: str | None = None,
        device_model: str | None = None,
        system_version: str | None = None,
        system_lang_code: str = "en",
        lang_pack: str = "",
        lang_code: str = "en",
        fsm_backend: Any | None = None,
        fsm_on_change: Callable[[list[dict[str, Any]]], Any] | None = None,
        intake: str = "auto",
    ) -> None:
        self.cfg = cfg
        self.bus = Bus(cfg.bus_max)
        self.bot = None
        self.mt = None
        self.api = None
        self.self_id: int | None = None
        self._me_cache: dict[str, Any] | None = None
        self._chats: dict[Any, Any] = {}
        self._users: dict[Any, Any] = {}
        self._error_handlers: list[Callable[[Obj, Exception], Awaitable[None] | None]] = []
        if cfg.bot:
            from goygram.transports.botapi import BotNet

            self.bot = BotNet(
                cfg.bot.token,
                self.bus,
                cfg.bot.timeout,
                cfg.bot.base,
                webhook_url=cfg.bot.webhook_url,
                webhook_host=cfg.bot.webhook_host,
                webhook_port=cfg.bot.webhook_port,
                webhook_path=cfg.bot.webhook_path,
                webhook_secret_token=cfg.bot.webhook_secret_token,
                webhook_max_body=cfg.bot.webhook_max_body,
                webhook_drop_pending_updates=cfg.bot.webhook_drop_pending_updates,
                offset_path=cfg.bot.offset_path,
            )
            self.api = BotAPI(self.bot)
        if cfg.mt:
            from goygram.transports.mtproto import MTNet

            self.mt = MTNet(
                cfg.mt.host,
                cfg.mt.port,
                self.bus,
                cfg.mt.key,
                cfg.mt.iv,
                proxy=proxy,
                app_name=app_name,
                app_version=app_version,
                device_model=device_model,
                system_version=system_version,
                system_lang_code=system_lang_code,
                lang_pack=lang_pack,
                lang_code=lang_code,
                cursor_path=Path.home() / ".goygram" / "cursors" / f"{hashlib.sha256(session_name.encode()).hexdigest()[:24]}.json",
            )
            if api_id is not None:
                self.mt._api_id = int(api_id)
            self._init_tl_schema()
            self._load_vault_from_disk(session_name, api_id, api_hash)
        self.fsm = FSMEngine(backend=fsm_backend, on_change=fsm_on_change)
        self.disp = Disp(self, self.bus)
        self._conv: dict[tuple, asyncio.Future] = {}
        self.hook: list[Fn] = []
        self.edit_hook: list[Fn] = []
        self.update_hook: list[Fn] = []
        self.cb_hook: list[CbFn] = []
        self.inline_hook: list[InlineFn] = []
        self.poll_hook: list[PollFn] = []
        self.member_hook: list[MemFn] = []
        self.stop_ev = asyncio.Event()
        self.log = get_logger("goygram.app")
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.bot_token = cfg.bot.token if cfg.bot else None
        self.default_transport = default_transport
        from goygram.session import STRING_PREFIX, Session
        if session is None:
            self.session = Session(name=session_name)
        elif isinstance(session, Session):
            self.session = session
        elif isinstance(session, str) and session.startswith(STRING_PREFIX):
            self.session = Session.from_string(session, name=session_name)
        elif isinstance(session, str):
            self.session = Session(name=session)
        else:
            raise TypeError("session must be a Session instance or an encrypted session string")
        self.intake = str(intake)

    def _init_tl_schema(self) -> None:
        from goygram.schema_manager import init_schema, CURRENT_LAYER_FLOOR
        from goygram import ext as _ext
        if _ext is None:
            return
        self.mt.layer = init_schema(
            _ext,
            None,
            lambda layer: self.mt.update_layer(layer),
            self._can_reload_schema,
        ) or CURRENT_LAYER_FLOOR

    def _can_reload_schema(self) -> bool:
        return self.mt is not None and self.mt.auth_ready.is_set() and not self.mt.pending

    def _load_vault_from_disk(self, session_name: str, api_id: Any, api_hash: Any) -> None:
        import logging
        from pathlib import Path
        from goygram.security import _read_vault, _extract_auth_blob
        from goygram.dc_fetcher import get_dynamic_dc_config, pick_dc_endpoint
        log = logging.getLogger("goygram.dc")
        vault = Path(f"{session_name}.vault")
        if not vault.exists() or vault.stat().st_size == 0:
            return
        vault_key = Path(session_name).name
        try:
            data = _read_vault(vault, vault_key)
            auth_key = data.get("auth_key")
            if auth_key and self.mt is not None:
                self.mt.auth_key = _extract_auth_blob({"auth_key": auth_key})
            server_salt = data.get("server_salt")
            if server_salt and self.mt is not None:
                try:
                    self.mt.server_salt = _extract_auth_blob({"auth_key": server_salt}) or self.mt.server_salt
                except Exception:
                    pass
            dc = data.get("dc")
            if dc is not None and self.mt is not None:
                dc_map = get_dynamic_dc_config()
                endpoint = pick_dc_endpoint(dc_map, preferred_dc=int(dc))
                self.mt.host = endpoint.host
                self.mt.port = endpoint.port
            user_data = data.get("user", {})
            uid = user_data.get("id", 0) if isinstance(user_data, dict) else 0
            if uid and uid != 0 and self.mt is not None:
                self.self_id = uid
                self.mt.self_id = uid
        except Exception:
            pass

    def _reg(self, host: list[Fn], fn: Fn | None, filt: Filter | None, once: bool = False):
        if isinstance(fn, Filter):
            filt = fn
            fn = None
        if once:
            host_ref = host
            def wrap(inner: Fn) -> Fn:
                async def guarded(msg: "Obj") -> Any:
                    try:
                        if filt is None or filt(msg):
                            return await inner(msg)
                        return None
                    finally:
                        try:
                            host_ref.remove(guarded)
                        except ValueError:
                            pass
                host_ref.append(guarded)
                return inner
            if fn is not None:
                return wrap(fn)
            return wrap
        def wrap(inner: Fn) -> Fn:
            if filt is None:
                host.append(inner)
                return inner
            async def guarded(msg: "Obj") -> Any:
                if filt(msg):
                    return await inner(msg)
                return None
            host.append(guarded)
            return inner
        if fn is not None:
            return wrap(fn)
        return wrap

    def on_msg(self, fn: Fn | None = None, filt: Filter | None = None, once: bool = False):
        return self._reg(self.hook, fn, filt, once)

    def on_edit(self, fn: Fn | None = None, filt: Filter | None = None, once: bool = False):
        return self._reg(self.edit_hook, fn, filt, once)

    def on_cb(self, fn: CbFn | None = None, *, filt: Filter | None = None, once: bool = False):
        return self._reg(self.cb_hook, fn, filt, once)

    def on_inline(self, fn: InlineFn | None = None, *, filt: Filter | None = None, once: bool = False):
        return self._reg(self.inline_hook, fn, filt, once)

    def on_poll(self, fn: PollFn | None = None, *, filt: Filter | None = None, once: bool = False):
        return self._reg(self.poll_hook, fn, filt, once)

    def on_member(self, fn: MemFn | None = None, *, filt: Filter | None = None, once: bool = False):
        return self._reg(self.member_hook, fn, filt, once)

    def on_update(self, fn: Callable[[object], Awaitable[Any]] | None = None, *, filt: Filter | None = None, once: bool = False):
        return self._reg(self.update_hook, fn, filt, once)

    def on_cmd(self, *name: str) -> Callable[[Fn], Fn]:
        from goygram.filters import command as _cmd_filt
        return self.on_msg(filt=_cmd_filt(*name))

    @property
    def transport(self) -> str:
        if self.bot is None and self.mt is None:
            return "none"
        if self.bot is None:
            return "mtproto"
        if self.mt is None:
            return "api"
        return self.default_transport if self.default_transport != "auto" else "mtproto"

    def use(self, which: str) -> None:
        norm = {"api": "api", "bot": "api", "botapi": "api", "mt": "mtproto", "mtproto": "mtproto"}
        target = norm.get(str(which).lower())
        if target is None:
            raise ValueError(f"unknown transport {which!r}; use 'api' or 'mtproto'")
        if target == "api" and self.bot is None:
            raise RuntimeError("bot net is not configured")
        if target == "mtproto" and self.mt is None:
            raise RuntimeError("mt net is not configured")
        self.default_transport = target

    def use_api(self) -> "AppCore":
        self.use("api")
        return self

    def use_mt(self) -> "AppCore":
        self.use("mtproto")
        return self

    def switch(self, which: str) -> None:
        self.use(which)

    def using(self, which: str) -> "_UsingCtx":
        return _UsingCtx(self, which)

    @property
    def me(self) -> int | None:
        return self.self_id

    async def get_me(self, refresh: bool = False) -> dict[str, Any] | None:
        if self._me_cache is not None and not refresh:
            return self._me_cache
        if self.bot is not None:
            try:
                info = await self.bot_req("getMe")
                if isinstance(info, dict):
                    self._me_cache = info
                    if info.get("id") is not None and self.self_id is None:
                        self.self_id = int(info["id"])
                        if self.mt is not None:
                            self.mt.self_id = self.self_id
                    return info
            except Exception as e:
                self.log.debug("getMe self-resolve failed: %r", e)
        if self.mt is not None:
            try:
                raw = await self.mt_req("users.getUsers", id=[{"_": "inputUserSelf"}])
                user = _find_ctor(raw, "user")
                if isinstance(user, dict) and user.get("id") is not None:
                    self._me_cache = user
                    self.self_id = int(user["id"])
                    self.mt.self_id = self.self_id
                    return user
            except Exception as e:
                self.log.debug("users.getUsers self-resolve failed: %r", e)
        return None

    async def get_self(self, *, full: bool = False, refresh: bool = False) -> dict[str, Any] | None:
        me = None if refresh else self._me_cache
        if me is None:
            me = await self.get_me()
        if me is None:
            return None
        if not full:
            return me
        if self.mt is None:
            return me
        raw = await self.mt_req("users.getFullUser", id={"_": "inputUserSelf"})
        full_user = _find_ctor(raw, "userFull")
        if isinstance(full_user, dict):
            out = dict(me)
            out["full"] = full_user
            return out
        return me

    def iter_history(self, chat_id: int | str, limit: int = 0, batch: int = 100, via: str | None = None):
        return _HistoryIter(self, chat_id, limit, batch, via)

    async def count_history(self, chat_id: int | str, via: str | None = None) -> int | None:
        tr = self.via(chat_id, via)
        if tr != "mt":
            return None
        peer = await self.mt.resolve_peer(self.raw_chat(chat_id))
        raw = await self.mt_req("messages.getHistory", peer=peer, offset_id=0, offset_date=0, add_offset=0, limit=1, max_id=0, min_id=0, hash=0)
        res = raw.get("result", raw) if isinstance(raw, dict) else {}
        return res.get("count") if isinstance(res, dict) else None

    def on_error(self, fn: Callable[[Obj, Exception], Awaitable[None] | None]):
        self._error_handlers.append(fn)
        return fn

    def group(self, name: str) -> "_HandlerGroup":
        return _HandlerGroup(self, name)

    def every(self, seconds: float, fn: Callable[..., Any], *args: Any, **kw: Any) -> "asyncio.Task":
        async def _loop() -> None:
            try:
                while not self.stop_ev.is_set():
                    await asyncio.sleep(seconds)
                    if self.stop_ev.is_set():
                        return
                    try:
                        await _call(fn, *args, **kw)
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        self.log.error("every(%s) tick failed: %r", seconds, e)
            except asyncio.CancelledError:
                pass
        return asyncio.create_task(_loop(), name=f"goygram-every-{seconds}")

    def later(self, seconds: float, fn: Callable[..., Any], *args: Any, **kw: Any) -> "asyncio.Task":
        async def _once() -> None:
            try:
                await asyncio.sleep(seconds)
                await _call(fn, *args, **kw)
            except asyncio.CancelledError:
                pass
        return asyncio.create_task(_once(), name="goygram-later")

    async def conv_wait(self, chat_id: int | str, user_id: int | str | None = None, filt: Filter | None = None, timeout: float = 60.0) -> "Obj | None":
        key = (chat_id, user_id)
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        if key in self._conv:
            old = self._conv.pop(key)
            if not old.done():
                old.set_exception(RuntimeError("conversation superseded"))
        self._conv[key] = fut
        try:
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            self._conv.pop(key, None)
            return None

    async def ask(self, chat_id: int | str, text: str, *, user_id: int | str | None = None, timeout: float = 60.0, kbd: Any = None) -> "Obj | None":
        if text:
            await self.send_msg(chat_id, text, kbd=kbd)
        return await self.conv_wait(chat_id, user_id, timeout=timeout)

    async def _conv_dispatch(self, msg: "Obj") -> None:
        if not self._conv:
            return
        key = (msg.chat_id, None)
        target = self._conv.pop(key, None)
        if target is None and msg.from_id is not None:
            target = self._conv.pop((msg.chat_id, msg.from_id), None)
        if target is None and msg.from_id is None:
            for k in list(self._conv):
                if k[0] == msg.chat_id:
                    target = self._conv.pop(k)
                    break
        if target is not None and not target.done():
            target.set_result(msg)
            return
        key2 = (msg.chat_id, msg.from_id)
        target = self._conv.pop(key2, None)
        if target is not None and not target.done():
            target.set_result(msg)

    def _bot_method_name(self, name: str) -> str:
        if "_" in name:
            parts = name.split("_")
            return parts[0] + "".join(x[:1].upper() + x[1:] for x in parts[1:])
        return name

    def _mt_method_name(self, name: str) -> str:
        name = name[3:] if name.startswith("mt_") else name
        if "." in name:
            return name
        parts = name.split("_")
        if len(parts) < 2:
            return name
        ns = parts[0]
        rest = parts[1:]
        return ns + "." + rest[0] + "".join(p[:1].upper() + p[1:] for p in rest[1:])

    def _dynamic_method(self, name: str):
        async def call(**kw: Any) -> Any:
            if name.startswith("mt_"):
                return await self.mt_req(self._mt_method_name(name), **kw)
            return await self.bot_req(self._bot_method_name(name), **kw)
        return call

    def help(self) -> None:
        print_methods(self)

    def __getattr__(self, name: str) -> Any:
        if self.api is not None and hasattr(self.api, name):
            return getattr(self.api, name)
        if name.startswith("mt_") and self.mt is not None:
            return self._dynamic_method(name)
        if not name.startswith("mt_") and not name.startswith("_") and self.bot is not None:
            return self._dynamic_method(name)
        raise AttributeError(name)

    def __dir__(self) -> list[str]:
        base = set(super().__dir__())
        base.add("help")
        return sorted(base)

    def stop(self) -> None:
        self.stop_ev.set()

    def raw_chat(self, chat_id: int | str) -> int | str:
        if isinstance(chat_id, str) and ":" in chat_id:
            pfx, raw = chat_id.split(":", 1)
            if pfx in {"bot", "mt"}:
                if raw.lstrip("-").isdigit():
                    return int(raw)
                return raw
        return chat_id

    def via(self, chat_id: int | str, via: str | None = None) -> str:
        _alias = {"api": "bot", "bot": "bot", "mtproto": "mt", "mt": "mt"}
        if via is not None:
            resolved = _alias.get(via)
            if resolved is None:
                raise ValueError(f"unknown transport {via!r}; use 'api' or 'mtproto'")
            if resolved == "bot" and self.bot is None:
                raise RuntimeError("bot net is not configured")
            if resolved == "mt" and self.mt is None:
                raise RuntimeError("mt net is not configured")
            return resolved
        if isinstance(chat_id, str) and chat_id.startswith("bot:"):
            if self.bot is None:
                raise RuntimeError("bot net is not configured")
            return "bot"
        if isinstance(chat_id, str) and chat_id.startswith("mt:"):
            if self.mt is None:
                raise RuntimeError("mt net is not configured")
            return "mt"
        if self.default_transport == "api" and self.bot is not None:
            return "bot"
        if self.default_transport == "mtproto" and self.mt is not None:
            return "mt"
        if self.bot is not None:
            return "bot"
        if self.mt is not None:
            return "mt"
        raise RuntimeError("no transport configured")

    def ikb(self) -> Any:
        from goygram.types.kbd import KbdBuilder
        return KbdBuilder(kind="inline")

    def rkb(self, **opts: Any) -> Any:
        from goygram.types.kbd import KbdBuilder
        return KbdBuilder(kind="reply", **opts)

    def frk(self, **opts: Any) -> Any:
        from goygram.types.kbd import KbdBuilder
        return KbdBuilder(kind="force", **opts)

    def rgk(self, **opts: Any) -> Any:
        from goygram.types.kbd import KbdBuilder
        return KbdBuilder(kind="remove", **opts)

    def html(self, text: str) -> dict[str, Any]:
        return {"text": text, "parse_mode": "HTML"}

    def md(self, text: str) -> dict[str, Any]:
        return {"text": text, "parse_mode": "MarkdownV2"}

    async def bot_req(self, meth: str, **kw: Any) -> Any:
        if self.bot is None:
            raise RuntimeError("bot net is not configured")
        data = {k: v for k, v in kw.items() if v is not None}
        if hasattr(self.bot, "call"):
            return await self.bot.call(meth, **data)
        return await self.bot.req(meth, data)

    async def download_file(self, file_id: str, destination: str | None = None) -> Any:
        if self.bot is not None and isinstance(file_id, str) and not str(file_id).startswith("{"):
            return await self.bot.download_file(file_id, destination)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        return await self.mt.download_file(file_id, destination)

    def _media_location(self, media: Any) -> dict[str, Any] | None:
        if not isinstance(media, dict):
            return None
        doc = media.get("document") if isinstance(media.get("document"), dict) else None
        photo = media.get("photo") if isinstance(media.get("photo"), dict) else None
        if doc is None and media.get("_") == "document":
            doc = media
        if photo is None and media.get("_") == "photo":
            photo = media
        if isinstance(doc, dict) and isinstance(doc.get("id"), int) and isinstance(doc.get("access_hash"), int):
            ref = doc.get("file_reference", b"")
            if isinstance(ref, str):
                try:
                    ref = bytes.fromhex(ref)
                except ValueError:
                    ref = ref.encode("utf-8")
            return {"_": "inputDocumentFileLocation", "id": doc["id"], "access_hash": doc["access_hash"], "file_reference": bytes(ref), "thumb_size": ""}
        if isinstance(photo, dict) and isinstance(photo.get("id"), int) and isinstance(photo.get("access_hash"), int):
            ref = photo.get("file_reference", b"")
            if isinstance(ref, str):
                try:
                    ref = bytes.fromhex(ref)
                except ValueError:
                    ref = ref.encode("utf-8")
            return {"_": "inputPhotoFileLocation", "id": photo["id"], "access_hash": photo["access_hash"], "file_reference": bytes(ref), "thumb_size": photo.get("largest_size", "")}
        return None

    async def download_media(self, source: Any, destination: str, *, via: str | None = None) -> Any:
        media = None
        src_kind = None
        if isinstance(source, dict):
            src_kind = source.get("src")
            media = source.get("media") if isinstance(source.get("media"), dict) else source
        else:
            src_kind = getattr(source, "src", None)
            media = getattr(source, "media", None)
            if media is None and isinstance(getattr(source, "raw", None), dict):
                media = source.raw.get("media")
        if via is not None:
            src_kind = "bot" if self.via(0, via) == "bot" else "mtproto"
        if src_kind == "bot" and self.bot is not None and isinstance(media, dict):
            doc = media.get("document") if isinstance(media.get("document"), dict) else media
            file_id = doc.get("file_id") if isinstance(doc, dict) else None
            if file_id:
                return await self.bot.download_file(file_id, destination)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        location = self._media_location(media) or self._media_location(source if isinstance(source, dict) else getattr(source, "raw", None))
        if location is None:
            raise ValueError("no downloadable media found in source")
        return await self.mt.download_file(location, destination)

    async def upload_file(self, source: Any, **kw: Any) -> Any:
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        return await self.mt.upload_file(source, **kw)

    async def send_msg(self, chat_id: int | str, text: str, *, via: str | None = None, reply_to: int | None = None, kbd: Any | None = None, **kw: Any) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            return await self.bot.send_msg(target, text, reply_to=reply_to, kbd=kbd, **kw)
        peer = await self.mt.resolve_peer(target)
        data = dict(kw)
        if reply_to is not None:
            data["reply_to"] = reply_to
        if kbd is not None:
            from goygram.types.kbd import kbd_to_tl
            tl_kbd = kbd_to_tl(kbd)
            if tl_kbd is not None:
                data["reply_markup"] = tl_kbd
        if str(data.pop("parse_mode", "")).lower() == "html":
            from goygram.sugar import html_to_entities
            plain, ents = html_to_entities(text)
            data["entities"] = ents
            text = plain
        data["_dispatch_chat_id"] = target
        data["_dispatch_message_text"] = text
        return await self.mt_req("messages.sendMessage", peer=peer, message=text, random_id=secrets.randbits(63), **data)

    async def mt_req(self, act: str, **kw: Any) -> Any:
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        data = {k: v.to_dict() if hasattr(v, "to_dict") else v for k, v in kw.items() if v is not None}
        if act.startswith("messages.") and isinstance(data.get("reply_markup"), dict) and "inline_keyboard" in data.get("reply_markup", {}):
            from goygram.types.kbd import kbd_to_tl
            tl_kbd = kbd_to_tl(data["reply_markup"])
            if tl_kbd is not None:
                data["reply_markup"] = tl_kbd
        if 'api_id' not in data and self.api_id is not None:
            data['api_id'] = self.api_id
        if 'api_hash' not in data and self.api_hash is not None:
            data['api_hash'] = self.api_hash
        if hasattr(self.mt, "call"):
            return await self.mt.call(act, **data)
        if hasattr(self.mt, "req"):
            return await self.mt.req(act, data)
        return await self.mt.send({"act": act, **data})

    async def send_photo(self, chat_id: int | str, photo: Any, caption: str | None = None, *, via: str | None = None, reply_to: int | None = None, kbd: Any | None = None, **kw: Any) -> Any:
        return await self.send_media(chat_id, photo, "photo", caption, via=via, reply_to=reply_to, kbd=kbd, **kw)

    async def send_doc(self, chat_id: int | str, doc: Any, caption: str | None = None, *, via: str | None = None, reply_to: int | None = None, kbd: Any | None = None, **kw: Any) -> Any:
        return await self.send_media(chat_id, doc, "document", caption, via=via, reply_to=reply_to, kbd=kbd, **kw)

    async def send_audio(self, chat_id: int | str, audio: Any, caption: str | None = None, *, via: str | None = None, reply_to: int | None = None, kbd: Any | None = None, **kw: Any) -> Any:
        return await self.send_media(chat_id, audio, "audio", caption, via=via, reply_to=reply_to, kbd=kbd, **kw)

    async def send_video(self, chat_id: int | str, video: Any, caption: str | None = None, *, via: str | None = None, reply_to: int | None = None, kbd: Any | None = None, **kw: Any) -> Any:
        return await self.send_media(chat_id, video, "video", caption, via=via, reply_to=reply_to, kbd=kbd, **kw)

    async def send_voice(self, chat_id: int | str, voice: Any, caption: str | None = None, *, via: str | None = None, reply_to: int | None = None, kbd: Any | None = None, **kw: Any) -> Any:
        return await self.send_media(chat_id, voice, "voice", caption, via=via, reply_to=reply_to, kbd=kbd, **kw)

    async def send_sticker(self, chat_id: int | str, sticker: Any, *, via: str | None = None, reply_to: int | None = None, kbd: Any | None = None, **kw: Any) -> Any:
        return await self.send_media(chat_id, sticker, "sticker", None, via=via, reply_to=reply_to, kbd=kbd, **kw)

    async def send_animation(self, chat_id: int | str, anim: Any, caption: str | None = None, *, via: str | None = None, reply_to: int | None = None, kbd: Any | None = None, **kw: Any) -> Any:
        return await self.send_media(chat_id, anim, "animation", caption, via=via, reply_to=reply_to, kbd=kbd, **kw)

    async def send_media(self, chat_id: int | str, source: Any, kind: str, caption: str | None = None, *, via: str | None = None, reply_to: int | None = None, kbd: Any | None = None, file_name: str | None = None, **kw: Any) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            data = dict(kw)
            if caption is not None:
                data["caption"] = caption
            if reply_to is not None:
                data["reply_parameters"] = {"message_id": reply_to}
            if kbd is not None:
                data["reply_markup"] = kbd.to_dict() if hasattr(kbd, "to_dict") else kbd
            if isinstance(source, (bytes, bytearray)):
                data[kind] = (file_name or "file.bin", bytes(source))
            elif isinstance(source, str) and (source.startswith("http://") or source.startswith("https://")):
                data[kind] = source
            elif isinstance(source, str) and source.startswith("file://"):
                data[kind] = (file_name or source[7:].split("/")[-1], open(source[7:], "rb").read())
            elif isinstance(source, (str, Path)) and Path(source).exists():
                data[kind] = (file_name or Path(source).name, open(source, "rb").read())
            else:
                data[kind] = source
            return await self.bot_req(_SEND_METHODS.get(kind, "sendDocument"), chat_id=target, **data)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        from goygram.types.kbd import kbd_to_tl
        peer = await self.mt.resolve_peer(target)
        if not isinstance(source, dict) or "_" not in source:
            up = await self.mt.upload_file(source, file_name=file_name)
            from goygram import ext as rx
            import json as _json
            if kind == "photo":
                media = {"_": "inputMediaUploadedPhoto", "file": {"_": "inputFile", "id": up["id"], "parts": up["parts"], "name": up["name"]}}
            elif kind == "sticker":
                media = {"_": "inputMediaUploadedDocument", "file": {"_": "inputFile", "id": up["id"], "parts": up["parts"], "name": up["name"]}, "mime_type": "image/webp", "attributes": [{"_": "documentAttributeSticker", "alt": "", "stickerset": {"_": "inputStickerSetEmpty"}}]}
            else:
                media = {"_": "inputMediaUploadedDocument", "file": {"_": "inputFile", "id": up["id"], "parts": up["parts"], "name": up["name"]}, "mime_type": _guess_mime(source, kind), "attributes": [{"_": "documentAttributeFilename", "file_name": up["name"]}]}
            ser = rx.serialize_constructor(media["_"], _json.dumps({k: v for k, v in media.items() if k != "_"}))
            media_raw = bytes(ser).hex()
        else:
            media_raw = source
        data = dict(kw)
        if caption is not None:
            data["message"] = caption
        elif "message" not in data:
            data["message"] = ""
        if reply_to is not None:
            data["reply_to"] = reply_to
        if kbd is not None:
            tl_kbd = kbd_to_tl(kbd)
            if tl_kbd is not None:
                data["reply_markup"] = tl_kbd
        return await self.mt_req("messages.sendMedia", peer=peer, media=media_raw, random_id=secrets.randbits(63), **data)

    _TYPING_MAP = {
        "typing": "sendMessageTypingAction",
        "upload_photo": "sendMessageUploadPhotoAction",
        "record_video": "sendMessageRecordVideoAction",
        "upload_video": "sendMessageUploadVideoAction",
        "record_voice": "sendMessageRecordAudioAction",
        "upload_voice": "sendMessageUploadAudioAction",
        "upload_document": "sendMessageUploadDocumentAction",
        "choose_sticker": "sendMessageChooseStickerAction",
        "find_location": "sendMessageGeoLocationAction",
        "record_video_note": "sendMessageRecordRoundAction",
        "upload_video_note": "sendMessageUploadRoundAction",
    }

    async def send_action(self, chat_id: int | str, action: str = "typing", progress: int = 0, via: str | None = None) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            return await self.bot_req("sendChatAction", chat_id=target, action=action)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        ctor = action if action.startswith("sendMessage") else self._TYPING_MAP.get(action, "sendMessageTypingAction")
        act: dict[str, Any] = {"_": ctor}
        if ctor in {"sendMessageUploadPhotoAction", "sendMessageUploadVideoAction", "sendMessageUploadAudioAction", "sendMessageUploadDocumentAction", "sendMessageUploadRoundAction"} and progress:
            act["progress"] = int(progress)
        return await self.mt_req("messages.setTyping", peer=peer, action=act)

    async def edit_msg(self, chat_id: int | str, msg_id: int, text: str, *, via: str | None = None, kbd: Any | None = None, **kw: Any) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            data = dict(kw)
            if kbd is not None:
                data["reply_markup"] = kbd.to_dict() if hasattr(kbd, "to_dict") else kbd
            return await self.bot_req("editMessageText", chat_id=target, message_id=msg_id, text=text, **data)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        data = dict(kw)
        if kbd is not None:
            from goygram.types.kbd import kbd_to_tl
            tl_kbd = kbd_to_tl(kbd)
            if tl_kbd is not None:
                data["reply_markup"] = tl_kbd
        if str(data.pop("parse_mode", "")).lower() == "html":
            from goygram.sugar import html_to_entities
            plain, ents = html_to_entities(text)
            data["entities"] = ents
            text = plain
        return await self.mt_req("messages.editMessage", peer=peer, id=msg_id, message=text, **data)

    async def delete_msg(self, chat_id: int | str, msg_ids: int | list[int], *, via: str | None = None, revoke: bool = True) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        ids = [int(msg_ids)] if isinstance(msg_ids, int) else [int(i) for i in msg_ids]
        if transport == "bot":
            for mid in ids:
                await self.bot_req("deleteMessage", chat_id=target, message_id=mid)
            return True
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        return await self.mt_req("messages.deleteMessages", id=ids, revoke=revoke)

    async def get_chat(self, chat_id: int | str, *, via: str | None = None, refresh: bool = False) -> Any:
        target = self.raw_chat(chat_id)
        if not refresh:
            cached = self._chats.get(target)
            if cached is not None:
                return cached
        transport = self.via(chat_id, via)
        if transport == "bot":
            info = await self.bot_req("getChat", chat_id=target)
        else:
            if self.mt is None:
                raise RuntimeError("mt net is not configured")
            peer = await self.mt.resolve_peer(target)
            info = await self.mt_req("messages.getPeerDialogs", peers=[peer])
        self._chats[target] = info
        return info

    async def get_user(self, user_id: int | str, *, via: str | None = None, refresh: bool = False) -> Any:
        target = self.raw_chat(user_id)
        if not refresh:
            cached = self._users.get(target)
            if cached is not None:
                return cached
        transport = self.via(user_id, via)
        if transport == "bot":
            info = await self.bot_req("getChat", chat_id=target)
        else:
            if self.mt is None:
                raise RuntimeError("mt net is not configured")
            info = await self.mt_req("users.getUsers", id=[{"_": "inputUser", "user_id": target}])
            from goygram.client import _find_ctor
            info = _find_ctor(info, "user") or info
        self._users[target] = info
        return info

    async def copy_msg(self, from_chat: int | str, msg_id: int, *, to: int | str, via: str | None = None, **kw: Any) -> Any:
        transport = self.via(to, via)
        src_target = self.raw_chat(from_chat)
        to_target = self.raw_chat(to)
        if transport == "bot":
            return await self.bot_req("copyMessage", chat_id=to_target, from_chat_id=src_target, message_id=msg_id, **kw)
        return await self.forward_msg(from_chat, msg_id, to=to, via=via, **kw)

    async def forward_msg(self, from_chat: int | str, msg_id: int, *, to: int | str, via: str | None = None, **kw: Any) -> Any:
        transport = self.via(to, via)
        src_target = self.raw_chat(from_chat)
        to_target = self.raw_chat(to)
        if transport == "bot":
            return await self.bot_req("forwardMessage", chat_id=to_target, from_chat_id=src_target, message_id=msg_id, **kw)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        from_peer = await self.mt.resolve_peer(src_target)
        to_peer = await self.mt.resolve_peer(to_target)
        return await self.mt_req("messages.forwardMessages", from_peer=from_peer, to_peer=to_peer, id=[int(msg_id)], random_id=[secrets.randbits(63)], **kw)

    async def mark_read(self, chat_id: int | str, max_id: int | None = None, via: str | None = None) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            data: dict[str, Any] = {"chat_id": target}
            if max_id is not None:
                data["message_id"] = max_id
            return await self.bot_req("readMessage", **data)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        data: dict[str, Any] = {"peer": peer}
        if max_id is not None:
            data["max_id"] = int(max_id)
        return await self.mt_req("messages.readHistory", **data)

    async def send_reaction(self, chat_id: int | str, msg_id: int, emoji: str = "👍", *, big: bool = False, via: str | None = None) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            return await self.bot_req("setMessageReaction", chat_id=target, message_id=msg_id, reaction=[{"type": "emoji", "emoji": emoji}], is_big=big)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        return await self.mt_req(
            "messages.sendReaction",
            peer=peer,
            msg_id=int(msg_id),
            reaction=[{"_": "reactionEmoji", "emoticon": emoji}],
            add_to_recent=False,
        )

    async def pin_msg(self, chat_id: int | str, msg_id: int, *, notify: bool = False, via: str | None = None) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            return await self.bot_req("pinChatMessage", chat_id=target, message_id=msg_id, disable_notification=not notify)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        return await self.mt_req("messages.updatePinnedMessage", peer=peer, msg_id=int(msg_id), unpin=False, silent=not notify)

    async def unpin_msg(self, chat_id: int | str, msg_id: int, via: str | None = None) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            return await self.bot_req("unpinChatMessage", chat_id=target, message_id=msg_id)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        return await self.mt_req("messages.updatePinnedMessage", peer=peer, msg_id=int(msg_id), unpin=True)

    async def unpin_all(self, chat_id: int | str, via: str | None = None) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            return await self.bot_req("unpinAllChatMessages", chat_id=target)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        return await self.mt_req("messages.unpinAllMessages", peer=peer)

    async def get_msg(self, chat_id: int | str, msg_id: int, via: str | None = None) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            return await self.bot_req("copyMessage", chat_id=target, from_chat_id=target, message_id=msg_id)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        res = await self.mt_req("messages.getMessages", id=[{"_": "inputMessageID", "id": int(msg_id)}], peer=peer)
        msgs = res.get("messages", []) if isinstance(res, dict) else []
        if not msgs and isinstance(res, dict):
            inner = res.get("result") if isinstance(res.get("result"), dict) else {}
            msgs = inner.get("messages", []) if isinstance(inner, dict) else []
        return msgs[0] if msgs else None

    async def send_media_group(self, chat_id: int | str, media: list[Any], *, via: str | None = None, reply_to: int | None = None, **kw: Any) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            group = []
            for m in media:
                if isinstance(m, tuple):
                    kind, src = m[0], m[1]
                    cap = m[2] if len(m) > 2 else None
                else:
                    kind, src, cap = "photo", m, None
                item: dict[str, Any] = {"type": kind, "media": src}
                if cap:
                    item["caption"] = cap
                group.append(item)
            data = dict(kw)
            data["media"] = group
            if reply_to is not None:
                data["reply_parameters"] = {"message_id": reply_to}
            return await self.bot_req("sendMediaGroup", chat_id=target, **data)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        from goygram import ext as rx
        import json as _json
        singles = []
        for m in media:
            if isinstance(m, tuple):
                kind, src = m[0], m[1]
                cap = m[2] if len(m) > 2 else None
            else:
                kind, src, cap = "photo", m, None
            up = await self.mt.upload_file(src)
            if kind == "photo":
                im = {"_": "inputMediaUploadedPhoto", "file": {"_": "inputFile", "id": up["id"], "parts": up["parts"], "name": up["name"]}}
            else:
                im = {"_": "inputMediaUploadedDocument", "file": {"_": "inputFile", "id": up["id"], "parts": up["parts"], "name": up["name"]}, "mime_type": _guess_mime(src, kind), "attributes": [{"_": "documentAttributeFilename", "file_name": up["name"]}]}
            singles.append({"_": "inputSingleMedia", "media": im, "random_id": secrets.randbits(63), "message": cap or ""})
        data = dict(kw)
        if reply_to is not None:
            data["reply_to"] = {"_": "inputReplyToMessage", "reply_to_msg_id": int(reply_to)}
        return await self.mt_req("messages.sendMultiMedia", peer=peer, multi_media=singles, **data)

    async def send_contact(self, chat_id: int | str, phone: str, first_name: str, *, last_name: str | None = None, via: str | None = None, reply_to: int | None = None, **kw: Any) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            data = dict(kw)
            data["phone_number"] = phone
            data["first_name"] = first_name
            if last_name:
                data["last_name"] = last_name
            if reply_to is not None:
                data["reply_parameters"] = {"message_id": reply_to}
            return await self.bot_req("sendContact", chat_id=target, **data)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        media = {"_": "inputMediaContact", "phone_number": phone, "first_name": first_name, "last_name": last_name or ""}
        data = dict(kw)
        if reply_to is not None:
            data["reply_to"] = {"_": "inputReplyToMessage", "reply_to_msg_id": int(reply_to)}
        return await self.mt_req("messages.sendMedia", peer=peer, media=media, message="", random_id=secrets.randbits(63), **data)

    async def send_location(self, chat_id: int | str, lat: float, long: float, *, via: str | None = None, reply_to: int | None = None, **kw: Any) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            data = dict(kw)
            data["latitude"] = lat
            data["longitude"] = long
            if reply_to is not None:
                data["reply_parameters"] = {"message_id": reply_to}
            return await self.bot_req("sendLocation", chat_id=target, **data)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        geo = {"_": "geoPoint", "long": long, "lat": lat, "access_hash": 0}
        media = {"_": "inputMediaGeoPoint", "geo_point": geo}
        data = dict(kw)
        if reply_to is not None:
            data["reply_to"] = {"_": "inputReplyToMessage", "reply_to_msg_id": int(reply_to)}
        return await self.mt_req("messages.sendMedia", peer=peer, media=media, message="", random_id=secrets.randbits(63), **data)

    async def send_venue(self, chat_id: int | str, lat: float, long: float, title: str, address: str, *, via: str | None = None, reply_to: int | None = None, **kw: Any) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            data = dict(kw)
            data.update({"latitude": lat, "longitude": long, "title": title, "address": address})
            if reply_to is not None:
                data["reply_parameters"] = {"message_id": reply_to}
            return await self.bot_req("sendVenue", chat_id=target, **data)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        geo = {"_": "geoPoint", "long": long, "lat": lat, "access_hash": 0}
        media = {"_": "inputMediaVenue", "geo_point": geo, "title": title, "address": address, "provider": "", "venue_id": "", "venue_type": ""}
        data = dict(kw)
        if reply_to is not None:
            data["reply_to"] = {"_": "inputReplyToMessage", "reply_to_msg_id": int(reply_to)}
        return await self.mt_req("messages.sendMedia", peer=peer, media=media, message="", random_id=secrets.randbits(63), **data)

    async def send_poll(self, chat_id: int | str, question: str, options: list[str], *, anonymous: bool = True, via: str | None = None, reply_to: int | None = None, **kw: Any) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            data = dict(kw)
            data["question"] = question
            data["options"] = [{"text": o, "voter_count": 0} for o in options]
            data["is_anonymous"] = anonymous
            if reply_to is not None:
                data["reply_parameters"] = {"message_id": reply_to}
            return await self.bot_req("sendPoll", chat_id=target, **data)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        media = {
            "_": "inputMediaPoll",
            "question": {"_": "textWithEntities", "text": question, "entities": []},
            "answers": [{"_": "pollAnswer", "text": {"_": "textWithEntities", "text": o, "entities": []}, "option": bytes([i]).hex()} for i, o in enumerate(options)],
        }
        if not anonymous:
            media["poll"] = {"_": "poll", "id": 0, "question": {"_": "textWithEntities", "text": question, "entities": []}, "answers": media["answers"], "public_voters": True}
        data = dict(kw)
        if reply_to is not None:
            data["reply_to"] = {"_": "inputReplyToMessage", "reply_to_msg_id": int(reply_to)}
        return await self.mt_req("messages.sendMedia", peer=peer, media=media, message="", random_id=secrets.randbits(63), **data)

    async def send_dice(self, chat_id: int | str, emoji: str = "🎲", *, via: str | None = None, reply_to: int | None = None, **kw: Any) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            data = dict(kw)
            data["emoji"] = emoji
            if reply_to is not None:
                data["reply_parameters"] = {"message_id": reply_to}
            return await self.bot_req("sendDice", chat_id=target, **data)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        media = {"_": "inputMediaDice", "emoticon": emoji}
        data = dict(kw)
        if reply_to is not None:
            data["reply_to"] = {"_": "inputReplyToMessage", "reply_to_msg_id": int(reply_to)}
        return await self.mt_req("messages.sendMedia", peer=peer, media=media, message="", random_id=secrets.randbits(63), **data)

    async def send_rich(self, chat_id: int | str, rich: Any, *, via: str | None = None, reply_to: int | None = None, **kw: Any) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        from goygram.rich import Rich, rich_html
        if isinstance(rich, Rich):
            payload_bot = rich.to_msg()
            payload_mt = rich.to_tl()
        elif isinstance(rich, str):
            payload_bot = rich_html(rich)
            payload_mt = {"_": "inputRichMessageHTML", **rich_html(rich)}
        else:
            payload_bot = rich
            payload_mt = rich
        if transport == "bot":
            data = dict(kw)
            data["rich_message"] = payload_bot
            if reply_to is not None:
                data["reply_parameters"] = {"message_id": reply_to}
            return await self.bot_req("sendRichMessage", chat_id=target, **data)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        data = dict(kw)
        data["message"] = ""
        data["rich_message"] = payload_mt
        if reply_to is not None:
            data["reply_to"] = {"_": "inputReplyToMessage", "reply_to_msg_id": int(reply_to)}
        return await self.mt_req("messages.sendMessage", peer=peer, random_id=secrets.randbits(63), **data)

    async def edit_rich(self, chat_id: int | str, msg_id: int, rich: Any, *, via: str | None = None, **kw: Any) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        from goygram.rich import Rich, rich_html
        if isinstance(rich, Rich):
            payload_bot = rich.to_msg()
            payload_mt = rich.to_tl()
        elif isinstance(rich, str):
            payload_bot = rich_html(rich)
            payload_mt = {"_": "inputRichMessageHTML", **rich_html(rich)}
        else:
            payload_bot = rich
            payload_mt = rich
        if transport == "bot":
            data = dict(kw)
            data["rich_message"] = payload_bot
            data["message_id"] = msg_id
            return await self.bot_req("editMessageText", chat_id=target, **data)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        data = dict(kw)
        data["message"] = ""
        data["rich_message"] = payload_mt
        return await self.mt_req("messages.editMessage", peer=peer, id=int(msg_id), **data)

    async def send_draft(self, chat_id: int | str, draft_id: Any, text: str, *, via: str | None = None, **kw: Any) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            data = dict(kw)
            return await self.bot_req("sendMessageDraft", chat_id=target, draft_id=draft_id, text=text, **data)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        action = {"_": "sendMessageTextDraftAction", "can_stop": True, "random_id": int(draft_id or 0)}
        if text:
            action["text"] = {"_": "textWithEntities", "text": text, "entities": []}
        return await self.mt_req("messages.setTyping", peer=peer, action=action)

    async def iter_participants(self, chat_id: int | str, *, limit: int = 0, batch: int = 200, search: str = "") -> Any:
        if self.mt is None:
            raise RuntimeError("iter_participants requires the mtproto transport")
        target = self.raw_chat(chat_id)
        peer = await self.mt.resolve_peer(target)
        offset = 0
        seen = 0
        while True:
            res = await self.mt_req(
                "channels.getParticipants",
                channel=peer,
                filter={"_": "channelParticipantsSearch", "q": search},
                offset=offset,
                limit=batch,
                hash=0,
            )
            users = None
            if isinstance(res, dict):
                inner = res.get("result") if isinstance(res.get("result"), dict) else res
                users = inner.get("participants") if isinstance(inner, dict) else None
            if not users:
                return
            for u in users:
                yield u
                seen += 1
                if limit and seen >= limit:
                    return
            if len(users) < batch:
                return
            offset += len(users)

    def iter_dialogs(self, limit: int = 0, batch: int = 100, folder: int = 0) -> "_DialogIter":
        return _DialogIter(self, limit, batch, folder)

    async def get_chat_info(self, chat_id: int | str, *, full: bool = False, via: str | None = None) -> Any:
        target = self.raw_chat(chat_id)
        transport = self.via(chat_id, via)
        if transport == "bot":
            if full:
                return await self.bot_req("getChatFullInfo", chat_id=target) if await self._bot_has("getChatFullInfo") else await self.bot_req("getChat", chat_id=target)
            return await self.bot_req("getChat", chat_id=target)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        if full:
            res = await self.mt_req("messages.getPeerDialogs", peers=[peer])
            inner = res.get("result", res) if isinstance(res, dict) else {}
            dialogs = inner.get("dialogs") if isinstance(inner, dict) else None
            if dialogs:
                return dialogs[0]
            return res
        res = await self.mt_req("messages.getPeerDialogs", peers=[peer])
        inner = res.get("result", res) if isinstance(res, dict) else {}
        chats = inner.get("chats") if isinstance(inner, dict) else None
        users = inner.get("users") if isinstance(inner, dict) else None
        if chats:
            return chats[0]
        if users:
            return users[0]
        return res

    async def _bot_has(self, meth: str) -> bool:
        try:
            await self.bot_req("getMe")
            return meth == "getChatFullInfo"
        except Exception:
            return False

    async def ban_member(self, chat_id: int | str, user_id: int | str, *, until: int | None = None, via: str | None = None) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            data: dict[str, Any] = {"chat_id": target, "user_id": self.raw_chat(user_id)}
            if until is not None:
                data["until_date"] = until
            return await self.bot_req("banChatMember", **data)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        uid = self.raw_chat(user_id)
        uper = await self.mt.resolve_peer(uid)
        data = {"channel": peer, "participant": uper}
        if until is not None:
            data["until_date"] = int(until)
        return await self.mt_req("channels.editBanned", banned_rights={"_": "chatBannedRights", "until_date": int(until or 0), "view_messages": True}, **data)

    async def unban_member(self, chat_id: int | str, user_id: int | str, *, via: str | None = None) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            return await self.bot_req("unbanChatMember", chat_id=target, user_id=self.raw_chat(user_id), only_if_banned=True)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        uper = await self.mt.resolve_peer(self.raw_chat(user_id))
        return await self.mt_req("channels.editBanned", channel=peer, participant=uper, banned_rights={"_": "chatBannedRights", "until_date": 0, "view_messages": False})

    async def kick_member(self, chat_id: int | str, user_id: int | str, *, via: str | None = None) -> Any:
        if self.via(chat_id, via) == "bot":
            return await self.ban_member(chat_id, user_id, via=via) and await self.unban_member(chat_id, user_id, via=via)
        return await self.ban_member(chat_id, user_id, via=via)

    async def promote_member(self, chat_id: int | str, user_id: int | str, *, rights: dict[str, bool] | None = None, title: str | None = None, via: str | None = None) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        r = rights or {}
        if transport == "bot":
            data: dict[str, Any] = {"chat_id": target, "user_id": self.raw_chat(user_id)}
            mapping = {
                "can_change_info": "can_change_info",
                "can_delete_messages": "can_delete_messages",
                "can_invite_users": "can_invite_users",
                "can_pin_messages": "can_pin_messages",
                "can_promote_members": "can_promote_members",
                "can_restrict_members": "can_restrict_members",
                "can_manage_video_chats": "can_manage_video_chats",
                "can_manage_chat": "can_manage_chat",
            }
            for k, bk in mapping.items():
                if k in r:
                    data[bk] = bool(r[k])
            if title:
                data["custom_title"] = title
            return await self.bot_req("promoteChatMember", **data)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        uper = await self.mt.resolve_peer(self.raw_chat(user_id))
        admin = {"_": "chatAdminRights"}
        for k, v in r.items():
            admin[k] = bool(v)
        data = {"channel": peer, "user_id": uper, "admin_rights": admin}
        if title:
            data["rank"] = title
        return await self.mt_req("channels.editAdmin", **data)

    async def set_chat_title(self, chat_id: int | str, title: str, *, via: str | None = None) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            return await self.bot_req("setChatTitle", chat_id=target, title=title)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        return await self.mt_req("channels.editTitle", channel=peer, title=title)

    async def set_chat_about(self, chat_id: int | str, about: str, *, via: str | None = None) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            return await self.bot_req("setChatDescription", chat_id=target, description=about)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        return await self.mt_req("channels.editAbout", about=about, **{"channel": peer})

    async def create_invite_link(self, chat_id: int | str, *, name: str | None = None, expires: int | None = None, member_limit: int | None = None, via: str | None = None) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            data: dict[str, Any] = {"chat_id": target}
            if name:
                data["name"] = name
            if expires:
                data["expire_date"] = expires
            if member_limit:
                data["member_limit"] = member_limit
            return await self.bot_req("createChatInviteLink", **data)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        return await self.mt_req("channels.exportInvite", **{"channel": peer})

    async def join_chat(self, chat_id: int | str, *, via: str | None = None) -> Any:
        if self.mt is None:
            raise RuntimeError("join_chat requires the mtproto transport")
        target = self.raw_chat(chat_id)
        peer = await self.mt.resolve_peer(target)
        return await self.mt_req("channels.joinChannel", **{"channel": peer})

    async def leave_chat(self, chat_id: int | str, *, via: str | None = None) -> Any:
        transport = self.via(chat_id, via)
        target = self.raw_chat(chat_id)
        if transport == "bot":
            return await self.bot_req("leaveChat", chat_id=target)
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        peer = await self.mt.resolve_peer(target)
        return await self.mt_req("channels.leaveChannel", **{"channel": peer})

    async def iter_members(self, chat_id: int | str, *, limit: int = 0, batch: int = 200, via: str | None = None) -> Any:
        if self.via(chat_id, via) == "bot":
            target = self.raw_chat(chat_id)
            offset = 0
            while True:
                res = await self.bot_req("getChatMemberCount", chat_id=target) if offset == 0 else None
                yield res if offset == 0 else None
                return
        async for p in self.iter_participants(chat_id, limit=limit, batch=batch):
            yield p

    def set_state(self, chat_id: int | str, user_id: int | str, state: str, data: dict[str, Any] | None = None, ttl: float | None = None) -> None:
        self.fsm.set(chat_id, user_id, state, data, ttl)

    def get_state(self, chat_id: int | str, user_id: int | str) -> str | None:
        return self.fsm.get(chat_id, user_id)

    def get_state_data(self, chat_id: int | str, user_id: int | str) -> dict[str, Any] | None:
        return self.fsm.get_data(chat_id, user_id)

    def clear_state(self, chat_id: int | str, user_id: int | str) -> None:
        self.fsm.clear(chat_id, user_id)

    async def close(self) -> None:
        self.stop_ev.set()
        await self.fsm.stop()
        await self.disp.close()
        if self.bot:
            await self.bot.close()
        if self.mt:
            await self.mt.close()

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        self.log.info("Starting GoyGram core.")
        tasks = []
        stop_wait = None
        try:
            tasks.append(asyncio.create_task(self.disp.consume(), name="disp"))
            await self.fsm.start()
            if self.mt:
                self.log.info("MT transport is enabled.")
                await bootstrap_session(self, api_id=self.api_id, api_hash=self.api_hash, session_name=self.session_name, bot_token=self.bot_token, session=self.session)
                if self.intake == "auto":
                    if self.bot is None:
                        self.intake = "mtproto"
                    elif self.session.is_bot:
                        self.intake = "mtproto"
                    else:
                        self.intake = "dual"
                await self.mt.start()
                tasks.append(self.mt._reader_task)
                try:
                    await self.mt.call("updates.getState", api_id=self.api_id)
                except Exception as exc:
                    self.log.debug("Initial MTProto state request failed: %s", type(exc).__name__)
            elif self.intake == "auto":
                self.intake = "api"
            if self.bot:
                self.log.info("Bot transport is enabled.")
                if self.mt is not None and self.intake != "dual":
                    self.log.info("Hybrid mode: updates are served exclusively by MTProto; Bot API polling is off.")
                if self.mt is not None and self.intake == "dual":
                    self.log.info("Dual-intake mode: updates flow from BOTH MTProto and Bot API; cross-transport dedup is active.")
                if self.bot.webhook_url and (self.mt is None or self.intake == "dual"):
                    await self.bot.start_webhook()
                elif self.mt is None or self.intake == "dual":
                    try:
                        await self.bot_req("deleteWebhook", drop_pending_updates=False)
                    except Exception as e:
                        self.log.error("Failed to clear webhook before polling: %r", e)
                    tasks.append(asyncio.create_task(self.bot.spin(), name="bot"))
            stop_wait = asyncio.create_task(self.stop_ev.wait(), name="stop-wait")
            done, _ = await asyncio.wait({stop_wait, *tasks}, return_when=asyncio.FIRST_COMPLETED)
            if stop_wait not in done:
                self.stop_ev.set()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await self.close()
            if stop_wait is not None:
                stop_wait.cancel()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


class GoyGram:
    def __init__(
        self,
        bot_token: str | None = None,
        mt_host: str | None = None,
        mt_port: int | None = None,
        mt_key: bytes | None = None,
        mt_iv: bytes | None = None,
        bot_timeout: int = 25,
        bot_base: str = "https://api.telegram.org",
        bus_max: int = 0,
        api_id: int | str | None = None,
        api_hash: str | None = None,
        session_name: str = "default",
        session: Any | None = None,
        default_transport: str = "auto",
        proxy: str | None = None,
        app_name: str | None = None,
        app_version: str | None = None,
        device_model: str | None = None,
        system_version: str | None = None,
        system_lang_code: str = "en",
        lang_pack: str = "",
        lang_code: str = "en",
        fsm_backend: Any | None = None,
        fsm_on_change: Callable[[list[dict[str, Any]]], Any] | None = None,
        webhook_url: str | None = None,
        webhook_host: str = "127.0.0.1",
        webhook_port: int = 8080,
        webhook_path: str = "/telegram/webhook",
        webhook_secret_token: str | None = None,
        webhook_max_body: int = 1024 * 1024,
        webhook_drop_pending_updates: bool = False,
        bot_offset_path: str | None = None,
        intake: str = "auto",
    ) -> None:
        if webhook_url is not None and bot_token is None:
            raise ValueError("webhook_url requires bot_token")
        bot = BotCfg(
            token=bot_token,
            timeout=bot_timeout,
            base=bot_base,
            webhook_url=webhook_url,
            webhook_host=webhook_host,
            webhook_port=webhook_port,
            webhook_path=webhook_path,
            webhook_secret_token=webhook_secret_token,
            webhook_max_body=webhook_max_body,
            webhook_drop_pending_updates=webhook_drop_pending_updates,
            offset_path=bot_offset_path,
        ) if bot_token is not None else None
        log = get_logger("goygram.dc")
        resolved_host = mt_host
        resolved_port = mt_port

        if resolved_host is None and (bot is None or api_id is not None or api_hash is not None):
            try:
                dc_map = get_dynamic_dc_config()
                selected = pick_dc_endpoint(dc_map, preferred_dc=2)
                resolved_host, resolved_port = selected.host, selected.port
                log.info("Dynamic DC routing selected dc%s %s:%s", selected.dc_id, selected.host, selected.port)
            except Exception as e:
                log.error("Dynamic DC routing failed: %r", e)
                resolved_host, resolved_port = "149.154.167.50", 443
                log.warning("Using fallback MT endpoint %s:%s", resolved_host, resolved_port)

        mt = MtCfg(host=resolved_host, port=resolved_port, key=mt_key, iv=mt_iv) if resolved_host is not None and resolved_port is not None else None
        self.core = AppCore(
            AppCfg(bot=bot, mt=mt, bus_max=bus_max),
            api_id=api_id,
            api_hash=api_hash,
            session_name=session_name,
            session=session,
            default_transport=default_transport,
            proxy=proxy,
            app_name=app_name,
            app_version=app_version,
            device_model=device_model,
            system_version=system_version,
            system_lang_code=system_lang_code,
            lang_pack=lang_pack,
            lang_code=lang_code,
            fsm_backend=fsm_backend,
            fsm_on_change=fsm_on_change,
            intake=intake,
        )

    def on_msg(self, fn: Fn | None = None, filt: Filter | None = None, once: bool = False):
        return self.core.on_msg(fn, filt=filt, once=once)

    def on_cb(self, fn: CbFn | None = None, *, filt: Filter | None = None, once: bool = False):
        return self.core.on_cb(fn, filt=filt, once=once)

    def on_inline(self, fn: InlineFn | None = None, *, filt: Filter | None = None, once: bool = False):
        return self.core.on_inline(fn, filt=filt, once=once)

    def on_cmd(self, *name: str) -> Callable[[Fn], Fn]:
        return self.core.on_cmd(*name)

    def on_poll(self, fn: PollFn | None = None, *, filt: Filter | None = None, once: bool = False):
        return self.core.on_poll(fn, filt=filt, once=once)

    def on_member(self, fn: MemFn | None = None, *, filt: Filter | None = None, once: bool = False):
        return self.core.on_member(fn, filt=filt, once=once)

    def on_edit(self, fn: Fn | None = None, filt: Filter | None = None, once: bool = False):
        return self.core.on_edit(fn, filt=filt, once=once)

    def on_update(self, fn: Callable[[object], Awaitable[Any]] | None = None, *, filt: Filter | None = None, once: bool = False):
        return self.core.on_update(fn, filt=filt, once=once)

    def help(self) -> None:
        self.core.help()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.core, name)

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(dir(self.core)))

    def stop(self) -> None:
        self.core.stop()

    async def run(self) -> None:
        await self.core.run()
