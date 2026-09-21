# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

import re as _re
import importlib
from html import unescape as _unescape
from typing import Any


def human_size(n: Any) -> str:
    try:
        v = float(n)
    except (TypeError, ValueError):
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(v) < 1024 or unit == "TB":
            return f"{v:.1f} {unit}" if unit != "B" else f"{int(v)} B"
        v /= 1024
    return f"{v:.1f} TB"


def human_duration(seconds: Any) -> str:
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return "?"
    if s < 60:
        return f"{s}s"
    m, sec = divmod(s, 60)
    if m < 60:
        return f"{m}m {sec}s"
    h, m = divmod(m, 60)
    if h < 24:
        return f"{h}h {m}m"
    d, h = divmod(h, 24)
    return f"{d}d {h}h"


def chunk_text(text: str, size: int = 4096, tail: str = "\n\n") -> list[str]:
    if size <= 0:
        raise ValueError("size must be positive")
    if len(text) <= size:
        return [text] if text else []
    out: list[str] = []
    cur = text
    while cur:
        if len(cur) <= size:
            out.append(cur)
            break
        cut = cur.rfind("\n", 0, size)
        if cut < size // 2:
            cut = cur.rfind(" ", 0, size)
        if cut < size // 2:
            cut = size
        out.append(cur[:cut].rstrip())
        cur = cur[cut:].lstrip()
    return [c for c in out if c]


class Html:
    __slots__ = ()

    def b(self, s: Any) -> str:
        return f"<b>{s}</b>"

    bold = b

    def i(self, s: Any) -> str:
        return f"<i>{s}</i>"

    italic = i

    def u(self, s: Any) -> str:
        return f"<u>{s}</u>"

    underline = u

    def s(self, s: Any) -> str:
        return f"<s>{s}</s>"

    strike = s
    strikethrough = s

    def code(self, s: Any) -> str:
        return f"<code>{s}</code>"

    def pre(self, s: Any, lang: str | None = None) -> str:
        if lang:
            return f'<pre><code class="language-{lang}">{s}</code></pre>'
        return f"<pre>{s}</pre>"

    def link(self, s: Any, url: str) -> str:
        return f'<a href="{url}">{s}</a>'

    def mention(self, uid: Any, name: str) -> str:
        return f'<a href="tg://user?id={uid}">{name}</a>'

    def spoiler(self, s: Any) -> str:
        return f"<tg-spoiler>{s}</tg-spoiler>"

    def quote(self, s: Any, expandable: bool = False) -> str:
        return f'<blockquote expandable="{str(expandable).lower()}">{s}</blockquote>'

    def emoji(self, eid: Any) -> str:
        return f'<tg-emoji emoji-id="{eid}">❤</tg-emoji>'

    def join(self, *parts: Any, sep: str = " ") -> str:
        return sep.join(str(p) for p in parts if p not in (None, ""))


html = Html()


def md5(s: str) -> str:
    import hashlib
    return hashlib.md5(s.encode()).hexdigest()


def now_ts() -> int:
    import time
    return int(time.time())


def plural_ru(n: int, one: str, few: str, many: str) -> str:
    n = abs(n) % 100
    if 11 <= n <= 14:
        return many
    d = n % 10
    if d == 1:
        return one
    if 2 <= d <= 4:
        return few
    return many


def parse_entities_html(text: str, entities: list[dict[str, Any]] | None) -> str:
    if not entities:
        return _esc(text)
    marks: list[tuple[int, int, str, dict[str, Any]]] = []
    for ent in entities:
        et = ent.get("type", "")
        off = int(ent.get("offset", 0))
        ln = int(ent.get("length", 0))
        marks.append((off, off + ln, et, ent))
    marks.sort(key=lambda m: m[0])
    out: list[str] = []
    pos = 0
    for start, end, et, ent in marks:
        if start < pos:
            continue
        out.append(_esc(text[pos:start]))
        frag = _esc(text[start:end])
        out.append(_apply_ent(frag, et, ent))
        pos = end
    out.append(_esc(text[pos:]))
    return "".join(out)


def _apply_ent(frag: str, et: str, ent: dict[str, Any]) -> str:
    if et in ("bold",):
        return f"<b>{frag}</b>"
    if et in ("italic",):
        return f"<i>{frag}</i>"
    if et in ("underline",):
        return f"<u>{frag}</u>"
    if et in ("strikethrough",):
        return f"<s>{frag}</s>"
    if et in ("code",):
        return f"<code>{frag}</code>"
    if et in ("pre",):
        return f"<pre>{frag}</pre>"
    if et == "text_link":
        return f'<a href="{_attr(ent.get("url", ""))}">{frag}</a>'
    if et == "url":
        return f'<a href="{_attr(frag)}">{frag}</a>'
    if et == "email":
        return f'<a href="mailto:{frag}">{frag}</a>'
    if et == "phone":
        return f'<a href="tel:{frag}">{frag}</a>'
    if et == "text_mention":
        u = ent.get("user") or {}
        return f'<a href="tg://user?id={u.get("id", "")}">{frag}</a>'
    if et == "spoiler":
        return f"<tg-spoiler>{frag}</tg-spoiler>"
    if et == "blockquote":
        return f"<blockquote>{frag}</blockquote>"
    return frag


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _attr(s: Any) -> str:
    return _esc(str(s)).replace('"', "&quot;")


def json_dumps(obj: Any, indent: int | None = 2) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, indent=indent)


def progress_bar(done: int, total: int, width: int = 10) -> str:
    if total <= 0:
        return "[" + " " * width + "]"
    filled = int(width * done / total + 0.5)
    return "[" + "#" * filled + " " * (width - filled) + "]"


def code_block(s: Any, lang: str = "") -> str:
    return f"```{lang}\n{s}\n```"


def b64e(s: str | bytes) -> str:
    import base64
    if isinstance(s, str):
        s = s.encode()
    return base64.b64encode(s).decode()


def b64d(s: str) -> bytes:
    import base64
    return base64.b64decode(s)


def rand_id() -> int:
    import secrets
    return secrets.randbits(63)


def len_s(s: Any) -> int:
    return len(str(s)) if s is not None else 0


def extract_sent_message(result: Any) -> dict[str, Any] | None:
    if result is None:
        return None
    if not isinstance(result, dict):
        obj_id = getattr(result, "message_id", None) or getattr(result, "id", None)
        if obj_id is not None:
            return {"id": obj_id, "message_id": obj_id}
        return None
    inner = result.get("result") if isinstance(result.get("result"), dict) else result
    if not isinstance(inner, dict):
        return None
    for upd in inner.get("updates") or []:
        msg = upd.get("message") if isinstance(upd, dict) else None
        if isinstance(msg, dict) and msg.get("id") is not None:
            return msg
    if inner.get("_") == "updateShortSentMessage":
        return dict(inner)
    if inner.get("id") is not None:
        return inner
    if result.get("id") is not None:
        return result
    return None


_TOKEN_RE = _re.compile(r"<[^>]+>|[^<]+")
_OPEN_RE = _re.compile(r"<([a-zA-Z][\w-]*)(?:\s[^>]*)?>")
_CLOSE_RE = _re.compile(r"</([a-zA-Z][\w-]*)>")
_NAME_RE = _re.compile(r"<([a-zA-Z][\w-]*)")
_TAG_RE = _re.compile(r"</?([A-Za-z][\w-]*)([^>]*)>")
_ATTR_RE = _re.compile(r'([^\s=]+)(?:\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|(\S+)))?')
_VOID = frozenset(("br", "input", "img"))


def _u16n(s: str) -> int:
    n = 0
    for c in s:
        n += 1 + (ord(c) > 0xFFFF)
    return n


def _utf16_fix(plain: str, ents: list[dict[str, Any]]) -> None:
    n = len(plain)
    m = [0] * (n + 1)
    u = 0
    i = 0
    while i < n:
        m[i] = u
        u += 1 + (ord(plain[i]) > 0xFFFF)
        i += 1
    m[n] = u
    for e in ents:
        o = e["offset"]
        ln = e["length"]
        e["offset"] = m[o]
        e["length"] = m[o + ln] - m[o]


def split_html_text(text: str, limit: int = 4096) -> list[str]:
    if limit < 256:
        raise ValueError("limit must be at least 256")
    tokens = _TOKEN_RE.findall(text)
    parts: list[str] = []
    stack: list[str] = []

    def open_tags() -> str:
        return "".join(f"<{name}>" for name in stack)

    def close_tags() -> str:
        return "".join(f"</{name}>" for name in reversed(stack))

    def close_units() -> int:
        n = 0
        for name in stack:
            n += 3 + len(name)
        return n

    current = [open_tags()]
    size = _u16n(current[0])

    def flush() -> None:
        nonlocal current, size
        parts.append("".join(current) + close_tags())
        current = [open_tags()]
        size = _u16n(current[0])

    for token in tokens:
        if token.startswith("<"):
            opening = _OPEN_RE.fullmatch(token)
            closing = _CLOSE_RE.fullmatch(token)
            if opening is not None:
                name = opening.group(1)
                if name not in _VOID:
                    stack.append(name)
                current.append(token)
                size += _u16n(token)
                continue
            if closing is not None:
                name = closing.group(1)
                for i in range(len(stack) - 1, -1, -1):
                    if stack[i] == name:
                        stack.pop(i)
                        break
                current.append(token)
                size += _u16n(token)
                continue
            current.append(token)
            size += _u16n(token)
            continue
        while token:
            budget = max(limit - size - close_units(), 1)
            tu = _u16n(token)
            if tu <= budget:
                current.append(token)
                size += tu
                break
            cut_n = 0
            acc = 0
            for c in token:
                w = 1 + (ord(c) > 0xFFFF)
                if acc + w > budget:
                    break
                acc += w
                cut_n += 1
            current.append(token[:cut_n])
            flush()
            token = token[cut_n:]
    tail = "".join(current)
    if tail.strip() or tail != open_tags():
        parts.append(tail + close_tags())
    if not parts:
        parts.append("")
    return parts


_ENT_MAP = {
    "b": "messageEntityBold",
    "strong": "messageEntityBold",
    "i": "messageEntityItalic",
    "em": "messageEntityItalic",
    "u": "messageEntityUnderline",
    "ins": "messageEntityUnderline",
    "s": "messageEntityStrike",
    "del": "messageEntityStrike",
    "code": "messageEntityCode",
    "pre": "messageEntityPre",
    "spoiler": "messageEntitySpoiler",
    "tg-spoiler": "messageEntitySpoiler",
    "blockquote": "messageEntityBlockquote",
    "quote": "messageEntityBlockquote",
}


def media_duration(path: str) -> int | None:
    ext = str(path).rsplit(".", 1)[-1].lower()
    if ext == "wav":
        try:
            import wave
            with wave.open(str(path), "rb") as wf:
                rate = wf.getframerate() or 0
                if rate:
                    secs = int(round(wf.getnframes() / float(rate)))
                    if secs > 0:
                        return secs
        except Exception:
            pass
    try:
        mutagen = importlib.import_module("mutagen")
        audio = mutagen.File(str(path))
        secs = int(round(float(getattr(getattr(audio, "info", None), "length", 0) or 0)))
        if secs > 0:
            return secs
    except Exception:
        pass
    try:
        import shutil
        import subprocess
        if shutil.which("ffprobe"):
            p = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                capture_output=True, text=True, timeout=5,
            )
            secs = int(round(float(p.stdout.strip() or 0)))
            if secs > 0:
                return secs
    except Exception:
        pass
    return None


_MD2 = {
    "__": "messageEntityUnderline",
    "||": "messageEntitySpoiler",
    "~~": "messageEntityStrike",
}
_MD1 = {
    "*": "messageEntityBold",
    "_": "messageEntityItalic",
    "`": "messageEntityCode",
}
_MD_LINK_RE = _re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
_MD_ESC_RE = _re.compile(r"([_*\[\]()~`>#\+\-=|{}.!\\])")


def md_to_entities(src: str) -> tuple[str, list[dict[str, Any]]]:
    out: list[str] = []
    ents: list[dict[str, Any]] = []
    stack: list[tuple[str, int]] = []
    i = 0
    n = len(src)
    pos = 0

    def close(mark: str) -> bool:
        k = len(stack) - 1
        while k >= 0:
            if stack[k][0] == mark:
                _, off = stack.pop(k)
                ents.append({"_": _MD2.get(mark) or _MD1[mark], "offset": off, "length": pos - off})
                return True
            k -= 1
        return False

    while i < n:
        c = src[i]
        if c == "\\" and i + 1 < n:
            out.append(src[i + 1])
            pos += 1
            i += 2
            continue
        if src.startswith("```", i):
            j = src.find("```", i + 3)
            if j == -1:
                out.append("```")
                pos += 3
                i += 3
                continue
            head = src[i + 3:j]
            if "\n" in head:
                lang, _, body = head.partition("\n")
            else:
                lang, body = "", head
            ents.append({"_": "messageEntityPre", "language": lang, "offset": pos, "length": len(body)})
            out.append(body)
            pos += len(body)
            i = j + 3
            continue
        two = src[i:i + 2]
        if two in _MD2:
            if not close(two):
                if src.find(two, i + 2) != -1:
                    stack.append((two, pos))
                else:
                    out.append(two)
                    pos += 2
            i += 2
            continue
        if c in _MD1:
            if not close(c):
                if src.find(c, i + 1) != -1:
                    stack.append((c, pos))
                else:
                    out.append(c)
                    pos += 1
            i += 1
            continue
        if c == "[":
            m = _MD_LINK_RE.match(src, i)
            if m:
                start = pos
                g1 = m.group(1)
                out.append(g1)
                pos += len(g1)
                url = m.group(2)
                if url.startswith("tg://user?id="):
                    ents.append({"_": "inputMessageEntityMentionName", "user_id": int(url.split("id=", 1)[1]), "offset": start, "length": len(g1)})
                else:
                    ents.append({"_": "messageEntityTextUrl", "url": url, "offset": start, "length": len(g1)})
                i = m.end()
                continue
        out.append(c)
        pos += 1
        i += 1
    plain = "".join(out)
    _utf16_fix(plain, ents)
    return plain, ents


def md_escape(text: str) -> str:
    return _MD_ESC_RE.sub(r"\\\1", text)


def _attrs(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in _ATTR_RE.finditer(raw):
        out[m.group(1)] = m.group(2) or m.group(3) or m.group(4) or ""
    return out


def html_to_entities(html_src: str) -> tuple[str, list[dict[str, Any]]]:
    out: list[str] = []
    ents: list[dict[str, Any]] = []
    stack: list[tuple[str, int, dict[str, Any]]] = []
    pos = 0
    last = 0
    for m in _TAG_RE.finditer(html_src):
        chunk = _unescape(html_src[last:m.start()])
        if chunk:
            out.append(chunk)
            pos += len(chunk)
        tag = m.group(1).lower()
        close = m.group(0).startswith("</")
        last = m.end()
        if close:
            i = len(stack) - 1
            while i >= 0:
                t, off, ent = stack[i]
                if t == tag:
                    stack.pop(i)
                    if ent:
                        ent["offset"] = off
                        ent["length"] = pos - off
                        if "emoji_id" in ent:
                            ent["_"] = "messageEntityCustomEmoji"
                            ent["document_id"] = ent.pop("emoji_id")
                        ents.append(ent)
                    break
                i -= 1
            continue
        if tag == "br":
            out.append("\n")
            pos += 1
            continue
        at = _attrs(m.group(2) or "")
        if tag == "a":
            href = at.get("href") or ""
            ent: dict[str, Any] = {}
            if href.startswith("tg://user?id="):
                ent = {"_": "inputMessageEntityMentionName", "user_id": int(href.split("id=", 1)[1])}
            elif href.startswith("tg://emoji?id="):
                ent = {"emoji_id": int(href.split("id=", 1)[1])}
            elif href:
                ent = {"_": "messageEntityTextUrl", "url": href}
            stack.append((tag, pos, ent))
            continue
        if tag == "tg-emoji":
            stack.append((tag, pos, {"emoji_id": int(at.get("emoji-id") or 0)}))
            continue
        ctor = _ENT_MAP.get(tag)
        if ctor is None:
            continue
        nested = False
        for _, _, prev in stack:
            if prev.get("_") == "messageEntityPre":
                cls = at.get("class") or ""
                if cls.startswith("language-"):
                    prev["language"] = cls[9:]
                nested = True
                break
        if nested:
            continue
        ent = {"_": ctor}
        if tag == "pre":
            lang = at.get("class") or ""
            ent["language"] = lang[9:] if lang.startswith("language-") else ""
        elif tag == "blockquote" and (at.get("expandable") or "").lower() == "true":
            ent["collapsed"] = True
        stack.append((tag, pos, ent))
    tail = _unescape(html_src[last:])
    if tail:
        out.append(tail)
        pos += len(tail)
    plain = "".join(out)
    _utf16_fix(plain, ents)
    return plain, ents


__all__ = [
    "Html", "html", "human_size", "human_duration", "chunk_text",
    "parse_entities_html", "json_dumps", "progress_bar", "code_block",
    "b64e", "b64d", "rand_id", "len_s", "md5", "now_ts", "plural_ru",
    "html_to_entities", "extract_sent_message", "split_html_text",
    "md_to_entities", "md_escape",
]
