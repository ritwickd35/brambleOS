#!/usr/bin/env python3
"""Add converted NAM captures as NEW amp entries (the 16 normal amps stay):
  add_nam_amps.py <base build dir> <out name> <name>=<fit json>[:<menu title>] ...
Uses the shared amp code already in the base build (amp_core) - each new amp is a stub with its settings plus its
engine program, placed in free module space; AMP lists (module + effect DB) grow in place (slack left by the 22
removed amps); the DB record is a copy of the 5150 record with a new title and a new effect id."""
import os, shutil, struct, subprocess, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import amps2, ampmodel as AM, build_amps2 as B, dbrec
from build_cut import groups
from build_bisect import zero_run


def append_entry(b, base, grp, value):
    ptr = struct.unpack_from("<I", b, base + 0x14 + 4 * grp)[0]; n = struct.unpack_from("<I", b, base + ptr)[0]
    assert b[base + ptr + 4 + 4 * n:base + ptr + 8 + 4 * n] in (bytes(4), b"\xff" * 4), "no slack behind the list"
    struct.pack_into("<I", b, base + ptr + 4 + 4 * n, value); struct.pack_into("<I", b, base + ptr, n + 1); return n


def main():
    base, name, jobs = sys.argv[1], sys.argv[2], [j.split("=") for j in sys.argv[3:]]
    out = os.path.join(RE, "build", name); src = os.path.join(out, "src"); shutil.rmtree(src, ignore_errors=True)
    shutil.copytree(os.path.join(base, "src"), src)
    mp = os.path.join(src, "1_dsp_modules_00240000.bin"); m = bytearray(open(mp, "rb").read())
    dp = os.path.join(src, "4_effect_db_presets_00190000.bin"); d = bytearray(open(dp, "rb").read())
    free = [tuple(x) for x in json.load(open(os.path.join(base, "free_after.json")))]
    gm, gd = groups(m, 0), groups(d, 0x10000); recs = dbrec.records(dp)
    # the existing shared amp code: take its address and entry points from any of our amp stubs (STAB)
    _, cs_, stub, ss = B.build_code()
    o0 = gm[3][0]; hs0 = struct.unpack_from("<I", m, o0)[0]
    stab = struct.unpack_from("<8I", m, o0 + hs0 + ss["STAB"] - 0x10003800); assert stab[0] == 0x42415453, "base has no shared amp code"
    hal = next(r for r in recs if r[0] == 3 and r[3].strip() == "Halen 51")
    ids = {struct.unpack_from("<I", d, 0x10000 + r)[0] for gl in gd for r in gl}
    log = []
    for nm, rest in jobs:
        fit, _, title = rest.partition(":"); title = title or f"NAM {nm}"
        s = json.load(open(fit)); nst = int(s["nst"]); s.setdefault("os", 2.0)
        idx = [next((j for n_, _, _, j, *_ in hal[4] if n_ == k), -1) for k in ("Gain", "Bass", "Middle", "Treble", "PRES", "VOL")] + [-1, -1]
        prog, _ = amps2.assemble_amp(nst, int(s["os"])); prog = np.array(prog, "<u4").tobytes()
        bstub = bytearray(stub); di = ss["DESC"] - 0x10003800
        struct.pack_into(f"<{len(AM.NAMES)}f", bstub, di, *[float(s.get(k, {"os": 2.0, "olp": 19000.0}.get(k, 0.0))) for k in AM.NAMES])
        struct.pack_into("<8b", bstub, di + 4 * len(AM.NAMES), *idx)
        struct.pack_into("<8I", bstub, ss["STAB"] - 0x10003800, *stab)          # same shared code, same entries
        hdr = bytearray(m[o0:o0 + hs0]); struct.pack_into("<6I", hdr, 0, hs0, len(bstub), hs0 + len(bstub), len(prog), ss["st_entry0"] | 1, ss["st_entry1"] | 1)
        blob = bytes(hdr) + bytes(bstub) + prog
        fit_ = sorted((ln, fo) for fo, ln in free if ln >= len(blob)); assert fit_, "no module space"
        ln, fo = fit_[0]; free.remove((fo, ln)); u = (len(blob) + 63) & ~63
        if ln > u: free.append((fo + u, ln - u))
        m[fo:fo + len(blob)] = blob; mi = append_entry(m, 0, 3, fo)
        # DB record: copy of the 5150 record, new title, new id
        import build_rv
        rec = bytearray(build_rv.clone_title(d, 0x10000 + gd[3][hal[1]], title))
        nid = max(i_ for i_ in ids if i_ >> 24 == 7) + 1; ids.add(nid); struct.pack_into("<I", rec, 0, nid)
        z = zero_run(d, 0x10000, len(rec) + 64, 0x20000); at = (z + 16) & ~3; d[at:at + len(rec)] = rec
        di_ = append_entry(d, 0x10000, 3, at - 0x10000); assert di_ == mi, (di_, mi)
        log.append(f"AMP #{mi} '{title}' (id {nid}): {os.path.basename(fit)}, {len(blob)} bytes at {fo}")
    open(mp, "wb").write(m); open(dp, "wb").write(d)
    json.dump(sorted(free, key=lambda r: -r[1]), open(os.path.join(out, "free_after.json"), "w"))
    binf = os.path.join(out, f"PocketMaster_CFW1.0.2+{name}.bin")
    subprocess.run([sys.executable, os.path.join(RE, "pmfw.py"), "pack", src, binf], check=True, stdout=subprocess.DEVNULL)
    print("\n".join(log)); print("built", os.path.relpath(binf, RE))


if __name__ == "__main__":
    main()
