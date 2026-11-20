#!/usr/bin/env python3
"""hw_tone.py <bypass.wav> <pedal.wav> <host args...>: pedal recording vs the C model fed with the bypass recording
(same input the pedal saw): tone difference per 1/3 octave (DI clip, level-matched) and gain-curve difference."""
import sys, os, subprocess
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit as A, pmloadtest as L
RE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
b = L.load(sys.argv[1]); y = L.load(sys.argv[2]); tb, ty = A.sync(b), A.sync(y)
xin = b[int((tb - 0.3) * A.FS):] * float(os.environ.get("IN_SCALE", "1"))
ref = np.frombuffer(subprocess.run([os.path.join(RE, "dsp", "host")] + sys.argv[3:], input=xin.astype("<f4").tobytes(), capture_output=True, check=True).stdout, "<f4").astype(float)
C = np.geomspace(80, 12000, 22); f = np.fft.rfftfreq(8192, 1 / A.FS)
def bands(s):
    X = 0
    for i in range(0, len(s) - 8192, 4096): X = X + np.abs(np.fft.rfft(s[i:i + 8192] * np.hanning(8192))) ** 2
    return np.array([10 * np.log10(X[(f > c / 1.12) & (f < c * 1.12)].mean() + 1e-20) for c in C])
d = bands(A.piece(y, ty, A.T_DI, A.T_DI + 12)) - bands(A.piece(ref, 0.3, A.T_DI, A.T_DI + 12)); d -= d.mean()
ramp = lambda s, t: np.array([20 * np.log10(np.std(A.piece(s, t, A.T_RAMP + i * .75 + .15, A.T_RAMP + i * .75 + .65)) + 1e-12) for i in range(9)])
r = ramp(y, ty) - ramp(ref, 0.3); r -= r[-1]
if os.environ.get("BANDS"): print(" ".join(f"{int(c)}:{v:+.0f}" for c, v in zip(C, d)))
print(f"{os.path.basename(sys.argv[2])}: tone diff vs C model {np.mean(np.abs(d)):.1f} dB (worst {np.max(np.abs(d)):.1f}), gain-curve diff {np.mean(np.abs(r)):.1f} dB")
