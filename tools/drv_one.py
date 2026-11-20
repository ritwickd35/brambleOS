#!/usr/bin/env python3
"""drv_one.py <fxid> [gain]: P08 with only the DRV slot on (given effect), 220 Hz tone in, USB level out;
then the same with everything off (is the audio still alive?). P08 restored."""
import sys, time, os
import numpy as np, sounddevice as sd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pmaudio, eprobe_decode as D
from pmflash import Link
from cut1_variants import read_p
from cut1_matrix import send, set_mod
fx = int(sys.argv[1], 0); g = float(sys.argv[2]) if len(sys.argv) > 2 else 50.0
l = Link(); orig = read_p(l); l.close(); base = orig
for k in range(10): base = set_mod(base, k, on=False)
t = np.arange(44100 * 4) / 44100; tone = (0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
def level(rec):
    send(rec); time.sleep(1.5); p = pmaudio.record("/tmp/drv_one.wav", 4); time.sleep(0.3)
    sd.play(np.stack([tone, tone], 1), samplerate=44100, device=pmaudio.out_device("External Headphones")); p.wait(); sd.stop()
    x = D.load("/tmp/drv_one.wav")[44100:44100 * 3]; return round(float(20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)), 1)
try:
    on = level(set_mod(base, 2, fx, [g, 50.0, 50.0, 0, 0, 0, 0, 0], True)); off = level(base)
finally:
    send(orig); time.sleep(0.5); l = Link(); back = read_p(l); l.close()
print(f"fx {fx} gain {g}: drive on {on} dB, all off afterwards {off} dB, P08 restored {back[4:] == orig[4:]}")
