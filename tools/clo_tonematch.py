#!/usr/bin/env python3
"""Tone match for a clone: fix the remaining tone difference to the capture (including the 6-10 kHz loss of the
pedal's fixed clone low-pass) with an EQ folded into the clone's output filter (FIRb, after the distortion, so it
is a pure tone change). Minimum-phase EQ (no added latency), 1/6-octave smoothing, +-9 dB, 80 Hz - 10.5 kHz;
above 10.5 kHz the EQ stays at its 10.5 kHz value (the steep fixed cut above ~12 kHz is not chased).
  clo_tonematch.py <in.clo> <capture.nam> <out.clo>"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pmclone as P, clone_score as S, namrun, di_set
FS = 44100; N = 8192


def spec(s):
    X = 0
    for i in range(0, len(s) - N, N // 2): X = X + np.abs(np.fft.rfft(s[i:i + N] * np.hanning(N))) ** 2
    return X


def minphase(mag):                                   # magnitude (rfft bins of N) -> minimum-phase impulse response
    c = np.fft.irfft(np.log(np.maximum(mag, 1e-6)), N); c[1:N // 2] *= 2; c[N // 2 + 1:] = 0
    return np.fft.irfft(np.exp(np.fft.rfft(c, N)), N)


def tonematch(c, nam, secs=60):
    x = di_set.load("train", secs) * 10 ** (-15.6 / 20)                    # training takes only, pedal-recording scale
    y = S.run(c, x); t = np.asarray(namrun.render(nam, x / S.USB)).ravel()[:len(x)]
    f = np.fft.rfftfreq(N, 1 / FS); r = spec(t) / (spec(y) + 1e-30); r *= np.median(spec(y)) / np.median(spec(t))
    g = np.ones_like(f)
    for i, fc in enumerate(f):                                             # 1/6-octave smoothing of the ratio
        if fc < 40: continue
        k = (f > fc / 2 ** (1 / 12)) & (f < fc * 2 ** (1 / 12)); g[i] = np.sqrt(np.mean(r[k]))
    lo, hi = np.argmin(abs(f - 80)), np.argmin(abs(f - 10500))
    g[:lo] = g[lo]; g[hi:] = g[hi]; g /= np.exp(np.mean(np.log(g[lo:hi])))  # level-neutral
    g = np.clip(g, 10 ** (-9 / 20), 10 ** (9 / 20))
    h = minphase(g)[:256] * np.r_[np.ones(192), np.hanning(128)[64:]]      # short EQ, tapered
    fb = np.convolve(c["fb"], h)[:len(c["fb"])]
    k = np.sqrt(np.sum(c["fb"] ** 2) / np.sum(fb ** 2))                    # keep the level
    out = dict(c); out["fb"] = fb * k
    before = S.compare(y, t)["tone_db"]; after = S.compare(S.run(out, x), t)["tone_db"]
    return out, before, after, 20 * np.log10(g[[np.argmin(abs(f - q)) for q in (2000, 6000, 8000, 10000)]])


def main():
    a, nam, b = sys.argv[1:4]; c = P.parse(open(a, "rb").read()); o, t0, t1, eq = tonematch(c, nam)
    open(b, "wb").write(P.build(o, 512))
    print(f"tone match: tone difference {t0:.2f} -> {t1:.2f} dB (training takes); EQ at 2/6/8/10 kHz {np.round(eq, 1).tolist()} dB")


if __name__ == "__main__":
    main()
