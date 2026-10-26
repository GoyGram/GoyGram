# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DcEndpoint:
    dc_id: int
    host: str
    port: int


def get_dynamic_dc_config(timeout: int = 6) -> dict[int, list[DcEndpoint]]:
    _ = timeout
    by_dc: dict[int, list[DcEndpoint]] = {
        1: [DcEndpoint(dc_id=1, host="149.154.175.53", port=443)],
        2: [DcEndpoint(dc_id=2, host="149.154.167.50", port=443)],
        3: [DcEndpoint(dc_id=3, host="149.154.175.100", port=443)],
        4: [DcEndpoint(dc_id=4, host="149.154.167.91", port=443)],
        5: [DcEndpoint(dc_id=5, host="91.108.56.130", port=443)],
    }
    by_dc[0] = by_dc[2]
    return by_dc


def pick_dc_endpoint(dc_map: dict[int, list[DcEndpoint]], preferred_dc: int | None = None) -> DcEndpoint:
    if preferred_dc is not None and preferred_dc in dc_map and dc_map[preferred_dc]:
        return dc_map[preferred_dc][0]
    if 0 in dc_map and dc_map[0]:
        return dc_map[0][0]
    for dc_id in (4, 2, 1, 5, 3):
        if dc_id in dc_map and dc_map[dc_id]:
            return dc_map[dc_id][0]
    raise RuntimeError("No available endpoint in DC map")


def probe_dc_endpoint(endpoint: DcEndpoint, timeout: float = 2.0) -> bool:
    # ponytail: sync TCP probe; good enough for a one-shot login-time health check,
    # upgrade to async if it ever runs in a hot path
    import socket as _socket
    s = _socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((endpoint.host, endpoint.port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def pick_reachable_dc(dc_map: dict[int, list[DcEndpoint]], preferred_dc: int | None = None) -> DcEndpoint:
    # Some Telegram edge frontends answer SYN with a SYN-ACK whose echoed TCP timestamp
    # is lower than the client's own TS; Linux PAWS then silently drops it and every
    # connect times out. Probe a few endpoints and return the first that completes a
    # TCP handshake instead of hard-failing on the preferred one.
    order: list[int] = []
    if preferred_dc is not None and preferred_dc in dc_map and dc_map[preferred_dc]:
        order.append(preferred_dc)
    order += [dc for dc in (4, 2, 1, 5, 3) if dc not in order]
    for dc_id in order:
        endpoints = dc_map.get(dc_id) or []
        for ep in endpoints:
            if probe_dc_endpoint(ep):
                return ep
    return dc_map[preferred_dc or 4][0] if (preferred_dc or 4) in dc_map else dc_map[4][0]
