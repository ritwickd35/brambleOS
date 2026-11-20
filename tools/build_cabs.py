#!/usr/bin/env python3
"""Cab catalog with our IRs: build_cabs.py <base build dir> <out name>
Factory cab record r keeps its effect id (presets keep working) and gets a new name + our IR (int32 taps,
up to 512, data block = 2048 bytes at 2048 * k, k from the record). Levels matched to the stock cabs' median."""
import os, shutil, struct, subprocess, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import ir_pick as P
# stock record index -> (new name, irs/<cab>, which IR: 0 main, 1 second mic, 2 third)
MAP = {0: ("Deluxe 1x12", "deluxe", 0), 1: ("Deluxe 1x12 B", "deluxe", 1), 2: ("Twin 2x12 B", "twin", 1),
       3: ("Vox 2x12", "ac30", 0), 4: ("Twin 2x12", "twin", 0), 5: ("Bassman 4x10", "bassman", 0),
       6: ("Vox 2x12 B", "ac30", 1), 7: ("JC 2x12", "jc120", 0), 8: ("4x12 Green B", "greenback", 1),
       9: ("4x12 Green", "greenback", 0), 10: ("4x12 V30 C", "v30", 2), 11: ("4x12 V30 B", "v30", 1),
       12: ("4x12 T75 B", "t75", 1), 13: ("4x12 T75", "t75", 0), 14: ("4x12 V30", "v30", 0), 25: ("SVT 8x10", "svt", 0)}


def pick(cab):
    import glob
    fs_ = sorted(glob.glob(os.path.join(RE, "irs", cab, "*.wav"))); s57 = [p for p in fs_ if "57" in os.path.basename(p)] or fs_
    a = P.typical(s57); rest = [p for p in fs_ if p not in s57] or [p for p in fs_ if p != a]
    b = P.typical(rest) if rest else a
    others = [p for p in s57 if p != a]                           # third: the darkest other SM57 position
    c = min(others, key=lambda p: float(np.mean(P.bands(P.load(p))[P.C > 3000]) - np.mean(P.bands(P.load(p))[P.C < 400]))) if others else a
    return [a, b, c]


def main():
    base, name = sys.argv[1], sys.argv[2]; out = os.path.join(RE, "build", name); src = os.path.join(out, "src")
    shutil.rmtree(src, ignore_errors=True); shutil.copytree(os.path.join(base, "src"), src)
    cp = os.path.join(src, "2_cab_catalog_00280000.bin"); b = bytearray(open(cp, "rb").read()); n0 = len(b)
    stock_e = []
    for r in MAP:
        k = struct.unpack_from("<I", b, 72 * r + 16)[0] >> 16; w = np.frombuffer(bytes(b[2048 * k:2048 * (k + 1)]), "<i4")
        stock_e.append(float(np.sum(w[w != -1].astype(float) ** 2)))
    E = float(np.median(stock_e)); cache = {}; src_log = []
    for r, (nm, cab, which) in MAP.items():
        k = struct.unpack_from("<I", b, 72 * r + 16)[0] >> 16; assert 1 <= k <= 16
        if cab not in cache: cache[cab] = pick(cab)
        f = cache[cab][which]; h, how = P.best_short(P.load(f))
        q = np.round(h * np.sqrt(E / np.sum(h ** 2))); assert np.max(np.abs(q)) < 2 ** 31 - 1
        blk = np.full(512, -1, "<i4"); blk[:len(q)] = q.astype("<i4"); b[2048 * k:2048 * (k + 1)] = blk.tobytes()
        o = 72 * r + 24; assert len(nm) <= 13; b[o:o + 14] = nm.encode().ljust(14, b"\0")
        src_log.append(f"{nm}: {os.path.basename(f)} ({how}, {len(q)} taps)")
    assert len(b) == n0; open(cp, "wb").write(b)
    open(os.path.join(out, "cabs.txt"), "w").write("\n".join(src_log) + "\n")
    binf = os.path.join(out, f"PocketMaster_CFW1.0.2+{name}.bin")
    subprocess.run([sys.executable, os.path.join(RE, "pmfw.py"), "pack", src, binf], check=True, stdout=subprocess.DEVNULL)
    print("\n".join(src_log)); print("built", os.path.relpath(binf, RE))


if __name__ == "__main__":
    main()
