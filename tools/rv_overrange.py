#!/usr/bin/env python3
"""rv_overrange.py: stock reverbs with Decay beyond the knob range (100, 150, 200, 400): T30 at 1 kHz and colouration."""
import sys, os, time, wave
import numpy as np, sounddevice as sd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pmaudio, space_bench as B
from pmflash import Link
from cut1_variants import read_p
from cut1_matrix import send, set_mod
REV = {"Room": 201326592, "Hall": 201326593, "Church": 201326594, "Plate 1": 201326608, "Dream": 201326613, "Air": 201326603}
x = B.signal(); play = np.stack([x, x], 1); dev = pmaudio.out_device("External Headphones")
l = Link(); orig = read_p(l); l.close(); base = orig
for k in range(10): base = set_mod(base, k, on=False)
try:
    for nm, fx in REV.items():
        row = []
        for dec in (100, 150, 200, 400):
            send(set_mod(base, 8, fx, [100, dec, 0, 0, 0, 0, 0, 0], True)); time.sleep(2)
            p = pmaudio.record("/tmp/ov.wav", len(x) / 44100 + 1.5); time.sleep(0.5); sd.play(play, samplerate=44100, device=dev); p.wait(); sd.stop()
            w = wave.open("/tmp/ov.wav"); y = B.align(np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2).astype(float) / 32768)
            r = B.reverb(y); row.append(f"{dec}: {r['t30'][1000]} s")
        print(nm, " | ".join(row), flush=True)
finally:
    send(orig); time.sleep(0.5); l = Link(); back = read_p(l); l.close(); print("P08 restored", back[4:] == orig[4:])
