#!/usr/bin/env python3
"""cab_knob_test.py: 4x12 Green with Low/High cut settings, measured response relative to knobs at 0. P08 restored."""
import sys, time, os
import numpy as np, sounddevice as sd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cab_capture as CC, pmaudio, eprobe_decode as D
from pmflash import Link
from cut1_variants import read_p
from cut1_matrix import send, set_mod
x = CC.sweep(); dev = pmaudio.out_device("External Headphones")
l = Link(); orig = read_p(l); l.close(); base = orig
for k in range(10): base = set_mod(base, k, on=False)
def take(rec):
    send(rec); time.sleep(3.0); p = pmaudio.record("/tmp/cab.wav", len(x) / 44100 + 1.5); time.sleep(0.3)
    sd.play(np.stack([x, x], 1), samplerate=44100, device=dev); p.wait(); sd.stop(); return D.load("/tmp/cab.wav").astype(float)
f = np.fft.rfftfreq(8192, 1 / 44100); C = [60, 100, 200, 500, 1000, 3000, 6000, 10000]
def bands(h):
    H = np.abs(np.fft.rfft(h, 8192)) ** 2; return np.array([10 * np.log10(H[(f > c / 1.15) & (f < c * 1.15)].mean() + 1e-20) for c in C])
try:
    ref = take(base); res = {}
    for kn in ((0, 0), (80, 0), (0, 80), (80, 80), (0, 0)):
        h = CC.deconv(take(set_mod(base, 4, 167772194, [50.0, float(kn[0]), float(kn[1]), 0, 0, 0, 0, 0], True)), ref); res.setdefault(kn, []).append(bands(h))
    r0 = res[(0, 0)][0]
    for kn, bs in res.items():
        for b in bs: print(f"LoCut {kn[0]:3d} HiCut {kn[1]:3d}:", " ".join(f"{c}:{v:+.0f}" for c, v in zip(C, b - r0)))
finally:
    send(orig); time.sleep(0.5); l = Link(); back = read_p(l); l.close(); print("P08 restored:", back[4:] == orig[4:])
