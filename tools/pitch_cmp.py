#!/usr/bin/env python3
"""pitch_cmp.py <wav> ...: fx audit takes of Octave / Pitch (default knobs: voices 220 and 880 Hz from the 440 tone):
tuning of each voice in cents and the energy that is not one of the three intended tones."""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pmloadtest as L, audit_fx as F, audit as A
for p in sys.argv[1:]:
    y = L.load(p); t0, _ = F.anchors(y); s = A.piece(y, t0, F.T_TONE + 0.3, F.T_TONE + 3.9)
    X = np.abs(np.fft.rfft(s * np.hanning(len(s)))) ** 2; f = np.fft.rfftfreq(len(s), 1 / 44100); keep = 0; out = []
    for f0 in (220, 440, 880):
        i = np.argmin(abs(f - f0)); lo, hi = np.searchsorted(f, f0 / 1.06), np.searchsorted(f, f0 * 1.06)
        j = lo + int(np.argmax(X[lo:hi])); keep += X[j - 20:j + 20].sum()
        if f0 != 440: out.append(f"{f0} Hz voice {1200 * np.log2(f[j] / f0):+.0f} cents")
    print(f"{os.path.basename(p)[3:-4]:12s} {', '.join(out)}; junk {10 * np.log10((X.sum() - keep) / X.sum()):.1f} dB")
