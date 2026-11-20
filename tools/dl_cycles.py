#!/usr/bin/env python3
"""rv_cycles.py <rvb fxid> ...: our reverb with Mix = 1 (timing probe): reads cycles per 64-frame block from the right
channel, with a guitar-level noise input. P08 restored."""
import sys, time, wave, os
import numpy as np, sounddevice as sd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pmaudio
from pmflash import Link
from cut1_variants import read_p
from cut1_matrix import send, set_mod
l = Link(); orig = read_p(l); l.close(); base = orig
for k in range(10): base = set_mod(base, k, on=False)
x = (0.1 * np.random.default_rng(1).standard_normal(44100 * 5)).astype(np.float32)
try:
    def rd(fx, mix):
        send(set_mod(base, 7, fx, [mix, 500, 50, 0, 25, 0, 0, 0], True)); time.sleep(2); p = pmaudio.record("/tmp/cy.wav", 5); time.sleep(0.3)
        sd.play(np.stack([x, x], 1), samplerate=44100, device=pmaudio.out_device("External Headphones")); p.wait(); sd.stop()
        w = wave.open("/tmp/cy.wav"); y = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2).astype(float) / 32768
        return float(np.median(y[44100 * 3:44100 * 4, 1]))
    fx0 = int(sys.argv[1]); g = rd(fx0, 2) / 0.1; print(f"output gain DSP -> USB: {g:.3f}")
    for fx in [int(a) for a in sys.argv[1:]]:
        c = rd(fx, 1) * 1e6 / g; print(f"{fx}: {c:,.0f} cycles per block = {100 * c / 278600:.0f} % of the budget", flush=True)
finally:
    send(orig); time.sleep(0.5); l = Link(); back = read_p(l); l.close(); print("P08 restored", back[4:] == orig[4:])
