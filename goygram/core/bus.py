# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

import asyncio
from typing import Any


class Bus:
    def __init__(self, maxsize: int = 0) -> None:
        self.q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=maxsize)

    async def push(self, src: str, data: dict[str, Any]) -> None:
        await self.q.put({"src": src, "data": data})

    async def fetch(self) -> dict[str, Any]:
        return await self.q.get()

