#!/usr/bin/env python3
"""chain_check.py <bypass.wav> <pedal.wav> [--drive <host effect>] [--amp <settings.txt>] [--cab <catalog record>]:
the pedal recording vs the same chain built from our C models (drive -> amp -> cab IR from build/cabs1). Reports the
overall match and the number of 64-sample blocks that differ grossly from the model (dropouts / overload)."""
import sys, os, subprocess, struct
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit as A, pmloadtest as L
RE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); H = os.path.join(RE, "dsp", "host")
a = sys.argv[1:]; opt = {a[i]: a[i + 1] for i in range(2, len(a) - 1, 2)}
b = L.load(a[0]); y = L.load(a[1]); x = b[int((A.sync(b) - 0.3) * A.FS):]
run = lambda args, s: np.frombuffer(subprocess.run([H] + args, input=s.astype("<f4").tobytes(), capture_output=True, check=True).stdout, "<f4").astype(float)
if "--drive" in opt: x = run([opt["--drive"], "50", "50", "50"], x * float(opt.get("--dscale", "2.0")))
if "--amp" in opt: x = run(["amp", opt["--amp"], "50", "50", "50", "50", "50", "50", "0"], x)
if "--cab" in opt:
    cb = open(os.path.join(RE, "build", "cabs1", "src", "2_cab_catalog_00280000.bin"), "rb").read(); r = int(opt["--cab"])
    k = struct.unpack_from("<I", cb, 72 * r + 16)[0] >> 16; w = np.frombuffer(cb[2048 * k:2048 * (k + 1)], "<i4").astype(float)
    x = np.convolve(x, w[w != -1] / 2 ** 23)[:len(x)]
R = A.piece(x, 0.3, A.T_TONE, A.T_DI + 10); Y = A.piece(y, A.sync(y), A.T_TONE, A.T_DI + 10); n = min(len(R), len(Y)); N = 1 << 22
c = np.fft.irfft(np.fft.rfft(Y[:n], N) * np.conj(np.fft.rfft(R[:n], N)), N); lag = int(np.argmax(np.abs(c))); lag = lag - N if lag > N // 2 else lag
r = Y[max(lag, 0):]; t = R[max(-lag, 0):]; m = (min(len(r), len(t)) // 64) * 64; r, t = r[:m], t[:m]; g = np.dot(r, t) / np.dot(t, t)
e = ((r - g * t) ** 2).reshape(-1, 64).sum(1); s = ((g * t) ** 2).reshape(-1, 64).sum(1); loud = s > 0.01 * np.median(s[s > 0])
bad = int(np.sum((e > 0.5 * s) & loud))
print(f"{os.path.basename(a[1])}: ESR vs model {np.sum(e) / np.sum(s):.3f}; blocks way off the model {bad} of {int(loud.sum())}")
