import json
import logging
import os
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

CACHE_DIR = Path.home() / ".goygram" / "cache"
CACHE_SCHEMA_PATH = CACHE_DIR / "api.tl"
CACHE_ETAG_PATH = CACHE_DIR / "api.tl.etag"
CACHE_MTPROTO_PATH = CACHE_DIR / "mtproto.tl"
CACHE_MTPROTO_ETAG_PATH = CACHE_DIR / "mtproto.tl.etag"

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


def _find_bundled_schema() -> tuple[str | None, str | None]:
    pkg_dir = Path(__file__).resolve().parent
    candidates = [
        pkg_dir.parent / "api.tl",
        pkg_dir / "api.tl",
        Path.cwd() / "api.tl",
        Path("/usr/share/goygram/api.tl"),
    ]
    for p in candidates:
        if p.exists():
            api = p.read_text()
            mtp = None
            mtp_candidate = p.with_name("mtproto.tl")
            if mtp_candidate.exists():
                mtp = mtp_candidate.read_text()
            return api, mtp
    return None, None


def _merge_schema_text(api_text: str, mtproto_text: str | None) -> str:
    if mtproto_text:
        return mtproto_text + "\n---types---\n" + api_text
    return api_text


def init_schema(ext_module, bundled_api_tl_path: str | None = None):
    from goygram.vendor.tl_schema import parse_api_tl
    import tempfile

    bootstrap_loaded = False
    try:
        info = json.loads(ext_module.schema_info())
        if info.get("methods", 0) > 0:
            bootstrap_loaded = True
            log.info("Bootstrap schema active: %s methods, %s ctors",
                     info["methods"], info["constructors"])
    except Exception:
        pass

    if not bootstrap_loaded:
        log.warning("No bootstrap schema available, schema_manager may fail")

    cached_available = CACHE_SCHEMA_PATH.exists()
    bundled_api, bundled_mtp = _find_bundled_schema()

    if not cached_available and bundled_api is None and bundled_api_tl_path:
        bundled_api = Path(bundled_api_tl_path).read_text()

    if bundled_api is not None:
        merged = _merge_schema_text(bundled_api, bundled_mtp)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tl", delete=False) as f:
            f.write(merged)
            tmp_path = f.name
        try:
            schema = parse_api_tl(tmp_path)
            schema_json = json.dumps(schema, separators=(",", ":"), ensure_ascii=False)
            info = ext_module.load_schema(schema_json)
            log.info("Loaded bundled schema: %s", info)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    elif cached_available:
        api_text = CACHE_SCHEMA_PATH.read_text()
        mtp_text = None
        if CACHE_MTPROTO_PATH.exists():
            mtp_text = CACHE_MTPROTO_PATH.read_text()
        merged = _merge_schema_text(api_text, mtp_text)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tl", delete=False) as f:
            f.write(merged)
            tmp_path = f.name
        try:
            schema = parse_api_tl(tmp_path)
            schema_json = json.dumps(schema, separators=(",", ":"), ensure_ascii=False)
            info = ext_module.load_schema(schema_json)
            log.info("Loaded cached schema: %s", info)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    bg = threading.Thread(target=_background_update, args=(ext_module,), daemon=True)
    bg.start()


def _background_update(ext_module):
    from goygram.vendor.tl_schema import parse_api_tl
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
