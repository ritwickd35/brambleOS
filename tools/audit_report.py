#!/usr/bin/env python3
"""Re-analyse the audit recordings (audio/audit/*.wav) with noise-corrected harshness; print a table."""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import audit as A, pmloadtest as L
FS = A.FS


def psd(s):
    w = np.hanning(len(s)); X = np.abs(np.fft.rfft(s * w)) ** 2 / np.sum(w ** 2); f = np.fft.rfftfreq(len(s), 1 / FS); return f, X


def harsh(y, t0, i, f0, noise):
    s = A.piece(y, t0, A.T_TONE + i + 0.15, A.T_TONE + i + 0.85); f, X = psd(s)
    fn, N = psd(noise[:len(s)]); N = np.interp(f, fn, N)
    band = (f > f0 * 0.98) & (f < f0 * 1.02); f0 = f[band][np.argmax(X[band])]
    harm = np.zeros_like(f, bool)
    for k in range(1, int(20000 / f0) + 1): harm |= np.abs(f - k * f0) < 250
    use = (f > 60) & (f < 16000)
    h = X[harm & use].sum(); o = max(X[~harm & use].sum() - N[~harm & use].sum(), 1e-3 * X[~harm & use].sum())
    return 10 * np.log10(o / h)


def one(path):
    y = L.load(path); t0 = A.sync(y); noise = A.piece(y, t0, 0.3, 1.15)
    hs = [harsh(y, t0, i, f, noise) for i, f in enumerate(A.TONES)]
    r = A.analyse(path)
    knee = next((s["in_db"] for s in r["ramp"] if s["thd"] > 10), None)
    outs = [s["out_db"] for s in r["ramp"]]
    return dict(harsh=[round(h, 1) for h in hs], noise=r["noise_dbfs"], knee=knee, thd=[s["thd"] for s in r["ramp"]],
                out=outs, tone=r["tone"])


if __name__ == "__main__":
    rows = []
    for f in sorted(os.listdir(A.OUT)):
        if not f.endswith(".wav") or f.startswith("00") or f.startswith("_"): continue
        try: d = one(os.path.join(A.OUT, f))
        except Exception as e: print(f, "error", e); continue
        d["file"] = f; rows.append(d)
        t = d["tone"]["peak_hz"] if d["tone"] else "-"
        b = d["tone"]["bands"] if d["tone"] else {}
        print(f"{f[:44]:44s} harsh 2.5k/4k/6k/8k {str(d['harsh']):28s} noise {d['noise']:6.1f}  THD>10% from {str(d['knee']):>4s} dB  "
              f"THD {d['thd'][0]:.0f}->{d['thd'][-1]:.0f}%  out {d['out'][0]:.0f}->{d['out'][-1]:.0f} dB  peak {t} Hz  "
              f"bands {[b.get(k) for k in (125, 250, 500, 2000, 4000, 8000)]}")
    json.dump(rows, open(os.path.join(os.path.dirname(HERE), "cut1", f"audit-report{A.TAG}.json"), "w"), indent=1)
