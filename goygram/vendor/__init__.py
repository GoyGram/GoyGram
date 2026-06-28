# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

from typing import Any

__all__ = ["BotNet", "MTNet"]


def __getattr__(name: str) -> Any:
    if name == "BotNet":
        from goygram.vendor.botapi import BotNet

        return BotNet
    if name == "MTNet":
        from goygram.vendor.mtproto import MTNet

        return MTNet
    raise AttributeError(name)
