# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations
from typing import Any
from goygram.api.types import *

def dump(v: Any) -> Any:
    if hasattr(v, "to_dict"):
        return v.to_dict()
    if isinstance(v, list):
        return [dump(x) for x in v]
    if isinstance(v, dict):
        return {k: dump(x) for k, x in v.items() if x is not None}
    return v

class BotAPI:
    __slots__ = ("net",)
    def __init__(self, net: Any) -> None:
        self.net = net

    async def call(self, meth: str, **kw: Any) -> Any:
        return await self.net.req(meth, dump(kw))

    def __getattr__(self, name: str) -> Any:
        async def dyn(**kw: Any) -> Any:
            parts = name.split("_")
            meth = parts[0] + "".join(x[:1].upper() + x[1:] for x in parts[1:])
            return await self.call(meth, **kw)
        return dyn

__all__ = ["BotAPI"]
