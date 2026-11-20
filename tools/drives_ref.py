#!/usr/bin/env python3
"""Float32 Python copy of dsp/ds1.c + pmfx.c (DS1_OS=4, no transistor ADAA), driven by logs/ds1_coefs.json.
Compares with the C host output; then reports where the engine model first diverges (stage taps)."""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import drives_engine as D
F = np.float32
C = {k: F(v) for k, v in json.load(open(os.path.join(RE, "logs", "ds1_coefs.json"))).items()}
HB, HB2 = [F(v) for v in D.HB], [F(v) for v in D.HB2]

class OP:
    def __init__(s, n): s.b0, s.b1, s.a1 = C[n + "_b0"], C[n + "_b1"], C[n + "_a1"]; s.x1 = s.y1 = F(0)
    def __call__(s, x): y = s.b0 * x + s.b1 * s.x1 - s.a1 * s.y1; s.x1, s.y1 = x, y; return y
class Chain:
    def __init__(s, cs): s.c = cs; s.x = [F(0)] * len(cs); s.y = [F(0)] * len(cs)
    def __call__(s, x):
        for k, c in enumerate(s.c):
            y = c * (x - s.y[k]) + s.x[k]; s.x[k], s.y[k] = x, y; x = y
        return x
def cub_f(x): return F(2/3) if x > 1 else F(-2/3) if x < -1 else F(x - x * x * x / F(3))
def cub_F(x):
    a = abs(x); return F(2/3) * a - F(0.25) if a > 1 else F(0.5) * x * x - x * x * x * x / F(12)
class ADAA:
    def __init__(s): s.x1 = s.F1 = F(0)
    def __call__(s, x):
        Fx = cub_F(x); d = x - s.x1
        y = (Fx - s.F1) / d if (d > 1e-4 or d < -1e-4) else cub_f(F(0.5) * (x + s.x1))
        s.x1, s.F1 = x, Fx; return F(y)

ops = {n: OP(n) for n in D.OPS["ds1"]}
u1a, u1b, ua2, ub2 = Chain(HB[0::2]), Chain(HB[1::2]), Chain([HB2[0], HB2[2]]), Chain([HB2[1]])
d1a, d1b, da2, db2 = Chain(HB[0::2]), Chain(HB[1::2]), Chain([HB2[0], HB2[2]]), Chain([HB2[1]])
diode = ADAA()
TAP = []
def ds1(x):
    x = ops["in_hp"](x); x = ops["boost_hp"](x) * C["boost"]
    TAP.append(('in', x)); m = [u1a(x), u1b(x)]; u = []
    for j in range(2): u += [ua2(m[j]), ub2(m[j])]
    TAP.append(('u', list(u))); v = []
    for y in u:
        y = cub_f(y) if y >= 0 else cub_f(F(1.4) * y) / F(1.4)
        y = y + C["opgain"] * ops["op_hp"](y)
        y = ops["op_lp"](y); y = ops["clip_lp"](y)
        v.append(diode(y * F(1.6)))
    TAP.append(('v', list(v))); m = [F(0.5) * (da2(v[2 * j + 1]) + db2(v[2 * j])) for j in range(2)]
    y = F(0.5) * (d1a(m[1]) + d1b(m[0]))
    TAP.append(('y', y)); lo, hi = ops["tone_lp"](y), ops["tone_hp"](y)
    y = (F(1) - C["tone"]) * lo * F(1.3) + C["tone"] * hi * F(1.8)
    return y * C["level"]

x = np.fromfile(os.path.join(RE, "audio", "ds1_host_in.f32"), "<f4")[:4096]
ref = np.fromfile(os.path.join(RE, "audio", "ds1_host_out.f32"), "<f4")[:4096]
py = np.array([ds1(F(v)) for v in x], np.float32)
print(f"python copy vs C host: max rel err {float(np.max(np.abs(py - ref)) / np.max(np.abs(ref))):.2e}")
np.save(os.path.join(RE, "logs", "ds1_pyref.npy"), py)

# engine side: stop at each tap for the first 8 samples, compare
import engine_emu as E
from easm import assemble
g, src, words, _ = D.build("ds1"); w, lab = assemble(src, 0)
e = E.Engine(); e.load_code(0, words); e.code[0x500] = 0xA00E0000
vals = json.load(open(os.path.join(RE, "logs", "ds1_coefs.json")))
for k, ex, v in g.sp:
    if k in vals: e.d[g.addr[k]] = E.f2u(vals[k])
    elif v is not None: e.d[g.addr[k]] = E.f2u(v)
e.d[0x193] = 1; e.d[0x13:0x53] = x[:64].view(np.uint32)
fv = lambda k: float(e.d[g.addr[k]:g.addr[k] + 1].view(np.float32)[0])
taps = [lab["tap_in"], lab["tap_u"], lab["tap_v"], lab["tap_y"]]
pc, ti, worst = 0, 0, {}
for n in range(8):
    for t, name in zip(taps, ("in", "u", "v", "y")):
        save = e.code[t]; e.code[t] = 0xA00E0000; e.steps = 0; e.run(pc, limit=100000); e.code[t] = save; pc = t
        tag, refv = TAP[4 * n + ("in", "u", "v", "y").index(name)]
        if name in ("in", "y"): got = [float(e.f(2))]; refv = [refv]
        else: got = [fv(f"{name}{k}") for k in range(4)]
        err = max(abs(a - b) for a, b in zip(got, refv)); worst[name] = max(worst.get(name, 0), err / (max(abs(b) for b in refv) + 1e-12))
for k, v in worst.items(): print(f"stage {k}: worst rel err over 8 samples {v:.2e}")
