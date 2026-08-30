import subprocess, sys, time

libs = ["goygram", "telethon", "pyrogram", "aiogram", "telegram"]

base_code = "import resource; print(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)"
base_rss = int(subprocess.check_output([sys.executable, "-c", base_code], stderr=subprocess.DEVNULL).decode().strip())

print("cold import time (min of 3)")
for lib in libs:
    code = f"import time; t0=time.perf_counter(); import {lib}; print(time.perf_counter()-t0)"
    runs = []
    for _ in range(3):
        t0 = time.perf_counter()
        subprocess.check_output([sys.executable, "-c", code], stderr=subprocess.DEVNULL)
        runs.append(time.perf_counter() - t0)
    print(f"  {lib:22s} {min(runs)*1000:7.1f} ms")

print(f"\nmemory, RSS delta after import (baseline {base_rss/1024:.0f} MB)")
for lib in libs:
    code = f"import resource; import {lib}; print(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)"
    rss = int(subprocess.check_output([sys.executable, "-c", code], stderr=subprocess.DEVNULL).decode().strip())
    print(f"  {lib:22s} {(rss-base_rss)/1024:6.1f} MB  (total {rss/1024:.0f} MB)")
