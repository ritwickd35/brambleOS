#!/usr/bin/env python3
"""rv_clicks.py <fxid> ...: reverb at mix 50 on a 220 Hz tone; counts sample jumps far above the clean tone's (CPU overrun
shows as clicks). Stock Light as reference. P08 restored."""
import sys, time, wave, os
import numpy as np, sounddevice as sd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pmaudio
from pmflash import Link
from cut1_variants import read_p
from cut1_matrix import send, set_mod
l = Link(); orig = read_p(l); l.close(); base = orig
for k in range(10): base = set_mod(base, k, on=False)
t = np.arange(44100 * 5) / 44100; tone = (0.15 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
def take(rec):
    send(rec); time.sleep(2); p = pmaudio.record("/tmp/ck.wav", 5); time.sleep(0.3)
    sd.play(np.stack([tone, tone], 1), samplerate=44100, device=pmaudio.out_device("External Headphones")); p.wait(); sd.stop()
    w = wave.open("/tmp/ck.wav"); y = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2).astype(float)[44100:44100 * 4, 0]
    d = np.abs(np.diff(y)); return int(np.sum(d > 2.5 * np.percentile(d, 99)))
try:
    for fx in [201326598] + [int(a) for a in sys.argv[1:]]:
        print(fx, "clicks:", take(set_mod(base, 8, fx, [50, 50, 0, 0, 0, 0, 0, 0], True)), flush=True)
finally:
    send(orig); time.sleep(0.5); l = Link(); back = read_p(l); l.close(); print("P08 restored", back[4:] == orig[4:])
