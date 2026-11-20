#!/usr/bin/env python3
"""Cab IR optimiser for the Pocket Master's 512-tap user IR slots (11.6 ms at 44.1 kHz).
Third-party IRs are usually 100-500 ms long and start with a pre-delay; the pedal (and the Sonicake app) simply
cut them to 512 samples, which throws away low-frequency energy and any late low-end build-up.
This tool: resamples to 44.1 kHz, removes pre-delay, converts to minimum phase (cepstral method: same magnitude
response, energy packed at the start), truncates to 512 taps with a short half-Hann fade, then optionally
re-applies a low-order correction so the 512-tap magnitude matches the original below 300 Hz.

  cabir.py <in.wav> <out.wav>          writes a 512-sample mono 44.1 kHz float WAV and prints the error report
  cabir.py demo                        synthetic 300 ms cab IR: plain cut vs optimised"""
import sys, wave
import numpy as np
FS = 44100; N = 512


def read_wav(p):
    with wave.open(p) as w:
        sr, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes(); raw = w.readframes(n)
    if sw == 2: x = np.frombuffer(raw, "<i2") / 32768.0
    elif sw == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3); x = ((b[:, 0].astype(np.int32) | b[:, 1].astype(np.int32) << 8 | b[:, 2].astype(np.int32) << 16) << 8 >> 8) / 8388608.0
    elif sw == 4: x = np.frombuffer(raw, "<i4") / 2147483648.0
    else: raise ValueError("unsupported sample width")
    return x.reshape(-1, ch)[:, 0].astype(np.float64), sr


def write_wav(p, x):
    q = np.clip(x / (np.max(np.abs(x)) + 1e-12) * 0.9, -1, 1)
    with wave.open(p, "wb") as w:
        w.setnchannels(1); w.setsampwidth(3); w.setframerate(FS)
        i = (q * 8388607).astype(np.int32); b = np.stack([i & 255, i >> 8 & 255, i >> 16 & 255], 1).astype(np.uint8)
        w.writeframes(b.tobytes())


def resample(x, sr):
    if sr == FS: return x
    n = int(round(len(x) * FS / sr)); X = np.fft.rfft(x); m = n // 2 + 1
    Y = np.zeros(m, complex); k = min(m, len(X)); Y[:k] = X[:k]
    return np.fft.irfft(Y, n) * (n / len(x))


def min_phase(h, nfft=1 << 16):
    H = np.abs(np.fft.fft(h, nfft)); H = np.maximum(H, 1e-6 * H.max())
    c = np.fft.ifft(np.log(H)).real
    w = np.zeros(nfft); w[0] = 1; w[1:nfft // 2] = 2; w[nfft // 2] = 1
    return np.fft.ifft(np.exp(np.fft.fft(c * w))).real[:len(h)]


def truncate(h):
    y = h[:N].copy(); f = 48; y[-f:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, f))); return y


def bands_db(h, ref=None):
    """Energy in 1/3-octave bands (what the ear hears), not fine detail."""
    nf = 1 << 15; H = np.abs(np.fft.rfft(h, nf)) ** 2; f = np.fft.rfftfreq(nf, 1 / FS)
    out = {}
    for c in (40, 63, 80, 100, 125, 160, 200, 250, 400, 1000, 2500, 5000):
        m = (f > c / 1.12) & (f < c * 1.12); out[c] = 10 * np.log10(np.mean(H[m]) + 1e-20)
    return out


def smooth_minphase(h, frac=6, nfft=1 << 16):
    """Fractional-octave smoothed magnitude (fine detail a 512-tap filter cannot hold anyway), then minimum
    phase, then an iterative correction of the truncated filter's low end (3 passes)."""
    H = np.abs(np.fft.rfft(h, nfft)); f = np.fft.rfftfreq(nfft, 1 / FS); P = H ** 2
    cs = np.concatenate([[0], np.cumsum(P)]); S = np.empty_like(H)
    k = np.arange(len(H)); lo = np.clip((k / 2 ** (0.5 / frac)).astype(int), 0, len(H) - 1)
    hi = np.clip((k * 2 ** (0.5 / frac)).astype(int) + 1, 1, len(H))
    S = np.sqrt((cs[hi] - cs[lo]) / np.maximum(hi - lo, 1))
    target = np.maximum(S, 1e-6 * S.max()); G = target.copy()
    for _ in range(4):
        full = np.concatenate([G, G[-2:0:-1]])
        c = np.fft.ifft(np.log(full)).real; w = np.zeros(nfft); w[0] = 1; w[1:nfft // 2] = 2; w[nfft // 2] = 1
        y = truncate(np.fft.ifft(np.exp(np.fft.fft(c * w))).real[:4 * N])
        Y = np.abs(np.fft.rfft(y, nfft)) + 1e-9
        corr = target / Y; corr[f > 400] = 1.0                       # correct the low end only
        G = G * np.clip(corr, 0.5, 2.0) ** 0.7
    return y


def ls_fit(h, frac=6, nfft=1 << 16):
    """Least-squares 512-tap FIR on a log-frequency grid (equal weight per octave, 30 Hz - 16 kHz) against the
    minimum-phase version of the fractional-octave smoothed response."""
    H = np.abs(np.fft.rfft(h, nfft)); P = H ** 2; k = np.arange(len(H))
    cs = np.concatenate([[0], np.cumsum(P)])
    lo = np.clip((k / 2 ** (0.5 / frac)).astype(int), 0, len(H) - 1); hi = np.clip((k * 2 ** (0.5 / frac)).astype(int) + 1, 1, len(H))
    S = np.maximum(np.sqrt((cs[hi] - cs[lo]) / np.maximum(hi - lo, 1)), 1e-6 * H.max())
    full = np.concatenate([S, S[-2:0:-1]]); c = np.fft.ifft(np.log(full)).real
    w = np.zeros(nfft); w[0] = 1; w[1:nfft // 2] = 2; w[nfft // 2] = 1
    D = np.fft.fft(c * w); D = np.exp(D[:len(H)])
    f = np.fft.rfftfreq(nfft, 1 / FS)
    fk = np.geomspace(30, 16000, 1500); idx = np.searchsorted(f, fk)
    E = np.exp(-2j * np.pi * np.outer(fk / FS, np.arange(N)))
    wt = 1 / np.abs(D[idx])                                         # relative (log-like) error
    A = np.vstack([(E * wt[:, None]).real, (E * wt[:, None]).imag]); b = np.concatenate([(D[idx] * wt).real, (D[idx] * wt).imag])
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    return sol


def optimise(h):
    h = h[np.argmax(np.abs(h) > 0.05 * np.max(np.abs(h))):]          # drop pre-delay
    return truncate(h), ls_fit(h), h


def report(full, plain, mp):
    a, b, c = bands_db(full), bands_db(plain), bands_db(mp)
    k = 1000; na, nb, nc = a[k], b[k], c[k]
    print(" band Hz   plain-cut error dB   optimised error dB   (vs the full IR, level-matched at 1 kHz)")
    for f in a:
        print(f" {f:6d}   {b[f] - nb - (a[f] - na):+8.1f}            {c[f] - nc - (a[f] - na):+8.1f}")
    lo = [f for f in a if f <= 200]
    eb = np.sqrt(np.mean([(b[f] - nb - (a[f] - na)) ** 2 for f in lo])); ec = np.sqrt(np.mean([(c[f] - nc - (a[f] - na)) ** 2 for f in lo]))
    print(f" RMS error 40-200 Hz: plain cut {eb:.1f} dB, optimised {ec:.1f} dB")
    al = list(a)
    eb2 = np.sqrt(np.mean([(b[f] - nb - (a[f] - na)) ** 2 for f in al])); ec2 = np.sqrt(np.mean([(c[f] - nc - (a[f] - na)) ** 2 for f in al]))
    print(f" RMS error 40-5000 Hz: plain cut {eb2:.1f} dB, optimised {ec2:.1f} dB")


def demo_ir():
    """Synthetic 4x12 close-mic IR: speaker resonance ~95 Hz (long ring), cone peaks 1.8/3.2 kHz, roll-off 5 kHz,
    a 1.5 ms pre-delay and late room reflections."""
    rng = np.random.default_rng(1); n = int(0.3 * FS); t = np.arange(n) / FS
    h = np.zeros(n); d = int(0.0015 * FS)
    for f0, q, g in ((95, 8.0, 1.0), (1800, 4, 0.5), (3200, 5, 0.35), (650, 2, 0.4)):
        h[d:] += g * np.exp(-np.pi * f0 / q * t[:n - d]) * np.sin(2 * np.pi * f0 * t[:n - d])
    for dt, g in ((0.006, 0.3), (0.011, 0.2), (0.019, 0.12)):
        k = d + int(dt * FS); h[k:] += g * h[d:n - k + d] * 0.5
    h += 0.002 * rng.standard_normal(n) * np.exp(-t / 0.05)
    lp = np.exp(-2 * np.pi * 5000 / FS); y = np.zeros(n); s = 0
    for i in range(n): s = (1 - lp) * h[i] + lp * s; y[i] = s
    return y


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["demo"]:
        plain, mp, full = optimise(demo_ir()); report(full, plain, mp)
    elif len(a) == 2:
        x, sr = read_wav(a[0]); plain, mp, full = optimise(resample(x, sr)); report(full, plain, mp); write_wav(a[1], mp)
        print("wrote", a[1])
    else:
        sys.exit(__doc__)
