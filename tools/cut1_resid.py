#!/usr/bin/env python3
"""Cut 1 headroom from recordings, robust to compressors/gates: detects sustained breakup of the 1 kHz test tone
via the periodicity residual y[n]-y[n-882] (882 samples = 20 periods of 1 kHz, 10 of 500 Hz).
Measures where each overload ENDS (the test module stops its own ramp on 2 late blocks), see cycles().
Needs delay/reverb tails low (mix ~1 %), otherwise the end is blurred.
Reads higher than the first-click method (it is the module's overrun point); compare runs, not absolutes.
Usage: cut1_resid.py <wav in audio/> ..."""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pmloadtest as L
FS, W = 44100, 0.0625


def resid(path, lag=882):
    y = L.load(path); d = y[lag:] - y[:-lag]; x = y[lag:]
    q = int(W * FS); m = len(d) // q
    return np.sqrt(np.mean(d[:m * q].reshape(m, q) ** 2, 1)) / (np.sqrt(np.mean(x[:m * q].reshape(m, q) ** 2, 1)) + 1e-9)


def regions(r, thr=0.8, k=8, minlen=1.0):
    rm = np.array([r[i:i + k].min() for i in range(len(r) - k + 1)]); hot = rm > thr; out = []; i = 0
    while i < len(hot):
        if hot[i]:
            j = i
            while j < len(hot) and hot[j]: j += 1
            a, b = i * W, (j + k - 1) * W
            if b - a >= minlen:
                if out and a - out[-1][1] <= 0.5: out[-1][1] = b
                else: out.append([a, b])
            i = j
        else:
            i += 1
    return out


def ends(path):
    """End of each overload (= the module's own overrun detection stops the ramp, so the tone becomes clean):
    the 3 strongest drops of the residual (0.5 s before vs 1 s after), >= 8 s apart, between 8 and 60 s."""
    r = resid(path); n = len(r); a = int(0.5 / W); b = int(1.0 / W)
    D = np.full(n, -9.0)
    for t in range(a, n - b):
        D[t] = r[t - a:t].mean() - r[t:t + b].mean()
    out = []
    for t in np.argsort(D)[::-1]:
        tt = t * W
        if 8 <= tt <= 60 and all(abs(tt - e) > 8 for e in out):
            out.append(tt)
        if len(out) == 3:
            break
    return sorted(out)


def cycles(path):
    """Headroom k per cycle = the module's own stop value (signal independent).
    Cycle 1: (end - marker - 2.5 s) / 0.25 s. Cycles 2-3: (end - previous end - 6 s) / 0.25 s
    (4 s rest + marker + 2 s rest). The 0.5 s in cycle 1 is calibrated on cycles 2-3 of 14 recordings."""
    e = ends(path)
    mk = max(t for t, _ in L.glitches(L.load(path)) if t < 7)
    ks = [(e[0] - mk - 2.5) / 0.25] + [(e[i + 1] - e[i] - 6.0) / 0.25 for i in range(len(e) - 1)]
    return [round(float(k), 1) for k in ks]


if __name__ == "__main__":
    for f in sys.argv[1:]:
        ks = cycles(f if os.path.exists(f) else os.path.join(L.OUT, f))
        print(f, "headroom per cycle", ks, "median", float(np.median(ks)))
