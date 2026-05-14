# GoyGram

[![License: AGPLv3](https://img.shields.io/badge/license-AGPLv3-black.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-1f6feb.svg)](https://www.python.org/)
[![Rust](https://img.shields.io/badge/rust-1.78%2B-b7410e.svg)](https://www.rust-lang.org/)
[![Build Status](https://img.shields.io/badge/build-maturin-ready-2ea043.svg)](#build)

GoyGram is a Telegram framework with one clean entrypoint for user code and split low-level lanes under the hood: Bot API on `aiohttp`, MT transport on raw sockets, Rust for frame and crypto primitives.

## Build

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip maturin aiohttp pydantic
maturin develop
```

## Quick Start

```python
import asyncio

from goygram import GoyGram, InlineKbd, LinkOpts


app = GoyGram(
    bot_token="123456:BOT_TOKEN",
)

kbd = InlineKbd().add_btn("Ping", data="ping")
links = LinkOpts(above=True, large=True)


@app.on_msg
async def echo(msg):
    if not msg.text:
        return
    if msg.text == "/start":
        await app.send_msg(msg.chat_id, "hello https://example.com", kbd=kbd, link_options=links, via=msg.src)
        return
    await msg.reply(f"rx: {msg.text}")


asyncio.run(app.run())
```

### Commands And Callbacks

```python
@app.on_cmd("start", "help")
async def boot(msg):
    await msg.reply("ready")


@app.on_cb
async def taps(cb):
    if cb.data == "ping":
        await cb.answer("pong")
        await cb.edit("updated")
```

## Public API

```python
from goygram import GoyGram, InlineKbd, ReplyKbd, Btn
```

`GoyGram(...)` accepts flat config:

- `bot_token`
- `mt_host`
- `mt_port`
- `mt_key`
- `mt_iv`

Main calls:

- `@app.on_msg`
- `@app.on_cmd("start")`
- `@app.on_cb`
- `@app.on_poll`
- `@app.on_member`
- `await app.send_msg(chat_id, text, kbd=..., via=...)`
- `await app.send_msg(chat_id, text, link_options=...)`
- `await app.send_photo(chat_id, photo, caption=...)`
- `await app.send_doc(chat_id, document, caption=...)`
- `await app.send_media_group(chat_id, media)`
- `await app.answer_cb(cb_id, text=...)`
- `await app.edit_text(chat_id, msg_id, text)`
- `await app.set_webhook(url)`
- `await app.delete_webhook()`
- `await app.get_webhook_info()`
- `await msg.reply(text, kbd=...)`
- `await msg.delete()`
- `await app.run()`

Extra UI helpers:

- `InlineKbd`
- `ReplyKbd`
- `ForceReply`
- `ReplyGone`

## Package Layout

```text
.
├── ext_rust
│   ├── Cargo.toml
│   └── src/lib.rs
├── goygram
│   ├── __init__.py
│   ├── client.py
│   ├── api
│   ├── core
│   ├── tl
│   ├── types
│   └── vendor
├── tools
│   ├── gen_botapi.py
│   └── gen_mtproto.py
└── tests
```

## Codegen

```bash
python tools/gen_botapi.py
python tools/gen_mtproto.py
```

Generated targets:

- `goygram/api/types.py`
- `goygram/api/methods.py`
- `goygram/tl/schema.py`

## Tests

```bash
python -m unittest tests.test_matrix -v
```
