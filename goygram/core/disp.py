# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

import asyncio
import time as _time
from collections.abc import Awaitable, Callable
from typing import Any

from goygram.logging import get_logger

from goygram.errors import StopPropagation
from goygram.types.obj import Obj

Fn = Callable[["Obj"], Awaitable[Any]]
CbFn = Fn
PollFn = Fn
MemFn = Fn
InlineFn = Fn


class Disp:
    def __init__(self, app: Any, bus: Any) -> None:
        self.app = app
        self.bus = bus
        self.stop_ev = asyncio.Event()
        self.log = get_logger("goygram.disp")
        self._seen: dict[tuple, float] = {}
        self._seen_sweep = 0.0

    def _dedup_key(self, data: dict[str, Any]) -> tuple | None:
        kind = data.get("kind")
        if kind not in {"msg", "edit", "cb", "inline"}:
            return None
        src = data.get("src")
        if src is None and isinstance(data.get("raw"), dict):
            src = "bot"
        if kind in {"cb", "inline"}:
            qid = data.get("query_id") or data.get("upd_id")
            if qid is None:
                return None
            return (kind, "q", int(qid))
        chat = data.get("chat_id")
        mid = data.get("msg_id")
        if chat is None or mid is None:
            return None
        return (kind, int(chat), int(mid))

    def _is_duplicate(self, data: dict[str, Any]) -> bool:
        key = self._dedup_key(data)
        if key is None:
            return False
        now = _time.monotonic()
        if now - self._seen_sweep > 300.0:
            for k in [k for k, ts in self._seen.items() if now - ts > 300.0]:
                del self._seen[k]
            self._seen_sweep = now
        if key in self._seen:
            return True
        self._seen[key] = now
        return False

    async def close(self) -> None:
        self.stop_ev.set()

    async def one(self, pkt: dict[str, Any]) -> None:
        data = pkt.get("data")
        if not isinstance(data, dict):
            return
        kind = data.get("kind")
        if kind == "err":
            self.log.warning("Disp error event: %s", data.get("text", ""))
            return
        if self._is_duplicate(data):
            self.log.debug("Duplicate update dropped (kind=%s chat=%s msg=%s)", data.get("kind"), data.get("chat_id"), data.get("msg_id"))
            return
        if kind != "update":
            update = Obj(pkt.get("src", "sys"), data, self.app)
            for fn in list(getattr(self.app, "update_hook", [])):
                try:
                    await fn(update)
                except StopPropagation:
                    return
                except Exception as e:
                    self.log.error("Handler failure: %r", e)
                    await self.bus.push("sys", {"kind": "err", "src": "disp", "text": repr(e)})
        if kind == "msg":
            msg = Obj(pkt.get("src", "sys"), data, self.app)
            await self.app._conv_dispatch(msg)
            for fn in list(self.app.hook):
                try:
                    await fn(msg)
                except StopPropagation:
                    return
                except Exception as e:
                    self.log.error("Handler failure: %r", e)
                    await self.bus.push("sys", {"kind": "err", "src": "disp", "text": repr(e)})
            return
        if kind == "edit":
            msg = Obj(pkt.get("src", "sys"), data, self.app)
            for fn in list(getattr(self.app, "edit_hook", [])):
                try:
                    await fn(msg)
                except StopPropagation:
                    return
                except Exception as e:
                    self.log.error("Handler failure: %r", e)
                    await self.bus.push("sys", {"kind": "err", "src": "disp", "text": repr(e)})
            return
        if kind == "poll":
            poll = Obj(pkt.get("src", "sys"), data, self.app)
            for fn in list(getattr(self.app, "poll_hook", [])):
                try:
                    await fn(poll)
                except StopPropagation:
                    return
                except Exception as e:
                    self.log.error("Handler failure: %r", e)
                    await self.bus.push("sys", {"kind": "err", "src": "disp", "text": repr(e)})
            return
        if kind == "cb":
            cb = Obj(pkt.get("src", "sys"), data, self.app)
            for fn in list(self.app.cb_hook):
                try:
                    await fn(cb)
                except StopPropagation:
                    return
                except Exception as e:
                    self.log.error("Handler failure: %r", e)
                    await self.bus.push("sys", {"kind": "err", "src": "disp", "text": repr(e)})
            return
        if kind == "inline":
            inline = Obj(pkt.get("src", "sys"), data, self.app)
            for fn in list(getattr(self.app, "inline_hook", [])):
                try:
                    await fn(inline)
                except StopPropagation:
                    return
                except Exception as e:
                    self.log.error("Handler failure: %r", e)
                    await self.bus.push("sys", {"kind": "err", "src": "disp", "text": repr(e)})
            return
        if kind == "update":
            update = Obj(pkt.get("src", "sys"), data, self.app)
            for fn in list(getattr(self.app, "update_hook", [])):
                try:
                    await fn(update)
                except StopPropagation:
                    return
                except Exception as e:
                    self.log.error("Handler failure: %r", e)
                    await self.bus.push("sys", {"kind": "err", "src": "disp", "text": repr(e)})
            return
        if kind != "member":
            return
        mem = Obj(pkt.get("src", "sys"), data, self.app)
        for fn in list(getattr(self.app, "member_hook", [])):
            try:
                await fn(mem)
            except StopPropagation:
                return
            except Exception as e:
                self.log.error("Handler failure: %r", e)
                await self.bus.push("sys", {"kind": "err", "src": "disp", "text": repr(e)})

    async def consume(self) -> None:
        while not self.stop_ev.is_set():
            try:
                pkt = await self.bus.fetch()
                await self.one(pkt)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.log.error("Handler failure: %r", e)
                await self.bus.push("sys", {"kind": "err", "src": "disp", "text": repr(e)})
