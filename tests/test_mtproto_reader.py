import asyncio
import struct

from goygram.core.bus import Bus
from goygram.vendor.mtproto import MTNet


def test_only_one_reader_owns_transport_and_close_cancels_pending() -> None:
    async def exercise() -> None:
        net = MTNet("127.0.0.1", 443, Bus(), b"", b"")
        starts = 0

        async def reader() -> None:
            nonlocal starts
            starts += 1
            await net.stop_ev.wait()

        net.spin = reader
        await asyncio.gather(net._ensure_reader(), net._ensure_reader())
        assert starts == 1

        future = asyncio.get_running_loop().create_future()
        net.pending[1] = (future, {})
        await net.close()

        assert future.cancelled()
        assert not net.pending

    asyncio.run(exercise())


def test_updates_container_scans_past_non_message_updates() -> None:
    async def exercise() -> None:
        bus = Bus()
        net = MTNet("127.0.0.1", 443, bus, b"", b"")
        captured = []

        async def capture() -> None:
            captured.append(await bus.fetch())

        waiter = asyncio.create_task(capture())
        net._parse_new_message = lambda _: {"kind": "msg", "text": "/ping"}
        message = struct.pack("<I", 0x1F2B0AFD) + b"message"
        update = struct.pack("<I", 0x8C88C923) + b"typing" + message
        container = struct.pack("<I", 0x74AE4240) + struct.pack("<I", 0x1CB5C415) + struct.pack("<i", 2) + update
        assert net._parse_updates(container)["updates"] == [{"_": "updateNewMessage", "id": None, "raw": message}]
        net._dispatch_updates({"updates": [{"_": "updateNewMessage", "raw": message}]})
        await asyncio.wait_for(waiter, timeout=1)

        assert captured == [{"src": "mt", "data": {"kind": "msg", "text": "/ping"}}]

    asyncio.run(exercise())
