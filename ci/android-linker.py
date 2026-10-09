#!/usr/bin/env python3
"""Cargo linker shim for the Android wheels.

PEP 738 says an Android extension module has to link libpython itself;
the Bionic linker will not pick the symbols up from the host binary. A
plain `maturin build --target *-linux-android` still produces a module
without that dependency, for two reasons:

* cargo links with -Wl,--as-needed, and libpython3.so is a symbol-less
  forwarding stub (the real symbols are in libpython3.X.so), so the
  linker discards it. The module then fails to import with
  "cannot locate symbol _Py_Dealloc".
* Termux keeps libpython3.so in $PREFIX/lib, which is not on Bionic's
  default search path, so the dependency needs an rpath pointing there.

Both are fixed by inserting the flags right in front of -lpython3.
Reads the real compiler from ANDROID_CC (exported by the workflow).
"""
import os
import subprocess
import sys

cc = os.environ["ANDROID_CC"]
prefix_lib = os.environ.get("ANDROID_PREFIX_LIB", "/data/data/com.termux/files/usr/lib")

args: list[str] = []
for arg in sys.argv[1:]:
    if arg.startswith("-lpython"):
        args += ["-Wl,--no-as-needed", f"-Wl,-rpath,{prefix_lib}"]
    args.append(arg)

sys.exit(subprocess.call([cc, *args]))
