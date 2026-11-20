#!/usr/bin/env python3
"""hw_vs_model.py <bypass.wav> <effect.wav> <host effect> <knobs...>: does the pedal output match the C model?
Uses the audit DI section; input scale from the bypass take; ESR after best delay and gain."""
import sys, os, subprocess
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit as A, pmloadtest as L
x, _ = A.signal(); RE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
b = L.load(sys.argv[1]); y = L.load(sys.argv[2])
seg = lambda s, t: A.piece(s, t, A.T_DI, A.T_DI + 6)
X = seg(x, 0.0); B = seg(b, A.sync(b)); Y = seg(y, A.sync(y))
def fit(ref, rec):
    n = min(len(ref), len(rec)); N = 1 << int(np.ceil(np.log2(2 * n)))
    c = np.fft.irfft(np.fft.rfft(rec[:n], N) * np.conj(np.fft.rfft(ref[:n], N)), N)
    lag = int(np.argmax(np.abs(c))); lag = lag - N if lag > N // 2 else lag
    r = rec[max(lag, 0):]; t = ref[max(-lag, 0):]; m = min(len(r), len(t)) - 100; r, t = r[:m], t[:m]
    g = np.dot(r, t) / np.dot(t, t); return float(np.sum((r - g * t) ** 2) / np.sum((g * t) ** 2)), lag, g


gout = float(np.std(B) / np.std(X * 2.87))                        # pedal output gain (bypass take vs played level)
xd = b[int((A.sync(b) - 0.3) * A.FS):] / gout                      # what the DSP saw, in the pedal's own clock
ref = np.frombuffer(subprocess.run([os.path.join(RE, "dsp", "host"), sys.argv[3]] + sys.argv[4:], input=xd.astype("<f4").tobytes(),
                                   capture_output=True, check=True).stdout, "<f4").astype(np.float64)
R = A.piece(ref, 0.3, A.T_DI, A.T_DI + 6) * gout
e, lag, g = fit(R, Y)
print(f"{os.path.basename(sys.argv[2])}: ESR vs C model {e:.4f}, level ratio {g:.3f} (1 = exact)")
