#!/usr/bin/env python3
"""ab_amps.py: our amps (audio/ampcap-amps16) vs the stock amps (audio/ampcap), both recorded on the pedal with the
same knob settings: tone difference (DI clip, 1/3 octave, level-matched), gain-curve difference, alias spikes."""
import os, sys, glob, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import audit as A, alias_metric as M
FS = 44100; C = np.geomspace(80, 10000, 20); f = np.fft.rfftfreq(8192, 1 / FS)
def bands(s):
    X = 0
    for i in range(0, len(s) - 8192, 4096): X = X + np.abs(np.fft.rfft(s[i:i + 8192] * np.hanning(8192))) ** 2
    return np.array([10 * np.log10(X[(f > c / 1.12) & (f < c * 1.12)].mean() + 1e-20) for c in C])
def ramp(y): return np.array([20 * np.log10(np.std(y[int((A.T_RAMP + i * .75 + .15) * FS):int((A.T_RAMP + i * .75 + .65) * FS)]) + 1e-12) for i in range(9)])
rows = []
for d in sorted(glob.glob(os.path.join(RE, "audio", "ampcap" + os.environ.get("AB_TAG", "-amps16"), "*/"))):
    amp = os.path.basename(d.rstrip("/")); st = os.path.join(RE, "audio", "ampcap", amp)
    for p in sorted(glob.glob(d + "*.f32")):
        q = os.path.join(st, os.path.basename(p))
        if not os.path.exists(q): continue
        y, s = np.fromfile(p, "<f4").astype(float), np.fromfile(q, "<f4").astype(float)
        seg = lambda z: z[int(A.T_DI * FS):int((A.T_DI + 10) * FS)]
        dt = bands(seg(y)) - bands(seg(s)); dt -= dt.mean(); dr = ramp(y) - ramp(s); dr -= dr[-1]
        ay, as_ = M.tones(y, 0.0), M.tones(s, 0.0)
        rows.append((amp, os.path.basename(p)[:-4], float(np.mean(np.abs(dt))), float(np.max(np.abs(dt))), float(np.mean(np.abs(dr))),
                     float(np.mean(list(ay.values()))), float(np.mean(list(as_.values())))))
print(f"{'amp':12s} {'knobs':22s} tone diff (worst) | gain-curve diff | fizz ours vs stock")
for r in rows: print(f"{r[0]:12s} {r[1]:22s} {r[2]:4.1f} ({r[3]:4.1f}) dB | {r[4]:4.1f} dB | {r[5]:6.1f} vs {r[6]:6.1f} dB")
json.dump(rows, open(os.path.join(RE, "logs", "ab_amps.json"), "w"))
