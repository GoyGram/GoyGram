# Benchmarks

Reproducible comparisons of GoyGram against the major Python Telegram libraries.

## What is measured

1. **AES-256-IGE throughput and latency** — MTProto packet encryption.
2. **TL codec** — native PyDict `dumps`/`loads` of a realistic `updateNewMessage` (text, forward, inline buttons) plus `messages.sendMessage` serialize. Latency percentiles on `loads`.
3. **AES-256-GCM throughput** — vault encryption.
4. **Cold import time**.
5. **Memory footprint** — RSS after import.

Not measured: live Telegram, a mock DC, C10K sessions. Those are network/OS tests, not the codec. Flooding api.telegram.org is not a benchmark.

## Environment

| Component | Version |
|---|---|
| Python | 3.11 |
| goygram | 0.7.89 (Rust core, AES-NI, native PyDict) |
| telethon | 1.44.0 |
| pyrogram | 2.0.106 |
| aiogram | 3.31.0 |
| python-telegram-bot | 22.8 |
| tgcrypto | 1.2.5 |

A single VPS (AMD Ryzen 9 5950X, 6 vCPU). Codec numbers below were re-run on 0.7.89 after the JSON/hex bridge was removed. IGE/import/RSS rows are the same box as before.

## Results

### AES-256-IGE throughput (MB/s, higher is better)

| Library | 256 B | 4 KiB | 64 KiB |
|---|---|---|---|
| goygram (Rust, AES-NI, built-in) | 544 | 1001 | 1094 |
| tgcrypto (C, separate install) | 168 | 224 | 234 |
| pyrogram | 168 | 223 | 228 |
| telethon (default) | 12 | 14 | 14 |

Per-message latency at 256 B (lower is better): goygram 0.4 µs, tgcrypto 1.3 µs, pyrogram 1.4 µs, telethon 23 µs.

### TL codec (ops/s, higher is better)

Payload: `updateNewMessage` with ~200-char text, `messageFwdHeader`, inline keyboard (callback + url). Packet 356 B. `ext.__file__` printed by the script.

| Operation | ops/s |
|---|---|
| serialize `messages.sendMessage` (nested dict peer) | 343,991 |
| dumps `updateNewMessage` | 106,580 |
| loads `updateNewMessage` | 228,493 |
| echo loads+dumps | 106,562 |
| AES-256-IGE enc+dec of that packet | 850,540 |

loads latency (µs): p50 3.7, p95 6.6, p99 8.2, p99.9 20.0.

### AES-256-GCM (4 KiB, ops/s)

| Operation | ops/s |
|---|---|
| encrypt | 292,099 |
| decrypt | 308,479 |

### Cold import time (ms, lower is better)

| Library | ms |
|---|---|
| goygram | 74 |
| python-telegram-bot | 141 |
| telethon | 272 |
| pyrogram | 436 |
| aiogram | 2699 |

### Memory footprint, RSS delta after import (MB, lower is better)

| Library | MB |
|---|---|
| goygram | 13 |
| python-telegram-bot | 19 |
| pyrogram | 35 |
| telethon | 48 |
| aiogram | 152 |

## Honest notes

- **No live Telegram.** A mock MTProto DC, 10k sessions, and hour-long leak runs are not in this folder. The codec+crypto path is what GoyGram claims; the numbers above are that path on loopback.
- **tgcrypto loses on raw AES-IGE now.** tgcrypto 1.2.5 is table-based software AES; GoyGram dispatches to AES-NI. Network RTT still dominates a real client.
- **Telethon's default IGE path is slow** because it drives OpenSSL through ctypes. `cryptg` is optional.
- **aiogram import/RSS** are pydantic v2.
- **Schema load** (layer 229, 823 methods, 1698 constructors) is once per process. Warm `loads` is a few microseconds.

## Reproduce

```bash
uv venv .bench && source .bench/bin/activate
uv pip install goygram telethon tgcrypto pyrogram aiogram python-telegram-bot
python bench_crypto.py
python bench_codec.py
python bench_import.py
```
