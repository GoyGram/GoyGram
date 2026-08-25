from __future__ import annotations

import asyncio
import json

from goygram.core.bus import Bus
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
