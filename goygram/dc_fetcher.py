# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

import re
import urllib.request
from urllib.request import ProxyHandler, build_opener
from dataclasses import dataclass

_PROXY_RE = re.compile(r"^proxy_for\s+(-?\d+)\s+([0-9.]+):(\d+);$")
_DEFAULT_RE = re.compile(r"^default\s+(\d+);$")


@dataclass(frozen=True)
class DcEndpoint:
    dc_id: int
    host: str
    port: int


def get_dynamic_dc_config(timeout: int = 6) -> dict[int, list[DcEndpoint]]:
    req = urllib.request.Request(
        "https://core.telegram.org/getProxyConfig",
        headers={"User-Agent": "GoyGram/1.0 (+dynamic-dc-routing)"},
    )
    # Use default opener with system proxy/env settings to match other network calls behavior.
    opener = build_opener(ProxyHandler())
    try:
        with opener.open(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8", errors="replace")
    except PermissionError:
        fallback = DcEndpoint(dc_id=2, host="149.154.167.50", port=443)
        return {2: [fallback], 0: [fallback]}

    by_dc: dict[int, list[DcEndpoint]] = {}
    default_dc: int | None = None
    for raw in payload.splitlines():
        line = raw.strip()
        d = _DEFAULT_RE.match(line)
        if d:
            default_dc = int(d.group(1))
            continue

        m = _PROXY_RE.match(line)
        if not m:
            continue
        dc_id = int(m.group(1))
        if dc_id <= 0 or dc_id not in {1, 2, 3, 4, 5}:
            continue
        by_dc.setdefault(dc_id, []).append(DcEndpoint(dc_id=dc_id, host=m.group(2), port=int(m.group(3))))

    if not by_dc:
        raise RuntimeError("No DC routes found in Telegram proxy config")

    if default_dc is not None and default_dc in by_dc:
        by_dc[0] = by_dc[default_dc]

    return by_dc


def pick_dc_endpoint(dc_map: dict[int, list[DcEndpoint]], preferred_dc: int | None = None) -> DcEndpoint:
    if preferred_dc is not None and preferred_dc in dc_map and dc_map[preferred_dc]:
        return dc_map[preferred_dc][0]
    if 0 in dc_map and dc_map[0]:
        return dc_map[0][0]
    for dc_id in (2, 1, 4, 5, 3):
        if dc_id in dc_map and dc_map[dc_id]:
            return dc_map[dc_id][0]
    raise RuntimeError("No available endpoint in DC map")
