#!/usr/bin/env python3
"""Score a clone against the NAM capture it was made from, offline with the validated clone model
(y = post * bqB( FIRb( sat( g * FIRa( bqA(x) ) ) ) ), g = 3.0 at knobs 50; post = engine low-pass, from the lin take).
x is at pedal-recording scale (DSP input x 0.166 x 0.96); the NAM sees x * c.
  clone_score.py <clo> <nam> [c]     (no c: search the c that matches best = the calibration the clone assumes)"""
import os, sys, json
import numpy as np
from scipy.signal import fftconvolve, lfilter
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import pmclone as P, namrun, clone_fit_check as K
FS = 44100; G = 3.0; USB = 0.166 * 0.96


def engine_post():
    p = os.path.join(RE, "amps", "clone_post.npy")
    if os.path.exists(p): return np.load(p)
    import clone_probe as C                                     # linear take vs bypass -> engine's own filter
    x = np.load(os.path.join(C.OUT, "bypass.npy")); y = np.load(os.path.join(C.OUT, "lin.npy")); a, b = C.SEG["noise"]; N = 4096; S = P_ = 0
    for i in range(a + FS, b - N, N // 2):
        X = np.fft.rfft(x[i:i + N] * np.hanning(N)); Y = np.fft.rfft(y[i:i + N] * np.hanning(N)); S = S + Y * np.conj(X); P_ = P_ + np.abs(X) ** 2
    H = np.abs(S / P_); H /= H[np.argmin(np.abs(np.fft.rfftfreq(N, 1 / FS) - 1000))]
    h = np.fft.irfft(H, N); h = np.roll(h, 64)[:129] * np.hanning(129); np.save(p, h); return h   # zero-phase -> linear-phase


def run(c, x):
    z = fftconvolve(lfilter(c["bqa"][:3], np.r_[1, c["bqa"][3:]], x), c["fa"])[:len(x)]
    z = lfilter(c["bqb"][:3], np.r_[1, c["bqb"][3:]], fftconvolve(K.sat(G * z, c["p"]), c["fb"])[:len(x)])
    return fftconvolve(z, engine_post())[64:64 + len(x)]


def di(secs=60):                                                   # held-out guitar DI (other songs/takes)
    import di_set
    return di_set.load("test", secs) * 10 ** (-15.6 / 20)           # pedal-recording scale (peak 0.9 at DSP scale)


def bands(s):
    f = np.fft.rfftfreq(8192, 1 / FS); C_ = np.geomspace(80, 8000, 20); X = 0
    for i in range(0, len(s) - 8192, 4096): X = X + np.abs(np.fft.rfft(s[i:i + 8192] * np.hanning(8192))) ** 2
    return np.array([10 * np.log10(X[(f > c / 1.12) & (f < c * 1.12)].mean() + 1e-30) for c in C_])


def compare(yh, t):
    a = slice(FS, len(t) - 2048)                                 # lag by FFT cross-correlation (+-1 s), then
    n = 1 << int(np.ceil(np.log2(2 * len(t))))                   # LS gain + short FIR (fractional delay), ESR
    xc = np.fft.irfft(np.fft.rfft(t, n) * np.conj(np.fft.rfft(yh, n)), n); xc = np.r_[xc[-FS:], xc[:FS]]
    L = int(np.argmax(np.abs(xc))) - FS
    A = np.stack([np.roll(yh, L + k) for k in range(-4, 5)], 1); w, *_ = np.linalg.lstsq(A[a], t[a], rcond=None); yy = A @ w
    esr = float(np.sum((yy - t)[a] ** 2) / np.sum(t[a] ** 2)); d = bands(yy[a]) - bands(t[a]); d -= d.mean()
    return dict(esr=round(esr, 3), tone_db=round(float(np.mean(np.abs(d))), 2))


def gain_curve(clo_c, nam, c):
    lv = []
    for db in (-24, -18, -12, -6, 0, 6):
        x = di(6) * 10 ** (db / 20); y = run(clo_c, x); t = np.asarray(namrun.render(nam, x * c)).ravel()[:len(x)]
        lv.append(20 * np.log10(np.std(y[FS:]) / np.std(t[FS:])))
    lv = np.array(lv); return round(float(np.max(lv) - np.min(lv)), 2)


def main():
    clo, nam = sys.argv[1:3]; c_ = P.parse(open(clo, "rb").read()); x = di(); y = run(c_, x)
    cs = [float(sys.argv[3])] if len(sys.argv) > 3 else np.geomspace(0.05, 64, 32)
    res = []
    for c in cs:
        t = np.asarray(namrun.render(nam, x * c)).ravel()[:len(x)]; r = compare(y, t); r["c"] = round(float(c), 3); res.append(r)
    print(" ".join(f"{r['c']}:{r['esr']}/{r['tone_db']}" for r in res), file=sys.stderr)
    best = min(res, key=lambda r: r["esr"]); best["gain_curve_db"] = gain_curve(c_, nam, best["c"])
    print(json.dumps(best))


if __name__ == "__main__":
    main()
