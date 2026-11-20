#!/usr/bin/env python3
"""Build CFW 1.0.2 + our modules, replacing existing module blobs strictly inside their own footprint
(header + code); no section changes size, no list or count changes (rule from the cut4a incident).

  build_cut.py <out.bin> [--no-cputest]
Replacements (edit PLAN below):
  NR  #0  Gate   -> dsp/mod_gate.bin (smart gate, knob THRE)        name unchanged
  FX1 #15 C-Wah  -> dsp/mod_ds1.bin  (DS-1 circuit model)            name 'DS-1+', knobs Dst / Tone / VOL
  DRV #7  Bass Drive -> Red Fuzz + cut1/combo.bin (CPU ramp test)    name 'CPU Test 2'"""
import os, shutil, struct, subprocess, sys
RE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DSP = os.path.join(RE, "dsp")
PLAN = [  # group, index, module binary, symbol file, expected (hdr, code) of the blob being replaced, renames
    (0, 0, "mod_gate.bin", "mod_gate.sym", (0x24, 0xbdc), []),
    (1, 15, "mod_ds1.bin", "mod_ds1.sym", (0x18, 0xb58), [(b"C-Wah\0", b"DS-1+\0"), (b"Wah\0", b"Dst\0"), (b"Range\0", b"Tone \0")]),
]


# engine (co-processor) program patches: (group, index, first word, new words). Bass EQ (EQ #2): replace the five
# biquad calls by "buffer 0x13 *= 0.5" and jump to the volume stage -> output -6 dB, flat. Idiom copied from stock
# programs (movhi/movlo r8, mov r9/r10/r11, 20080000 = vmuls).
ENGINE = [(5, 2, 4, [0x78c63f00, 0x78860000, 0x79060013, 0x7a060040, 0x7b060013, 0x20080000, 0xa0080e13])]


# engine busy-loop for the engine-capacity ramp (combo3 rewrites the inner count at code word 0xE05)
ENGINE_RAMP = [(5, 2, 4, [0x77060010, 0x74060000, 0x74000001, 0xa4040e07, 0xa7040e05, 0xa0080e13])]


def groups(b, base):
    ptrs = struct.unpack_from("<11I", b, base + 0x14); out = []
    for p in ptrs:
        n = struct.unpack_from("<I", b, base + p)[0]
        out.append(list(struct.unpack_from(f"<{n}I", b, base + p + 4)) if n < 256 else [])
    return out


IMG_BASE = 0x13000          # DSP address of the module section (NOTES.md 29)


def multidrive(m, d, g):
    """DRV #7 -> mod_drv.bin + engine programs (DS-1 is also the blob's own program, TS808 follows)."""
    o = g[2][7]; nxt = min(x for gl in g for x in gl if x > o); foot = nxt - o
    hs, cs, ts, st = struct.unpack_from("<4I", m, o); assert (hs, cs, st) == (0x24, 2660, 1836), (hs, cs, st)
    code = bytearray(open(os.path.join(DSP, "mod_drv.bin"), "rb").read()); code += b"\0" * ((-len(code)) % 4)
    sym = {l.split()[2]: int(l.split()[0], 16) for l in open(os.path.join(DSP, "mod_drv.sym"))}
    progs = [open(os.path.join(RE, "build", "progs", f"{n}.bin"), "rb").read() for n in ("ds1", "ts808")]
    p0 = 0x24 + len(code); p1 = p0 + len(progs[0])
    i = code.find(struct.pack("<I", 0x42415450)); assert i >= 0 and code.find(struct.pack("<I", 0x42415450), i + 1) < 0
    w = [struct.unpack("<%dI" % (len(p) // 4), p) for p in progs]
    struct.pack_into("<9I", code, i, 0x42415450, IMG_BASE + o + p0, IMG_BASE + o + p1, len(w[0]), len(w[1]),
                     w[0][0], w[1][0], w[0][-1], w[1][-1])
    hdr = bytearray(m[o:o + 0x24])
    struct.pack_into("<6I", hdr, 0, 0x24, len(code), 0x24 + len(code), len(progs[0]), sym["lt_entry0"] | 1, sym["lt_entry1"] | 1)
    blob = bytes(hdr) + bytes(code) + progs[0] + progs[1]
    assert len(blob) <= foot, (len(blob), foot)
    m[o:o + foot] = blob + b"\0" * (foot - len(blob))
    r = 0x10000 + groups(d, 0x10000)[2][7]
    for a, b in [(b"Bass Drive\0", b"Multi Drv \0"), (b"Blend\0", b"Model\0"), (b"Treble\0", b"Tone  \0")]:
        j = d.find(a, r, r + 0x100); assert j > 0, a; d[j:j + len(a)] = b
    print(f"DRV #7: multi drive {len(blob)} of {foot} bytes")


def main():
    out = sys.argv[1]; cputest = "--no-cputest" not in sys.argv
    combo = sys.argv[sys.argv.index("--combo") + 1] if "--combo" in sys.argv else os.path.join(RE, "cut1", "combo.bin")
    src = os.path.join(os.path.dirname(out), "src"); shutil.rmtree(src, ignore_errors=True)
    shutil.copytree(os.path.join(RE, "cfw", "src"), src)
    mp = os.path.join(src, "1_dsp_modules_00240000.bin"); m = bytearray(open(mp, "rb").read()); n0 = len(m)
    dp = os.path.join(src, "4_effect_db_presets_00190000.bin"); d = bytearray(open(dp, "rb").read())
    g = groups(m, 0); dg = groups(d, 0x10000)
    plan = PLAN[:1] if "--gate-only" in sys.argv else PLAN
    for grp, idx, binf, symf, expect, ren in plan:
        o = g[grp][idx]; hs, cs = struct.unpack_from("<2I", m, o)
        assert (hs, cs) == expect, (grp, idx, hex(hs), hex(cs))
        foot = hs + cs
        code = open(os.path.join(DSP, binf), "rb").read(); code += b"\0" * ((-len(code)) % 4)
        sym = {l.split()[2]: int(l.split()[0], 16) for l in open(os.path.join(DSP, symf))}
        hdr = struct.pack("<6I", 0x24, len(code), 0x24 + len(code), 0, sym["lt_entry0"] | 1, sym["lt_entry1"] | 1) + \
              struct.pack("<3I", 0xF240, 0xF2C0, 0x4770)          # same trailing words as the stock headers
        assert len(hdr) == 0x24
        blob = hdr + code
        assert len(blob) <= foot, f"group {grp} #{idx}: {len(blob):#x} > footprint {foot:#x}"
        m[o:o + foot] = blob + b"\0" * (foot - len(blob))
        r = 0x10000 + dg[grp][idx]
        for a, b in ren:
            assert len(a) == len(b)
            j = d.find(a, r, r + 0x100); assert j > 0, (grp, idx, a)
            d[j:j + len(a)] = b
        print(f"group {grp} #{idx}: {binf} {len(blob):#x} of {foot:#x} bytes")
    if cputest:
        rf, bd = g[2][6], g[2][7]
        nxt = min(x for gl in g for x in gl if x > bd)
        hs, cs, ts, st = struct.unpack_from("<4I", m, rf); assert (hs, cs, ts, st) == (0x24, 0x148, 0x16c, 0x338)
        code = bytes(m[rf + hs:rf + ts]).ljust(0x200, b"\0") + open(combo, "rb").read()
        code += b"\0" * ((-len(code)) % 4)
        hdr = bytearray(m[rf:rf + 0x24]); struct.pack_into("<6I", hdr, 0, 0x24, len(code), 0x24 + len(code), st, 0x10002A01, 0x10002A1D)
        blob = bytes(hdr) + code + bytes(m[rf + ts:rf + ts + st]); assert len(blob) <= nxt - bd
        m[bd:bd + len(blob)] = blob
        i = d.find(b"Bass Drive\0", 0x10000); assert i > 0; d[i:i + 10] = b"CPU Test 2"
        print("DRV #7: CPU ramp test")
    if "--multidrive" in sys.argv: multidrive(m, d, g)
    patches = ENGINE if "--engine-test" in sys.argv else ENGINE_RAMP if "--engine-ramp" in sys.argv else []
    if patches:
        for grp, idx, w0, words in patches:
            o = g[grp][idx]; hs, cs, ts, st = struct.unpack_from("<4I", m, o)
            assert 4 * (w0 + len(words)) <= st
            for k, w in enumerate(words): struct.pack_into("<I", m, o + ts + 4 * (w0 + k), w)
            print(f"engine patch: group {grp} #{idx} words {w0}..{w0 + len(words) - 1}")
    assert len(m) == n0
    open(mp, "wb").write(m); open(dp, "wb").write(d)
    subprocess.run([sys.executable, os.path.join(RE, "pmfw.py"), "pack", src, out], check=True, stdout=subprocess.DEVNULL)
    print("built", out)


if __name__ == "__main__":
    main()
