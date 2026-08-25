# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
import json
import logging
import os
import threading
from pathlib import Path

log = logging.getLogger("goygram.schema_manager")

SCHEMA_REF = "e94c20aa033c73fc614ef727913ca35305162ffc"
SCHEMA_URL = f"https://raw.githubusercontent.com/GoyGram/GoyGram/{SCHEMA_REF}/api.tl"
MTPROTO_SCHEMA_URL = f"https://raw.githubusercontent.com/GoyGram/GoyGram/{SCHEMA_REF}/mtproto.tl"

CACHE_DIR = Path.home() / ".goygram" / "cache"
CACHE_SCHEMA_PATH = CACHE_DIR / "api-211.tl"
CACHE_ETAG_PATH = CACHE_DIR / "api-211.tl.etag"
CACHE_MTPROTO_PATH = CACHE_DIR / "mtproto-211.tl"
CACHE_MTPROTO_ETAG_PATH = CACHE_DIR / "mtproto-211.tl.etag"

_fetch_lock = threading.Lock()


def _http_get(url: str, etag: str | None = None) -> tuple[str | None, str | None]:
    import urllib.request, urllib.error

    req = urllib.request.Request(url)
    if etag:
        req.add_header("If-None-Match", etag)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            new_etag = resp.headers.get("ETag", None)
            return body, new_etag
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return None, etag
        log.warning("HTTP %s fetching %s", e.code, url)
        return None, None
    except Exception as e:
        log.warning("Error fetching %s: %s", url, e)
        return None, None


def _fetch_and_cache_schema() -> tuple[str | None, str | None]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cached_etag = None
    if CACHE_ETAG_PATH.exists():
        cached_etag = CACHE_ETAG_PATH.read_text().strip()

    body, new_etag = _http_get(SCHEMA_URL, cached_etag)
    if body is not None:
        CACHE_SCHEMA_PATH.write_text(body)
        if new_etag:
            CACHE_ETAG_PATH.write_text(new_etag)

    mtproto_etag = None
    if CACHE_MTPROTO_ETAG_PATH.exists():
        mtproto_etag = CACHE_MTPROTO_ETAG_PATH.read_text().strip()

    mtproto_body, mtproto_new_etag = _http_get(MTPROTO_SCHEMA_URL, mtproto_etag)
    if mtproto_body is not None:
        CACHE_MTPROTO_PATH.write_text(mtproto_body)
        if mtproto_new_etag:
            CACHE_MTPROTO_ETAG_PATH.write_text(mtproto_new_etag)

    return body, mtproto_body


def _merge_schema_text(api_text: str, mtproto_text: str | None) -> str:
    if mtproto_text:
        return mtproto_text + "\n---types---\n" + api_text
    return api_text


def init_schema(ext_module, bundled_api_tl_path: str | None = None):
    from goygram.protocol.tl_schema import parse_api_tl
    import tempfile

    try:
        info = json.loads(ext_module.schema_info())
        log.info("Bootstrap schema active: %s methods, %s ctors",
                 info.get("methods", 0), info.get("constructors", 0))
    except Exception:
        log.warning("No bootstrap schema available, schema_manager may fail")

    api_text = CACHE_SCHEMA_PATH.read_text() if CACHE_SCHEMA_PATH.exists() else None
    mtp_text = CACHE_MTPROTO_PATH.read_text() if CACHE_MTPROTO_PATH.exists() else None
    if api_text is None:
        api_text, mtp_text = _fetch_and_cache_schema()
    if api_text is None:
        raise RuntimeError("Unable to load Telegram TL schema from the network or cache")

    merged = _merge_schema_text(api_text, mtp_text)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".tl", delete=False) as f:
        f.write(merged)
        tmp_path = f.name
    try:
        schema = parse_api_tl(tmp_path)
        schema_json = json.dumps(schema, separators=(",", ":"), ensure_ascii=False)
        info = ext_module.load_schema(schema_json)
        log.info("Loaded network schema: %s", info)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    bg = threading.Thread(target=_background_update, args=(ext_module,), daemon=True)
    bg.start()


def _background_update(ext_module):
    from goygram.protocol.tl_schema import parse_api_tl
    import tempfile

    log.debug("Background schema update started")
    api_text, mtp_text = _fetch_and_cache_schema()

    if api_text is None:
        log.debug("No schema update available")
        return

    merged = _merge_schema_text(api_text, mtp_text)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".tl", delete=False) as f:
        f.write(merged)
        tmp_path = f.name
    try:
        schema = parse_api_tl(tmp_path)
        schema_json = json.dumps(schema, separators=(",", ":"), ensure_ascii=False)
        info = ext_module.load_schema(schema_json)
        log.info("Schema hot-reloaded: %s", info)
    except Exception as e:
        log.warning("Schema hot-reload failed: %s", e)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
