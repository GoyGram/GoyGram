# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOT_API_URL = "https://core.telegram.org/bots/api"
API_TL_URL = (
    "https://raw.githubusercontent.com/telegramdesktop/tdesktop/dev/"
    "Telegram/SourceFiles/mtproto/scheme/api.tl"
)
MTPROTO_TL_URL = (
    "https://raw.githubusercontent.com/telegramdesktop/tdesktop/dev/"
    "Telegram/SourceFiles/mtproto/scheme/mtproto.tl"
)

CORE_METHODS = [
    "def __init__(self, *args: Any, **kwargs: Any) -> None: ...",
    "async def run(self) -> None: ...",
    "async def start(self) -> None: ...",
    "def stop(self) -> None: ...",
    "async def send_msg(self, *args: Any, **kwargs: Any) -> Any: ...",
    "async def mt_req(self, *args: Any, **kwargs: Any) -> Any: ...",
    "async def bot_req(self, *args: Any, **kwargs: Any) -> Any: ...",
    "async def get_me(self, *args: Any, **kwargs: Any) -> Any: ...",
    "def on_msg(self, *args: Any, **kwargs: Any) -> Any: ...",
    "def on_cb(self, *args: Any, **kwargs: Any) -> Any: ...",
    "def on_edit(self, *args: Any, **kwargs: Any) -> Any: ...",
    "def on_inline(self, *args: Any, **kwargs: Any) -> Any: ...",
    "def on_update(self, *args: Any, **kwargs: Any) -> Any: ...",
]


def _fetch(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "goygram-stubgen"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def bot_methods(html: str) -> list[str]:
    names = []
    seen = set()
    for m in re.finditer(r"<h4[^>]*>\s*(?:<a[^>]*>.*?</a>)?\s*([a-z][a-zA-Z0-9]+)\s*</h4>", html, re.S):
        name = m.group(1)
        if name in seen:
            continue
        seen.add(name)
        names.append(name)
    if len(names) < 50:
        for m in re.finditer(r'id="([a-z][a-z0-9]+)"', html):
            name = m.group(1)
            if name in seen or len(name) < 4:
                continue
            seen.add(name)
            names.append(name)
    return names


def tl_functions(text: str) -> list[str]:
    names = []
    in_fn = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("---functions---"):
            in_fn = True
            continue
        if s.startswith("---types---"):
            in_fn = False
            continue
        if not in_fn or not s or s.startswith("//"):
            continue
        m = re.match(r"^([A-Za-z0-9_.]+)#", s)
        if m:
            names.append(m.group(1))
    return names


def camel_to_snake(name: str) -> str:
    out = []
    for c in name:
        if c.isupper():
            out.append("_")
            out.append(c.lower())
        else:
            out.append(c)
    return "".join(out).lstrip("_")


def ident(name: str) -> str:
    name = name.replace(".", "_")
    if name.isidentifier():
        return name
    return "_" + re.sub(r"[^0-9a-zA-Z_]", "_", name)


def emit_async(name: str) -> str:
    return f"    async def {ident(name)}(self, *args: Any, **kwargs: Any) -> Any: ..."


def write_ext_pyi(path: Path) -> None:
    path.write_text(
        "# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.\n"
        "from typing import Any\n\n"
        "def load_schema(schema_json: str) -> dict[str, Any]: ...\n"
        "def schema_info() -> dict[str, Any]: ...\n"
        "def serialize_method(method: str, args: str | dict[str, Any]) -> bytes: ...\n"
        "def serialize_constructor(name: str, args: str | dict[str, Any]) -> bytes: ...\n"
        "def deserialize_constructor(data: bytes) -> dict[str, Any] | list[Any]: ...\n"
        "def aes_ige_enc(data: bytes, key: bytes, iv: bytes) -> bytes: ...\n"
        "def aes_ige_dec(data: bytes, key: bytes, iv: bytes) -> bytes: ...\n"
        "def aes_ige_enc_raw(data: bytes, key: bytes, iv: bytes) -> list[int]: ...\n"
        "def aes_ige_dec_raw(data: bytes, key: bytes, iv: bytes) -> list[int]: ...\n"
        "def aes_ige_fast_path() -> bool: ...\n"
        "def aes_gcm_encrypt(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes) -> bytes: ...\n"
        "def aes_gcm_decrypt(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes: ...\n"
        "def cut(data: bytes, offset: int, length: int) -> bytes: ...\n"
        "def pack(parts: list[bytes]) -> bytes: ...\n",
        encoding="utf-8",
    )


def write_init_pyi(path: Path, bot: list[str], mt: list[str]) -> None:
    lines = [
        "# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.",
        "from typing import Any",
        "",
        "from .session import Session as Session",
        "from .errors import StopPropagation as StopPropagation",
        "",
        "class GoyGram:",
    ]
    seen = set()
    for row in CORE_METHODS:
        lines.append(f"    {row}")
    for name in bot:
        for alias in (name, camel_to_snake(name)):
            if alias in seen:
                continue
            seen.add(alias)
            lines.append(emit_async(alias))
    for raw in mt:
        dotted = raw
        snake = dotted.replace(".", "_")
        aliases = [snake]
        if "." in dotted:
            ns, rest = dotted.split(".", 1)
            aliases.append(ns + "_" + camel_to_snake(rest))
            aliases.append("mt_" + snake)
            aliases.append("mt_" + ns + "_" + camel_to_snake(rest))
        for alias in aliases:
            if alias in seen:
                continue
            seen.add(alias)
            lines.append(emit_async(alias))
    lines.append("")
    lines.append("__all__: list[str]")
    lines.append("__version__: str")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--bot-html", default="")
    p.add_argument("--api-tl", default="")
    p.add_argument("--mtproto-tl", default="")
    args = p.parse_args()
    cache = Path.home() / ".goygram" / "cache"
    bot_html = Path(args.bot_html).read_text(encoding="utf-8") if args.bot_html else _fetch(BOT_API_URL)
    api_tl = Path(args.api_tl).read_text(encoding="utf-8") if args.api_tl else (
        (cache / "api.tl").read_text(encoding="utf-8") if (cache / "api.tl").exists() else _fetch(API_TL_URL)
    )
    mt_tl = Path(args.mtproto_tl).read_text(encoding="utf-8") if args.mtproto_tl else (
        (cache / "mtproto.tl").read_text(encoding="utf-8") if (cache / "mtproto.tl").exists() else _fetch(MTPROTO_TL_URL)
    )
    bot = bot_methods(bot_html)
    mt = tl_functions(api_tl) + tl_functions(mt_tl)
    if not bot:
        print("no Bot API methods parsed", file=sys.stderr)
        return 1
    if not mt:
        print("no MTProto methods parsed", file=sys.stderr)
        return 1
    pkg = ROOT / "goygram"
    write_ext_pyi(pkg / "ext.pyi")
    write_init_pyi(pkg / "__init__.pyi", bot, mt)
    (pkg / "py.typed").write_text("", encoding="utf-8")
    print(f"wrote stubs: bot={len(bot)} mt={len(mt)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
