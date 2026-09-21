# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

import argparse
import json
import keyword
import re
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

from goygram.protocol.tl_schema import parse_api_tl
from goygram.schema_manager import CACHE_MTPROTO_PATH, CACHE_SCHEMA_PATH, MTPROTO_SCHEMA_URL, SCHEMA_URL

BOT_API_JSON = "https://raw.githubusercontent.com/PaulSonOfLars/telegram-bot-api-spec/main/api.json"
JsonMap = Dict[str, Any]
FieldSpec = Dict[str, Any]
NamedFields = Tuple[str, List[FieldSpec]]

PRIM = {
    "#": "int",
    "int": "int",
    "Int": "int",
    "long": "int",
    "Long": "int",
    "double": "float",
    "Double": "float",
    "string": "str",
    "String": "str",
    "bytes": "str",
    "Bytes": "str",
    "true": "bool",
    "True": "bool",
    "Bool": "bool",
    "boolTrue": "bool",
    "boolFalse": "bool",
    "int128": "str",
    "int256": "str",
}


def _fetch(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "goygram-stubgen"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def _ident(name: str) -> str:
    out = re.sub(r"[^0-9A-Za-z_]", "_", name)
    if not out or out[0].isdigit():
        out = "_" + out
    return out


def _py_type(raw: str, known: set[str]) -> str:
    if raw in PRIM:
        return PRIM[raw]
    ident = _ident(raw)
    if ident in known:
        return ident
    return "Any"


def _field_ann(field: FieldSpec, known: set[str]) -> str:
    if field.get("is_vector"):
        inner = field.get("vector_inner") or "int"
        if field.get("vector_inner_is_vector"):
            return f"list[list[{_py_type(inner, known)}]]"
        return f"list[{_py_type(inner, known)}]"
    raw = str(field.get("type") or "Any")
    if raw in PRIM:
        return PRIM[raw]
    if raw in {"int", "str", "bool", "float", "Any"} or "|" in raw or raw.startswith("list["):
        return raw
    return _py_type(raw, known)


def _emit_typed(name: str, fields: List[FieldSpec], known: set[str], tag: str | None) -> str:
    ident = _ident(name)
    rows: list[tuple[str, str]] = []
    if tag is not None:
        rows.append(("_", f'Literal["{tag}"]'))
    bad = False
    for f in fields:
        fname = str(f.get("name") or "")
        if not fname or fname == "_":
            continue
        if not fname.isidentifier() or keyword.iskeyword(fname):
            bad = True
            break
        rows.append((fname, _field_ann(f, known)))
    if bad:
        bits = [f'"_": "{tag}"'] if tag is not None else []
        for f in fields:
            fname = str(f.get("name") or "")
            if not fname or fname == "_":
                continue
            bits.append(f'"{fname}": "{_field_ann(f, known)}"')
        body = ", ".join(bits) if bits else '"id": "int"'
        return f'{ident} = TypedDict("{ident}", {{{body}}}, total=False)\n'
    lines = [f"class {ident}(TypedDict, total=False):"]
    if not rows:
        lines.append("    pass")
    else:
        for key, ann in rows:
            lines.append(f"    {key}: {ann}")
    return "\n".join(lines) + "\n"


def _load_tl() -> JsonMap:
    api = CACHE_SCHEMA_PATH.read_text(encoding="utf-8") if CACHE_SCHEMA_PATH.exists() else _fetch(SCHEMA_URL)
    mtp = CACHE_MTPROTO_PATH.read_text(encoding="utf-8") if CACHE_MTPROTO_PATH.exists() else _fetch(MTPROTO_SCHEMA_URL)
    merged = mtp + "\n---types---\n" + api
    with tempfile.NamedTemporaryFile("w", suffix=".tl", delete=False, encoding="utf-8") as handle:
        handle.write(merged)
        path = handle.name
    try:
        return parse_api_tl(path)
    finally:
        Path(path).unlink(missing_ok=True)


def _bot_ann(types: List[Any], known: set[str]) -> str:
    parts: list[str] = []
    for t in types:
        t = str(t).strip()
        if t.startswith("Array of "):
            parts.append(f"list[{_bot_ann([t[9:]], known)}]")
            continue
        mapped = {"Integer": "int", "String": "str", "Boolean": "bool", "Float": "float", "True": "bool"}.get(t)
        if mapped:
            parts.append(mapped)
            continue
        ident = _ident(t)
        parts.append(ident if ident in known else "Any")
    out: list[str] = []
    for p in parts:
        if p not in out:
            out.append(p)
    return out[0] if len(out) == 1 else " | ".join(out) if out else "Any"


def _bot_fields(spec: JsonMap, known: set[str]) -> List[FieldSpec]:
    fields: List[FieldSpec] = []
    for p in spec.get("fields") or []:
        if not isinstance(p, dict):
            continue
        pname = p.get("name")
        if not pname:
            continue
        fields.append({"name": pname, "type": _bot_ann(p.get("types") or [], known)})
    return fields


def _bot_spec() -> Tuple[List[NamedFields], List[NamedFields]]:
    raw = json.loads(_fetch(BOT_API_JSON))
    types = raw.get("types") or {}
    methods = raw.get("methods") or {}
    known = {_ident(n) for n in list(types) + list(methods)}
    t_out = [(n, _bot_fields(spec, known)) for n, spec in types.items() if isinstance(spec, dict)]
    m_out = [(n, _bot_fields(spec, known)) for n, spec in methods.items() if isinstance(spec, dict)]
    return t_out, m_out


def _snake(name: str) -> str:
    out: list[str] = []
    for i, c in enumerate(name):
        if c.isupper() and i:
            out.append("_")
        out.append(c.lower())
    return "".join(out)


def _aliases(raw: str) -> list[str]:
    us = raw.replace(".", "_")
    if "." in raw:
        ns, rest = raw.split(".", 1)
        snake = ns + "_" + _snake(rest)
    else:
        snake = _snake(raw)
    names = [us, snake, "mt_" + us, "mt_" + snake]
    out: list[str] = []
    for n in names:
        ident = _ident(n)
        if ident not in out:
            out.append(ident)
    return out


def _core_pyi(client_py: Path) -> list[str]:
    import ast
    tree = ast.parse(client_py.read_text(encoding="utf-8"))
    lines: list[str] = []
    seen: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name not in {"AppCore", "GoyGram"}:
            continue
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if item.name.startswith("_") and item.name != "__init__":
                continue
            if item.name in seen:
                continue
            seen.add(item.name)
            prefix = "async " if isinstance(item, ast.AsyncFunctionDef) else ""
            lines.append(f"    {prefix}def {item.name}(self, *args: Any, **kwargs: Any) -> Any: ...")
    return lines


def generate(out_dir: Path) -> Path:
    schema = _load_tl()
    ctors: Dict[str, FieldSpec] = schema.get("constructors") or {}
    methods: Dict[str, FieldSpec] = schema.get("methods") or {}
    known = {_ident(n) for n in list(ctors) + list(methods)}
    chunks = [
        "# generated by python -m goygram.stubgen - not part of the runtime",
        "from __future__ import annotations",
        "from typing import Any, Literal, TypedDict, Unpack, overload",
        "",
    ]
    emitted: Dict[str, str] = {}
    for name, spec in sorted(ctors.items()):
        ident = _ident(name)
        chunks.append(_emit_typed(name, spec.get("fields") or [], known, name))
        chunks.append("")
        emitted[ident] = ident
    for name, spec in sorted(methods.items()):
        ident = _ident(name)
        chunks.append(_emit_typed(name, spec.get("fields") or [], known, None))
        chunks.append("")
        emitted[ident] = ident
        for alias in _aliases(name):
            if alias != ident and alias not in emitted:
                chunks.append(f"{alias} = {ident}")
                emitted[alias] = ident
        chunks.append("")
    bot_methods: List[NamedFields] = []
    try:
        bot_types, bot_methods = _bot_spec()
        for name, _fields in bot_types + bot_methods:
            known.add(_ident(name))
        for name, fields in bot_types:
            ident = _ident(name)
            chunks.append(_emit_typed(name, fields, known, None))
            chunks.append("")
            emitted[ident] = ident
        for name, fields in bot_methods:
            ident = _ident(name)
            chunks.append(_emit_typed(name, fields, known, None))
            chunks.append("")
            emitted[ident] = ident
            for alias in _aliases(name):
                if alias != ident and alias not in emitted:
                    chunks.append(f"{alias} = {ident}")
                    emitted[alias] = ident
            chunks.append("")
    except Exception as exc:
        print(f"bot api spec skipped: {exc}", file=sys.stderr)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "telegram.py"
    path.write_text("\n".join(chunks), encoding="utf-8")
    client_src = Path(__file__).resolve().parent / "client.py"
    rpc: list[str] = [
        "# generated by python -m goygram.stubgen - not part of the runtime",
        "from __future__ import annotations",
        "from typing import Any, Literal, Unpack, overload",
        "from .telegram import *",
        "",
        "class GoyGram:",
    ]
    used_fn: set[str] = set()
    if client_src.exists():
        core = [ln for ln in _core_pyi(client_src) if "def mt_req(" not in ln and "def bot_req(" not in ln]
        rpc.extend(core)
        for line in core:
            m = re.search(r"def (\w+)\(", line)
            if m:
                used_fn.add(m.group(1))
    for name, spec in sorted(methods.items()):
        ident = _ident(name)
        for alias in _aliases(name):
            if alias in used_fn:
                continue
            used_fn.add(alias)
            rpc.append(f"    async def {alias}(self, **kwargs: Unpack[{ident}]) -> Any: ...")
    for name, _fields in bot_methods:
        ident = _ident(name)
        for alias in _aliases(name):
            if alias in used_fn:
                continue
            used_fn.add(alias)
            rpc.append(f"    async def {alias}(self, **kwargs: Unpack[{ident}]) -> Any: ...")
    for name, spec in sorted(methods.items()):
        ident = _ident(name)
        lits = ", ".join(f'"{x}"' for x in dict.fromkeys([name, ident, *_aliases(name)]))
        rpc.append("    @overload")
        rpc.append(f"    async def mt_req(self, act: Literal[{lits}], /, **kwargs: Unpack[{ident}]) -> Any: ...")
    rpc.append("    async def mt_req(self, act: str, /, **kwargs: Any) -> Any: ...")
    for name, _fields in bot_methods:
        ident = _ident(name)
        lits = ", ".join(f'"{x}"' for x in dict.fromkeys([name, ident, *_aliases(name)]))
        rpc.append("    @overload")
        rpc.append(f"    async def bot_req(self, act: Literal[{lits}], /, **kwargs: Unpack[{ident}]) -> Any: ...")
    rpc.append("    async def bot_req(self, act: str, /, **kwargs: Any) -> Any: ...")
    rpc.append("")
    (out_dir / "client.pyi").write_text("\n".join(rpc), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m goygram.stubgen")
    p.add_argument("--out", default="", help="directory (default: installed goygram package)")
    args = p.parse_args(argv)
    if args.out:
        dest = Path(args.out)
    else:
        dest = Path(__file__).resolve().parent
    path = generate(dest)
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
    print(f"wrote {path}")
    print(f"wrote {path.parent / 'client.pyi'}")
    print("from goygram.telegram import message, messages_sendMessage, messages_send_message, sendMessage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
