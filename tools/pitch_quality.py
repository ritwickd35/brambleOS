#!/usr/bin/env python3
"""pitch_quality.py <wav...>: fx audit recordings; on the 440 Hz tone: main peaks and the energy that is neither the
dry tone nor the intended shifted tone(s) (the two biggest peaks), in dB."""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pmloadtest as L, audit_fx as F, audit as A
for p in sys.argv[1:]:
    y = L.load(p); t0, _ = F.anchors(y); s = A.piece(y, t0, F.T_TONE + 0.3, F.T_TONE + 3.9)
    X = np.abs(np.fft.rfft(s * np.hanning(len(s)))) ** 2; f = np.fft.rfftfreq(len(s), 1 / 44100); Xc = X.copy(); pk = []
    for _ in range(5):
        i = int(np.argmax(Xc)); pk.append((int(f[i]), round(float(10 * np.log10(Xc[i] / X.max())), 1))); Xc[max(0, i - 30):i + 30] = 0
    keep = sum(X[max(0, int(np.argmin(abs(f - a))) - 20):int(np.argmin(abs(f - a))) + 20].sum() for a, _ in pk[:2])
    print(f"{os.path.basename(p)[3:-4]:14s} peaks {pk}  junk {10 * np.log10((X.sum() - keep) / X.sum()):.1f} dB")
