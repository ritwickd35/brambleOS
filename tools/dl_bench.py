#!/usr/bin/env python3
"""dl_bench.py: our delay voices offline (dsp/dl_host) with the space_bench delay metrics (Mix 100, F.Back 60, Tone mid)."""
import os, sys, subprocess
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import space_bench as B
VOICES = ["Digital", "Slap", "EP-3", "Analog", "Echo"]
TIMES = [500, 120, 500, 500, 350]
def run(vi, mix=100, fb=60, tone=25):
    p = [mix, TIMES[vi], fb, 0, 0, tone, 0, 0]
    x = B.signal()[B.PRE:]; st = np.stack([x, x], 1).astype("<f4").ravel()
    y = np.frombuffer(subprocess.run([os.path.join(RE, "dsp", "dl_host"), str(vi)] + [str(v) for v in p], input=st.tobytes(), capture_output=True, check=True).stdout, "<f4")
    return y.reshape(-1, 2).astype(float)
if __name__ == "__main__":
    for vi, nm in enumerate(VOICES):
        r = B.delay(run(vi)); print(f"{nm:8s} reps {r.get('repeats')} spacing {r.get('spacing_ms')} decay/rep {r.get('decay_per_repeat_db')} hf/rep {r.get('hf_loss_per_repeat_db')} wobble {r.get('wobble_cents') and round(r['wobble_cents'])}c dist {r.get('repeat_distortion_db')} LR {r.get('lr_balance_db')}")
