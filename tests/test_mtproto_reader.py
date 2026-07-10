import asyncio

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
