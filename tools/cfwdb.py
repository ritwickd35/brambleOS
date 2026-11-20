#!/usr/bin/env python3
"""Effect database reader (section 4 at +0x10000): fxid, name and per-knob default for every effect.
  cfwdb.py new        effects in the CFW 1.0.2 DB whose fxid the stock DB does not have
Record (inferred): u32 fxid, ..., then knob blocks of 0x18 bytes {u16 0xFFFF, u16 ui_pos, f32 min, max, step, default,
u8 idx, u8, u8, u8 kind}, then NUL-terminated strings. Knob blocks are located by shape, not by a fixed offset,
because the Smart Box records carry extra bytes before them."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE)
B = 0x10000
NAMES = ["NR", "FX1", "DRV", "AMP", "IR", "EQ", "FX2", "DLY", "RVB", "CLONE"]


def _lists(d):
    ptrs = struct.unpack_from("<11I", d, B + 0x14); g = []
    for p in ptrs[:10]:
        n = struct.unpack_from("<I", d, B + p)[0]; g.append(list(struct.unpack_from(f"<{n}I", d, B + p + 4)))
    return g, sorted(set(ptrs) | {o for x in g for o in x})


def _knobs(r):
    def ok(p):
        if r[p:p + 2] != b"\xff\xff" or p + 0x18 > len(r): return None
        mn, mx, st, df = struct.unpack_from("<4f", r, p + 4); idx = r[p + 0x14]
        if idx < 8 and abs(mn) < 1e5 and abs(mx) < 1e5 and mn <= df <= mx and st >= 0: return (idx, mn, mx, df)
        return None
    for p in range(4, len(r) - 0x18, 2):
        if ok(p):
            out = []
            while ok(p): out.append(ok(p)); p += 0x18
            names = []
            for x in r[p:].split(b"\0"):
                if not x or not all(0x20 <= c < 0x7F for c in x): break
                names.append(x.decode())
            return out, names
    return [], []


def effects(path):
    d = open(path, "rb").read(); g, allo = _lists(d); res = []
    for gi, offs in enumerate(g):
        for j, o in enumerate(offs):
            e = min([x for x in allo if x > o] + [o + 0x400]); r = d[B + o:B + e]
            fx = struct.unpack_from("<I", r, 0)[0]; kn, nm = _knobs(r)
            p = [0.0] * 8
            for idx, mn, mx, df in kn: p[idx] = df
            res.append(dict(group=NAMES[gi], module=gi, index=j, fxid=fx, name=nm[0] if nm else "?", params=p, knobs=len(kn)))
    return res


def new_in_cfw():
    s = {e["fxid"] for e in effects(os.path.join(RE, "unpacked", "4_effect_db_presets_00190000.bin"))}
    return [e for e in effects(os.path.join(RE, "cfw", "src", "4_effect_db_presets_00190000.bin")) if e["fxid"] not in s]


if __name__ == "__main__":
    if sys.argv[1:] == ["new"]:
        for e in new_in_cfw(): print(e["group"], e["index"], hex(e["fxid"]), e["name"], e["knobs"], e["params"])
    else:
        sys.exit(__doc__)
