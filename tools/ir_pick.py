#!/usr/bin/env python3
"""Pick and shorten cab IRs (downloaded to irs/<cab>/), compare with the stock-style cut.
  ir_pick.py            per cab: pick the most typical SM57 IR (+ a second mic for blending), build
                        stock-style (plain cut) and improved (minimum phase + fitted, same length) short IRs,
                        report the tone error vs the full IR, write irs/out/<cab>_*.f32 and listen clips.
Short length N = 416 samples at 44.1 kHz (what the stock cab block holds)."""
import glob, json, os, sys
import numpy as np, soundfile as sf
from scipy.signal import resample_poly
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
FS, N = 44100, int(os.environ.get("IR_N", 512))
OUT = os.path.join(RE, "irs", "out")
C = np.geomspace(60, 12000, 48)                      # 1/7-octave analysis bands


def load(p):
    x, fs = sf.read(p, always_2d=True); x = x[:, 0].astype(float)
    if fs != FS: g = np.gcd(int(fs), FS); x = resample_poly(x, FS // g, int(fs) // g)
    k = int(np.argmax(np.abs(x) > 0.05 * np.max(np.abs(x)))); x = x[max(k - 8, 0):]
    return x[:FS] / (np.sqrt(np.sum(x[:FS] ** 2)) + 1e-12)


def bands(h, nfft=1 << 16):
    H = np.abs(np.fft.rfft(h, nfft)) ** 2; f = np.fft.rfftfreq(nfft, 1 / FS)
    return np.array([10 * np.log10(H[(f > c / 1.05) & (f < c * 1.05)].mean() + 1e-20) for c in C])


def minphase(h, nfft=1 << 16, mag=None):
    """homomorphic minimum-phase signal with the magnitude of h (or the given full-length |H|)"""
    H = np.abs(np.fft.fft(h, nfft)) if mag is None else mag; c = np.fft.ifft(np.log(np.maximum(H, 1e-8))).real
    w = np.zeros(nfft); w[0] = 1; w[1:nfft // 2] = 2; w[nfft // 2] = 1
    return np.fft.ifft(np.exp(np.fft.fft(c * w))).real[:len(h) if h is not None else nfft]


def fit_short(h, n=N, iters=6):
    """n-tap FIR whose 1/7-octave magnitude matches the full IR: minimum phase, half-Hann end window, then
    iterative band-gain correction (keeps the lows that a plain cut loses)."""
    target = bands(h); m = minphase(h); w = np.r_[np.ones(n - 64), np.hanning(128)[64:]]; s = m[:n] * w
    f = np.fft.rfftfreq(1 << 16, 1 / FS)
    for _ in range(iters):
        err = target - bands(s)                                         # dB per band
        g = 10 ** (np.interp(np.log(np.maximum(f, 1)), np.log(C), err) / 20)
        M = np.abs(np.fft.rfft(s, 1 << 16)) * g; Mf = np.r_[M, M[-2:0:-1]]                  # full symmetric |H|
        s = minphase(None, 1 << 16, Mf)[:n] * w
    return s


def best_short(h):
    """plain cut, or the fitted minimum-phase version, whichever matches the full IR better"""
    a, b = h[:N] * np.r_[np.ones(N - 64), np.hanning(128)[64:]], fit_short(h)
    return (b, "fitted") if sum(err_db(b, h)) < sum(err_db(a, h)) else (a, "windowed cut")


def err_db(s, h):
    d = bands(s) - bands(h); d -= np.mean(d); lo = C < 250
    return round(float(np.mean(np.abs(d))), 2), round(float(np.mean(np.abs(d[lo]))), 2)


def typical(files):
    B = np.array([bands(load(p)) for p in files]); B -= B.mean(1, keepdims=True)
    return files[int(np.argmin(np.abs(B - np.median(B, 0)).mean(1)))]


def main():
    os.makedirs(OUT, exist_ok=True); rep = {}
    for d in sorted(glob.glob(os.path.join(RE, "irs", "*/"))):
        cab = os.path.basename(d.rstrip("/"))
        if cab == "out": continue
        fs_ = sorted(glob.glob(d + "*.wav"))
        if not fs_: continue
        s57 = [p for p in fs_ if "57" in os.path.basename(p)] or fs_
        main_ir = typical(s57); other = [p for p in fs_ if p not in s57] or [p for p in fs_ if p != main_ir]
        h = load(main_ir); cut = h[:N]; imp, how = best_short(h)
        rep[cab] = dict(file=os.path.basename(main_ir), second=os.path.basename(typical(other)) if other else None,
                        plain_cut_err_db=err_db(cut, h), improved_err_db=err_db(imp, h), method=how)
        for nm, v in (("full", h), ("cut", cut), ("improved", imp)): v.astype("<f4").tofile(os.path.join(OUT, f"{cab}_{nm}.f32"))
        print(cab, rep[cab], flush=True)
    json.dump(rep, open(os.path.join(OUT, "pick.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
