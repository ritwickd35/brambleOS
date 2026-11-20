#!/usr/bin/env python3
"""drv_blocks.py <fxid> [...]: for each DRV effect, how many of the 64 samples per engine block it changes
(vs everything off), plus the level. 64 = runs normally, 1 = the sample loop stops after one sample, 0 = no effect.
Then checks the audio is still alive. P08 restored."""
import sys, time, os
import numpy as np, sounddevice as sd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pmaudio, eprobe_decode as D
from pmflash import Link
from cut1_variants import read_p
from cut1_matrix import send, set_mod
rng = np.random.default_rng(5); sig = (0.15 * rng.standard_normal(44100 * 4)).astype(np.float32)
sig = np.convolve(sig, np.ones(4) / 4, "same").astype(np.float32)
def take(rec):
    send(rec); time.sleep(1.5); p = pmaudio.record("/tmp/drv_blocks.wav", 5); time.sleep(0.3)
    sd.play(np.stack([sig, sig], 1), samplerate=44100, device=pmaudio.out_device("External Headphones")); p.wait(); sd.stop()
    return D.load("/tmp/drv_blocks.wav").astype(np.float64)
def blocks(b, y):
    B = b[44100:44100 * 3]; n = len(B) - 2000; best = None
    for lag in range(-600, 600):
        Y = y[44100 + 1000 + lag:44100 + 1000 + lag + 4000]; e = np.sum((Y - B[1000:5000] * (np.dot(Y, B[1000:5000]) / np.dot(B[1000:5000], B[1000:5000]))) ** 2) / np.sum(Y ** 2 + 1e-20)
        if best is None or e < best[0]: best = (e, lag)
    lag = best[1]; Y = y[44100 + 1000 + lag:44100 + 1000 + lag + n]; Bb = B[1000:1000 + n]
    g = np.dot(Y, Bb) / np.dot(Bb, Bb); d = Y - g * Bb
    r = np.array([np.mean(d[k::64] ** 2) / np.mean((g * Bb[k::64]) ** 2 + 1e-20) for k in range(64)])
    tot = float(np.sum(d ** 2) / np.sum((g * Bb) ** 2)); spikes = int(np.sum(r > 10 * np.median(r)))
    return (f'whole-signal change {tot:.3f}, outlier positions {spikes}'), round(float(20 * np.log10(np.std(y[44100:44100 * 3]) + 1e-12)), 1)


l = Link(); orig = read_p(l); l.close(); base = orig
for k in range(10): base = set_mod(base, k, on=False)
try:
    b = take(base)
    for a in sys.argv[1:]:
        fx = int(a, 0); y = take(set_mod(base, 2, fx, [50.0, 50.0, 50.0, 0, 0, 0, 0, 0], True)); nb, lv = blocks(b, y)
        alive = take(base); al = round(float(20 * np.log10(np.std(alive[44100:44100 * 3]) + 1e-12)), 1)
        print(f"fx {fx}: {nb}, level {lv} dB; audio afterwards {al} dB", flush=True)
        if al < -100: break
finally:
    send(orig); time.sleep(0.5); l = Link(); back = read_p(l); l.close(); print("P08 restored:", back[4:] == orig[4:])
