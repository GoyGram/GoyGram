# Benchmarks

Reproducible comparisons of GoyGram against the major Python Telegram libraries.

## What is measured

1. **AES-256-IGE throughput and latency** — the core MTProto crypto operation (packet encryption).
2. **Cold import time** — how long the library takes to load.
3. **Memory footprint** — resident set size after import.

## Environment

| Component | Version |
|---|---|
| Python | 3.11 |
| goygram | 0.7.58 (Rust core, `lto = true`, `opt-level = 3`) |
| telethon | 1.44.0 |
| pyrogram | 2.0.106 |
| aiogram | 3.31.0 |
| python-telegram-bot | 22.8 |
| tgcrypto | 1.2.5 |

A single unremarkable VPS, no special hardware. Each library was measured in a fresh process.

## Results

### AES-256-IGE throughput (MB/s, higher is better)

| Library | 256 B | 4 KiB | 64 KiB |
|---|---|---|---|
| goygram (Rust, built-in) | 80 | 115 | 113 |
| telethon (default) | 9 | 12 | 12 |
| tgcrypto (C, separate install) | 149 | 204 | 210 |
| pyrogram | 151 | 200 | 203 |

Per-message latency at 256 B (lower is better): goygram 3.0 µs, tgcrypto 1.4 µs, pyrogram 1.5 µs, telethon ~100 µs.

### Cold import time (ms, lower is better)

| Library | ms |
|---|---|
| goygram | 87 |
| python-telegram-bot | 140 |
| telethon | 298 |
| pyrogram | 477 |
| aiogram | 3112 |

### Memory footprint, RSS delta after import (MB, lower is better)

| Library | MB |
|---|---|
| goygram | 12 |
| python-telegram-bot | 18 |
| pyrogram | 35 |
| telethon | 48 |
| aiogram | 152 |

## Honest notes

- **tgcrypto is ~2× faster than the Rust core on raw AES-IGE.** tgcrypto is a hand-optimized C library written specifically for Telegram; GoyGram's core is a general-purpose Rust AES crate. Both are far beyond what Telegram needs — the network round-trip dominates. The difference is that GoyGram's crypto is built in, while tgcrypto (or Telethon's `cryptg`) must be installed separately.
- **Telethon's default path is slow** because it drives OpenSSL through `ctypes`, re-running the key schedule and unpacking buffers byte-by-byte on every call. Its fast path (`cryptg`) is not installed by default. This is not a bug in Telethon, it is a default-configuration fact.
- **aiogram's import time and memory** are dominated by pydantic v2.

## Reproduce

```bash
uv venv .bench && source .bench/bin/activate
uv pip install goygram telethon tgcrypto pyrogram aiogram python-telegram-bot
python bench_crypto.py
python bench_import.py
```
