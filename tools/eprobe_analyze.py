#!/usr/bin/env python3
"""Turn logs/eprobe_runs.json into a readable per-test report (logs/eprobe_report.txt) and compare known ops with
the engine model (prints a short summary)."""
import json, os, struct, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import engine_emu as E
u2f = lambda u: struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RE, "logs", "eprobe_runs.json")
plan = json.load(open(sys.argv[2] if len(sys.argv) > 2 else os.path.join(RE, "logs", "eprobe_plan.json")))
REP = sys.argv[3] if len(sys.argv) > 3 else os.path.join(RE, "logs", "eprobe_report.txt")
runs = json.load(open(src))["runs"]
CFG, T, NC, TW, NM = plan["cfg"], plan["tests"], len(plan["cfg"]), plan["tw"], plan["nmark"]


def fmt(u):
    f = u2f(u)
    return f"{u:08x}({f:.6g})" if 1e-6 < abs(f) < 1e7 or u in (0, 0x80000000) else f"{u:08x}"


def model(ti, c):
    """what engine_emu predicts for this run (unknown words = no-op)"""
    e = E.Engine(); w = T[ti]["words"]; prog = []
    for r in range(15): v = CFG[c][r]; prog += [((0x70 | r) << 24) | 0xC60000 | (v >> 16), ((0x70 | r) << 24) | 0x860000 | (v & 0xFFFF)]
    prog = [0x51000C3E, 0xA1040E03, 0xA00E0000, 0x51080C3E] + prog + w
    if T[ti]["ctr"] != 255: prog += [((0x70 | T[ti]["ctr"]) << 24) | 1] * NM
    prog += [((0x50 | r) << 24) | 0x80000 | (0xC40 + r) for r in range(15)] + [0x70061234, 0x50080C4F, 0xA00E0000]
    e.code[0xE00:] = 0xA00E0000; e.load_code(0xE00, prog); e.d[0xC3E] = 2
    for i in range(32): e.d[0xC80 + i] = E.f2u(100.0 + i)
    e.d[0xC40:0xC50] = 0x7F7F7F7F
    try: e.run(0xE00, limit=5000)
    except RuntimeError: pass
    return [int(e.d[0xC40 + r]) for r in range(16)], [int(x) for x in e.d[0xC80:0xC90]], bool(e.unknown)


lines, agree, disagree, missing = [], 0, [], 0
for ti, t in enumerate(T):
    lines.append(f"== {ti:3d} {t['name']}  words {' '.join(f'{w:08x}' for w in t['words'])}  ctr {t['ctr']}")
    for c in range(NC):
        r = runs.get(str(ti * NC + c))
        if r is None: lines.append(f"   cfg{c}: (no frame)"); missing += 1; continue
        mc, ms, vals = r["mc"], r["ms"], {int(k): v for k, v in r["vals"].items()}
        done = bool(mc >> 15 & 1)
        res = [vals.get(k, CFG[c][k]) if not ms >> k & 1 else None for k in range(15)]
        dat = [vals.get(16 + j, E.f2u(100.0 + j)) for j in range(16)]
        parts = [f"r{k}: {fmt(CFG[c][k])} -> {fmt(res[k])}" for k in range(15) if res[k] is not None and res[k] != CFG[c][k]]
        parts += [f"d{0xC80+j:x}: {fmt(dat[j])}" for j in range(16) if dat[j] != E.f2u(100.0 + j)]
        sk = [k for k in range(16) if ms >> k & 1]
        if t["ctr"] != 255 and res[t["ctr"]] is not None: parts.append(f"markers run {res[t['ctr']] - CFG[c][t['ctr']]}")
        lines.append(f"   cfg{c}: {'done' if done else 'NOT DONE'}{' skipped-stores ' + str(sk) if sk else ''}  " + "; ".join(parts))
        mr, md, munk = model(ti, c)
        if not munk:
            hw = [(res[k] if res[k] is not None else 0x7F7F7F7F) for k in range(15)]
            ok = hw == mr[:15] and dat == md and done == (mr[15] == 0x1234)
            if ok: agree += 1
            else: disagree.append(f"{t['name']} cfg{c}")
open(REP, "w").write("\n".join(lines) + "\n\nmodel disagreements:\n" + "\n".join(disagree) + "\n")
print(f"runs decoded {len(runs)}, missing {missing}; model-predictable runs: agree {agree}, disagree {len(disagree)}")
