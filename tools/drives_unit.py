#!/usr/bin/env python3
"""Unit test of each drives_engine building block in the engine model vs a float32 Python reference."""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drives_engine as D, engine_emu as E
from easm import assemble
F = np.float32
rng = np.random.default_rng(3)

def cub_f(x): return F(2/3) if x > 1 else F(-2/3) if x < -1 else F(x - x*x*x/F(3))
def cub_F(x):
    a = abs(x)
    return F(2/3)*a - F(0.25) if a > 1 else F(0.5)*x*x - x**4/F(12)

def run_block(emit, pre, xs, state):
    g = D.Gen("ds1"); g.L = ["    movf r13,0.5", "    movf r14,1.0"]; emit(g); g.L.append("    halt")
    w, _ = assemble("\n".join(g.L) + "\n", 0)
    e = E.Engine(); e.load_code(0, w)
    for k, v in g.sp and [(k, v) for k, _, v in g.sp if v is not None]: e.d[g.addr[k]] = E.f2u(v)
    for k, v in pre.items(): e.d[g.addr[k]] = E.f2u(v)
    out = []
    for x in xs:
        e.steps = 0; e.setf(2, x); e.run(0, limit=5000); out.append(float(e.f(2)))
    return np.array(out, np.float32), e, g

xs = (rng.standard_normal(200) * 1.5).astype(np.float32)
res = {}
y, *_ = run_block(lambda g: g.cubic("r2"), {}, xs, None)
res["cubic"] = np.max(np.abs(y - np.array([cub_f(x) for x in xs])))

ref = []; x1 = F(0); F1 = F(0)
for x in xs:
    Fx = cub_F(x); d = x - x1
    yy = (Fx - F1) / d if abs(d) > 1e-4 else cub_f(F(0.5) * (x + x1))
    ref.append(yy); x1, F1 = x, Fx
y, *_ = run_block(lambda g: g.adaa("diode", "r2"), {"diode_x1": 0.0, "diode_F1": 0.0}, xs, None)
res["adaa"] = np.max(np.abs(y - np.array(ref, np.float32)))

b0, b1, a1 = F(0.3), F(0.2), F(-0.5); ref = []; px = py = F(0)
for x in xs: yy = b0*x + b1*px - a1*py; ref.append(yy); px, py = x, yy
y, *_ = run_block(lambda g: g.onepole("in_hp", "r2"), {"in_hp_b0": b0, "in_hp_b1": b1, "in_hp_a1": a1, "in_hp_x1": 0, "in_hp_y1": 0}, xs, None)
res["onepole"] = np.max(np.abs(y - np.array(ref, np.float32)))

c = F(D.HB[0]); ref = []; px = py = F(0)
for x in xs: yy = c*(x - py) + px; ref.append(yy); px, py = x, yy
y, *_ = run_block(lambda g: g.ap("hb0", "up1a", 0, "r2"), {"up1a_x0": 0, "up1a_y0": 0}, xs, None)
res["allpass"] = np.max(np.abs(y - np.array(ref, np.float32)))

def tr(x): return cub_f(x) if x >= 0 else cub_f(F(1.4) * x) * F(1/1.4)
y, *_ = run_block(lambda g: g.transistor("r2"), {}, xs, None)
res["transistor"] = np.max(np.abs(y - np.array([tr(x) for x in xs])))
for k, v in res.items(): print(f"{k:10s} max abs err {float(v):.2e}  {'ok' if v < 1e-4 else 'WRONG'}")
