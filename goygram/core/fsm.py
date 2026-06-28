from __future__ import annotations
import asyncio, time
from typing import Any


class StateItem:
    __slots__ = ('state', 'data', 'expiry')

    def __init__(self, state: str, data: dict[str, Any] | None = None, expiry: float = 0.0) -> None:
        self.state = state
        self.data = data if data is not None else {}
        self.expiry = expiry


class FSMEngine:
    def __init__(self, ttl: float = 3600.0) -> None:
        self._states: dict[tuple[int, int], StateItem] = {}
        self._ttl = ttl
        self._task: asyncio.Task[None] | None = None
        self._stop_ev = asyncio.Event()

    def set(self, chat_id: int | str, user_id: int | str, state: str, data: dict[str, Any] | None = None, ttl: float | None = None) -> None:
        key = (int(chat_id), int(user_id))
        existing = self._states.get(key)
        now = time.time()
        if existing is not None:
            if data is not None:
                existing.data.update(data)
            existing.state = state
            existing.expiry = now + (ttl if ttl is not None else self._ttl)
        else:
            merged_data = data if data is not None else {}
            expiry = now + (ttl if ttl is not None else self._ttl)
            self._states[key] = StateItem(state, merged_data, expiry)

    def get(self, chat_id: int | str, user_id: int | str) -> str | None:
        key = (int(chat_id), int(user_id))
        item = self._states.get(key)
        if item is None:
            return None
        if time.time() > item.expiry:
            del self._states[key]
            return None
        return item.state

    def get_data(self, chat_id: int | str, user_id: int | str) -> dict[str, Any] | None:
        key = (int(chat_id), int(user_id))
        item = self._states.get(key)
        if item is None:
            return None
        if time.time() > item.expiry:
            del self._states[key]
            return None
        return dict(item.data)

    def clear(self, chat_id: int | str, user_id: int | str) -> None:
        self._states.pop((int(chat_id), int(user_id)), None)

    async def start(self) -> None:
        self._stop_ev.clear()
        self._task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        self._stop_ev.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
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
            if len(stale) >= batch:
                await asyncio.sleep(0)

    def __len__(self) -> int:
        return len(self._states)
