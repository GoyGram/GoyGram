# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations
from typing import Any
from goygram.api.types import camel

class BotAPI:
    __slots__ = ("net", "__dict__")
    def __init__(self, net: Any) -> None:
        self.net = net

    async def call(self, meth: str, **kw: Any) -> Any:
        return await self.net.req(meth, kw)

    def __getattr__(self, name: str) -> Any:
        meth = camel(name)
        async def dyn(**kw: Any) -> Any:
            return await self.call(meth, **kw)
        self.__dict__[name] = dyn
        return dyn

__all__ = ["BotAPI"]
