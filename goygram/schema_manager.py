# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import threading
from pathlib import Path

log = logging.getLogger("goygram.schema_manager")

SCHEMA_URL = (
    "https://raw.githubusercontent.com/telegramdesktop/tdesktop/dev/"
    "Telegram/SourceFiles/mtproto/scheme/api.tl"
)
MTPROTO_SCHEMA_URL = (
    "https://raw.githubusercontent.com/telegramdesktop/tdesktop/dev/"
    "Telegram/SourceFiles/mtproto/scheme/mtproto.tl"
)
LAYER_URL = "https://core.telegram.org/api/layers"
CURRENT_LAYER_FLOOR = 229

CACHE_DIR = Path.home() / ".goygram" / "cache"
CACHE_SCHEMA_PATH = CACHE_DIR / "api.tl"
CACHE_ETAG_PATH = CACHE_DIR / "api.tl.etag"
CACHE_MTPROTO_PATH = CACHE_DIR / "mtproto.tl"
CACHE_MTPROTO_ETAG_PATH = CACHE_DIR / "mtproto.tl.etag"
CACHE_LAYER_PATH = CACHE_DIR / "schema.layer"

_fetch_lock = threading.Lock()


def _http_get(url: str, etag: str | None = None) -> tuple[str | None, str | None]:
    import urllib.error
    import urllib.request

    req = urllib.request.Request(url)
    if etag:
        req.add_header("If-None-Match", etag)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read().decode("utf-8"), response.headers.get("ETag")
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return None, etag
        log.warning("HTTP %s fetching %s", exc.code, url)
        return None, None
    except Exception as exc:
        log.warning("Error fetching %s: %s", url, exc)
        return None, None


def _latest_layer() -> int:
    body, _ = _http_get(LAYER_URL)
    if body is None:
        return CURRENT_LAYER_FLOOR
    values = [int(value) for value in re.findall(r"Layer\s+(\d+)", body, re.IGNORECASE)]
    return max([CURRENT_LAYER_FLOOR, *values]) if values else CURRENT_LAYER_FLOOR


def _cached_layer() -> int | None:
    try:
        layer = int(CACHE_LAYER_PATH.read_text().strip())
        return layer if layer > 0 else None
    except (OSError, ValueError):
        return None


def _fetch_and_cache_schema(layer: int) -> tuple[str | None, str | None]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    api_etag = CACHE_ETAG_PATH.read_text().strip() if CACHE_ETAG_PATH.exists() else None
    mtp_etag = CACHE_MTPROTO_ETAG_PATH.read_text().strip() if CACHE_MTPROTO_ETAG_PATH.exists() else None
    api_text, api_new_etag = _http_get(SCHEMA_URL, api_etag)
    mtp_text, mtp_new_etag = _http_get(MTPROTO_SCHEMA_URL, mtp_etag)
    if api_text is not None:
        CACHE_SCHEMA_PATH.write_text(api_text)
        if api_new_etag:
            CACHE_ETAG_PATH.write_text(api_new_etag)
    if mtp_text is not None:
        CACHE_MTPROTO_PATH.write_text(mtp_text)
        if mtp_new_etag:
            CACHE_MTPROTO_ETAG_PATH.write_text(mtp_new_etag)
    if api_text is not None and mtp_text is not None:
        CACHE_LAYER_PATH.write_text(str(layer))
    return api_text, mtp_text


def _load_schema(ext_module, api_text: str, mtproto_text: str | None) -> None:
    from goygram.protocol.tl_schema import parse_api_tl

    merged = mtproto_text + "\n---types---\n" + api_text if mtproto_text else api_text
    with tempfile.NamedTemporaryFile(mode="w", suffix=".tl", delete=False) as handle:
        handle.write(merged)
        path = handle.name
    try:
        schema = parse_api_tl(path)
        info = ext_module.load_schema(json.dumps(schema, separators=(",", ":"), ensure_ascii=False))
        log.info("Loaded official Telegram schema: %s", info)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def init_schema(ext_module, bundled_api_tl_path: str | None = None, on_layer=None):
    try:
        info = json.loads(ext_module.schema_info())
        log.info("Bootstrap schema active: %s methods, %s ctors", info.get("methods", 0), info.get("constructors", 0))
    except Exception:
        log.warning("No bootstrap schema available, schema_manager may fail")

    cached_layer = _cached_layer()
    latest_layer = _latest_layer()
    api_text = CACHE_SCHEMA_PATH.read_text() if CACHE_SCHEMA_PATH.exists() else None
    mtproto_text = CACHE_MTPROTO_PATH.read_text() if CACHE_MTPROTO_PATH.exists() else None
    refresh = api_text is None or mtproto_text is None or cached_layer is None or cached_layer != latest_layer
    if refresh:
        fresh_api, fresh_mtp = _fetch_and_cache_schema(latest_layer)
        if fresh_api is not None:
            api_text, mtproto_text = fresh_api, fresh_mtp
            cached_layer = latest_layer
    if api_text is None:
        raise RuntimeError("Unable to load official Telegram schema from the network or cache")
    if cached_layer is None:
        cached_layer = latest_layer
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_LAYER_PATH.write_text(str(cached_layer))
    _load_schema(ext_module, api_text, mtproto_text)
    threading.Thread(target=_background_update, args=(ext_module, on_layer), daemon=True).start()
    return cached_layer


def _background_update(ext_module, on_layer=None):
    log.debug("Background schema update started")
    layer = _latest_layer()
    api_text, mtproto_text = _fetch_and_cache_schema(layer)
    if api_text is None:
        log.debug("No schema update available")
        return
    try:
        _load_schema(ext_module, api_text, mtproto_text)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_LAYER_PATH.write_text(str(layer))
        if callable(on_layer):
            on_layer(layer)
        log.info("Schema hot-reloaded layer=%s", layer)
    except Exception as exc:
        log.warning("Schema hot-reload failed: %s", exc)
