import secrets
import time

import goygram
import goygram.ext as rx
from goygram.schema_manager import init_schema
from goygram.types.kbd import kbd_to_tl

init_schema(rx)
print("goygram", goygram.__version__)
print("ext", rx.__file__)

peer = {"_": "peerUser", "user_id": 1}
text = "ping payload " * 14
kbd = kbd_to_tl({"inline_keyboard": [[{"text": "ok", "callback_data": "pong"}, {"text": "link", "url": "https://t.me"}]]})
msg = {
    "_": "message",
    "id": 42,
    "from_id": peer,
    "peer_id": peer,
    "date": 1700000000,
    "message": text,
    "fwd_from": {"_": "messageFwdHeader", "from_id": peer, "date": 1699990000},
    "reply_markup": kbd,
}
upd = {"_": "updateNewMessage", "message": msg, "pts": 1, "pts_count": 1}
pkt = rx.dumps(upd)
simple = {"_": "message", "id": 42, "peer_id": peer, "date": 1700000000, "message": "bench " * 4}
plain = rx.dumps(simple)

send = {
    "peer": {"_": "inputPeerUser", "user_id": 1, "access_hash": 1},
    "message": text,
    "random_id": secrets.randbits(62),
}


def rate(fn, budget=0.8):
    t0 = time.perf_counter()
    n = 0
    while time.perf_counter() - t0 < budget:
        fn()
        n += 1
    return n / (time.perf_counter() - t0)


def pct(xs, p):
    xs = sorted(xs)
    i = min(len(xs) - 1, int(len(xs) * p / 100.0))
    return xs[i] * 1e6


n = 8000
samples = []
for _ in range(n):
    t0 = time.perf_counter()
    rx.loads(pkt)
    samples.append(time.perf_counter() - t0)

ser = rate(lambda: rx.serialize_method("messages.sendMessage", send))
plainload = rate(lambda: rx.loads(plain))
dump = rate(lambda: rx.dumps(upd))
load = rate(lambda: rx.loads(pkt))
echo = rate(lambda: (rx.loads(pkt), rx.dumps({"_": "message", "id": 43, "peer_id": peer, "date": 1700000001, "message": "pong"})))

key = secrets.token_bytes(32)
iv = secrets.token_bytes(32)
pad = pkt + bytes((16 - len(pkt) % 16) % 16)
ige = rate(lambda: rx.aes_ige_dec(rx.aes_ige_enc(pad, key, iv), key, iv))
nonce = secrets.token_bytes(12)
blob = secrets.token_bytes(4096)
gcm_e = rate(lambda: rx.aes_gcm_encrypt(key, nonce, blob, b""))
ct = rx.aes_gcm_encrypt(key, nonce, blob, b"")
gcm_d = rate(lambda: rx.aes_gcm_decrypt(key, nonce, ct, b""))

info = rx.schema_info()
print(f"packet {len(pkt)} B  schema layer {info['layer']} {info['constructors']} ctors")
print(f"serialize messages.sendMessage     {ser:>10,.0f} ops/s")
print(f"loads message                      {plainload:>10,.0f} ops/s")
print(f"dumps updateNewMessage             {dump:>10,.0f} ops/s")
print(f"loads updateNewMessage             {load:>10,.0f} ops/s")
print(f"echo loads+dumps                   {echo:>10,.0f} ops/s")
print(f"AES-256-IGE enc+dec packet         {ige:>10,.0f} ops/s")
print(f"AES-256-GCM encrypt 4 KiB          {gcm_e:>10,.0f} ops/s")
print(f"AES-256-GCM decrypt 4 KiB          {gcm_d:>10,.0f} ops/s")
print("loads latency us")
print(f"  p50 {pct(samples, 50):.1f}  p95 {pct(samples, 95):.1f}  p99 {pct(samples, 99):.1f}  p99.9 {pct(samples, 99.9):.1f}")
