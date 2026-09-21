# Benchmarks

Reproducible comparisons of GoyGram against the major Python Telegram libraries.

## What is measured

1. **AES-256-IGE throughput and latency** — MTProto packet encryption.
2. **TL codec (simple)** — serialize `messages.sendMessage`, deserialize a `message` object.
3. **TL codec (realistic)** — native PyDict `dumps`/`loads` of `updateNewMessage` (text, forward, inline buttons). Latency percentiles on `loads`.
4. **AES-256-GCM throughput** — vault encryption.
5. **Cold import time**.
6. **Memory footprint** — RSS after import.

Not measured: live Telegram, a mock DC, C10K sessions.

## Environment

| Component | Version |
|---|---|
| Python | 3.11 |
| goygram | 0.8.4 (Rust core, AES-NI, native PyDict) |
| telethon | 1.44.0 |
| pyrogram | 2.0.106 |
| aiogram | 3.31.0 |
| python-telegram-bot | 22.8 |
| tgcrypto | 1.2.5 |

A single VPS (AMD Ryzen 9 5950X, 6 vCPU). Every table below was rerun on 0.8.4; values are medians of repeated runs pinned to one CPU.

## Results

### AES-256-IGE throughput (MB/s, higher is better)

| Library | 256 B | 4 KiB | 64 KiB |
|---|---|---|---|
| goygram (Rust, AES-NI, built-in) | 503.7 | 969.3 | 1062.5 |
| tgcrypto (C, separate install) | 151.3 | 198.6 | 204.3 |
| pyrogram | 144.9 | 196.2 | 202.4 |
| telethon (default) | 9.0 | 10.5 | 10.8 |

![AES-256-IGE throughput](03-aes-ige-throughput.png)

GoyGram dispatches to AES-NI at runtime. tgcrypto 1.2.5 is table-based software AES. Network RTT still dominates a real client.

Per-message latency at 256 B (lower is better): goygram 0.6 µs, tgcrypto 1.6 µs, pyrogram 1.7 µs, telethon 29.4 µs.

![AES-256-IGE latency](04-aes-ige-latency.png)

### TL codec, simple (ops/s, higher is better)

| Operation | ops/s |
|---|---|
| serialize `messages.sendMessage` | 351,270 |
| loads `message` | 577,821 |

![TL codec](05-tl-codec.png)

### TL codec, realistic `updateNewMessage` (ops/s)

Payload: ~200-char text, `messageFwdHeader`, inline keyboard. Packet 356 B.

| Operation | ops/s |
|---|---|
| dumps `updateNewMessage` | 97,283 |
| loads `updateNewMessage` | 225,347 |
| echo loads+dumps | 107,395 |
| AES-256-IGE enc+dec of that packet | 889,291 |

loads latency (µs): p50 3.8, p95 6.4, p99 8.9, p99.9 20.7.

![loads latency](06-loads-latency.png)

### AES-256-GCM (4 KiB, ops/s)

| Operation | ops/s |
|---|---|
| encrypt | 293,032 |
| decrypt | 290,105 |

![AES-256-GCM vault](07-aes-gcm-vault.png)

### Cold import time (ms, lower is better)

| Library | ms |
|---|---|
| goygram | 77.2 |
| python-telegram-bot | 142.8 |
| telethon | 342.0 |
| pyrogram | 461.5 |
| aiogram | 3016.3 |

![Cold import](01-cold-import.png)

### Memory footprint, RSS delta after import (MB, lower is better)

| Library | MB |
|---|---|
| goygram | 10.8 |
| python-telegram-bot | 18.8 |
| pyrogram | 35.6 |
| telethon | 48.4 |
| aiogram | 152.2 |

![RSS after import](02-rss-memory.png)

## Honest notes

- **No live Telegram.** A mock MTProto DC, 10k sessions, and hour-long leak runs are not in this folder.
- **tgcrypto loses on raw AES-IGE now.** tgcrypto 1.2.5 is table-based software AES; GoyGram dispatches to AES-NI. Network RTT still dominates a real client.
- **Telethon's default IGE path is slow** because it drives OpenSSL through ctypes. `cryptg` is optional.
- **aiogram import/RSS** are pydantic v2.
- **Schema load** (layer 229, 823 methods, 1698 constructors) is once per process. Warm `loads` is a few microseconds.

## Reproduce

```bash
python -m venv .bench && source .bench/bin/activate
python -m pip install goygram telethon tgcrypto pyrogram aiogram python-telegram-bot
python bench_crypto.py
python bench_codec.py
python bench_import.py
```
