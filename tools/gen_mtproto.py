# Copyleft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

HDR = "# Copyleft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.\n"
OUT = Path(__file__).resolve().parents[1] / "goygram" / "tl"
FALLBACK = """
resPQ#05162463 nonce:int128 server_nonce:int128 pq:bytes server_public_key_fingerprints:Vector<long> = ResPQ;
p_q_inner_data#83c95aec pq:bytes p:bytes q:bytes nonce:int128 server_nonce:int128 new_nonce:int256 = P_Q_inner_data;
ping#7abe77ec ping_id:long = Pong;
msgs_ack#62d6b459 msg_ids:Vector<long> = MsgsAck;
invokeWithLayer#da9b0d0d layer:int query:bytes = X;
---functions---
ping#7abe77ec ping_id:long = Pong;
"""


def split_tl(raw: str) -> list[dict[str, Any]]:
    kind = "ctor"
    out: list[dict[str, Any]] = []
    for ln in raw.splitlines():
        line = ln.strip()
        if not line:
            continue
        if line.startswith("---functions---"):
            kind = "func"
            continue
        if line.startswith("---types---"):
            kind = "ctor"
            continue
        if line.startswith("Copyleft 2026 "):
            continue
        line = line.rstrip(";")
        m = re.match(r"([A-Za-z0-9_.]+)#([0-9a-fA-F]+)\s*(.*?)\s*=\s*([A-Za-z0-9_.<>]+)$", line)
        if not m:
            continue
        name, cid, rest, res = m.groups()
        fields = []
        if rest:
            for item in rest.split():
                if ":" not in item:
                    continue
                k, v = item.split(":", 1)
                fields.append({"name": k, "type": v})
        out.append({"kind": kind, "name": name, "id": int(cid, 16), "res": res, "fields": fields})
    return out


def gen(schema: list[dict[str, Any]]) -> str:
    out = [
        HDR,
        "from __future__ import annotations\n",
        "import struct\n",
        "from typing import Any\n\n",
        "def pad4(n: int) -> int:\n",
        "    return (4 - (n % 4)) % 4\n\n",
        "def enc_bytes(v: bytes) -> bytes:\n",
        "    n = len(v)\n",
        "    if n < 254:\n",
        "        head = bytes([n])\n",
        "        raw = head + v\n",
        "        return raw + (b\"\\x00\" * pad4(len(raw)))\n",
        "    head = bytes([254]) + n.to_bytes(3, \"little\")\n",
        "    raw = head + v\n",
        "    return raw + (b\"\\x00\" * pad4(len(raw)))\n\n",
        "def enc_str(v: str) -> bytes:\n",
        "    return enc_bytes(v.encode())\n\n",
        "def enc_vec(tp: str, vals: list[Any]) -> bytes:\n",
        "    raw = struct.pack(\"<I\", 0x1cb5c415)\n",
        "    raw += struct.pack(\"<i\", len(vals))\n",
        "    for item in vals:\n",
        "        raw += enc_val(tp, item)\n",
        "    return raw\n\n",
        "def enc_val(tp: str, v: Any) -> bytes:\n",
        "    if tp == \"int\":\n",
        "        return struct.pack(\"<i\", int(v))\n",
        "    if tp == \"long\":\n",
        "        return struct.pack(\"<q\", int(v))\n",
        "    if tp == \"int128\":\n",
        "        raw = bytes(v)\n",
        "        if len(raw) != 16:\n",
        "            raise ValueError(\"int128 must be 16 bytes\")\n",
        "        return raw\n",
        "    if tp == \"int256\":\n",
        "        raw = bytes(v)\n",
        "        if len(raw) != 32:\n",
        "            raise ValueError(\"int256 must be 32 bytes\")\n",
        "        return raw\n",
        "    if tp == \"double\":\n",
        "        return struct.pack(\"<d\", float(v))\n",
        "    if tp == \"string\":\n",
        "        return enc_str(str(v))\n",
        "    if tp == \"bytes\":\n",
        "        return enc_bytes(bytes(v))\n",
        "    if tp == \"Bool\":\n",
        "        return struct.pack(\"<I\", 0x997275b5 if v else 0xbc799737)\n",
        "    if tp.startswith(\"Vector<\") and tp.endswith(\">\"):\n",
        "        return enc_vec(tp[7:-1], list(v))\n",
        "    if hasattr(v, \"to_bytes\"):\n",
        "        return v.to_bytes()\n",
        "    raise TypeError(tp)\n\n",
        "class TlObj:\n",
        "    __slots__ = ()\n",
        "    cid = 0\n",
        "    res = \"\"\n",
        "    def to_dict(self) -> dict[str, Any]:\n",
        "        return {k: getattr(self, k) for k in self.__slots__}\n",
        "    def to_bytes(self) -> bytes:\n",
        "        raise RuntimeError(\"abstract tl obj\")\n\n",
    ]
    names = []
    for item in schema:
        cls = "".join(x[:1].upper() + x[1:] for x in re.split(r"[._]", item["name"]) if x)
        names.append(cls)
        slots = ", ".join(repr(f["name"]) for f in item["fields"])
        sig = ", ".join(f"{f['name']}: Any" for f in item["fields"])
        out.append(f"class {cls}(TlObj):\n")
        out.append(f"    __slots__ = ({slots})\n" if slots else "    __slots__ = ()\n")
        out.append(f"    cid = 0x{item['id']:08x}\n")
        out.append(f"    res = {item['res']!r}\n")
        out.append(f"    def __init__(self, {sig}) -> None:\n" if sig else "    def __init__(self) -> None:\n")
        out.extend([f"        self.{f['name']} = {f['name']}\n" for f in item["fields"]] or ["        return None\n"])
        out.append("    def to_bytes(self) -> bytes:\n")
        out.append("        raw = struct.pack(\"<I\", self.cid)\n")
        for f in item["fields"]:
            out.append(f"        raw += enc_val({f['type']!r}, self.{f['name']})\n")
        out.append("        return raw\n\n")
    out.append("REG = {\n")
    for item in schema:
        cls = "".join(x[:1].upper() + x[1:] for x in re.split(r"[._]", item["name"]) if x)
        out.append(f"    0x{item['id']:08x}: {cls},\n")
    out.append("}\n\n")
    out.append(f"__all__ = {sorted(set(names + ['TlObj', 'REG', 'enc_val']))!r}\n")
    return "".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default=None)
    ap.add_argument("--out", dest="out", default=str(OUT))
    ns = ap.parse_args()
    raw = Path(ns.src).read_text(encoding="utf-8") if ns.src else FALLBACK
    schema = split_tl(raw)
    out = Path(ns.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "schema.py").write_text(gen(schema), encoding="utf-8")


if __name__ == "__main__":
    main()
