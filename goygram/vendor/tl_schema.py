# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

import json
import re
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("goygram.tl.schema_loader")

VECTOR_RE = re.compile(r"^Vector<(.*)>$")
FLAG_RE = re.compile(r"^flags\.(\d+)\?(.+)$")


def _parse_field_type(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    m = VECTOR_RE.match(raw)
    if m:
        inner = _parse_field_type(m.group(1))
        return {"type": "Vector", "is_vector": True, "vector_inner": inner["type"]}

    m = FLAG_RE.match(raw)
    if m:
        bit = int(m.group(1))
        inner_raw = m.group(2)
        inner = _parse_field_type(inner_raw)
        inner["flag_bit"] = bit
        return inner

    if raw in {"true", "True"}:
        return {"type": "true", "is_bare": True}

    return {"type": raw}


def _parse_fields(fields_str: str) -> tuple[list[dict[str, Any]], bool]:
    result: list[dict[str, Any]] = []
    has_flags = False
    tokens = fields_str.strip().split()
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if ":" not in token:
            i += 1
            continue
        name, type_str = token.split(":", 1)
        field = _parse_field_type(type_str)
        field["name"] = name
        if type_str == "#":
            has_flags = True
        result.append(field)
        i += 1
    return result, has_flags


def parse_api_tl(path: str | Path) -> dict[str, dict[str, Any]]:
    raw = Path(path).read_text(encoding="utf-8")
    in_functions = False
    methods: dict[str, dict[str, Any]] = {}

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith("---functions---"):
            in_functions = True
            continue
        if line.startswith("---types---"):
            in_functions = False
            continue
        if not in_functions:
            continue

        line = line.rstrip(";")
        m = re.match(
            r"^([A-Za-z0-9_.]+)#([0-9a-fA-F]+)\s*(.*?)\s*=\s*.+$",
            line,
        )
        if not m:
            continue

        name = m.group(1)
        cid = int(m.group(2), 16)
        rest = m.group(3).strip()

        fields, has_flags = _parse_fields(rest)

        methods[name] = {
            "cid": cid,
            "fields": fields,
            "has_flags": has_flags,
        }

    log.info("Parsed %d TL methods from %s", len(methods), path)
    return methods


def load_schema_into_rust(ext_module: Any, api_tl_path: str | Path) -> dict[str, dict[str, Any]]:
    methods = parse_api_tl(api_tl_path)
    schema_json = json.dumps(methods, separators=(",", ":"), ensure_ascii=False)
    ext_module.load_schema(schema_json)
    return methods
