#!/usr/bin/env python3
"""ampcmp.py <our name> [settings json]: our C model vs the stock capture, per knob set: mean |dB| difference in
1/3-octave bands (DI clip) and the gain-ramp level difference (dB). Small = sounds alike."""
import sys, os, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import ampmodel as AM, audit as A, amp_capture as AC
name = sys.argv[1]; s = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else AM.load(name)
stock = AM.LINEUP[name][0]; kn_names = AC.stock_amps()[stock][1]
spec = json.load(open(os.path.join(RE, "audio", "ampcap", stock.replace(" ", "_"), "spec.json")))
f = np.geomspace(80, 12000, 23)
def bands(y):
    w = 4096; X = 0
    for i in range(0, len(y) - w, w // 2): X = X + np.abs(np.fft.rfft(y[i:i + w] * np.hanning(w))) ** 2
    fr = np.fft.rfftfreq(w, 1 / 44100); return np.array([10 * np.log10(X[(fr > a / 1.12) & (fr < a * 1.12)].mean() + 1e-20) for a in f])
for c in spec:
    x = np.fromfile(c["in"], "<f4").astype(float); y = np.fromfile(c["out"], "<f4").astype(float)
    eff = [50.0] * 6 + [0]
    for i, nm in enumerate(AC.OURS):
        if AC.ALIAS.get(nm, nm) in [AC.ALIAS.get(k, k) for k in kn_names]: eff[i] = c["knobs"][i]
    m = AM.run(s, eff, x)
    seg = lambda z: z[int(A.T_DI * 44100):int((A.T_DI + 8) * 44100)]
    d = bands(seg(m)) - bands(seg(y)); d -= d.mean()
    ramp = [20 * np.log10(np.std(z[int((A.T_RAMP + i * .75 + .15) * 44100):int((A.T_RAMP + i * .75 + .65) * 44100)]) + 1e-12) for z in (m, y) for i in range(9)]
    rd = np.array(ramp[:9]) - np.array(ramp[9:]); rd -= rd[-1]
    if os.environ.get("BANDS"): print("   ", " ".join(f"{int(a)}:{v:+.0f}" for a, v in zip(f, d)))
    print(c["knobs"], f"tone diff {np.mean(np.abs(d)):.1f} dB (worst {np.max(np.abs(d)):.1f}), gain-curve diff {np.mean(np.abs(rd)):.1f} dB")
