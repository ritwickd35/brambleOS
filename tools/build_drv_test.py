#!/usr/bin/env python3
"""Build a test firmware: cut2 (English) + DRV #7 ("Bass Drive") replaced by Red Fuzz code + our wrapper module.
usage: build_drv_test.py <module.bin linked at 0x10002A00> <entry0 addr> <entry1 addr> <effect name (10 chars)> <out.bin>"""
import os, shutil, struct, subprocess, sys
RE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
mod, e0, e1, name, out = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16), sys.argv[4].encode(), sys.argv[5]
assert len(name) == 10, "name must be exactly 10 characters (replaces 'Bass Drive' in place)"
src = os.path.join(os.path.dirname(out), "src")
shutil.rmtree(src, ignore_errors=True)
shutil.copytree(os.path.join(RE, "build", "cut2", "src"), src)
p = os.path.join(src, "1_dsp_modules_00240000.bin")
m = bytearray(open(p, "rb").read())
ptrs = struct.unpack_from("<11I", m, 0x14)
grp = lambda g: list(struct.unpack_from(f"<{struct.unpack_from('<I', m, ptrs[g])[0]}I", m, ptrs[g] + 4))
drv, amp0 = grp(2), grp(3)[0]
rf, bd = drv[6], drv[7]
hs, cs, ts, st = struct.unpack_from("<4I", m, rf)
assert (hs, cs, ts, st) == (0x24, 0x148, 0x16c, 0x338)
code = bytes(m[rf + hs:rf + ts]).ljust(0x200, b"\0") + open(mod, "rb").read()
code += b"\0" * ((-len(code)) % 4)
assert 0x10002800 + len(code) <= 0x10003800
hdr = bytearray(m[rf:rf + 0x24])
struct.pack_into("<6I", hdr, 0, 0x24, len(code), 0x24 + len(code), st, e0 | 1, e1 | 1)
blob = bytes(hdr) + code + bytes(m[rf + ts:rf + ts + st])
assert len(blob) <= amp0 - bd
m[bd:amp0] = blob + b"\0" * (amp0 - bd - len(blob))
open(p, "wb").write(m)
q = os.path.join(src, "4_effect_db_presets_00190000.bin")
d = bytearray(open(q, "rb").read())
i = d.find(b"Bass Drive\0", 0x10000)
assert i > 0
d[i:i + 10] = name
open(q, "wb").write(d)
subprocess.run([sys.executable, os.path.join(RE, "pmfw.py"), "pack", src, out], check=True)
print(f"blob {len(blob):#x} bytes, code {len(code):#x}, effect renamed to {name.decode()!r}")
