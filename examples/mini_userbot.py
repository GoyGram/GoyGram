# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

import asyncio
import os

from goygram import GoyGram


app = GoyGram(
    api_id=os.environ["GOYGRAM_API_ID"],
    api_hash=os.environ["GOYGRAM_API_HASH"],
    session_name=os.getenv("GOYGRAM_SESSION", "mini_userbot"),
)


@app.on_cmd("ping")
async def ping(msg) -> None:
    await msg.reply("pong")


@app.on_cmd("echo")
async def echo(msg) -> None:
    await msg.reply(msg.args or "echo: empty")


@app.on_cmd("id")
async def identity(msg) -> None:
    user_id = msg.from_id or app.core.self_id
    await msg.reply(f"chat_id={msg.chat_id}\nuser_id={user_id}\nmessage_id={msg.id}")


@app.on_cmd("state")
async def state(msg) -> None:
    user_id = msg.from_id or app.core.self_id
    if msg.chat_id is None or user_id is None:
        return
    current = app.get_state(msg.chat_id, user_id)
    if current is None:
        app.set_state(msg.chat_id, user_id, "active", {"uses": 1})
        await msg.reply("state=active")
        return
    data = app.get_state_data(msg.chat_id, user_id) or {}
    await msg.reply(f"state={current}\ndata={data}")


@app.on_cmd("help")
async def help_command(msg) -> None:
    await msg.reply("!ping\n!echo text\n!id\n!state\n!help")


@app.on_edit
async def edited_message(msg) -> None:
    if not msg.is_me and msg.chat_id != app.core.self_id:
        return
    text = (msg.text or "").strip()
    if text == "!ping":
        await msg.reply("pong (edited)")
        return
    if text.startswith("!echo "):
        await msg.reply(text[6:].strip() or "echo: empty")
        return
    await msg.reply(f"edited: {text}")


if __name__ == "__main__":
    asyncio.run(app.run())
