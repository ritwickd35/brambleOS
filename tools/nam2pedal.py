#!/usr/bin/env python3
"""NAM capture -> pedal conversion: fit our amp model (dsp/amp.c, runs on the pedal's audio engine) plus a
512-tap cabinet IR (runs in the pedal's cab block) to a NAM (A1/A2) capture. Runs on the Mac (CPU/MPS).
  nam2pedal.py fit <file.nam> <name> [steps] [--amp-only]   -> amps/nam_<name>.fit.json, irs/out/nam_<name>_cab.f32
  nam2pedal.py eval <name>                                     scores on held-out guitar audio
The capture is rendered with tools/namref.py (our NAM WaveNet runtime) on 70 s of real guitar DI plus level ramps.
Scores: ESR (0 = identical waveform), tone difference per 1/3 octave (dB), gain-curve difference (dB)."""
import os, sys, json, math, hashlib
import numpy as np
import torch
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import ampfit as F, ampmodel as AM
FS = 44100.0
torch.set_num_threads(int(os.environ.get("NAM_THREADS", "4")))


def render(path):
    """(x, y) arrays: DI (70 s) + 220 Hz level ramp + noise at three levels, all through the NAM capture (cached)."""
    key = hashlib.sha1(open(path, "rb").read()).hexdigest()[:10]; cx = os.path.join(RE, "audio", f"nam_{key}_x.f32"); cy = cx.replace("_x.", "_y.")
    if os.path.exists(cy): return np.fromfile(cx, "<f4").astype(np.float64), np.fromfile(cy, "<f4").astype(np.float64)
    import namrun
    di = np.fromfile(os.path.join(RE, "audio", "di_reference_44100.f32"), "<f4").astype(np.float64)
    t = np.arange(int(0.75 * FS)) / FS; ramp = np.concatenate([10 ** (L / 20) * np.sin(2 * np.pi * 220 * t) for L in range(-48, 1, 6)])
    rng = np.random.default_rng(5); nz = np.concatenate([10 ** (L / 20) * rng.standard_normal(int(2 * FS)) for L in (-40, -25, -12)])
    x = np.concatenate([di, np.zeros(int(0.5 * FS)), ramp, np.zeros(int(0.5 * FS)), nz]); y = namrun.render(path, x, FS)
    x.astype("<f4").tofile(cx); y.astype("<f4").tofile(cy); return x, y


class Conv(torch.nn.Module):
    def __init__(self, s0, cab, amp_only):
        super().__init__(); self.amp = F.Model(s0); self.amp_only = amp_only
        self.w = torch.nn.Parameter(torch.tensor(cab, dtype=torch.float64)) if not amp_only else None
    def forward(self, x):
        y = self.amp(x, [50, 50, 50, 50, 50, 50, 0])
        if self.amp_only: return y
        n = y.shape[-1] + 512; nf = 1 << (n - 1).bit_length()
        return torch.fft.irfft(torch.fft.rfft(y, nf) * torch.fft.rfft(self.w, nf), nf)[..., :y.shape[-1]]


def bands(y):
    f = np.fft.rfftfreq(8192, 1 / FS); C = np.geomspace(80, 10000, 20); X = 0
    for i in range(0, len(y) - 8192, 4096): X = X + np.abs(np.fft.rfft(y[i:i + 8192] * np.hanning(8192))) ** 2
    return np.array([10 * np.log10(X[(f > c / 1.12) & (f < c * 1.12)].mean() + 1e-20) for c in C])


def scores(yh, t):
    e = float(np.sum((yh - t) ** 2) / np.sum(t ** 2)); d = bands(yh) - bands(t); d -= d.mean()
    return dict(esr=round(e, 3), tone_db=round(float(np.mean(np.abs(d))), 2))


def shift(y, lag):                                                   # lag > 0: delay, lag < 0: advance
    return np.r_[np.zeros(lag), y[:len(y) - lag]] if lag >= 0 else np.r_[y[-lag:], np.zeros(-lag)]


def align(y0, t):
    best = None
    for L_ in range(-64, 96):
        tt = shift(t, L_)
        for sg in (1.0, -1.0):
            e_ = float(np.sum((y0 - sg * tt) ** 2) / np.sum(tt ** 2 + 1e-30))
            if best is None or e_ < best[0]: best = (e_, L_, sg)
    return best[1], best[2]


def fit(path, name, steps, amp_only):
    x, y = render(path); n_di = int(70 * FS); split = int(52 * FS)
    g = float(np.std(y[:split]) / np.std(x[:split]))
    s0 = AM.load("recto"); s0["os"] = 2.0; s0["out"] = s0["out"] * 1.0
    cab = np.fromfile(os.path.join(RE, "irs", "out", "v30_improved.f32"), "<f4").astype(np.float64)[:512]
    cab = np.r_[cab, np.zeros(512 - len(cab))] * (0.2 / (np.sqrt(np.sum(cab ** 2)) + 1e-9))
    m = Conv(s0, cab, amp_only); opt = torch.optim.Adam(m.parameters(), lr=0.02); rng = np.random.default_rng(1)
    with torch.no_grad(): y0 = m(torch.tensor(x[:int(20 * FS)])).numpy()         # alignment: delay + polarity of the capture
    lag, pol = align(y0, y[:int(20 * FS)]); best = (0, lag, pol)
    _, lag, pol = best; print("alignment: delay", lag, "samples, polarity", pol, flush=True)
    y_orig = y.copy(); y = pol * shift(y_orig, lag)
    train_x = np.r_[x[:split], x[n_di:]]; train_y = np.r_[y[:split], y[n_di:]]
    L = int(0.75 * FS); log = []
    y_raw = pol * np.r_[np.zeros(lag), y_orig[:len(y_orig) - lag]] if False else None
    for it in range(steps):
        if it in (150, 400, 800):                                   # re-align with the partly trained model
            with torch.no_grad(): y0 = m(torch.tensor(x[:int(15 * FS)])).numpy()
            lag, pol = align(y0, y_orig[:int(15 * FS)])
            y = pol * shift(y_orig, lag)
            train_y = np.r_[y[:split], y[n_di:]]; print("re-aligned: delay", lag, "polarity", pol, flush=True)
        idx = rng.integers(0, len(train_x) - L, 6); xb = torch.tensor(np.stack([train_x[i:i + L] for i in idx]))
        tb = torch.tensor(np.stack([train_y[i:i + L] for i in idx]))
        opt.zero_grad(); yb = m(xb)
        loss = ((yb - tb) ** 2).sum() / ((tb ** 2).sum() + 1e-12) + 0.5 * sum(F.stft_loss(yb[k], tb[k]) for k in range(len(idx))) / len(idx)
        loss.backward(); opt.step()
        if it % 100 == 0 or it == steps - 1:
            with torch.no_grad():
                vh = m(torch.tensor(x[split:n_di])).detach().numpy()
            sc = scores(vh, y[split:n_di]); log.append((it, round(float(loss), 4), sc)); print(it, round(float(loss), 4), sc, flush=True)
    s = m.amp.settings(); s["os"] = 2.0; s["_lag"] = lag; s["_pol"] = pol; os.makedirs(os.path.join(RE, "amps"), exist_ok=True)
    json.dump(s, open(os.path.join(RE, "amps", f"nam_{name}.fit.json"), "w"), indent=1)
    if not amp_only: m.w.detach().numpy().astype("<f4").tofile(os.path.join(RE, "irs", "out", f"nam_{name}_cab.f32"))
    json.dump(log, open(os.path.join(RE, "logs", f"nam2pedal_{name}.json"), "w"))


def evaluate(path, name):
    """the real C model (what the pedal runs) + the fitted IR, against the capture on held-out guitar audio"""
    x, y = render(path); split, n_di = int(52 * FS), int(70 * FS)
    s = json.load(open(os.path.join(RE, "amps", f"nam_{name}.fit.json"))); lag = int(s.get("_lag", 0)); y = s.get("_pol", 1.0) * shift(y, lag)
    yh = AM.run(s, [50, 50, 50, 50, 50, 50, 0], x[split - int(FS):n_di])[int(FS):]
    cp = os.path.join(RE, "irs", "out", f"nam_{name}_cab.f32")
    if os.path.exists(cp): yh = np.convolve(yh, np.fromfile(cp, "<f4").astype(np.float64))[:len(yh)]
    yt = y[split:n_di]; best = None                                                 # residual delay/polarity search
    for L_ in range(-24, 25):
        a_, b_ = (yh[L_:], yt[:len(yt) - L_]) if L_ >= 0 else (yh[:L_], yt[-L_:])
        for sg in (1.0, -1.0):
            e_ = float(np.sum((sg * a_ - b_) ** 2) / np.sum(b_ ** 2))
            if best is None or e_ < best[0]: best = (e_, L_, sg)
    sc = scores(yh, yt); sc["esr"] = round(best[0], 3); sc["esr_lag"] = best[1]
    t = y[n_di:]; r = AM.run(s, [50] * 6 + [0], x[n_di:])
    if os.path.exists(cp): r = np.convolve(r, np.fromfile(cp, "<f4").astype(np.float64))[:len(r)]
    seg = int(0.75 * FS) + 0; o = int(0.5 * FS)
    lv = lambda z: np.array([20 * np.log10(np.std(z[o + i * seg + 3000:o + (i + 1) * seg - 3000]) + 1e-12) for i in range(9)])
    gd = lv(r) - lv(t); gd -= gd[-1]; sc["gain_curve_db"] = round(float(np.mean(np.abs(gd))), 2)
    print(f"{name}: held-out guitar ESR {sc['esr']} (NAM's own small model ~0.02, earlier filter models 0.29-0.36), "
          f"tone difference {sc['tone_db']} dB, gain-curve difference {sc['gain_curve_db']} dB")
    return sc


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "fit": fit(a[1], a[2], int(a[3]) if len(a) > 3 and a[3].isdigit() else 1500, "--amp-only" in a)
    else: evaluate(a[1], a[2])
