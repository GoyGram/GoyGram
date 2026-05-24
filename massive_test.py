# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
import asyncio, os, secrets, time
from goygram import GoyGram

os.environ["ALL_PROXY"] = "socks5://127.0.0.1:2080"

app = GoyGram(api_id=31228640, api_hash="6b96981510216203ccf9c6e499ce8827", session_name="my_account")

PASSED = 0
FAILED = 0

def ok(n, d=""):
    global PASSED; PASSED += 1
    print(f"  [OK] {n}" + (f" — {d}" if d else ""))

def fail(n, e=""):
    global FAILED; FAILED += 1
    print(f"  [FAIL] {n}" + (f": {e}" if e else ""))

async def main():
    global PASSED, FAILED
    print("=== GoyGram Live Dynamic RPC Test (fresh DH) ===\n")

    mt = app.core.mt
    mt.auth_key = None

    try:
        await asyncio.wait_for(mt.ensure_auth_key(), timeout=25)
        print(f"  Auth OK (salt={mt.server_salt[:4].hex()}, init_done={mt._init_done})\n")
    except asyncio.TimeoutError:
        fail("auth", "timeout"); app.stop(); return
    except Exception as e:
        fail("auth", str(e)); app.stop(); return

    c = mt.codec

    async def rpc(name, coro, timeout=25):
        try:
            res = await asyncio.wait_for(coro, timeout=timeout)
            ok(name)
            return res
        except asyncio.TimeoutError:
            fail(name, "timeout"); return None
        except Exception as e:
            fail(name, str(e)); return None

    print("--- 1: updates.getState ---")
    res = await rpc("updates.getState", app.core.mt_req("updates.getState"))
    if isinstance(res, dict):
        print(f"    pts={res.get('pts')}, date={res.get('date')}")

    print("--- 2: users.getFullUser ---")
    res = await rpc("users.getFullUser",
        app.core.mt_req("users.getFullUser", id=c.input_user_self().hex()))
    if isinstance(res, dict):
        uid = res.get("id") or res.get("user_id") or 0
        if uid:
            app.core.self_id = uid; mt.self_id = uid
            print(f"    ID={uid}, name={res.get('first_name','?')}")

    print("--- 3: users.getUsers ---")
    await rpc("users.getUsers",
        app.core.mt_req("users.getUsers", id=[c.input_user_self().hex()]))

    print("--- 4: messages.getDialogs ---")
    await rpc("messages.getDialogs",
        app.core.mt_req("messages.getDialogs",
            exclude_pinned=False, limit=5,
            offset_date=0, offset_id=0, hash=0))

    print("--- 5: contacts.resolveUsername ---")
    await rpc("contacts.resolveUsername",
        app.core.mt_req("contacts.resolveUsername", username="samsepi0l_ovf"))

    print(f"\n{'='*60}")
    print(f"Results: {PASSED}/{PASSED+FAILED} passed, {FAILED} failed")
    app.stop()

if __name__ == "__main__":
    asyncio.run(main())
