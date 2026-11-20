#!/usr/bin/env python3
"""Decode a cut-8c bench recording: per bench average and max engine counter. ebench_decode.py <wav|f32> [out.json]"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import eprobe_decode as D


def decode(path):
    fr = D.segments(D.load(path))
    while fr and not (len(fr[0]) == 16 and all(b[1] > a[1] for a, b in zip(fr[0], fr[0][1:]))): fr = fr[1:]
    tab = {0: np.zeros(16), 1: np.zeros(16)}; cnt = {0: np.zeros(16), 1: np.zeros(16)}
    for k, f in enumerate(fr[:4]):
        for (c, a), v in zip(f, ([0] if k & 1 else []) + list(range(16))): tab[c][v] += a; cnt[c][v] += 1
    for c in (0, 1): tab[c] = tab[c] / np.maximum(cnt[c], 1)
    res = {}
    for f in fr[4:]:
        v = [int(np.argmin(np.abs(tab[c] - a))) for c, a in f]
        if len(v) != 21: continue
        h = lambda i, n: int("".join(f"{x:x}" for x in v[i:i + n]), 16)
        if sum(v[:19]) & 0xFF != h(19, 2): continue
        res[h(0, 3)] = (h(3, 8), h(11, 8))
    return res


if __name__ == "__main__":
    res = decode(sys.argv[1]); names = json.load(open(os.path.join(RE, "logs", "ebench_plan.json")))
    base = res.get(0, (0, 0))[0]
    out = {names[k]: dict(avg=a, max=m, minus_empty=a - base) for k, (a, m) in sorted(res.items()) if k < len(names)}
    json.dump(out, open(sys.argv[2] if len(sys.argv) > 2 else os.path.join(RE, "logs", "ebench.json"), "w"), indent=1)
    print(f"benches decoded {len(out)} of {len(names)}")
