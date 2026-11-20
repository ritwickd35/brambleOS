#!/usr/bin/env python3
"""dropouts.py <wav> ...: engine overload check. Over the sustained 220 Hz ramp steps, counts 64-sample blocks whose
level falls far below the surrounding blocks (gaps / repeated or skipped blocks) and reports the worst dip."""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit as A, pmloadtest as L
for p in sys.argv[1:]:
    y = L.load(p); t0 = A.sync(y); bad = 0; worst = 0.0; n = 0
    for i in range(4, 9):                                         # loudest 5 steps
        s = A.piece(y, t0, A.T_RAMP + i * .75 + .1, A.T_RAMP + i * .75 + .7); m = len(s) // 64
        r = np.sqrt(np.mean(s[:m * 64].reshape(m, 64) ** 2, 1)); med = np.median(r); n += m
        dip = r / (med + 1e-12); bad += int(np.sum(dip < 0.5)); worst = min(worst, float(20 * np.log10(dip.min() + 1e-9)))
    print(f"{os.path.basename(p)}: {bad} of {n} blocks dropped below half level, worst dip {worst:.1f} dB")
