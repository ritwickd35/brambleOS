#!/usr/bin/env python3
"""Decode a cut-8 engine probe recording.  eprobe_decode.py <wav|f32> [out.json]
Symbols: one block per nibble, amplitude 0.03+0.02*v, carrier alternating 4/8 cycles per 64 samples; frames are
separated by >= 2 silent blocks. First 4 frames calibrate the levels per carrier."""
import json, os, struct, sys, wave
import numpy as np
RE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path):
    if path.endswith(".f32"): return np.fromfile(path, "<f4")
    w = wave.open(path); x = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, w.getnchannels())
    return x[:, 0].astype(np.float32) / 32768.0


def envelopes(x):
    n = np.arange(len(x)); k = np.ones(16) / 16
    out = []
    for cyc in (4, 8):
        z = x * np.exp(-2j * np.pi * cyc * n / 64)
        out.append(2 * np.abs(np.convolve(z, k, "same")))
    return out


def segments(x):
    a1, a2 = envelopes(x); a = np.maximum(a1, a2); on = a > 0.045 * np.percentile(a, 99.9)   # 0.5 x lowest level
    car = np.where(a2 > a1, 1, 0)
    # frames: runs of 'on' separated by >= 96 samples off
    frames, i, N = [], 0, len(x)
    idx = np.flatnonzero(on)
    if not len(idx): return []
    gaps = np.flatnonzero(np.diff(idx) > 96)
    starts = np.r_[idx[0], idx[gaps + 1]]; ends = np.r_[idx[gaps], idx[-1]]
    for s, e in zip(starts, ends):
        c = car[s:e + 1]; ch = np.flatnonzero(np.diff(c) != 0) + 1
        bounds = np.r_[0, ch, len(c)]; syms = []
        for b0, b1 in zip(bounds[:-1], bounds[1:]):
            L = b1 - b0
            if L < 24: continue                       # transition glitch
            nsym = max(1, int(round(L / 64.0)))       # same carrier twice cannot happen; guard anyway
            mid = s + b0 + L // 4, s + b0 + 3 * L // 4
            amp = float(np.median((a2 if c[b0] else a1)[mid[0]:mid[1]]))
            syms += [(int(c[b0]), amp)] * nsym
        frames.append(syms)
    return frames


def decode(path):
    fr = segments(load(path))
    while fr and not (len(fr[0]) == 16 and all(b[1] > a[1] for a, b in zip(fr[0], fr[0][1:]))): fr = fr[1:]   # skip pre-start audio
    cal = fr[:4]; lev = {0: [], 1: []}
    tab = {0: np.zeros(16), 1: np.zeros(16)}; cnt = {0: np.zeros(16), 1: np.zeros(16)}
    for k, f in enumerate(cal):
        vals = ([0] if k & 1 else []) + list(range(16))
        for (c, a), v in zip(f, vals): tab[c][v] += a; cnt[c][v] += 1
    for c in (0, 1): tab[c] = tab[c] / np.maximum(cnt[c], 1)
    def nib(c, a): return int(np.argmin(np.abs(tab[c] - a)))
    runs, bad = {}, 0
    for f in fr[4:]:
        v = [nib(c, a) for c, a in f]
        if len(v) < 17: bad += 1; continue
        hexs = lambda i, n: int("".join(f"{x:x}" for x in v[i:i + n]) or "0", 16)
        run = hexs(0, 3); mc = hexs(3, 8); ms = hexs(11, 4); p = 15; vals = {}
        for b in range(32):
            if b != 15 and mc >> b & 1: vals[b] = hexs(p, 8); p += 8
        if len(v) != p + 2 or (sum(v[:p]) & 0xFF) != hexs(p, 2): bad += 1; continue
        runs[run] = dict(mc=mc, ms=ms, vals=vals)
    return runs, bad, len(fr), tab


if __name__ == "__main__":
    runs, bad, nf, tab = decode(sys.argv[1])
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(RE, "logs", "eprobe_runs.json")
    json.dump(dict(runs={str(k): v for k, v in runs.items()}, bad=bad, frames=nf,
                   levels={str(c): list(map(float, tab[c])) for c in tab}), open(out, "w"))
    print(f"frames {nf} decoded {len(runs)} bad {bad}")
