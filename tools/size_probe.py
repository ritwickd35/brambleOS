#!/usr/bin/env python3
"""MCU-section size probe: size_probe.py <extra bytes>: clone5 with the MCU section padded by N bytes (0xFF), flashed.
Prints OK (flashed) or REFUSED (updater NAK, pedal stays in update mode)."""
import os, shutil, subprocess, sys
RE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); n = int(sys.argv[1], 0)
out = os.path.join(RE, "build", f"pad{n:x}"); shutil.rmtree(out, ignore_errors=True); shutil.copytree(os.path.join(RE, "build", "clone5"), out)
p = os.path.join(out, "src", "3_mcu_app_00000000.bin"); b = open(p, "rb").read(); open(p, "wb").write(b + b"\xff" * n)
binf = os.path.join(out, "pad.bin"); subprocess.run([sys.executable, os.path.join(RE, "pmfw.py"), "pack", os.path.join(out, "src"), binf], check=True, stdout=subprocess.DEVNULL)
log = f"/tmp/probe_{n:x}.log"
r = subprocess.run([sys.executable, os.path.join(RE, "tools", "pmflash.py"), "flash", binf, "--yes"], stdout=open(log, "w"), stderr=subprocess.STDOUT)
t = open(log).read()
print(f"+{n:#x} (MCU section {len(b) + n:#x}):", "OK" if "DONE" in t else "REFUSED" if "STOPPED" in t else "UNKNOWN: " + t[-200:])
