#!/usr/bin/env python3
"""Does the hypothesised clone structure predict the pedal?  model: y = h_out * FIRb( sat( g * FIRa(x) ) )
x = bypass recording (what the DSP sees), sat = pm(1-exp(-pr v)) for v>=0, -nm(1-exp(nr v)) for v<0 (p from the
.clo), h_out = short LS-fitted linear filter (absorbs knob EQ, output gain, delay). Grid over g.
  clone_fit_check.py <take name> <clo file or gen spec>"""
import os, sys
import numpy as np
from scipy.signal import fftconvolve
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import clone_probe as C, pmclone as P
from scipy.signal import lfilter
FS = 44100


def sat(v, p):
    pm, nm, pr, nr = p
    return np.where(v >= 0, pm * (1 - np.exp(-pr * np.maximum(v, 0))), -nm * (1 - np.exp(nr * np.minimum(v, 0))))


def lsfir(z, y, lags):
    A = np.stack([np.roll(z, L) for L in lags], 1); w, *_ = np.linalg.lstsq(A, y, rcond=None); return A @ w, w


def check(take, clo, segs=("noise", "sine", "di"), sat_fn=sat):
    x = np.load(os.path.join(C.OUT, "bypass.npy")); y = np.load(os.path.join(C.OUT, take + ".npy")); c = P.parse(clo)
    idx = np.concatenate([np.arange(C.SEG[s][0] + FS, C.SEG[s][1]) for s in segs]); best = None   # skip 1 s settle
    za = fftconvolve(lfilter(c["bqa"][:3], np.r_[1, c["bqa"][3:]], x), c["fa"])[:len(x)]
    # coarse lag between model and take
    lin = fftconvolve(za, c["fb"])[:len(x)]
    ni = np.arange(*C.SEG["noise"])                       # lag from the noise only (the sine is periodic)
    cc = [np.dot(np.roll(lin, L)[ni], y[ni]) for L in range(-400, 400)]; L0 = int(np.argmax(np.abs(cc))) - 400
    for g in np.r_[np.geomspace(0.01, 1000, 41), np.geomspace(2, 5, 25)]:
        z = lfilter(c["bqb"][:3], np.r_[1, c["bqb"][3:]], fftconvolve(sat_fn(g * za, c["p"]), c["fb"])[:len(x)])
        yh, w = lsfir(z, y, range(L0 - 48, L0 + 48)); e = np.sum((yh - y)[idx] ** 2) / np.sum(y[idx] ** 2)
        if best is None or e < best[0]: best = (e, g, yh)
    e, g, yh = best
    sl = lambda s: slice(C.SEG[s][0] + FS, C.SEG[s][1])
    per = {s: round(float(np.sum((yh - y)[sl(s)] ** 2) / np.sum(y[sl(s)] ** 2)), 3) for s in segs}
    return dict(esr=round(float(e), 3), g=round(float(g), 3), lag=L0, per=per)


if __name__ == "__main__":
    t, src = sys.argv[1:3]; clo = C.gen(src[4:]) if src.startswith("gen:") else open(src, "rb").read()
    print(t, check(t, clo))
