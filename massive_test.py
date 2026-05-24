# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
import json
from goygram import ext as rx
from goygram.vendor.tl_schema import parse_api_tl
from goygram.vendor.tl_core import MTCodec

methods = parse_api_tl("api.tl")
schema_json = json.dumps(methods, separators=(",", ":"), ensure_ascii=False)
rx.load_schema(schema_json)
codec = MTCodec()
print(f"Loaded {len(methods)} TL methods\n")

passed = 0
failed = 0

def verify(name, body, expected_cid):
    global passed, failed
    cid = int.from_bytes(body[:4], "little")
    if cid == expected_cid:
        passed += 1
        print(f"  [OK] {name} (cid=0x{cid:08x}, {len(body)} bytes)")
    else:
        failed += 1
        print(f"  [FAIL] {name}: cid=0x{cid:08x} expected 0x{expected_cid:08x}")

# No-arg methods
verify("updates.getState",
    bytes(rx.serialize_method("updates.getState", "{}")), 0xedd4882a)
verify("auth.logOut",
    bytes(rx.serialize_method("auth.logOut", "{}")), 0x3e72ba19)
verify("messages.getAllDrafts",
    bytes(rx.serialize_method("messages.getAllDrafts", "{}")), 0x6a3f8d65)

# Bool type
verify("account.updateStatus(offline=True)",
    bytes(rx.serialize_method("account.updateStatus", json.dumps({"offline": True}))), 0x6628562c)
verify("account.updateStatus(offline=False)",
    bytes(rx.serialize_method("account.updateStatus", json.dumps({"offline": False}))), 0x6628562c)

# Complex type args
self_peer = codec.input_peer_self()
verify("messages.getHistory",
    bytes(rx.serialize_method("messages.getHistory", json.dumps({
        "peer": self_peer.hex(), "offset_id": 0, "offset_date": 0,
        "add_offset": 0, "limit": 20, "max_id": 0, "min_id": 0, "hash": 0
    }))), 0x4423e6c5)

# Flags
verify("messages.sendMessage(no_webpage=True)",
    bytes(rx.serialize_method("messages.sendMessage", json.dumps({
        "peer": self_peer.hex(), "message": "Hello World",
        "random_id": 123456789, "no_webpage": True
    }))), 0x545cd15a)
verify("messages.sendMessage(silent=True)",
    bytes(rx.serialize_method("messages.sendMessage", json.dumps({
        "peer": self_peer.hex(), "message": "Silent", "random_id": 42, "silent": True
    }))), 0x545cd15a)

# Flag exclusion
verify("messages.getDialogs(exclude_pinned=True)",
    bytes(rx.serialize_method("messages.getDialogs", json.dumps({
        "exclude_pinned": True, "limit": 10, "offset_date": 0, "offset_id": 0, "hash": 0
    }))), 0xa0f4cb4f)
verify("messages.getDialogs(exclude_pinned=False)",
    bytes(rx.serialize_method("messages.getDialogs", json.dumps({
        "exclude_pinned": False, "limit": 5, "offset_date": 0, "offset_id": 0, "hash": 0
    }))), 0xa0f4cb4f)

# Vector<int>
verify("messages.deleteMessages",
    bytes(rx.serialize_method("messages.deleteMessages", json.dumps({
        "id": [1, 2, 3], "revoke": True
    }))), 0xe58e95d2)

# Vector<complex>
verify("users.getUsers",
    bytes(rx.serialize_method("users.getUsers", json.dumps({
        "id": [codec.input_user_self().hex()]
    }))), 0x0d91a548)

# String + int args
verify("contacts.resolveUsername",
    bytes(rx.serialize_method("contacts.resolveUsername", json.dumps({
        "username": "testuser"
    }))), 0x725afbbc)

# Auth methods
verify("auth.sendCode",
    bytes(rx.serialize_method("auth.sendCode", json.dumps({
        "phone_number": "79991112233", "api_id": 12345,
        "api_hash": "a" * 32, "settings": "783d25ad00000000"
    }))), 0xa677244f)
verify("auth.signIn",
    bytes(rx.serialize_method("auth.signIn", json.dumps({
        "phone_number": "79991112233", "phone_code_hash": "abc123def456"
    }))), 0x8d52a951)

# Channel type
verify("channels.getFullChannel",
    bytes(rx.serialize_method("channels.getFullChannel", json.dumps({
        "channel": codec.input_peer_channel(1234567890, 9876543210).hex()
    }))), 0x08736a09)

# Int args
verify("updates.getDifference",
    bytes(rx.serialize_method("updates.getDifference", json.dumps({
        "pts": 12345, "date": 1700000000, "qts": 0
    }))), 0x19c2f763)
verify("auth.exportAuthorization",
    bytes(rx.serialize_method("auth.exportAuthorization", json.dumps({
        "dc_id": 2
    }))), 0xe5bfffcd)

# Edge cases
try:
    rx.serialize_method("nonexistent.method", "{}")
    print("  [FAIL] nonexistent.method should raise error")
    failed += 1
except Exception:
    print("  [OK] nonexistent.method correctly raises error")
    passed += 1

assert rx.tl_method_exists("messages.sendMessage")
assert rx.tl_method_exists("messages.getDialogs")
assert rx.tl_method_exists("users.getUsers")
assert not rx.tl_method_exists("fake.method")
print("  [OK] tl_method_exists lookups correct")
passed += 1

print(f"\n{'='*60}")
print(f"Results: {passed}/{passed+failed} passed, {failed} failed")
print(f"Dynamic TL serializer: {len(methods)} methods, 0 hardcoded definitions")
assert failed == 0, f"{failed} tests failed!"
print("ALL TESTS PASSED")
