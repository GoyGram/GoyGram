# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

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


def split_html_text(text: str, limit: int = 4096) -> list[str]:
    import re
    if limit < 256:
        raise ValueError("limit must be at least 256")
    units = lambda s: len(s.encode("utf-16-le")) // 2
    tokens = re.findall(r"<[^>]+>|[^<]+", text)
    parts: list[str] = []
    stack: list[str] = []

    def open_tags() -> str:
        names = []
        for tag in stack:
            match = re.match(r"<([a-zA-Z][\w-]*)", tag)
            if match is not None:
                names.append(match.group(1))
        return "".join(f"<{name}>" for name in names)

    def close_tags() -> str:
        names = []
        for tag in stack:
            match = re.match(r"<([a-zA-Z][\w-]*)", tag)
            if match is not None:
                names.append(match.group(1))
        return "".join(f"</{name}>" for name in reversed(names))

    def close_units() -> int:
        total = 0
        for tag in stack:
            match = re.match(r"<([a-zA-Z][\w-]*)", tag)
            if match is not None:
                total += units(f"</{match.group(1)}>")
        return total

    current = [open_tags()]
    size = units(current[0])

    def flush() -> None:
        nonlocal current, size
        parts.append("".join(current) + close_tags())
        current = [open_tags()]
        size = units(current[0])

    for token in tokens:
        if token.startswith("<"):
            opening = re.fullmatch(r"<([a-zA-Z][\w-]*)(?:\s[^>]*)?>", token)
            closing = re.fullmatch(r"</([a-zA-Z][\w-]*)>", token)
            if opening is not None:
                name = opening.group(1)
                if name not in ("br", "input", "img"):
                    stack.append(token)
                current.append(token)
                size += units(token)
                continue
            if closing is not None:
                name = closing.group(1)
                for i in range(len(stack) - 1, -1, -1):
                    match = re.match(r"<([a-zA-Z][\w-]*)", stack[i])
                    if match is not None and match.group(1) == name:
                        stack.pop(i)
                        break
                current.append(token)
                size += units(token)
                continue
            current.append(token)
            size += units(token)
            continue
        while token:
            budget = max(limit - size - close_units(), 1)
            if units(token) <= budget:
                current.append(token)
                size += units(token)
                break
            cut = token.encode("utf-16-le")[: budget * 2].decode("utf-16-le", errors="ignore")
            current.append(cut)
            flush()
            token = token[len(cut):]
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


def html_to_entities(html_src: str) -> tuple[str, list[dict[str, Any]]]:
    from html.parser import HTMLParser

    class _P(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.out: list[str] = []
            self.ents: list[dict[str, Any]] = []
            self.stack: list[tuple[str, int, dict[str, Any]]] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            at = dict(attrs)
            if tag == "br":
                self.out.append("\n")
                return
            if tag == "a":
                ent: dict[str, Any] | None = None
                href = at.get("href", "")
                if href.startswith("tg://user?id="):
                    ent = {"_": "inputMessageEntityMentionName", "user_id": int(href.split("id=", 1)[1])}
                elif href.startswith("tg://emoji?id="):
                    self.stack.append((tag, len("".join(self.out)), {"emoji_id": int(href.split("id=", 1)[1])}))
                    return
                elif href:
                    ent = {"_": "messageEntityTextUrl", "url": href}
                if ent is not None:
                    self.stack.append((tag, len("".join(self.out)), ent))
                else:
                    self.stack.append((tag, len("".join(self.out)), {}))
                return
            if tag == "tg-emoji":
                self.stack.append((tag, len("".join(self.out)), {"emoji_id": int(at.get("emoji-id", 0))}))
                return
            ctor = _ENT_MAP.get(tag)
            if ctor is None:
                return
            for _, _, prev in self.stack:
                if prev.get("_") == "messageEntityPre":
                    if at.get("class", "").startswith("language-"):
                        prev["language"] = at["class"][9:]
                    return
            ent = {"_": ctor}
            if tag == "pre" and at.get("class", "").startswith("language-"):
                ent["language"] = at["class"][9:]
            self.stack.append((tag, len("".join(self.out)), ent))

        def handle_endtag(self, tag: str) -> None:
            for i in range(len(self.stack) - 1, -1, -1):
                t, off, ent = self.stack[i]
                if t == tag:
                    self.stack.pop(i)
                    text = "".join(self.out)
                    if not ent:
                        return
                    ent["offset"] = off
                    ent["length"] = len(text) - off
                    if "user_id" in ent:
                        ent["_"] = "inputMessageEntityMentionName"
                    if "emoji_id" in ent:
                        ent["_"] = "messageEntityCustomEmoji"
                        ent["document_id"] = ent.pop("emoji_id")
                    self.ents.append(ent)
                    return

        def handle_data(self, data: str) -> None:
            self.out.append(data)

    p = _P()
    p.feed(html_src)
    p.close()
    return "".join(p.out), p.ents


__all__ = [
    "Html", "html", "human_size", "human_duration", "chunk_text",
    "parse_entities_html", "json_dumps", "progress_bar", "code_block",
    "b64e", "b64d", "rand_id", "len_s", "md5", "now_ts", "plural_ru",
    "html_to_entities", "extract_sent_message", "split_html_text",
]
