# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations
from typing import Any
from html import escape


def _attr(value: Any) -> str:
    return escape(str(value), quote=True)


class Rich:
    __slots__ = ("_parts",)

    def __init__(self, *parts: Any) -> None:
        self._parts: list[str] = []
        for p in parts:
            self.add(p)

    def add(self, part: Any) -> "Rich":
        if part is None:
            return self
        if isinstance(part, Rich):
            self._parts.extend(part._parts)
        elif isinstance(part, str):
            self._parts.append(part)
        else:
            self._parts.append(str(part))
        return self

    def text(self, s: Any) -> "Rich":
        return self.add(s)

    def nl(self, n: int = 1) -> "Rich":
        return self.add("\n" * n)

    def b(self, s: Any) -> "Rich":
        return self.add(f"<b>{s}</b>")

    def i(self, s: Any) -> "Rich":
        return self.add(f"<i>{s}</i>")

    def u(self, s: Any) -> "Rich":
        return self.add(f"<u>{s}</u>")

    def s(self, s: Any) -> "Rich":
        return self.add(f"<s>{s}</s>")

    def spoiler(self, s: Any) -> "Rich":
        return self.add(f"<tg-spoiler>{s}</tg-spoiler>")

    def code(self, s: Any) -> "Rich":
        return self.add(f"<code>{s}</code>")

    def pre(self, s: Any, lang: str | None = None) -> "Rich":
        if lang:
            return self.add(f'<pre><code class="language-{lang}">{s}</code></pre>')
        return self.add(f"<pre>{s}</pre>")

    def link(self, s: Any, url: str) -> "Rich":
        return self.add(f'<a href="{_attr(url)}">{s}</a>')

    def mention(self, uid: Any, name: str) -> "Rich":
        return self.add(f'<a href="tg://user?id={uid}">{name}</a>')

    def emoji(self, eid: Any, alt: str = "❤") -> "Rich":
        return self.add(f'<tg-emoji emoji-id="{_attr(eid)}">{alt}</tg-emoji>')

    def time(self, ts: Any, fmt: str = "wDT", label: str | None = None) -> "Rich":
        inner = label if label is not None else ""
        return self.add(f'<tg-time unix="{_attr(ts)}" format="{_attr(fmt)}">{inner}</tg-time>')

    def heading(self, s: Any, level: int = 1) -> "Rich":
        lv = max(1, min(6, int(level)))
        return self.add(f"<h{lv}>{s}</h{lv}>")

    def details(self, title: str, body: "Rich | str | None", *, open_: bool = False) -> "Rich":
        attr = " open" if open_ else ""
        self.add(f"<details{attr}><summary>{title}</summary>")
        if body is not None:
            self.add(body)
        return self.add("</details>")

    def list(self, items: Any, *, ordered: bool = False) -> "Rich":
        tag = "ol" if ordered else "ul"
        self.add(f"<{tag}>")
        for it in items:
            self.add(f"<li>{it}</li>")
        return self.add(f"</{tag}>")

    def quote(self, s: Any, cite: str | None = None) -> "Rich":
        if cite is not None:
            return self.add(f"<blockquote><strong>{cite}</strong>\n{s}</blockquote>")
        return self.add(f"<blockquote>{s}</blockquote>")

    def pull_quote(self, s: Any, cite: str | None = None) -> "Rich":
        if cite is not None:
            return self.add(f"<aside>{s}<cite>{cite}</cite></aside>")
        return self.add(f"<aside>{s}</aside>")

    def img(self, url: str, caption: str | None = None, cite: str | None = None) -> "Rich":
        if caption is not None or cite is not None:
            inner = f"<figcaption>{caption or ''}{f'<cite>{cite}</cite>' if cite else ''}</figcaption>"
            return self.add(f'<img src="{_attr(url)}"/>{inner}')
        return self.add(f'<img src="{_attr(url)}"/>')

    def video(self, url: str, caption: str | None = None) -> "Rich":
        return self.add(f'<video src="{_attr(url)}">{f"<figcaption>{caption}</figcaption>" if caption else ""}</video>')

    def collage(self, media: list[str], caption: str | None = None, cite: str | None = None) -> "Rich":
        self.add("<tg-collage>")
        for m in media:
            self.add(f'<img src="{_attr(m)}"/>')
        if caption or cite:
            self.add(f"<figcaption>{caption or ''}{f'<cite>{cite}</cite>' if cite else ''}</figcaption>")
        return self.add("</tg-collage>")

    def slideshow(self, media: list[tuple[str, str]], caption: str | None = None, cite: str | None = None) -> "Rich":
        self.add("<tg-slideshow>")
        for kind, m in media:
            if kind == "video":
                self.add(f'<video src="{_attr(m)}"/>')
            else:
                self.add(f'<img src="{_attr(m)}"/>')
        if caption or cite:
            self.add(f"<figcaption>{caption or ''}{f'<cite>{cite}</cite>' if cite else ''}</figcaption>")
        return self.add("</tg-slideshow>")

    def map(self, lat: Any, long: Any, zoom: int = 14) -> "Rich":
        return self.add(f'<tg-map lat="{_attr(lat)}" long="{_attr(long)}" zoom="{_attr(zoom)}"/>')

    def math(self, src: str) -> "Rich":
        return self.add(f"<tg-math>{src}</tg-math>")

    def anchor(self, name: str) -> "Rich":
        return self.add(f'<a name="{_attr(name)}"></a>')

    def btn_url(self, s: str, url: str, *, style: str | None = None) -> "Rich":
        st = f' style="{_attr(style)}"' if style else ""
        return self.add(f'<tg-button type="url"{st} url="{_attr(url)}">{s}</tg-button>')

    def btn_user(self, s: str, uid: Any, *, style: str | None = None) -> "Rich":
        st = f' style="{_attr(style)}"' if style else ""
        return self.add(f'<tg-button type="url"{st} url="tg://user?id={uid}">{s}</tg-button>')

    def btn_cb(self, s: str, data: str, *, style: str | None = None) -> "Rich":
        st = f' style="{_attr(style)}"' if style else ""
        return self.add(f'<tg-button type="callback_data"{st} data="{_attr(data)}">{s}</tg-button>')

    def btn_app(self, s: str, url: str, *, style: str | None = None) -> "Rich":
        st = f' style="{_attr(style)}"' if style else ""
        return self.add(f'<tg-button type="web_app"{st} url="{_attr(url)}">{s}</tg-button>')

    def btn_login(self, s: str, url: str, *, forward_text: str | None = None, write_access: bool = False, style: str | None = None) -> "Rich":
        st = f' style="{_attr(style)}"' if style else ""
        ft = f' forward-text="{_attr(forward_text)}"' if forward_text else ""
        wa = " request-write-access" if write_access else ""
        return self.add(f'<tg-button type="login_url"{st} url="{_attr(url)}"{ft}{wa}>{s}</tg-button>')

    def btn_inline(self, s: str, query: str, *, current: bool = False, style: str | None = None) -> "Rich":
        st = f' style="{_attr(style)}"' if style else ""
        t = "switch_inline_query_current_chat" if current else "switch_inline_query"
        return self.add(f'<tg-button type="{_attr(t)}"{st} query="{_attr(query)}">{s}</tg-button>')

    def btn_inline_chosen(self, s: str, query: str, *, allow_user: bool = False, allow_bot: bool = False, allow_group: bool = False, allow_channel: bool = False, style: str | None = None) -> "Rich":
        st = f' style="{_attr(style)}"' if style else ""
        flags = ""
        if allow_user:
            flags += " allow-user-chats"
        if allow_bot:
            flags += " allow-bot-chats"
        if allow_group:
            flags += " allow-group-chats"
        if allow_channel:
            flags += " allow-channel-chats"
        return self.add(f'<tg-button type="switch_inline_query_chosen_chat"{st} query="{_attr(query)}"{flags}>{s}</tg-button>')

    def btn_copy(self, s: str, text: str) -> "Rich":
        return self.add(f'<tg-button type="copy_text" text="{_attr(text)}">{s}</tg-button>')

    def btn_disabled(self, s: str) -> "Rich":
        return self.add(f'<tg-button type="disabled">{s}</tg-button>')

    def btn_row(self, *buttons: "Rich", align: str = "left") -> "Rich":
        self.add(f'<tg-button-row align="{_attr(align)}">')
        for b in buttons:
            self.add(b)
        return self.add("</tg-button-row>")

    def buttons(self, rows: list[list[dict[str, Any]]], align: str = "left") -> "Rich":
        for row in rows:
            self.add(f'<tg-button-row align="{_attr(align)}">')
            for b in row:
                self.add(btn_html(b))
            self.add("</tg-button-row>")
        return self

    def build(self) -> str:
        return "".join(self._parts)

    def to_html(self) -> str:
        html = self.build()
        import re as _re
        return _re.sub(r"\n(?![^<]*>)", "<br>", html)

    def to_msg(self) -> dict[str, Any]:
        html = self.to_html()
        return {"html": html}

    def to_tl(self, markdown: bool = False) -> dict[str, Any]:
        if markdown:
            return {"_": "inputRichMessageMarkdown", "markdown": self.build()}
        html = self.to_html()
        return {"_": "inputRichMessageHTML", "html": html}

    def __str__(self) -> str:
        return self.build()

    def __len__(self) -> int:
        return len(self.build())

    def __add__(self, other: Any) -> "Rich":
        out = Rich()
        out._parts = list(self._parts)
        if isinstance(other, Rich):
            out._parts.extend(other._parts)
        elif other is not None:
            out._parts.append(str(other))
        return out


def btn_html(b: dict[str, Any]) -> str:
    btype = b.get("type", "url")
    attrs = f'type="{_attr(btype)}"'
    if b.get("style"):
        attrs += f' style="{_attr(b["style"])}"'
    if b.get("url") is not None:
        attrs += f' url="{_attr(b["url"])}"'
    if b.get("data") is not None:
        attrs += f' data="{_attr(b["data"])}"'
    if b.get("query") is not None:
        attrs += f' query="{_attr(b["query"])}"'
    if b.get("text") is not None:
        attrs += f' text="{_attr(b["text"])}"'
    return f"<tg-button {attrs}>{b.get('label', '')}</tg-button>"


def rich_html(html: str) -> dict[str, Any]:
    import re as _re
    return {"html": _re.sub(r"\n(?![^<]*>)", "<br>", html)}
