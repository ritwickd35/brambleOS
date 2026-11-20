#!/usr/bin/env python3
"""Detailed reverb / delay benchmark on the pedal.
  space_bench.py record <db.bin> <tag>    every RVB/DLY effect at 2 settings (default; long = Decay max / F.Back 60 %),
                                          Mix at 100 where the knob exists (wet as clean as possible)
  space_bench.py report <tag>             metrics -> logs/space_bench-<tag>.json + table
Signal: 0.0 click | 4.5 s silence | 4.5 1 kHz burst 0.25 s -12 dBFS | 4.5 s silence | 9.5 noise burst 0.25 s | 4.5 s.
Reverb metrics (click): T30 per octave (125..4k, Schroeder), EDT, echo density (time to normalised density 1,
Abel & Huang), colouration (late-tail spectral peak prominence, dB), width (1 - L/R correlation of the tail), pre-delay.
Delay metrics: repeat time, decay per repeat, HF loss per repeat (4k vs 500 Hz), pitch wobble of the burst repeats
(cents p-p), repeat distortion (non-1 kHz energy in the 1st repeat, dB), stereo pattern (L/R energy of repeats)."""
import json, os, sys, time, wave
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
FS = 44100; T_BURST, T_NOISE, DUR = 4.5, 9.5, 14.5


def signal():
    n = int(DUR * FS); x = np.zeros(n); x[int(0.02 * FS)] = 0.5
    t = np.arange(int(0.25 * FS)) / FS; w = np.hanning(len(t)) ** 0.3
    x[int(T_BURST * FS):int(T_BURST * FS) + len(t)] = 0.25 * np.sin(2 * np.pi * 1000 * t) * w
    x[int(T_NOISE * FS):int(T_NOISE * FS) + len(t)] = 0.1 * np.random.default_rng(3).standard_normal(len(t)) * w
    return np.r_[np.zeros(FS // 2), 0.3 * np.sin(2 * np.pi * 1000 * np.arange(int(0.05 * FS)) / FS), np.zeros(FS // 2), x].astype(np.float32)


PRE = FS // 2 + int(0.05 * FS) + FS // 2           # samples before t = 0 of the test part


def align(y):
    """sync on the leading 1 kHz marker (first loud 5 ms window)"""
    e = np.convolve(np.abs(y[:, 0]), np.ones(220) / 220, "same"); i = int(np.argmax(e > 0.3 * e[:3 * FS].max()))
    return y[i + int(0.05 * FS) + FS // 2:]


def octave(x, fc):
    X = np.fft.rfft(x, 1 << 18); f = np.fft.rfftfreq(1 << 18, 1 / FS); X[(f < fc / 1.414) | (f > fc * 1.414)] = 0
    return np.fft.irfft(X, 1 << 18)[:len(x)]


def schroeder_t30(h):
    nf = np.mean(h[-int(0.3 * FS):] ** 2)                         # noise floor from the window end (Lundeby-style)
    env = np.convolve(h ** 2, np.ones(441) / 441, "same"); cut = int(np.argmax(env < 3 * nf)) if np.any(env < 3 * nf) else len(h)
    hh = h[:max(cut, 2000)] ** 2 - nf; hh = np.maximum(hh, 0)
    e = np.cumsum(hh[::-1])[::-1]; d = 10 * np.log10(e / (e[0] + 1e-30) + 1e-30)
    i5, i35 = np.argmax(d < -5), np.argmax(d < -35)
    if i35 <= i5: return None
    return round(float(60 * (i35 - i5) / FS / 30), 2)


def reverb(y):
    h = y[int(0.02 * FS) - 50:int(0.02 * FS) + int(4.3 * FS)]; m = h.mean(1)
    pk = int(np.argmax(np.abs(m[:2000])))
    t30 = {fc: schroeder_t30(octave(m, fc)) for fc in (125, 250, 500, 1000, 2000, 4000)}
    e = np.cumsum(m[::-1] ** 2)[::-1]; d = 10 * np.log10(e / e[0] + 1e-30); edt = round(float(6 * np.argmax(d < -10) / FS), 2)
    w = int(0.02 * FS); ned = []; nf = np.mean(m[-int(0.3 * FS):] ** 2)  # Abel & Huang normalised echo density
    for i in range(pk + 64, min(len(m), pk + int(0.4 * FS)) - w, w // 4):
        s = m[i:i + w]
        if np.mean(s ** 2) < 30 * nf: break                         # only where the tail is well above the noise
        sd = np.std(s) + 1e-12; ned.append(np.mean(np.abs(s) > sd) / 0.3173)
    ned = np.array(ned); t_dense = float(np.argmax(ned > 0.9) * (w // 4) / FS) if np.any(ned > 0.9) else None
    late = m[int(0.15 * FS):int(0.65 * FS)]; X = 10 * np.log10(np.abs(np.fft.rfft(late * np.hanning(len(late)))) ** 2 + 1e-20)
    f = np.fft.rfftfreq(len(late), 1 / FS); band = (f > 200) & (f < 5000); xb = X[band]
    smooth = np.convolve(xb, np.ones(201) / 201, "same"); colour = round(float(np.percentile(xb - smooth, 99.5)), 1)
    tail = h[int(0.05 * FS):int(1.0 * FS)]; width = round(1 - float(np.corrcoef(tail[:, 0], tail[:, 1])[0, 1]), 2) if np.std(tail[:, 1]) > 1e-7 else 0.0
    onset = int(np.argmax(np.abs(m[pk + 20:]) > 0.05 * np.abs(m).max())) + 20
    return dict(t30=t30, edt=edt, dense_after_s=None if t_dense is None else round(t_dense, 3), colouration_db=colour, width=width,
                predelay_ms=round(onset / FS * 1000, 1), level_db=round(float(10 * np.log10(np.sum(m ** 2) + 1e-20)), 1))


def delay(y):
    m = y[:, 0] + y[:, 1]; i0 = int((T_BURST - 0.02) * FS); s = m[i0:i0 + int(4.4 * FS)]
    env = np.convolve(s ** 2, np.ones(441) / 441, "same"); thr = 0.02 * env.max(); reps = []; i = 0; on = False
    for k, v in enumerate(env):
        if v > thr and not on: on = True; st = k
        if v < thr * 0.5 and on: on = False; reps.append((st, k))
    if len(reps) < 2: return dict(repeats=len(reps))
    r = [s[a:b] for a, b in reps[:6]]; lv = [10 * np.log10(np.sum(x ** 2) + 1e-20) for x in r]
    spacing = round(float(np.median(np.diff([a for a, _ in reps[:6]])) / FS * 1000), 1)
    def hf(x):
        X = np.abs(np.fft.rfft(x, 16384)) ** 2; f = np.fft.rfftfreq(16384, 1 / FS)
        return 10 * np.log10(X[(f > 3000) & (f < 5000)].sum() / (X[(f > 400) & (f < 600)].sum() + 1e-20) + 1e-20)
    def pitch(x):                                                  # period-by-period frequency from zero crossings
        c = x[len(x) // 5:-len(x) // 5]; z = np.where((c[:-1] < 0) & (c[1:] >= 0))[0]
        if len(z) < 20: return None
        zf = z + c[z] / (c[z] - c[z + 1]); per = np.diff(zf[::8]) / 8; f = FS / per
        return float(1200 * np.log2(np.percentile(f, 95) / np.percentile(f, 5)))
    def dist(x):
        x = x[len(x) // 5:-len(x) // 5]; n = len(x); k_ = np.arange(n) / n
        win = 0.35875 - 0.48829 * np.cos(2 * np.pi * k_) + 0.14128 * np.cos(4 * np.pi * k_) - 0.01168 * np.cos(6 * np.pi * k_)
        X = np.abs(np.fft.rfft(x * win, 16384)) ** 2; f = np.fft.rfftfreq(16384, 1 / FS); k = (f > 950) & (f < 1050)
        return 10 * np.log10((X.sum() - X[k].sum()) / (X[k].sum() + 1e-20) + 1e-20)
    L = y[i0:i0 + int(4.4 * FS), 0]; R = y[i0:i0 + int(4.4 * FS), 1]
    lr = [round(float(10 * np.log10((np.sum(L[a:b] ** 2) + 1e-20) / (np.sum(R[a:b] ** 2) + 1e-20))), 1) for a, b in reps[1:5]]
    return dict(repeats=len(reps), spacing_ms=spacing, decay_per_repeat_db=round(float(np.median(np.diff(lv[1:]))), 1) if len(lv) > 2 else None,
                hf_loss_per_repeat_db=round(float(np.median(np.diff([hf(x) for x in r[1:]]))), 1) if len(r) > 2 else None,
                wobble_cents=None if len(r) < 2 or pitch(r[1]) is None else round(pitch(r[1]), 1), repeat_distortion_db=round(float(dist(r[1])), 1),
                lr_balance_db=lr)


def record(db, tag):
    import sounddevice as sd, pmaudio, dbrec
    from pmflash import Link
    from cut1_variants import read_p
    from cut1_matrix import send, set_mod
    out = os.path.join(RE, "audio", f"bench-{tag}"); os.makedirs(out, exist_ok=True)
    x = signal(); play = np.stack([x, x], 1); dev = pmaudio.out_device("External Headphones")
    l = Link(); orig = read_p(l); l.close(); base = orig
    for k in range(10): base = set_mod(base, k, on=False)
    try:
        only = os.environ.get("BENCH_ONLY")
        for g, i, fx, title, kn in [r for r in dbrec.records(db) if r[0] in (7, 8) and (not only or f"{r[0]}:{r[1]}" in only.split(","))]:
            for setting in ("default", "long"):
                p = [0.0] * 8
                for _j, (nm, df, mx, j, *_r) in enumerate(kn[:8]):
                    if j > 7: continue
                    p[j] = 100.0 if nm == "Mix" else (mx if nm == "Decay" else 0.6 * mx if nm == "F.Back" else df) if setting == "long" else df
                    if nm == "Mix" and setting == "default": p[j] = 100.0
                send(set_mod(base, g, fx, p, True)); time.sleep(2.0)
                path = os.path.join(out, f"{'DLY' if g == 7 else 'RVB'} {title} - {setting}.wav")
                pr = pmaudio.record(path, len(x) / FS + 1.5); time.sleep(0.5); sd.play(play, samplerate=FS, device=dev); pr.wait(); sd.stop()
                print(time.strftime("%H:%M:%S"), title, setting, flush=True)
    finally:
        send(orig); time.sleep(0.5); l = Link(); back = read_p(l); l.close(); print("P08 restored:", back[4:] == orig[4:], flush=True)


def report(tag):
    import glob
    res = {}
    for p in sorted(glob.glob(os.path.join(RE, "audio", f"bench-{tag}", "*.wav"))):
        w = wave.open(p); y = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2).astype(float) / 32768; y = align(y)
        nm = os.path.basename(p)[:-4]
        try: res[nm] = reverb(y) if nm.startswith("RVB") else delay(y)
        except Exception as e: res[nm] = dict(error=str(e)[:60])
    json.dump(res, open(os.path.join(RE, "logs", f"space_bench-{tag}.json"), "w"), indent=1)
    for k, v in res.items(): print(f"{k:32s} {v}")


if __name__ == "__main__":
    if sys.argv[1] == "record": record(sys.argv[2], sys.argv[3])
    else: report(sys.argv[2])
