# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

import asyncio
import signal
from collections.abc import Awaitable, Callable
import logging
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from goygram.api.methods import BotAPI
from goygram.core.bus import Bus
from goygram.core.disp import Disp
from goygram.core.fsm import FSMEngine
from goygram.types.cb import CbObj
from goygram.types.member import MemberObj
from goygram.types.msg import MsgObj
from goygram.types.poll import PollObj
from goygram.logging import get_logger
from goygram.security import bootstrap_session
from goygram.filters import Filter
from goygram.dc_fetcher import get_dynamic_dc_config, pick_dc_endpoint
from goygram.utils import print_methods

Fn = Callable[[MsgObj], Awaitable[Any]]
CbFn = Callable[[CbObj], Awaitable[Any]]
PollFn = Callable[[PollObj], Awaitable[Any]]
MemFn = Callable[[MemberObj], Awaitable[Any]]


class BotCfg(BaseModel):
    model_config = ConfigDict(frozen=True)
    token: str
    timeout: int = 25
    base: str = "https://api.telegram.org"


class MtCfg(BaseModel):
    model_config = ConfigDict(frozen=True)
    host: str
    port: int
    key: bytes | None = None
    iv: bytes | None = None


class AppCfg(BaseModel):
    model_config = ConfigDict(frozen=True)
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
        proxy: str | None = None,
        app_name: str | None = None,
        app_version: str | None = None,
        device_model: str | None = None,
        system_version: str | None = None,
        system_lang_code: str = "en",
        lang_pack: str = "",
        lang_code: str = "en",
    ) -> None:
        self.cfg = cfg
        self.bus = Bus(cfg.bus_max)
        self.bot = None
        self.mt = None
        self.api = None
        if cfg.bot:
            from goygram.vendor.botapi import BotNet

            self.bot = BotNet(cfg.bot.token, self.bus, cfg.bot.timeout, cfg.bot.base)
            self.api = BotAPI(self.bot)
        if cfg.mt:
            from goygram.vendor.mtproto import MTNet

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
            )
            if api_id is not None:
                self.mt._api_id = int(api_id)
            self._init_tl_schema()
            self._load_vault_from_disk(session_name, api_id, api_hash)
        self.fsm = FSMEngine()
        self.disp = Disp(self, self.bus)
        self.hook: list[Fn] = []
        self.cb_hook: list[CbFn] = []
        self.poll_hook: list[PollFn] = []
        self.member_hook: list[MemFn] = []
        self.update_hook: list[Callable[[object], Awaitable[Any]]] = []
        self.stop_ev = asyncio.Event()
        self.log = get_logger("goygram.app")
        self.self_id: int | None = None
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name

    def _init_tl_schema(self) -> None:
        from goygram.schema_manager import init_schema
        from goygram import ext as _ext
        if _ext is None:
            return
        init_schema(_ext, None)

    def _load_vault_from_disk(self, session_name: str, api_id: Any, api_hash: Any) -> None:
        import logging
        from pathlib import Path
        from goygram.security import _read_vault, _extract_auth_blob
        from goygram.dc_fetcher import get_dynamic_dc_config, pick_dc_endpoint
        log = logging.getLogger("goygram.dc")
        vault = Path(f"{session_name}.vault")
        if not vault.exists() or vault.stat().st_size == 0:
            return
        try:
            data = _read_vault(vault, session_name)
            auth_key = data.get("auth_key")
            if auth_key and self.mt is not None:
                self.mt.auth_key = _extract_auth_blob({"auth_key": auth_key})
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

    def on_msg(self, fn: Fn | None = None, filt: Filter | None = None):
        if isinstance(fn, Filter):
            filt = fn
            fn = None
        def wrap(inner: Fn) -> Fn:
            if filt is None:
                self.hook.append(inner)
                return inner
            async def guarded(msg: MsgObj) -> Any:
                if filt(msg):
                    return await inner(msg)
                return None
            self.hook.append(guarded)
            return inner
        if fn is not None:
            return wrap(fn)
        return wrap

    def on_cb(self, fn: CbFn | None = None, *, filt: Filter | None = None):
        if isinstance(fn, Filter):
            filt = fn
            fn = None
        def wrap(inner: CbFn) -> CbFn:
            if filt is None:
                self.cb_hook.append(inner)
                return inner
            async def guarded(cb: CbObj) -> Any:
                if filt(cb):
                    return await inner(cb)
                return None
            self.cb_hook.append(guarded)
            return inner
        if fn is not None:
            return wrap(fn)
        return wrap

    def on_poll(self, fn: PollFn | None = None, *, filt: Filter | None = None):
        if isinstance(fn, Filter):
            filt = fn
            fn = None
        def wrap(inner: PollFn) -> PollFn:
            if filt is None:
                self.poll_hook.append(inner)
                return inner
            async def guarded(poll: PollObj) -> Any:
                if filt(poll):
                    return await inner(poll)
                return None
            self.poll_hook.append(guarded)
            return inner
        if fn is not None:
            return wrap(fn)
        return wrap

    def on_member(self, fn: MemFn | None = None, *, filt: Filter | None = None):
        def wrap(inner: MemFn) -> MemFn:
            if filt is None:
                self.member_hook.append(inner)
                return inner
            async def guarded(mem: MemberObj) -> Any:
                if filt(mem):
                    return await inner(mem)
                return None
            self.member_hook.append(guarded)
            return inner
        if fn is not None:
            return wrap(fn)
        return wrap

    def on_update(self, fn: Callable[[object], Awaitable[Any]] | None = None, *, filt: Filter | None = None):
        def wrap(inner: Callable[[object], Awaitable[Any]]) -> Callable[[object], Awaitable[Any]]:
            if filt is None:
                self.update_hook.append(inner)
                return inner
            async def guarded(event: object) -> Any:
                if filt(event):
                    return await inner(event)
                return None
            self.update_hook.append(guarded)
            return inner
        if fn is not None:
            return wrap(fn)
        return wrap

    def on_cmd(self, *name: str) -> Callable[[Fn], Fn]:
        from goygram.filters import command as _cmd_filt
        return self.on_msg(filt=_cmd_filt(*name))

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
        if via in {"bot", "mt"}:
            if via == "bot" and self.bot is None:
                raise RuntimeError("bot net is not configured")
            if via == "mt" and self.mt is None:
                raise RuntimeError("mt net is not configured")
            return via
        if isinstance(chat_id, str) and chat_id.startswith("bot:"):
            if self.bot is None:
                raise RuntimeError("bot net is not configured")
            return "bot"
        if isinstance(chat_id, str) and chat_id.startswith("mt:"):
            if self.mt is None:
                raise RuntimeError("mt net is not configured")
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

    async def mt_req(self, act: str, **kw: Any) -> Any:
        if self.mt is None:
            raise RuntimeError("mt net is not configured")
        data = {k: v.to_dict() if hasattr(v, "to_dict") else v for k, v in kw.items() if v is not None}
        if 'api_id' not in data and self.api_id is not None:
            data['api_id'] = self.api_id
        if 'api_hash' not in data and self.api_hash is not None:
            data['api_hash'] = self.api_hash
        if hasattr(self.mt, "call"):
            return await self.mt.call(act, **data)
        if hasattr(self.mt, "req"):
            return await self.mt.req(act, data)
        return await self.mt.send({"act": act, **data})

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
        try:
            tasks.append(asyncio.create_task(self.disp.consume(), name="disp"))
            await self.fsm.start()
            if self.bot:
                self.log.info("Bot transport is enabled.")
                try:
                    await self.bot_req("deleteWebhook", drop_pending_updates=False)
                except Exception as e:
                    self.log.error("Failed to clear webhook before polling: %r", e)
                tasks.append(asyncio.create_task(self.bot.spin(), name="bot"))
            if self.mt:
                self.log.info("MT transport is enabled.")
                await bootstrap_session(self, api_id=self.api_id, api_hash=self.api_hash, session_name=self.session_name)
                await self.mt.start()
                tasks.append(self.mt._reader_task)
                await self.mt.call("updates.getState", api_id=self.api_id)
            await self.stop_ev.wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await self.close()
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
        proxy: str | None = None,
        app_name: str | None = None,
        app_version: str | None = None,
        device_model: str | None = None,
        system_version: str | None = None,
        system_lang_code: str = "en",
        lang_pack: str = "",
        lang_code: str = "en",
    ) -> None:
        bot = BotCfg(token=bot_token, timeout=bot_timeout, base=bot_base) if bot_token is not None else None
        log = get_logger("goygram.dc")
        resolved_host = mt_host
        resolved_port = mt_port

        if bot is None and resolved_host is None:
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
            proxy=proxy,
            app_name=app_name,
            app_version=app_version,
            device_model=device_model,
            system_version=system_version,
            system_lang_code=system_lang_code,
            lang_pack=lang_pack,
            lang_code=lang_code,
        )

    def on_msg(self, fn: Fn | None = None, filt: Filter | None = None):
        return self.core.on_msg(fn, filt=filt)

    def on_cb(self, fn: CbFn | None = None, *, filt: Filter | None = None):
        return self.core.on_cb(fn, filt=filt)

    def on_cmd(self, *name: str) -> Callable[[Fn], Fn]:
        return self.core.on_cmd(*name)

    def on_poll(self, fn: PollFn | None = None, *, filt: Filter | None = None):
        return self.core.on_poll(fn, filt=filt)

    def on_member(self, fn: MemFn | None = None, *, filt: Filter | None = None):
        return self.core.on_member(fn, filt=filt)

    def on_update(self, fn: Callable[[object], Awaitable[Any]] | None = None, *, filt: Filter | None = None):
        return self.core.on_update(fn, filt=filt)

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
