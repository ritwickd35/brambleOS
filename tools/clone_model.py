#!/usr/bin/env python3
"""Reference model of the pedal's clone engine, fitted to pedal recordings (audio/cloneprobe):
   y = post * FIRb( sat( g * FIRa( pre * x ) ) ),  sat from the .clo params, pre/post = fixed engine filters
   (knobs at 50), learned once from a probe take and saved to amps/clone_engine.json.
  clone_model.py learn <take> <clo|gen spec>      fit pre/post/g on one take
  clone_model.py test <take> <clo|gen spec>       ESR of the saved model on another take (nothing refitted but delay)"""
import json, os, sys
import numpy as np, torch
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import clone_probe as C, pmclone as P
EJ = os.path.join(RE, "amps", "clone_engine.json"); NT = 63


def tconv(x, h):                                   # causal FIR, x (T,), h (K,)
    return torch.nn.functional.conv1d(torch.nn.functional.pad(x, (len(h) - 1, 0))[None, None], h.flip(0)[None, None])[0, 0]


def sat(v, p):
    pm, nm, pr, nr = p
    return torch.where(v >= 0, pm * (1 - torch.exp(-pr * v.clamp(min=0))), -nm * (1 - torch.exp(nr * v.clamp(max=0))))


def model(x, c, pre, post, g):
    t = lambda a: torch.tensor(np.asarray(a, np.float64))
    z = tconv(tconv(x, pre), t(c["fa"])); z = sat(g * z, t(c["p"])); return tconv(tconv(z, t(c["fb"])), post)


def load(take, src):
    clo = C.gen(src[4:]) if src.startswith("gen:") else open(src, "rb").read()
    return torch.tensor(np.load(os.path.join(C.OUT, "bypass.npy"))), torch.tensor(np.load(os.path.join(C.OUT, take + ".npy"))), P.parse(clo)


def align(y, yh, idx):                              # integer lag + gain from the noise segment
    a, b = C.SEG["noise"]; a += 44100; best = None
    for L in range(-300, 300):
        yr = torch.roll(yh, L)[a:b]; g = float((yr * y[a:b]).sum() / (yr * yr).sum())
        e = float(((g * yr - y[a:b]) ** 2).sum())
        if best is None or e < best[0]: best = (e, L)
    return best[1]


IDX = lambda: torch.tensor(np.concatenate([np.arange(C.SEG[s][0] + 44100, C.SEG[s][1]) for s in ("noise", "sine", "di")]))


def esr(y, yh, s): a, b = C.SEG[s]; a += 44100; return round(float(((yh - y)[a:b] ** 2).sum() / (y[a:b] ** 2).sum()), 4)


def learn(take, src):
    x, y, c = load(take, src); idx = IDX()
    pre = torch.zeros(NT, dtype=torch.float64); pre[NT // 2] = 1; post = pre.clone(); lg = torch.tensor(np.log(3.0), dtype=torch.float64)
    with torch.no_grad():
        yh = model(x, c, pre, post, lg.exp()); L = align(y, yh, idx); y = torch.roll(y, -L)
        post[NT // 2] = float((yh[idx] * y[idx]).sum() / (yh[idx] ** 2).sum())
    pre.requires_grad_(); post.requires_grad_(); lg.requires_grad_()
    opt = torch.optim.Adam([pre, post, lg], 1e-3)
    for it in range(1500):
        opt.zero_grad(); yh = model(x, c, pre, post, lg.exp()); loss = ((yh - y)[idx] ** 2).sum() / (y[idx] ** 2).sum(); loss.backward(); opt.step()
        if it % 300 == 0: print(it, round(float(loss), 4), flush=True)
    with torch.no_grad(): yh = model(x, c, pre, post, lg.exp())
    json.dump(dict(pre=pre.detach().tolist(), post=post.detach().tolist(), g=float(lg.exp())), open(EJ, "w"))
    print("learned on", take, {s: esr(y, yh, s) for s in ("noise", "sine", "di")}, "g", round(float(lg.exp()), 3))


def test(take, src):
    x, y, c = load(take, src); e = json.load(open(EJ)); t = lambda a: torch.tensor(a, dtype=torch.float64)
    with torch.no_grad():
        yh = model(x, c, t(e["pre"]), t(e["post"]), e["g"]); L = align(y, yh, IDX()); y = torch.roll(y, -L)
        i = IDX(); k = float((yh[i] * y[i]).sum() / (yh[i] ** 2).sum()); yh = k * yh       # one output gain
    print("test", take, {s: esr(y, yh, s) for s in ("noise", "sine", "di")})


if __name__ == "__main__":
    {"learn": learn, "test": test}[sys.argv[1]](*sys.argv[2:4])
