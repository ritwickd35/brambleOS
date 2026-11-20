#!/usr/bin/env python3
"""Reliable audio check: P08 with every effect off, 220 Hz tone in, USB level out (exit 0 if audio passes).
P08 is restored byte-identically."""
import sys, time, os
import numpy as np, sounddevice as sd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pmaudio, eprobe_decode as D
from pmflash import Link
from cut1_variants import read_p
from cut1_matrix import send, set_mod
l = Link(); orig = read_p(l); l.close(); base = orig
for k in range(10): base = set_mod(base, k, on=False)
lv = -240.0
try:
    send(base); time.sleep(1.5)
    t = np.arange(44100 * 5) / 44100; tone = (0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    p = pmaudio.record("/tmp/pm_audio_ok.wav", 5); time.sleep(0.3)
    sd.play(np.stack([tone, tone], 1), samplerate=44100, device=pmaudio.out_device("External Headphones")); p.wait(); sd.stop()
    x = D.load("/tmp/pm_audio_ok.wav"); lv = float(20 * np.log10(np.sqrt(np.mean(x[44100:] ** 2)) + 1e-12))
finally:
    send(orig); time.sleep(0.5); l = Link(); back = read_p(l); l.close()
print(f"audio level {lv:.1f} dB, P08 restored {back[4:] == orig[4:]}"); sys.exit(0 if lv > -60 else 1)
