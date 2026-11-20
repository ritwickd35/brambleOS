#!/usr/bin/env python3
"""Aliasing metric that ignores noise: for each audit test tone, the power in the discrete alias spikes
(|k f0 - m fs| folded, not a harmonic) above the local noise floor, relative to the harmonics, in dB.
  alias_metric.py <wav> [...]       audit recordings (audit.py signal)
  alias_metric.py --host <effect> <knobs...>   the same metric on the offline C model (no noise)"""
import os, sys, subprocess
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import audit as A
FS = A.FS


def alias_db(s, f0n):
    w = np.hanning(len(s)); X = np.abs(np.fft.rfft(s * w)) ** 2; f = np.fft.rfftfreq(len(s), 1 / FS); df = f[1]
    band = (f > f0n * 0.98) & (f < f0n * 1.02); f0 = f[band][np.argmax(X[band])]
    harm = [k * f0 for k in range(1, int(20000 / f0) + 1)]
    H = sum(X[np.abs(f - h) < 8 * df].sum() for h in harm)
    spikes = set()
    for k in range(2, 60):
        a = (k * f0) % FS; a = FS - a if a > FS / 2 else a
        if 40 < a < 20000 and min(abs(a - h) for h in harm) > 30: spikes.add(round(a / df))
    P = 0.0
    for b in spikes:
        lo, hi = max(b - 3, 0), min(b + 4, len(X)); pk = X[lo:hi].sum()
        ring = np.r_[X[max(b - 60, 0):max(b - 10, 0)], X[b + 10:b + 60]]; floor = np.median(ring) * (hi - lo) if len(ring) else 0
        P += max(pk - floor, 0.0)
    return float(10 * np.log10(P / H + 1e-15))


def tones(y, t0):
    return {f: round(alias_db(A.piece(y, t0, A.T_TONE + i + 0.15, A.T_TONE + i + 0.85), f), 1) for i, f in enumerate(A.TONES)}


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "--host":
        x, _ = A.signal()
        y = np.frombuffer(subprocess.run([os.path.join(RE, "dsp", "host"), a[1]] + a[2:], input=(x * 2.87).astype("<f4").tobytes(),
                                         capture_output=True, check=True).stdout, "<f4").astype(np.float64)
        print("offline", a[1], a[2:], tones(y, 0.0))
    else:
        import pmloadtest as L
        for p in a:
            y = L.load(p); print(os.path.basename(p), tones(y, A.sync(y)))
