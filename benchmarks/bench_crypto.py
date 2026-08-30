import time
from telethon.crypto.aes import AES as TelethonAES
import tgcrypto
from pyrogram.crypto import aes as pyro_aes
import goygram.ext as rx

key = bytes(range(32))
iv = bytes(range(32, 64))

impls = {
    "goygram (Rust, built-in)": lambda d: rx.aes_ige_enc(d, key, iv),
    "telethon (default)": lambda d: TelethonAES.encrypt_ige(d, key, iv),
    "tgcrypto (C, separate install)": lambda d: tgcrypto.ige256_encrypt(d, key, iv),
    "pyrogram": lambda d: pyro_aes.ige256_encrypt(d, key, iv),
}

msg = bytes(range(64))
outs = {name: bytes(fn(msg)) for name, fn in impls.items()}
assert all(o == outs["goygram (Rust, built-in)"] for o in outs.values()), "outputs differ"


def bench(fn, data, budget=1.0):
    for _ in range(50):
        fn(data)
    iters = 0
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < budget:
        fn(data)
        iters += 1
    dt = time.perf_counter() - t0
    return (iters * len(data)) / dt / 1e6


print("AES-256-IGE throughput (MB/s)")
header = " | ".join(f"{n:>24}" for n in impls)
print(f"{'size':>6} | {header}")
for size in (256, 4096, 65536):
    data = bytes(size)
    vals = [bench(fn, data) for fn in impls.values()]
    print(f"{size:>6} | " + " | ".join(f"{v:>24.1f}" for v in vals))

print("\nper-op latency, 256 B")
data = bytes(256)
for name, fn in impls.items():
    for _ in range(20):
        fn(data)
    t0 = time.perf_counter()
    for _ in range(200):
        fn(data)
    dt = (time.perf_counter() - t0) / 200
    print(f"  {name:24s} {dt*1e6:8.1f} µs/op")
