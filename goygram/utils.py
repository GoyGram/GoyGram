# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

import inspect
from typing import Any

from goygram.filters import Filter, me, text


def print_methods(app: Any) -> None:
    lines: list[str] = []
    lines.append("=== GoyGram Developer Help ===")
    lines.append("• All methods are dynamically dispatched via runtime TL parsing:")
    lines.append("  - Bot API: app.<camelCase>(...) e.g. app.sendMessage(...)")
    lines.append("  - MTProto: app.mt_<namespace>_<method>(...) e.g. app.mt_messages_get_dialogs(...)")
    lines.append("  - Complex types must be pre-serialized via codec helpers")
    lines.append("• Built-in:")
    for name in sorted(x for x in dir(app) if not x.startswith("_") and callable(getattr(app, x, None))):
        if name == "help":
            sig = inspect.signature(getattr(app, name))
            lines.append(f"  - {name}{sig}")
    lines.append("• Filters:")
    lines.append("  - text: Message has text")
    lines.append("  - me: Event from current account/bot")
    lines.append("  - Combine with &, |, ~ (Filter operators)")
    print("\n".join(lines))


__all__ = ["print_methods", "Filter", "text", "me"]
