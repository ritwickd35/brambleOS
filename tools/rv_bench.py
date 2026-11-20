#!/usr/bin/env python3
"""rv_bench.py: our reverb voices offline (dsp/rv_host) with the space_bench signal and metrics, against targets."""
import os, sys, subprocess, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import space_bench as B
VOICES = ["Room", "Chamber", "Hall", "Church", "Plate", "Shimmer", "Spring", "Dream", "Ambient"]
# knob layout per voice: (index of Mix, index of Decay, n knobs)
LAYOUT = {0: (0, 1, 4), 1: (0, 1, 5), 2: (0, 1, 4), 3: (0, 1, 4), 4: (0, 1, 4), 5: (0, 1, 5), 6: (0, 1, 4), 7: (0, 1, 6), 8: (0, 2, 6)}
TARGET = {"Room": (0.4, 0.8), "Chamber": (1.0, 1.6), "Hall": (1.8, 2.6), "Church": (3.0, 6.0), "Plate": (1.5, 3.0),
          "Shimmer": (3.0, 6.0), "Spring": (1.5, 3.0), "Dream": (3.0, 6.0), "Ambient": (4.0, 10.0)}   # T30 at default Decay


def run(vi, decay):
    mi, di, nk = LAYOUT[vi]; p = [50.0] * 8; p[mi] = 100.0; p[di] = decay
    if vi == 8: p[1] = 50.0; p[3] = 70.0; p[4] = 40.0; p[5] = 0.0
    else:
        for k in range(2, nk): p[k] = 0.0
        if vi in (1, 5, 7): p[2] = 30.0
        if vi == 7: p[3] = 50.0
    x = B.signal()[B.PRE:]; st = np.stack([x, x], 1).astype("<f4").ravel()
    y = np.frombuffer(subprocess.run([os.path.join(RE, "dsp", "rv_host"), str(vi)] + [str(v) for v in p], input=st.tobytes(), capture_output=True, check=True).stdout, "<f4")
    return y.reshape(-1, 2).astype(float)


if __name__ == "__main__":
    res = {}
    for vi, nm in enumerate(VOICES):
        for lab, dec in (("default", 50.0), ("long", 100.0)):
            r = B.reverb(run(vi, dec)); res[f"{nm} - {lab}"] = r
            t = r["t30"]; lo, hi = TARGET[nm]; ok = "" if lab == "long" else ("  OK" if t[1000] and lo <= t[1000] <= hi else f"  target {lo}-{hi}")
            print(f"{nm:8s} {lab:7s} T30 {t[500]}/{t[1000]}/{t[2000]} dense {r['dense_after_s']} colour {r['colouration_db']} width {r['width']} pre {r['predelay_ms']}{ok}")
    json.dump(res, open(os.path.join(RE, "logs", "rv_bench.json"), "w"), indent=1)
