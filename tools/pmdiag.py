#!/usr/bin/env python3
"""Analyse a cut1b diagnostic recording: dropout fraction per 0.25 s (envelope only, ignores distortion)."""
import sys, numpy as np
sys.path.insert(0, __import__("os").path.dirname(__file__))
import pmloadtest as L
FS = 44100
y = L.load(sys.argv[1])
w = 32; n = len(y) // w
env = np.sqrt(np.mean(y[:n * w].reshape(n, w) ** 2, axis=1))
med = np.median(env[env > 0])
bad = env < 0.5 * med
step = int(0.25 * FS / w)
print("time   dropout%   (each '#' = 5 %)")
for i in range(0, n - step, step):
    f = 100 * bad[i:i + step].mean()
    print(f"{i * w / FS:6.2f}s {f:6.1f}%  {'#' * int(f / 5)}")
