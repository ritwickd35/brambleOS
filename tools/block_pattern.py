#!/usr/bin/env python3
"""block_pattern.py <bypass.wav> <effect.wav> ...: audit recordings; per 64-sample engine block, at how many sample
positions the effect output differs from bypass beyond scaling (DI clip section). 64 = whole block processed."""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit as A, pmloadtest as L
b = L.load(sys.argv[1]); B = A.piece(b, A.sync(b), A.T_DI, A.T_DI + 8)
for p in sys.argv[2:]:
  try:
    y = L.load(p); Y = A.piece(y, A.sync(y), A.T_DI, A.T_DI + 8); n = len(B) - 200; best = None
    for lag in range(-100, 100):
        e = np.sum((Y[100 + lag:100 + lag + n] - B[100:100 + n]) ** 2)
        if best is None or e < best[0]: best = (e, lag)
    Yb = Y[100 + best[1]:100 + best[1] + n]; Bb = B[100:100 + n]; g = np.dot(Yb, Bb) / np.dot(Bb, Bb); d = Yb - g * Bb
    tot = float(np.sum(d ** 2) / np.sum((g * Bb) ** 2)); pos = np.array([np.mean(d[k::64] ** 2) for k in range(64)])
    spikes = int(np.sum(pos > 10 * np.median(pos)))
    kind = "unchanged" if tot < 0.01 else (f"{spikes} sample(s) per block changed" if spikes and spikes < 8 else "whole block changed")
    print(f"{os.path.basename(p)}: {kind} (residual {tot:.3f})")
  except Exception as e: print(os.path.basename(p), "not analysable:", str(e)[:60])
