# Copyleft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

HDR = "# Copyleft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.\n"
OUT = Path(__file__).resolve().parents[1] / "goygram" / "api"
BOT_URL = "https://core.telegram.org/bots/api"
FALLBACK: dict[str, Any] = {
    "types": [
        {"name": "User", "fields": [{"name": "id", "type": "int"}, {"name": "is_bot", "type": "bool"}, {"name": "first_name", "type": "str"}, {"name": "username", "type": "str", "optional": True}]},
        {"name": "Chat", "fields": [{"name": "id", "type": "int"}, {"name": "type", "type": "str"}, {"name": "title", "type": "str", "optional": True}, {"name": "username", "type": "str", "optional": True}]},
        {"name": "InlineKeyboardButton", "fields": [{"name": "text", "type": "str"}, {"name": "callback_data", "type": "str", "optional": True}, {"name": "url", "type": "str", "optional": True}]},
        {"name": "InlineKeyboardMarkup", "fields": [{"name": "inline_keyboard", "type": "list[InlineKeyboardButton]"}]},
        {"name": "KeyboardButton", "fields": [{"name": "text", "type": "str"}]},
        {"name": "ReplyKeyboardMarkup", "fields": [{"name": "keyboard", "type": "list[KeyboardButton]"}, {"name": "resize_keyboard", "type": "bool", "optional": True}, {"name": "one_time_keyboard", "type": "bool", "optional": True}]},
        {"name": "Message", "fields": [{"name": "message_id", "type": "int"}, {"name": "date", "type": "int"}, {"name": "chat", "type": "Chat"}, {"name": "text", "type": "str", "optional": True}]},
    ],
    "methods": [
        {"name": "getMe", "returns": "User", "params": []},
        {"name": "sendMessage", "returns": "Message", "params": [{"name": "chat_id", "type": "int|str"}, {"name": "text", "type": "str"}, {"name": "parse_mode", "type": "str", "optional": True}, {"name": "reply_parameters", "type": "dict[str,Any]", "optional": True}, {"name": "reply_markup", "type": "InlineKeyboardMarkup|ReplyKeyboardMarkup|dict[str,Any]", "optional": True}, {"name": "message_thread_id", "type": "int", "optional": True}]},
        {"name": "editMessageText", "returns": "Message|bool", "params": [{"name": "chat_id", "type": "int|str", "optional": True}, {"name": "message_id", "type": "int", "optional": True}, {"name": "inline_message_id", "type": "str", "optional": True}, {"name": "text", "type": "str"}, {"name": "reply_markup", "type": "InlineKeyboardMarkup|dict[str,Any]", "optional": True}]},
        {"name": "deleteMessage", "returns": "bool", "params": [{"name": "chat_id", "type": "int|str"}, {"name": "message_id", "type": "int"}]},
    ],
}


def snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def py_t(tp: str, opt: bool = False) -> str:
    raw = tp.replace("Integer", "int").replace("String", "str").replace("Boolean", "bool").replace("Float", "float").replace("True", "bool")
    raw = raw.replace("Array of ", "list[").replace("]", "]")
    if raw.startswith("list[") and not raw.endswith("]"):
        raw += "]"
    raw = raw.replace(" or ", "|").replace("'", "")
    raw = raw.replace("InputFile", "bytes|str")
    raw = raw.replace("Object", "dict[str,Any]")
    raw = raw.replace("Array", "list")
    if "|" in raw:
        parts = [x.strip() for x in raw.split("|") if x.strip()]
        raw = "|".join(parts)
    if opt and "None" not in raw:
        raw = f"{raw}|None"
    return raw or "Any"


class BotHtml(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_h4 = False
        self.in_table = False
        self.cur = ""
        self.buf: list[str] = []
        self.head: list[str] = []
        self.rows: list[list[str]] = []
        self.row: list[str] = []
        self.cell: list[str] = []
        self.kind = ""
        self.methods: list[dict[str, Any]] = []
        self.types: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "h4":
            self.in_h4 = True
            self.buf = []
        elif tag == "table":
            self.in_table = True
            self.rows = []
            self.head = []
        elif self.in_table and tag == "tr":
            self.row = []
        elif self.in_table and tag in {"td", "th"}:
            self.cell = []
            self.kind = tag

    def handle_endtag(self, tag: str) -> None:
        if tag == "h4" and self.in_h4:
            self.in_h4 = False
            self.cur = "".join(self.buf).strip()
        elif tag in {"td", "th"} and self.in_table:
            txt = " ".join("".join(self.cell).split())
            self.row.append(txt)
        elif tag == "tr" and self.in_table and self.row:
            if self.kind == "th" and not self.head:
                self.head = self.row[:]
            else:
                self.rows.append(self.row[:])
        elif tag == "table" and self.in_table:
            self.in_table = False
            self.flush()

    def handle_data(self, data: str) -> None:
        if self.in_h4:
            self.buf.append(data)
        if self.in_table and self.kind:
            self.cell.append(data)

    def flush(self) -> None:
        low = self.cur.lower()
        if not self.head or not self.rows:
            return
        if "parameter" in " ".join(x.lower() for x in self.head):
            params = []
            for row in self.rows:
                if len(row) < 2:
                    continue
                opt = len(row) > 2 and "optional" in row[2].lower()
                params.append({"name": snake(row[0]), "type": py_t(row[1], opt), "optional": opt})
            ret = "Any"
            m = re.search(r"returns? ([A-Za-z0-9_ \[\]or]+)", low)
            if m:
                ret = py_t(m.group(1))
            self.methods.append({"name": self.cur, "returns": ret, "params": params})
            return
        if "field" in " ".join(x.lower() for x in self.head):
            fields = []
            for row in self.rows:
                if len(row) < 2:
                    continue
                opt = len(row) > 2 and "optional" in row[2].lower()
                fields.append({"name": snake(row[0]), "type": py_t(row[1], opt), "optional": opt})
            self.types.append({"name": self.cur, "fields": fields})


def load_schema(src: str | None) -> dict[str, Any]:
    if src:
        raw = Path(src).read_text(encoding="utf-8")
    else:
        try:
            with urllib.request.urlopen(BOT_URL, timeout=20) as r:
                raw = r.read().decode("utf-8", "replace")
        except Exception:
            return FALLBACK
    txt = raw.strip()
    if txt.startswith("{"):
        obj = json.loads(txt)
        if "types" in obj and "methods" in obj:
            return obj
    p = BotHtml()
    p.feed(raw)
    if p.types or p.methods:
        return {"types": p.types or FALLBACK["types"], "methods": p.methods or FALLBACK["methods"]}
    return FALLBACK


def gen_types(spec: dict[str, Any]) -> str:
    out = [HDR, "from __future__ import annotations\n", "from typing import Any\n\n", "def dump(v: Any) -> Any:\n", "    if hasattr(v, \"to_dict\"):\n", "        return v.to_dict()\n", "    if isinstance(v, list):\n", "        return [dump(x) for x in v]\n", "    if isinstance(v, dict):\n", "        return {k: dump(x) for k, x in v.items() if x is not None}\n", "    return v\n\n"]
    names = []
    for tp in spec["types"]:
        name = tp["name"]
        names.append(name)
        fields = tp.get("fields", [])
        slots = ", ".join(repr(x["name"]) for x in fields)
        sig = []
        body = []
        rows = []
        for f in fields:
            ann = py_t(f["type"], f.get("optional", False))
            sig.append(f"{f['name']}: {ann} = None" if f.get("optional") else f"{f['name']}: {ann}")
            body.append(f"        self.{f['name']} = {f['name']}\n")
            rows.append(f"            \"{f['name']}\": dump(self.{f['name']}),\n")
        out.append(f"class {name}:\n")
        out.append(f"    __slots__ = ({slots})\n" if slots else "    __slots__ = ()\n")
        out.append(f"    def __init__(self, {', '.join(sig)}) -> None:\n" if sig else "    def __init__(self) -> None:\n")
        out.extend(body or ["        return None\n"])
        out.append("\n    def to_dict(self) -> dict[str, Any]:\n        return {\n")
        out.extend(rows)
        out.append("        }\n\n")
    out.append(f"__all__ = {names!r}\n")
    return "".join(out)


def gen_methods(spec: dict[str, Any]) -> str:
    out = [HDR, "from __future__ import annotations\n", "from typing import Any\n", "from goygram.api.types import *\n\n", "def dump(v: Any) -> Any:\n", "    if hasattr(v, \"to_dict\"):\n", "        return v.to_dict()\n", "    if isinstance(v, list):\n", "        return [dump(x) for x in v]\n", "    if isinstance(v, dict):\n", "        return {k: dump(x) for k, x in v.items() if x is not None}\n", "    return v\n\n", "class BotAPI:\n", "    __slots__ = (\"net\",)\n", "    def __init__(self, net: Any) -> None:\n", "        self.net = net\n\n", "    async def call(self, meth: str, **kw: Any) -> Any:\n", "        return await self.net.req(meth, dump(kw))\n\n", "    def __getattr__(self, name: str) -> Any:\n", "        async def dyn(**kw: Any) -> Any:\n", "            parts = name.split(\"_\")\n", "            meth = parts[0] + \"\".join(x[:1].upper() + x[1:] for x in parts[1:])\n", "            return await self.call(meth, **kw)\n", "        return dyn\n\n"]
    for m in spec["methods"]:
        py_name = snake(m["name"])
        params = m.get("params", [])
        req = [p for p in params if not p.get("optional")]
        opt = [p for p in params if p.get("optional")]
        sig = []
        body = ["        data: dict[str, Any] = {}\n"]
        for p in req + opt:
            ann = py_t(p["type"], p.get("optional", False))
            sig.append(f"{p['name']}: {ann} = None" if p.get("optional") else f"{p['name']}: {ann}")
            body.append(f"        if {p['name']} is not None:\n")
            body.append(f"            data[\"{p['name']}\"] = dump({p['name']})\n")
        head = f"    async def {py_name}(self" + (", " + ", ".join(sig) if sig else "") + f") -> {py_t(m.get('returns', 'Any'))}:\n"
        out.append(head)
        out.extend(body)
        out.append(f"        return await self.net.req(\"{m['name']}\", data)\n\n")
    out.append("__all__ = [\"BotAPI\"]\n")
    return "".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default=None)
    ap.add_argument("--out", dest="out", default=str(OUT))
    ns = ap.parse_args()
    spec = load_schema(ns.src)
    out = Path(ns.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "types.py").write_text(gen_types(spec), encoding="utf-8")
    (out / "methods.py").write_text(gen_methods(spec), encoding="utf-8")


if __name__ == "__main__":
    main()
