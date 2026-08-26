# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi026-wq. Licensed under AGPLv3.
from __future__ import annotations

import asyncio
import copy
import time
from collections.abc import Callable
from typing import Any


class StateItem:
    __slots__ = ('state', 'data', 'expiry')

    def __init__(self, state: str, data: dict[str, Any] | None = None, expiry: float = 0.0) -> None:
        self.state = state
        self.data = data if data is not None else {}
        self.expiry = expiry


class FSMEngine:
    def __init__(
        self,
        ttl: float = 3600.0,
        *,
        backend: Any | None = None,
        on_change: Callable[[list[dict[str, Any]]], Any] | None = None,
    ) -> None:
        self._states: dict[tuple[int, int], StateItem] = {}
        self._ttl = ttl
        self._backend = backend
        self._on_change = on_change
        self._task: asyncio.Task[None] | None = None
        self._stop_ev = asyncio.Event()
        self.restore(self._backend.load() if self._backend is not None else [])

    def snapshot(self) -> list[dict[str, Any]]:
        now = time.time()
        return [
            {
                "chat_id": chat_id,
                "user_id": user_id,
                "state": item.state,
                "data": copy.deepcopy(item.data),
                "expiry": item.expiry,
            }
            for (chat_id, user_id), item in self._states.items()
            if item.expiry > now
        ]

    def restore(self, snapshot: Any) -> None:
        self._states.clear()
        if not isinstance(snapshot, list):
            return
        now = time.time()
        for item in snapshot:
            if not isinstance(item, dict):
                continue
            try:
                chat_id = int(item["chat_id"])
                user_id = int(item["user_id"])
                state = str(item["state"])
                expiry = float(item["expiry"])
            except (KeyError, TypeError, ValueError):
                continue
            data = item.get("data", {})
            if expiry > now and isinstance(data, dict):
                self._states[(chat_id, user_id)] = StateItem(state, copy.deepcopy(data), expiry)

    def _changed(self) -> None:
        snapshot = self.snapshot()
        if self._backend is not None:
            self._backend.save(copy.deepcopy(snapshot))
        if self._on_change is not None:
            self._on_change(copy.deepcopy(snapshot))

    def set(self, chat_id: int | str, user_id: int | str, state: str, data: dict[str, Any] | None = None, ttl: float | None = None) -> None:
        key = (int(chat_id), int(user_id))
        existing = self._states.get(key)
        now = time.time()
        if existing is not None:
            if data is not None:
                existing.data.update(copy.deepcopy(data))
            existing.state = state
            existing.expiry = now + (ttl if ttl is not None else self._ttl)
        else:
            merged_data = copy.deepcopy(data) if data is not None else {}
            expiry = now + (ttl if ttl is not None else self._ttl)
            self._states[key] = StateItem(state, merged_data, expiry)
        self._changed()

    def get(self, chat_id: int | str, user_id: int | str) -> str | None:
        key = (int(chat_id), int(user_id))
        item = self._states.get(key)
        if item is None:
            return None
        if time.time() > item.expiry:
            del self._states[key]
            self._changed()
            return None
        return item.state

    def get_data(self, chat_id: int | str, user_id: int | str) -> dict[str, Any] | None:
        key = (int(chat_id), int(user_id))
        item = self._states.get(key)
        if item is None:
            return None
        if time.time() > item.expiry:
            del self._states[key]
            self._changed()
            return None
        return copy.deepcopy(item.data)

    def clear(self, chat_id: int | str, user_id: int | str) -> None:
        self._states.pop((int(chat_id), int(user_id)), None)
        self._changed()

    async def start(self) -> None:
        self._stop_ev.clear()
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        self._stop_ev.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._states.clear()

    async def _cleanup_loop(self) -> None:
        batch = 1000
        while not self._stop_ev.is_set():
            await asyncio.sleep(600)
            if self._stop_ev.is_set():
                break
            stale: list[tuple[int, int]] = []
            now = time.time()
            for key, item in self._states.items():
                if now > item.expiry:
                    stale.append(key)
                    if len(stale) >= batch:
                        break
            for key in stale:
                self._states.pop(key, None)
            if stale:
                self._changed()
            if len(stale) >= batch:
                await asyncio.sleep(0)

    def __len__(self) -> int:
        return len(self._states)
