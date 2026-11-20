#!/usr/bin/env python3
"""Cut 4a: CFW 1.0.2 + our two test modules (nothing of the CFW is changed except where stated).
  DRV #7 'Bass Drive' -> Red Fuzz code + cut1/combo.bin ('CPU Test 2', same module as on stock cut3d: CPU ramp)
  FX1 #15 'C-Wah'     -> cut1/fx1probe.bin, renamed 'CTest' (fxid 0x05000008): audio test + memory-speed benchmark
  No section changes size (cut4b; cut4a appended data and did not boot).
usage: build_cfw_test.py <out.bin>"""
import os, shutil, struct, subprocess, sys
RE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_BASE = 0x13000                     # DSP address of the module section (inferred from the CFW's own entry thunks)
out = sys.argv[1]
src = os.path.join(os.path.dirname(out), "src")
shutil.rmtree(src, ignore_errors=True)
shutil.copytree(os.path.join(RE, "cfw", "src"), src)
mp = os.path.join(src, "1_dsp_modules_00240000.bin"); m = bytearray(open(mp, "rb").read())
dp = os.path.join(src, "4_effect_db_presets_00190000.bin"); d = bytearray(open(dp, "rb").read())


def groups(b, base):
    ptrs = struct.unpack_from("<11I", b, base + 0x14); out = []
    for p in ptrs:
        n = struct.unpack_from("<I", b, base + p)[0]
        out.append(list(struct.unpack_from(f"<{n}I", b, base + p + 4)) if n < 256 else [])
    return ptrs, out


# ---- DRV #7: CPU ramp module (identical build to cut3d) ----
ptrs, g = groups(m, 0)
rf, bd = g[2][6], g[2][7]
nxt = min(o for gl in g for o in gl if o > bd)
hs, cs, ts, st = struct.unpack_from("<4I", m, rf)
assert (hs, cs, ts, st) == (0x24, 0x148, 0x16c, 0x338)
code = bytes(m[rf + hs:rf + ts]).ljust(0x200, b"\0") + open(os.path.join(RE, "cut1", "combo.bin"), "rb").read()
code += b"\0" * ((-len(code)) % 4)
hdr = bytearray(m[rf:rf + 0x24]); struct.pack_into("<6I", hdr, 0, 0x24, len(code), 0x24 + len(code), st, 0x10002A01, 0x10002A1D)
blob = bytes(hdr) + code + bytes(m[rf + ts:rf + ts + st])
assert len(blob) <= nxt - bd, (hex(len(blob)), hex(nxt - bd))
m[bd:bd + len(blob)] = blob
i = d.find(b"Bass Drive\0", 0x10000); assert i > 0; d[i:i + 10] = b"CPU Test 2"

# ---- FX1: new probe module ----
fx = open(os.path.join(RE, "cut1", "fx1probe.bin"), "rb").read()
sym = {}
for line in subprocess.run(["docker", "run", "--rm", "-v", f"{RE}:/w", "-w", "/w/cut1", "pmarm", "arm-none-eabi-nm", "fx1probe.elf"],
                           capture_output=True, text=True, check=True).stdout.splitlines():
    a, _, n = line.split(); sym[n] = int(a, 16)
pic = fx[sym["__pic_start"] - 0x10001000:sym["__pic_end"] - 0x10001000]
tremolo_stock = groups(open(os.path.join(RE, "unpacked", "1_dsp_modules_00240000.bin"), "rb").read(), 0)[1][1][11]
th = open(os.path.join(RE, "unpacked", "1_dsp_modules_00240000.bin"), "rb").read()[tremolo_stock:tremolo_stock + 0x24]
assert struct.unpack_from("<I", th, 0)[0] == 0x24
# cut4b: NO growth (cut4a grew the module section past 0x59000 bytes of DSP image and the pedal did not boot).
# The probe overwrites the CFW's FX1 'C-Wah' blob (#15, normal header, code copied to the slot, nothing else in
# the image refers to it) strictly inside that blob's own footprint; FX2 keeps its own C-Wah.
cw = g[1][15]
chs, ccs = struct.unpack_from("<2I", m, cw)
assert (chs, ccs) == (0x18, 0xb58), (hex(chs), hex(ccs))
foot = chs + ccs
blob_off = cw
pic_off = blob_off + 0x24 + len(fx); pic_off += (-pic_off) % 16
assert pic_off + len(pic) <= cw + foot, "probe does not fit into the C-Wah footprint"
fxp = bytearray(fx)
k = sym["img_addr"] - 0x10001000; assert fxp[k:k + 4] == struct.pack("<I", 0xC0DEADD1)
struct.pack_into("<I", fxp, k, (IMG_BASE + pic_off) | 1)
fxp = bytes(fxp) + b"\0" * ((-len(fxp)) % 4)
hdr = bytearray(th); struct.pack_into("<6I", hdr, 0, 0x24, len(fxp), 0x24 + len(fxp), 0, sym["lt_entry0"] | 1, sym["lt_entry1"] | 1)
region = bytes(hdr) + fxp
region = region + b"\0" * (pic_off - cw - len(region)) + pic
region = region + b"\0" * (foot - len(region))
n0 = len(m); m[cw:cw + foot] = region; assert len(m) == n0
open(mp, "wb").write(m)

# ---- effect DB: rename FX1 #15 only (in place, same length) ----
B = 0x10000
dptrs, dg = groups(d, B)
r = B + dg[1][15]
fxid = struct.unpack_from("<I", d, r)[0]; assert fxid == 0x05000008, hex(fxid)
j = d.find(b"C-Wah\0", r, r + 0x80); assert j > 0
d[j:j + 5] = b"CTest"
open(dp, "wb").write(d)
blob_off_report = cw
subprocess.run([sys.executable, os.path.join(RE, "pmfw.py"), "pack", src, out], check=True)
print(f"DRV#7 blob {len(blob):#x} (span {nxt - bd:#x}); FX1#15 probe @{cw:#x} ({0x24 + len(fxp):#x} of {foot:#x} B), "
      f"pic copy @{pic_off:#x} -> DSP {IMG_BASE + pic_off:#x}; module section {len(m):#x} (unchanged size: {len(m) == 0x49ff0})")
