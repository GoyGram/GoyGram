# parallel transfer technique adapted from mautrix-telegram's parallel_file_transfer.py (AGPL-3.0, Tulir Asokan)
from __future__ import annotations
import asyncio, hashlib, math, os, re as _re, secrets, tempfile
from pathlib import Path
from typing import Any

from goygram.errors import FileReferenceExpiredError, GoyGramError
from goygram.transports.mtproto import MTNet

max_connections = 20
full_size = 100 * 1024 * 1024
big_size = 10 * 1024 * 1024


def connection_count(file_size: int) -> int:
    if file_size >= full_size:
        return max_connections
    return max(1, math.ceil((file_size / full_size) * max_connections))


class ChargedSender(MTNet):
    def __init__(self, host: str, port: int, auth_key: bytes | None, server_salt: bytes | None, *, proxy: str | None = None, app_name: str | None = None, app_version: str | None = None, device_model: str | None = None, system_version: str | None = None, system_lang_code: str = "en", lang_pack: str = "", lang_code: str = "en") -> None:
        super().__init__(host, port, None, None, proxy=proxy, app_name=app_name, app_version=app_version, device_model=device_model, system_version=system_version, system_lang_code=system_lang_code, lang_pack=lang_pack, lang_code=lang_code)
        if auth_key is not None:
            self.auth_key = auth_key
        if server_salt:
            self.server_salt = server_salt

    def _dispatch_update(self, update: Any) -> None:
        return

    def _dispatch_updates(self, result: Any) -> None:
        return

    async def _post_reconnect_recovery(self) -> None:
        return


class _UploadLane:
    __slots__ = ("conn", "file_id", "big", "total", "index", "stride", "previous")

    def __init__(self, conn: ChargedSender, file_id: int, big: bool, total: int, index: int, stride: int) -> None:
        self.conn = conn
        self.file_id = file_id
        self.big = big
        self.total = total
        self.index = index
        self.stride = stride
        self.previous: asyncio.Task[None] | None = None

    async def push(self, data: bytes) -> None:
        if self.previous is not None:
            await self.previous
        self.previous = asyncio.ensure_future(self._push(data))

    async def _push(self, data: bytes) -> None:
        kw: dict[str, Any] = {"file_id": self.file_id, "file_part": self.index, "bytes": data}
        if self.big:
            kw["file_total_parts"] = self.total
        act = "upload.saveBigFilePart" if self.big else "upload.saveFilePart"
        result = await self.conn.call(act, **kw)
        if result is False or (isinstance(result, dict) and result.get("ok") is False):
            raise RuntimeError("upload part rejected")
        self.index += self.stride

    async def finish(self) -> None:
        if self.previous is not None:
            await self.previous


class _DownloadLane:
    __slots__ = ("conn", "location", "offset", "limit", "stride", "remaining")

    def __init__(self, conn: ChargedSender, location: Any, offset: int, limit: int, stride: int, remaining: int) -> None:
        self.conn = conn
        self.location = location
        self.offset = offset
        self.limit = limit
        self.stride = stride
        self.remaining = remaining

    async def next(self) -> bytes | None:
        if self.remaining <= 0:
            return None
        response = await self.conn.call("upload.getFile", location=self.location, offset=self.offset, limit=self.limit)
        self.remaining -= 1
        self.offset += self.stride
        body = response.get("result") if isinstance(response, dict) and isinstance(response.get("result"), dict) else response
        payload = body.get("bytes") if isinstance(body, dict) else None
        if isinstance(payload, str):
            try:
                payload = bytes.fromhex(payload)
            except ValueError:
                payload = None
        if not isinstance(payload, (bytes, bytearray)):
            raise RuntimeError("upload.getFile returned no bytes")
        return bytes(payload)


async def _spawn_sender(mtnet: MTNet, host: str, port: int, auth_key: bytes | None, salt: bytes) -> ChargedSender:
    sender = ChargedSender(host, port, auth_key, salt, proxy=mtnet.proxy_url, app_name=mtnet.app_name, app_version=mtnet.app_version, device_model=mtnet.device_model, system_version=mtnet.system_version, system_lang_code=mtnet.system_lang_code, lang_pack=mtnet.lang_pack, lang_code=mtnet.lang_code)
    sender._api_id = mtnet._api_id
    sender.layer = mtnet.layer
    await sender.ensure_auth_key()
    await sender._ensure_reader()
    return sender


async def _home_senders(mtnet: MTNet, count: int) -> list[ChargedSender]:
    return [await _spawn_sender(mtnet, mtnet.host, mtnet.port, mtnet.auth_key, mtnet.server_salt) for _ in range(count)]


async def _file_dc_senders(mtnet: MTNet, count: int, dc_id: int) -> list[ChargedSender]:
    from goygram.dc_fetcher import get_dynamic_dc_config, pick_dc_endpoint
    endpoint = pick_dc_endpoint(get_dynamic_dc_config(), preferred_dc=int(dc_id))
    if endpoint.host == mtnet.host and endpoint.port == mtnet.port and mtnet.auth_key:
        return await _home_senders(mtnet, count)
    if not getattr(mtnet, "dc_auth_keys", None):
        mtnet.dc_auth_keys = {}
    cached = mtnet.dc_auth_keys.get(int(dc_id))
    if isinstance(cached, dict) and cached.get("key"):
        return [await _spawn_sender(mtnet, endpoint.host, endpoint.port, cached["key"], cached.get("salt") or b"\x00" * 8) for _ in range(count)]
    export = await mtnet.call("auth.exportAuthorization", dc_id=int(dc_id))
    body = export.get("result") if isinstance(export, dict) and isinstance(export.get("result"), dict) else export
    export_id = body.get("id") if isinstance(body, dict) else None
    export_bytes = body.get("bytes") if isinstance(body, dict) else None
    if isinstance(export_bytes, str):
        export_bytes = bytes.fromhex(export_bytes)
    if not isinstance(export_id, int) or not isinstance(export_bytes, (bytes, bytearray)):
        raise RuntimeError("auth.exportAuthorization returned no usable payload")
    first = await _spawn_sender(mtnet, endpoint.host, endpoint.port, None, b"\x00" * 8)
    await first.call("auth.importAuthorization", id=int(export_id), bytes=bytes(export_bytes))
    auth_key = first.auth_key
    if auth_key is None:
        raise RuntimeError("file DC authorization produced no auth key")
    mtnet.dc_auth_keys[int(dc_id)] = {"key": auth_key, "salt": first.server_salt}
    hook = getattr(mtnet, "_entity_flush_hook", None)
    if callable(hook):
        try:
            hook()
        except Exception:
            pass
    rest = [await _spawn_sender(mtnet, endpoint.host, endpoint.port, auth_key, first.server_salt) for _ in range(count - 1)]
    return [first, *rest]


async def charged_upload(mtnet: MTNet, source: Any, *, file_name: str | None = None, part_size: int = 524288, progress: Any = None, connections: int | None = None) -> dict[str, Any]:
    if part_size < 1024 or part_size > 524288 or part_size % 1024:
        raise ValueError("part_size must be a multiple of 1024 between 1024 and 524288")
    close_source = False
    if isinstance(source, (str, os.PathLike)):
        path = Path(source)
        handle = path.open("rb")
        close_source = True
        file_name = file_name or path.name
        size = path.stat().st_size
    else:
        handle = source
        file_name = file_name or "file"
        try:
            if not handle.seekable():
                return await mtnet.upload_file(source, file_name=file_name, part_size=part_size, progress=progress)
            current = handle.tell()
            size = handle.seek(0, os.SEEK_END)
            handle.seek(current)
        except Exception:
            return await mtnet.upload_file(source, file_name=file_name, part_size=part_size, progress=progress)
    big = size > big_size
    parts_total = max(1, (size + part_size - 1) // part_size)
    conns = connections or connection_count(size)
    conns = max(1, min(conns, max_connections, parts_total))
    file_id = secrets.randbits(63)
    md5 = hashlib.new("md5")
    senders = await _home_senders(mtnet, conns)
    lanes = [_UploadLane(conn, file_id, big, parts_total, i, conns) for i, conn in enumerate(senders)]
    sent = 0
    ticker = 0
    try:
        while True:
            chunk = handle.read(part_size)
            if not chunk:
                break
            if not big:
                md5.update(chunk)
            await lanes[ticker].push(chunk)
            sent += len(chunk)
            if progress is not None:
                if asyncio.iscoroutinefunction(progress):
                    await progress(sent, size or sent)
                else:
                    progress(sent, size or sent)
            ticker = (ticker + 1) % conns
        for lane in lanes:
            await lane.finish()
    finally:
        await asyncio.gather(*(sender.close() for sender in senders), return_exceptions=True)
        if close_source:
            handle.close()
    return {"id": file_id, "parts": parts_total, "name": file_name, "md5": md5.hexdigest() if not big else "", "big": big}


async def charged_download(mtnet: MTNet, location: Any, destination: Any, *, size: int = 0, part_size: int = 524288, progress: Any = None, media_source: Any = None, connections: int | None = None) -> int:
    if part_size < 1024 or part_size > 524288 or part_size % 1024:
        raise ValueError("part_size must be a multiple of 1024 between 1024 and 524288")
    if size <= 0:
        return await mtnet.download_file(location, destination, limit=part_size, progress=progress, media_source=media_source)
    close_target = False
    temp_path: Path | None = None
    if isinstance(destination, (str, os.PathLike)):
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(dir=target.parent, delete=False)
        temp_path = Path(handle.name)
        close_target = True
    else:
        target = None
        handle = destination
    file_dc: int | None = None
    refreshed = False
    while True:
        try:
            await mtnet.call("upload.getFile", location=location, offset=0, limit=1024)
            break
        except FileReferenceExpiredError:
            if refreshed or media_source is None:
                raise
            refreshed = True
            location = await mtnet._refresh_file_reference(media_source, location)
        except GoyGramError as exc:
            match = _re.search(r"FILE_MIGRATE_(\d+)", str(exc).upper())
            if match is None:
                raise
            file_dc = int(match.group(1))
            break
    conns = connections or connection_count(size)
    conns = max(1, min(conns, max_connections))
    parts_total = (size + part_size - 1) // part_size
    senders: list[ChargedSender] = []
    if file_dc is not None:
        senders = await _file_dc_senders(mtnet, conns, file_dc)
    else:
        senders = await _home_senders(mtnet, conns)
    total = 0

    def build_lanes() -> list[_DownloadLane]:
        minimum, remainder = divmod(parts_total, len(senders))
        lanes: list[_DownloadLane] = []
        for i, conn in enumerate(senders):
            if remainder > 0:
                count = minimum + 1
                remainder -= 1
            else:
                count = minimum
            if count <= 0:
                break
            lanes.append(_DownloadLane(conn, location, i * part_size, part_size, len(senders) * part_size, count))
        return lanes

    try:
        for attempt in range(3):
            try:
                lanes = build_lanes()
                total = 0
                handle.seek(0)
                handle.truncate()
                active = list(lanes)
                while active:
                    batch = list(active)
                    results = await asyncio.gather(*(lane.next() for lane in batch))
                    for lane, data in zip(batch, results):
                        if data:
                            handle.write(data)
                            total += len(data)
                        if not data or len(data) < lane.limit:
                            active.remove(lane)
                    if progress is not None:
                        if asyncio.iscoroutinefunction(progress):
                            await progress(total, size)
                        else:
                            progress(total, size)
                break
            except FileReferenceExpiredError:
                if attempt >= 2 or media_source is None:
                    raise
                location = await mtnet._refresh_file_reference(media_source, location)
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise
    finally:
        await asyncio.gather(*(sender.close() for sender in senders), return_exceptions=True)
        if close_target:
            handle.close()
    if temp_path is not None and target is not None:
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, target)
    return total
