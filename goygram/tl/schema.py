# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations
import struct
from typing import Any

def pad4(n: int) -> int:
    return (4 - (n % 4)) % 4

def enc_bytes(v: bytes) -> bytes:
    n = len(v)
    if n < 254:
        head = bytes([n])
        raw = head + v
        return raw + (b"\x00" * pad4(len(raw)))
    head = bytes([254]) + n.to_bytes(3, "little")
    raw = head + v
    return raw + (b"\x00" * pad4(len(raw)))

def enc_str(v: str) -> bytes:
    return enc_bytes(v.encode())

def enc_vec(tp: str, vals: list[Any]) -> bytes:
    raw = struct.pack("<I", 0x1cb5c415)
    raw += struct.pack("<i", len(vals))
    for item in vals:
        raw += enc_val(tp, item)
    return raw

def enc_val(tp: str, v: Any) -> bytes:
    if tp == "int":
        return struct.pack("<i", int(v))
    if tp == "long":
        return struct.pack("<q", int(v))
    if tp == "int128":
        raw = bytes(v)
        if len(raw) != 16:
            raise ValueError("int128 must be 16 bytes")
        return raw
    if tp == "int256":
        raw = bytes(v)
        if len(raw) != 32:
            raise ValueError("int256 must be 32 bytes")
        return raw
    if tp == "double":
        return struct.pack("<d", float(v))
    if tp == "string":
        return enc_str(str(v))
    if tp == "bytes":
        return enc_bytes(bytes(v))
    if tp == "Bool":
        return struct.pack("<I", 0x997275b5 if v else 0xbc799737)
    if tp.startswith("Vector<") and tp.endswith(">"):
        return enc_vec(tp[7:-1], list(v))
    if hasattr(v, "to_bytes"):
        return v.to_bytes()
    raise TypeError(tp)

class TlObj:
    __slots__ = ()
    cid = 0
    res = ""
    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__slots__}
    def to_bytes(self) -> bytes:
        raise RuntimeError("abstract tl obj")

class ResPQ(TlObj):
    __slots__ = ('nonce', 'server_nonce', 'pq', 'server_public_key_fingerprints')
    cid = 0x05162463
    res = 'ResPQ'
    def __init__(self, nonce: Any, server_nonce: Any, pq: Any, server_public_key_fingerprints: Any) -> None:
        self.nonce = nonce
        self.server_nonce = server_nonce
        self.pq = pq
        self.server_public_key_fingerprints = server_public_key_fingerprints
    def to_bytes(self) -> bytes:
        raw = struct.pack("<I", self.cid)
        raw += enc_val('int128', self.nonce)
        raw += enc_val('int128', self.server_nonce)
        raw += enc_val('bytes', self.pq)
        raw += enc_val('Vector<long>', self.server_public_key_fingerprints)
        return raw

class PQInnerData(TlObj):
    __slots__ = ('pq', 'p', 'q', 'nonce', 'server_nonce', 'new_nonce')
    cid = 0x83c95aec
    res = 'P_Q_inner_data'
    def __init__(self, pq: Any, p: Any, q: Any, nonce: Any, server_nonce: Any, new_nonce: Any) -> None:
        self.pq = pq
        self.p = p
        self.q = q
        self.nonce = nonce
        self.server_nonce = server_nonce
        self.new_nonce = new_nonce
    def to_bytes(self) -> bytes:
        raw = struct.pack("<I", self.cid)
        raw += enc_val('bytes', self.pq)
        raw += enc_val('bytes', self.p)
        raw += enc_val('bytes', self.q)
        raw += enc_val('int128', self.nonce)
        raw += enc_val('int128', self.server_nonce)
        raw += enc_val('int256', self.new_nonce)
        return raw

class Ping(TlObj):
    __slots__ = ('ping_id')
    cid = 0x7abe77ec
    res = 'Pong'
    def __init__(self, ping_id: Any) -> None:
        self.ping_id = ping_id
    def to_bytes(self) -> bytes:
        raw = struct.pack("<I", self.cid)
        raw += enc_val('long', self.ping_id)
        return raw

class MsgsAck(TlObj):
    __slots__ = ('msg_ids')
    cid = 0x62d6b459
    res = 'MsgsAck'
    def __init__(self, msg_ids: Any) -> None:
        self.msg_ids = msg_ids
    def to_bytes(self) -> bytes:
        raw = struct.pack("<I", self.cid)
        raw += enc_val('Vector<long>', self.msg_ids)
        return raw

class InvokeWithLayer(TlObj):
    __slots__ = ('layer', 'query')
    cid = 0xda9b0d0d
    res = 'X'
    def __init__(self, layer: Any, query: Any) -> None:
        self.layer = layer
        self.query = query
    def to_bytes(self) -> bytes:
        raw = struct.pack("<I", self.cid)
        raw += enc_val('int', self.layer)
        raw += enc_val('bytes', self.query)
        return raw

class Ping(TlObj):
    __slots__ = ('ping_id')
    cid = 0x7abe77ec
    res = 'Pong'
    def __init__(self, ping_id: Any) -> None:
        self.ping_id = ping_id
    def to_bytes(self) -> bytes:
        raw = struct.pack("<I", self.cid)
        raw += enc_val('long', self.ping_id)
        return raw

REG = {
    0x05162463: ResPQ,
    0x83c95aec: PQInnerData,
    0x7abe77ec: Ping,
    0x62d6b459: MsgsAck,
    0xda9b0d0d: InvokeWithLayer,
    0x7abe77ec: Ping,
}

__all__ = ['InvokeWithLayer', 'MsgsAck', 'PQInnerData', 'Ping', 'REG', 'ResPQ', 'TlObj', 'enc_val']
