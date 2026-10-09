<!-- Improved compatibility of back to top link: See: https://github.com/othneildrew/Best-README-Template/pull/73 -->
<a id="readme-top"></a>

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/GoyGram/GoyGram">
    <img src="https://raw.githubusercontent.com/GoyGram/GoyGram/main/GoyGram.png" alt="GoyGram logo" width="650">
  </a>

  <h3 align="center">GoyGram</h3>

  <p align="center">
    A Telegram framework where Bot API and MTProto run side by side, with the crypto in Rust.
    <br />
    <a href="https://goygram.github.io/docs"><strong>Read the docs »</strong></a>
    <br />
    <br />
    <a href="https://goygram.github.io/docs">Documentation</a>
    &middot;
    <a href="https://github.com/GoyGram/GoyGram/wiki">Wiki</a>
    &middot;
    <a href="https://pypi.org/project/goygram/">PyPI</a>
    &middot;
    <a href="https://github.com/GoyGram/GoyGram/issues">Report bug</a>
    &middot;
    <a href="https://github.com/GoyGram/GoyGram/issues">Request feature</a>
  </p>
</div>

<!-- PROJECT SHIELDS -->
<!-- Reference style links are declared at the bottom of this file. -->
<div align="center">

[![Python 3.13+][python-shield]][python-url]
[![Rust core][rust-shield]][rust-url]
[![PyPI version][pypi-shield]][pypi-url]
[![PyPI downloads][downloads-shield]][pypi-url]
[![License: AGPL v3][license-shield]][license-url]
[![Strict CI][strict-shield]][strict-url]
[![Publish][pub-shield]][pub-url]
[![Telegram][telegram-shield]][telegram-url]
[![Platforms][mtproto-shield]][mtproto-url]
[![OpSec][opsec-shield]][opsec-url]
[![Docs][docs-shield]][docs-url]
[![Wiki][wiki-shield]][wiki-url]
[![Last commit][commit-shield]][commit-url]
[![Stars][stars-shield]][stars-url]
[![Forks][forks-shield]][forks-url]
[![Issues][issues-shield]][issues-url]

</div>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of contents</summary>
  <ol>
    <li><a href="#goygram">GoyGram</a></li>
    <li><a href="#key-features">Key features</a></li>
    <li><a href="#benchmarks">Benchmarks</a></li>
    <li>
      <a href="#getting-started">Getting started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#documentation">Documentation</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
  </ol>
</details>

<!-- ABOUT THE PROJECT -->
## GoyGram

> Bot API and MTProto in one process, with the crypto in Rust

GoyGram is a Telegram framework for Python. Bot API and MTProto run in the same process and share one event loop and one set of handlers, so a bot and a userbot can live in the same app instead of two. Nothing on the hot path is Python: AES for every packet and the TL codec are Rust, compiled straight into the package.

```python
import asyncio
from goygram import GoyGram, filters

app = GoyGram(bot_token="123456:ABC_TOKEN")

@app.on_msg(filt=filters.text)
async def echo(msg):
    await msg.reply("Hello from GoyGram")

asyncio.run(app.run())
```

### Key features

- **Ready**: `pip install goygram`. Python 3.13 and newer, with wheels for Linux, Windows, macOS and Android.
- **Two transports**: Bot API and MTProto in one app. Switch per call with `via="api"` or `via="mtproto"`, and a reply goes back the way the original message arrived.
- **Fast to start**: 77 ms to import, about 11 MB of memory. Telethon takes 342 ms and 48 MB for the same job.
- **Rust core**: AES-256-IGE for MTProto packets, AES-256-GCM for vaults, with AES-NI used when the CPU has it.
- **No generated wrappers**: any Bot API method works right away, in snake_case or camelCase. MTProto methods go through the `mt_` prefix. A method Telegram adds tomorrow works without a new release of GoyGram.
- **One event object**: `MsgObj`, `CbObj`, `PollObj`, `MemberObj` and `InlineObj` are aliases of a single dynamic `Obj`. Fields are read on demand, so you only pay for the ones you touch.
- **Sessions in one place**: a `Session` is your in-memory state, the `.vault` file and a portable encrypted string at once. No separate MemorySession, StringSession and SQLiteSession classes to keep in sync.
- **OpSec**: the vault key comes out of PBKDF2-SHA256 at 600,000 rounds over your machine id. Memory is zeroized on shutdown, and a wrong key raises instead of quietly falling back to plaintext.
- **Light**: `aiohttp`, `rich` and `qrcode`. That is the whole dependency list.
- **Bots over MTProto**: pass `bot_token` together with `api_id` and `api_hash`, and the bot speaks raw MTProto instead of HTTP.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Benchmarks

Cold import, memory footprint and MTProto crypto, measured against telethon, pyrogram, aiogram and python-telegram-bot.

| | goygram | telethon | pyrogram | aiogram | python-telegram-bot |
|---|---|---|---|---|---|
| cold import (ms) | **77.2** | 342.0 | 461.5 | 3016.3 | 142.8 |
| RSS delta (MB) | **10.8** | 48.4 | 35.6 | 152.2 | 18.8 |
| AES-256-IGE (MB/s, 64 KiB) | **1062.5** | 10.8 | 202.4 | — | — |
| loads `message` (ops/s) | **577,821** | — | — | — | — |
| loads `updateNewMessage` (ops/s) | **225,347** | — | — | — | — |

There is no C extension to install separately, the crypto is already in the package. For scale, tgcrypto reaches 204.3 MB/s on the same hardware. Parsing a realistic `updateNewMessage` costs 3.8 µs at p50 and 8.9 µs at p99. How the numbers were taken is written up in [`benchmarks/`](./benchmarks).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->
## Getting started

### Prerequisites

Python 3.13 or newer. The prebuilt wheels pull nothing else in, and Rust is only needed when you build from source.

A bot needs a token from [@BotFather](https://t.me/BotFather). A user account needs an `api_id` and an `api_hash` from [my.telegram.org](https://my.telegram.org).

### Installation

```bash
pip install goygram
```

The wheels are built against the stable ABI and carry the `cp38-abi3` tag, so one native build loads on CPython 3.13 and everything newer, on Linux, Windows, macOS and Termux.

On Termux pip resolves a prebuilt wheel the same way it does anywhere else, because the CPython that Termux ships reports Android platform tags:

```bash
pkg install python-pip
pip install goygram
```

Phones (`arm64_v8a`) and emulator or Chromebook builds (`x86_64`) are both covered, built against Android API level 24. The dependencies resolve to wheels as well, so nothing is compiled on the device.

To build from source when your platform has no wheel, Rust has to be on the machine:

```bash
git clone https://github.com/GoyGram/GoyGram
cd GoyGram
python -m pip install --no-build-isolation .
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- USAGE EXAMPLES -->
## Usage

A user account talks MTProto, so it needs an `api_id` and an `api_hash`:

```python
import asyncio
from goygram import GoyGram

app = GoyGram(api_id=123456, api_hash="0123456789abcdef0123456789abcdef")

@app.on_cmd("ping")
async def ping(msg):
    await msg.reply("pong")

asyncio.run(app.run())
```

The first run opens a login screen in the terminal. Pick a QR code or a phone number, and give the 2FA password if the account has one. The session lands in `default.vault`, encrypted with AES-256-GCM.

```python
# several accounts out of one process
app = GoyGram(api_id=..., api_hash=..., session_name="farm_worker_1")

# one message through Bot API, the next through MTProto
await app.send_msg("123456789", "via Bot API", via="api")
await app.send_msg("123456789", "via MTProto", via="mtproto")
```

> [!WARNING]
> Leave `GOYGRAM_VAULT_KEY` unset and the vault key is derived from the host machine id. Whoever holds both the vault file and that machine id can open it. Set `GOYGRAM_VAULT_KEY` to 32 random bytes whenever the vault has to stay closed on a host that could be compromised or copied.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- DOCUMENTATION -->
## Documentation

The rest of the library has its own pages:

- [Documentation site](https://goygram.github.io/docs), the full guide in English and Russian
- [Quick start, Bot API](https://github.com/GoyGram/GoyGram/wiki/Quick-Start-Bot-API)
- [Quick start, MTProto userbot](https://github.com/GoyGram/GoyGram/wiki/Quick-Start-MTProto-Userbot)
- [Sessions and authentication](https://github.com/GoyGram/GoyGram/wiki/Sessions-and-Authentication)
- [Bot API calls](https://github.com/GoyGram/GoyGram/wiki/Bot-API-Calls) and [MTProto calls](https://github.com/GoyGram/GoyGram/wiki/MTProto-Calls)
- [Architecture and runtime behaviour](https://github.com/GoyGram/GoyGram/wiki/Architecture-and-Runtime-Behavior)
- [Benchmarks](https://github.com/GoyGram/GoyGram/wiki/Benchmarks)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTRIBUTING -->
## Contributing

Bug reports and pull requests are welcome.

CI is strict about two things: the type check has to pass, and commits have to be signed (`git commit -S`).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- LICENSE -->
## License

GoyGram is released under the GNU Affero General Public License v3.0. The full text is in [`LICENSE`](./LICENSE).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTACT -->
## Contact

Questions and bug reports go to [GitHub issues](https://github.com/GoyGram/GoyGram/issues).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
[python-shield]: https://img.shields.io/badge/python-3.13+-blue.svg?style=for-the-badge&logo=python
[python-url]: https://www.python.org
[rust-shield]: https://img.shields.io/badge/Rust_Core-Native-orange.svg?style=for-the-badge&logo=rust
[rust-url]: https://www.rust-lang.org/
[pypi-shield]: https://img.shields.io/pypi/v/goygram.svg?style=for-the-badge&logo=pypi&color=3775A9
[pypi-url]: https://pypi.org/project/goygram/
[downloads-shield]: https://img.shields.io/pypi/dm/goygram.svg?style=for-the-badge&logo=pypi&color=3775A9
[license-shield]: https://img.shields.io/badge/License-AGPL_v3-red.svg?style=for-the-badge
[license-url]: https://www.gnu.org/licenses/agpl-3.0
[strict-shield]: https://img.shields.io/github/actions/workflow/status/GoyGram/GoyGram/strict.yml?style=for-the-badge&label=strict
[strict-url]: https://github.com/GoyGram/GoyGram/actions
[pub-shield]: https://img.shields.io/github/actions/workflow/status/GoyGram/GoyGram/pub.yml?style=for-the-badge&label=publish
[pub-url]: https://github.com/GoyGram/GoyGram/actions
[telegram-shield]: https://img.shields.io/badge/Telegram-MTProto_%7C_BotAPI-2CA5E0.svg?style=for-the-badge&logo=telegram
[telegram-url]: https://telegram.org
[mtproto-shield]: https://img.shields.io/badge/Platforms-Linux_%7C_macOS_%7C_Windows_%7C_Android-4B4B4B.svg?style=for-the-badge&logo=linux&logoColor=white
[mtproto-url]: https://pypi.org/project/goygram/
[opsec-shield]: https://img.shields.io/badge/OpSec-Vault_Encrypted-black.svg?style=for-the-badge
[opsec-url]: https://github.com/GoyGram/GoyGram
[docs-shield]: https://img.shields.io/badge/Docs-Read_the_Wiki-blue.svg?style=for-the-badge&logo=readthedocs
[docs-url]: https://goygram.github.io/docs
[wiki-shield]: https://img.shields.io/badge/Wiki-GitHub-blue.svg?style=for-the-badge&logo=github
[wiki-url]: https://github.com/GoyGram/GoyGram/wiki
[commit-shield]: https://img.shields.io/github/last-commit/GoyGram/GoyGram?style=for-the-badge
[commit-url]: https://github.com/GoyGram/GoyGram/commits
[stars-shield]: https://img.shields.io/github/stars/GoyGram/GoyGram?style=for-the-badge
[stars-url]: https://github.com/GoyGram/GoyGram/stargazers
[forks-shield]: https://img.shields.io/github/forks/GoyGram/GoyGram?style=for-the-badge
[forks-url]: https://github.com/GoyGram/GoyGram/network/members
[issues-shield]: https://img.shields.io/github/issues/GoyGram/GoyGram?style=for-the-badge
[issues-url]: https://github.com/GoyGram/GoyGram/issues
