#!/usr/bin/env python3
"""Bisect the cut4a boot failure. Base = the daily firmware sources (CFW 1.0.2 + smart gate). One change per test:
  t1  module section: copy the FX1 list (27 entries, unchanged) to the end of the section, point the header at it
  t2  effect DB: copy the FX1 list (27 entries, unchanged) into the DB's zero padding, point the header at it
  t3  t1 + module FX1 count 28: the extra entry points to a copy of the C-Wah blob appended to the section
  t4  t2 + DB FX1 count 28: the extra entry points to a copy of the C-Wah record (renamed) in the padding
  t5  t3 + t4: a complete, consistent 28th FX1 effect (a copy of C-Wah named C-Wa2)
  t6  module section grows by 112 zero bytes, nothing else (t1's growth without the list move)
  t7  move the FX1 list into the free space of the gate slot (section size unchanged)
  t8  consistent 28th FX1 effect C-Wa2 with its own id, everything inside the existing sections\nusage: build_bisect.py t1..t8"""
import os, shutil, struct, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
from build_cut import groups

FX1, CWAH = 1, 15


def daily_src(out):
    src = os.path.join(out, "src"); shutil.rmtree(src, ignore_errors=True)
    shutil.copytree(os.path.join(RE, "build", "daily", "src"), src); return src


def zero_run(b, start, need, end=None):
    """first 4-aligned offset in [start, end) where `need` erased (255) bytes follow"""
    i = (start + 3) & ~3; z = bytes([255]) * need; b = b[:end] if end else b
    while i + need <= len(b):
        j = b.find(z, i)
        if j < 0: return -1
        if j % 4 == 0: return j
        i = j + 1
    return -1


def main():
    t = sys.argv[1]; out = os.path.join(RE, "build", f"bisect-{t}"); os.makedirs(out, exist_ok=True)
    src = daily_src(out)
    mp = os.path.join(src, "1_dsp_modules_00240000.bin"); m = bytearray(open(mp, "rb").read())
    dp = os.path.join(src, "4_effect_db_presets_00190000.bin"); d = bytearray(open(dp, "rb").read())
    n0m, n0d = len(m), len(d)
    if t == "t6": m += bytes(112)                                # growth only, same size as t1
    if t == "t7":                                                # move the FX1 list into zero space inside the section
        ptr = struct.unpack_from("<I", m, 0x14 + 4 * FX1)[0]; n = struct.unpack_from("<I", m, ptr)[0]
        lst = bytes(m[ptr:ptr + 4 + 4 * n]); z = m.find(bytes(1500)); assert z > 0
        at = (z + 64) & ~3; assert m[at:at + len(lst)] == bytes(len(lst))
        m[at:at + len(lst)] = lst; struct.pack_into("<I", m, 0x14 + 4 * FX1, at)
    if t == "t8":                                                # 28-entry FX1 list inside the section; entry 28 shares the C-Wah blob
        ptr = struct.unpack_from("<I", m, 0x14 + 4 * FX1)[0]; n = struct.unpack_from("<I", m, ptr)[0]
        lst = list(struct.unpack_from(f"<{n}I", m, ptr + 4)); lst.append(lst[CWAH])
        z = m.find(bytes(1500)); at = (z + 64) & ~3; new = struct.pack(f"<I{len(lst)}I", len(lst), *lst)
        assert m[at:at + len(new)] == bytes(len(new)); m[at:at + len(new)] = new; struct.pack_into("<I", m, 0x14 + 4 * FX1, at)
    if t in ("t1", "t3", "t5"):
        ptr = struct.unpack_from("<I", m, 0x14 + 4 * FX1)[0]; n = struct.unpack_from("<I", m, ptr)[0]
        lst = list(struct.unpack_from(f"<{n}I", m, ptr + 4))
        if t in ("t3", "t5"):
            o = lst[CWAH]; hs, cs, ts, st = struct.unpack_from("<4I", m, o); blob = bytes(m[o:o + ts + st])
            while len(m) % 4: m.append(0)
            new = len(m); m += blob; lst.append(new)
        while len(m) % 4: m.append(0)
        at = len(m); m += struct.pack(f"<I{len(lst)}I", len(lst), *lst)
        struct.pack_into("<I", m, 0x14 + 4 * FX1, at)
    if t in ("t2", "t4", "t5", "t8"):
        base = 0x10000
        ptr = struct.unpack_from("<I", d, base + 0x14 + 4 * FX1)[0]; n = struct.unpack_from("<I", d, base + ptr)[0]
        lst = list(struct.unpack_from(f"<{n}I", d, base + ptr + 4))
        extra = b""
        if t in ("t4", "t5", "t8"):
            g = groups(d, base); r = lst[CWAH]; nxt = min(x for gl in g for x in gl if x > r); rec = bytearray(d[base + r:base + nxt])
            j = rec.find(b"C-Wah\0"); assert j >= 0; rec[j:j + 6] = b"C-Wa2\0"
            if t == "t8":                                        # unique effect id: next free index in C-Wah's group
                cid = struct.unpack_from("<I", rec, 0)[0]; ids = {struct.unpack_from("<I", d, base + x)[0] for x in lst}
                nid = cid + 1; assert nid not in ids; struct.pack_into("<I", rec, 0, nid); print("C-Wa2 effect id", nid)
            extra = bytes(rec)
        need = 4 * (len(lst) + 2) + len(extra) + 64
        z = zero_run(d, base, need, 2 * base); assert z > 0, "no padding inside the effect DB block"
        p = z + 16
        if extra:
            d[p:p + len(extra)] = extra; lst.append(p - base); p += (len(extra) + 3) & ~3
        d[p:p + 4 * (len(lst) + 1)] = struct.pack(f"<I{len(lst)}I", len(lst), *lst)
        struct.pack_into("<I", d, base + 0x14 + 4 * FX1, p - base)
    assert len(d) == n0d
    open(mp, "wb").write(m); open(dp, "wb").write(d)
    binf = os.path.join(out, f"PocketMaster_CFW1.0.2+bisect-{t}.bin")
    subprocess.run([sys.executable, os.path.join(RE, "pmfw.py"), "pack", src, binf], check=True, stdout=subprocess.DEVNULL)
    print(f"{t}: module section {n0m} -> {len(m)} bytes; built {os.path.basename(binf)}")


if __name__ == "__main__":
    main()
