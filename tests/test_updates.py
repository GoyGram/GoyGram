# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from goygram.client import AppCore
from goygram.core.bus import Bus
from goygram.core.fsm import FSMEngine
from goygram.vendor.botapi import BotNet
from goygram.vendor.mtproto import MTNet
import goygram.vendor.mtproto as mtproto


def make_net() -> BotNet:
    return BotNet("token", Bus())


def test_edited_message_is_normalized_as_edit() -> None:
    packet = make_net().norm(
        {
            "update_id": 10,
            "edited_message": {
                "message_id": 7,
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 456},
                "text": "edited",
            },
        }
    )

    assert packet is not None
    assert packet["kind"] == "edit"
    assert packet["msg_id"] == 7
    assert packet["chat_id"] == 123
    assert packet["text"] == "edited"


def test_unrecognized_update_is_preserved_for_generic_handlers() -> None:
    update = {
        "update_id": 11,
        "business_connection": {
            "id": "bc-1",
            "user": {"id": 456},
            "user_chat_id": 456,
            "date": 1,
        },
    }

    packet = make_net().norm(update)

    assert packet is not None
    assert packet["kind"] == "update"
    assert packet["update_type"] == "business_connection"
    assert packet["raw"] == update


def test_nested_rpc_updates_are_dispatched_in_order() -> None:
    net = MTNet("127.0.0.1", 443, Bus())
    seen: list[str] = []

    def collect(update: dict[str, object]) -> None:
        seen.append(str(update["_"]))

    net._dispatch_update = collect
    net._dispatch_updates(
        {
            "ok": True,
            "result": {
                "_": "updates",
                "updates": [
                    {"_": "updateNewMessage", "id": 1},
                    {"_": "updateReadHistoryInbox", "max_id": 2},
                ],
            },
        }
    )

    assert seen == ["updateNewMessage", "updateReadHistoryInbox"]


def test_single_structured_update_is_dispatched() -> None:
    net = MTNet("127.0.0.1", 443, Bus())
    seen: list[str] = []
    net._dispatch_update = lambda update: seen.append(str(update["_"]))

    net._dispatch_updates({"_": "updateShortSentMessage", "id": 3})

    assert seen == ["updateShortSentMessage"]


def test_bot_polling_requests_all_update_families() -> None:
    net = make_net()
    requests: list[tuple[str, dict[str, object]]] = []

    async def fake_req(m: str, data: dict[str, object] | None = None) -> list[object]:
        requests.append((m, data or {}))
        net.stop_ev.set()
        return []

    async def fake_boot() -> None:
        return None

    net.boot = fake_boot
    net.req = fake_req
    asyncio.run(net.spin())

    assert requests[0][0] == "getUpdates"
    assert requests[0][1]["allowed_updates"] == []


def test_structured_sent_code_is_preferred_over_heuristic_parser(monkeypatch) -> None:
    net = MTNet("127.0.0.1", 443, Bus())

    class FakeRx:
        @staticmethod
        def deserialize_constructor(data: bytes) -> str:
            return json.dumps(
                {
                    "_": "auth.sentCode",
                    "phone_code_hash": "hash-from-schema",
                    "type": {"_": "auth.sentCodeTypeEmailCode"},
                }
            )

    monkeypatch.setattr(mtproto, "rx", FakeRx)

    result = net._parse_rpc_result(b"\x02\x25\x00\x5e")

    assert result == {"ok": True, "phone_code_hash": "hash-from-schema"}


def test_vault_restore_loads_server_salt(monkeypatch, tmp_path) -> None:
    vault = tmp_path / "live.vault"
    vault.write_bytes(b"vault")
    app = object.__new__(AppCore)
    app.mt = SimpleNamespace(
        auth_key=None,
        server_salt=b"\x00" * 8,
        host="127.0.0.1",
        port=443,
        self_id=None,
    )
    app.self_id = None
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "goygram.security._read_vault",
        lambda path, session_name: {
            "auth_key": "00" * 256,
            "server_salt": "0102030405060708",
            "dc": 4,
            "user": {"id": 123},
        },
    )

    app._load_vault_from_disk("live", None, None)

    assert app.mt.server_salt == bytes.fromhex("0102030405060708")
    assert app.mt.host == "149.154.167.91"


def test_fsm_backend_loads_and_saves_json_snapshot() -> None:
    backend = {
        "items": [{"chat_id": 1, "user_id": 2, "state": "loaded", "data": {"x": 1}, "expiry": 4102444800}],
        "saved": [],
    }

    class Storage:
        def load(self):
            return backend["items"]

        def save(self, snapshot):
            backend["saved"].append(snapshot)

    fsm = FSMEngine(backend=Storage())

    assert fsm.get(1, 2) == "loaded"
    fsm.set(1, 2, "next", {"y": 2})

    assert backend["saved"][-1][0]["state"] == "next"
    assert backend["saved"][-1][0]["data"] == {"x": 1, "y": 2}


def test_fsm_on_change_receives_snapshot_for_external_persistence() -> None:
    snapshots = []
    fsm = FSMEngine(on_change=snapshots.append)

    fsm.set("10", "20", "waiting", {"step": 1})
    fsm.clear("10", "20")

    assert snapshots[0][0] == {
        "chat_id": 10,
        "user_id": 20,
        "state": "waiting",
        "data": {"step": 1},
        "expiry": snapshots[0][0]["expiry"],
    }
    assert snapshots[-1] == []


def test_public_client_accepts_fsm_backend() -> None:
    class Storage:
        def load(self):
            return []

        def save(self, snapshot):
            self.snapshot = snapshot

    storage = Storage()
    from goygram import GoyGram

    app = GoyGram(bot_token="token", fsm_backend=storage)
    app.set_state(1, 2, "ready", {"step": 1})

    assert app.get_state(1, 2) == "ready"
    assert storage.snapshot[0]["state"] == "ready"


def test_mt_builder_serializes_vectors_of_bytes() -> None:
    net = MTNet("127.0.0.1", 443, Bus())
    from goygram.schema_manager import init_schema

    init_schema(mtproto.rx, "api.tl")
    refs = [b"input-message"]

    body = net._build_body("messages.getMessages", {"ids": refs})

    assert int.from_bytes(body[:4], "little") == 0x63C66506
