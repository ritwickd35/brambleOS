#!/usr/bin/env python3
"""NAM capture -> our multi-stage amp model (+ 512-tap cab filter for amp+cab captures), for the planned own clone
engine (NAM_PLAN.md, decision 2026-11-20). Trained on the guitar_di train takes at several input levels (DSP
scale: NAM input = DSP input sample), loss = pre-emphasised, level-balanced ESR + multi-resolution STFT.
  nam2amp.py fit <file.nam> <name> [steps]   -> amps/namx_<name>.json (+ irs/out/namx_<name>_cab.f32)
  nam2amp.py score <file.nam> <name>         held-out R takes: esr, tone, dynamics, fizz, crest (C model = pedal code)
Measures: fizz_db = (4-10 kHz share of loud passages) ours - capture; crest_db = peak/RMS on loud passages,
ours - capture (negative = harder clipping / more squashed); level_db = loudness ours - capture."""
import json, os, sys, time
import numpy as np, torch
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import ampfit as F, ampmodel as AM, namrun, di_set, nam2clo
FS = 44100; KN = [50, 50, 50, 50, 50, 50, 0]
torch.set_num_threads(int(os.environ.get("THREADS", "4")))


def data(nam, which):
    d = di_set.load(which, 180 if which == "train" else 60); parts = []
    for k, gdb in enumerate((-18, -6, 6) if which == "train" else (-6,)):
        n = len(d) // (3 if which == "train" else 1); parts += [np.zeros(FS // 4), d[k * n:(k + 1) * n] * 10 ** (gdb / 20)]
    x = np.concatenate(parts); return x, np.asarray(namrun.render(nam, x)).ravel()[:len(x)]


def preemph(y): return y[..., 1:] - 0.85 * y[..., :-1]


class Conv(torch.nn.Module):
    def __init__(self, s0, cab):
        super().__init__(); self.amp = F.Model(s0)
        self.w = torch.nn.Parameter(torch.tensor(cab)) if cab is not None else None
    def forward(self, x):
        y = self.amp(x, KN)
        if self.w is None: return y
        n = y.shape[-1] + 512; nf = 1 << (n - 1).bit_length()
        return torch.fft.irfft(torch.fft.rfft(y, nf) * torch.fft.rfft(self.w, nf), nf)[..., :y.shape[-1]]


def align(a, b, r=96):
    best = None
    for L in range(-r, r):
        bb = np.roll(b, L)
        for sg in (1.0, -1.0):
            e = float(np.sum((a - sg * bb) ** 2) / np.sum(bb ** 2 + 1e-30))
            if best is None or e < best[0]: best = (e, L, sg)
    return best[1], best[2]


def trial(s0, cab, x, y, steps):
    """short training from this start; returns the plain ESR on 10 s (aligned)"""
    m = Conv(s0, None if cab is None else ls_cab(s0, x, y)); opt = torch.optim.Adam(m.parameters(), lr=0.02); rng = np.random.default_rng(2); L = int(0.75 * FS)
    with torch.no_grad(): y0 = m(torch.tensor(x[:int(15 * FS)])).numpy()
    lag, pol = align(y0, y[:int(15 * FS)]); yt = pol * np.roll(y, lag)
    for it in range(steps):
        idx = rng.integers(FS, len(x) - L, 6); xb = torch.tensor(np.stack([x[i:i + L] for i in idx])); tb = torch.tensor(np.stack([yt[i:i + L] for i in idx]))
        opt.zero_grad(); yb = m(xb); e = (tb ** 2).sum(1); loss = (((yb - tb) ** 2).sum(1) / (e + 0.1 * e.mean() + 1e-12)).mean(); loss.backward(); opt.step()
    with torch.no_grad(): yv = m(torch.tensor(x[int(20 * FS):int(30 * FS)])).numpy()
    tv = yt[int(20 * FS):int(30 * FS)]; k = np.dot(yv, tv) / np.dot(yv, yv); return float(np.sum((k * yv - tv) ** 2) / np.sum(tv ** 2))


def ls_cab(s0, x, y):
    """cab first: least-squares 512-tap filter from this amp's output to the capture (delay included)"""
    from scipy.linalg import solve_toeplitz
    z = AM.run(s0, KN, x[:int(40 * FS)]); t = y[:len(z)]; n = 1 << int(np.ceil(np.log2(2 * len(z))))
    Z = np.fft.rfft(z, n); r = np.fft.irfft(Z * np.conj(Z), n)[:512]; q = np.fft.irfft(np.fft.rfft(t, n) * np.conj(Z), n)[:512]
    r[0] *= 1.001; return solve_toeplitz(r, q)


def fit(nam, name, steps):
    x, y = data(nam, "train"); kind, why = nam2clo.capture_type(nam, y)
    print(f"{time.strftime('%T')}   {name}: capture type {'amp + cab' if kind == 'full' else 'amp only'} ({why})", flush=True)
    cab = None
    if kind == "full":
        c = np.fromfile(os.path.join(RE, "irs", "out", "v30_improved.f32"), "<f4").astype(np.float64)[:512]
        cab = np.r_[c, np.zeros(512 - len(c))] * (0.2 / (np.sqrt(np.sum(c ** 2)) + 1e-9))
    inits = os.environ.get("INITS", "recto").split(",")
    if len(inits) > 1 or os.environ.get("CABFIRST"):                   # pick the start that learns best
        best = None
        for nm_ in inits:
            s_ = json.load(open(os.path.join(RE, "amps", f"{nm_}.fit.json"))) if os.path.exists(os.path.join(RE, "amps", f"{nm_}.fit.json")) else AM.load(nm_)
            s_ = dict(s_); s_["os"] = 2.0; e_ = trial(s_, cab, x, y, int(os.environ.get("TRIAL", "200")))
            print(f"{time.strftime('%T')}   {name}: start from {nm_}: error after the trial {e_:.3f}", flush=True)
            if best is None or e_ < best[0]: best = (e_, s_)
        s0 = best[1]
    else:
        s0 = AM.load("recto"); s0["os"] = 2.0
    if cab is not None and os.environ.get("CABFIRST"): cab = ls_cab(s0, x, y)
    m = Conv(s0, cab); opt = torch.optim.Adam(m.parameters(), lr=0.02); sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps)
    rng = np.random.default_rng(1); L = int(0.75 * FS); t0 = time.time(); lag, pol = 0, 1.0; yt = y
    for it in range(steps):
        if it in (0, 150, 400, 800):                                   # (re)align the capture with the model
            with torch.no_grad(): y0 = m(torch.tensor(x[:int(15 * FS)])).numpy()
            lag, pol = align(y0, y[:int(15 * FS)]); yt = pol * np.roll(y, lag)
            with torch.no_grad():                                      # level: model output scale to the capture's
                k = abs(float(np.dot(y0, yt[:len(y0)]) / np.dot(y0, y0))) + 1e-9
                if "out" in m.amp.lp: m.amp.lp["out"].data += float(np.log(k))
                elif m.w is not None: m.w.data *= k
        idx = rng.integers(FS, len(x) - L, 6); xb = torch.tensor(np.stack([x[i:i + L] for i in idx])); tb = torch.tensor(np.stack([yt[i:i + L] for i in idx]))
        opt.zero_grad(); yb = m(xb); e = (tb ** 2).sum(1)
        pe = ((preemph(yb) - preemph(tb)) ** 2).sum(1) / ((preemph(tb) ** 2).sum(1) + 0.1 * (preemph(tb) ** 2).sum(1).mean() + 1e-12)
        es = ((yb - tb) ** 2).sum(1) / (e + 0.1 * e.mean() + 1e-12)    # plain level-balanced ESR leads (high-gain
        w = float(os.environ.get("PRE_W", "0.2"))                          # rigs did not learn with pre-emphasis alone)
        loss = es.mean() + w * pe.mean() + 0.5 * sum(F.stft_loss(yb[k], tb[k]) for k in range(len(idx))) / len(idx)
        loss.backward(); opt.step(); sch.step()
        if it % 250 == 0 or it == steps - 1:
            el = time.time() - t0
            print(f"{time.strftime('%T')}   {name}: step {it}/{steps - 1}, training error {float(es.mean()):.3f} (pre-emph {float(pe.mean()):.3f}), {el:.0f} s, ~{el / max(it, 1) * (steps - 1 - it):.0f} s left", flush=True)
    s = m.amp.settings(); s["os"] = 2.0; s["_lag"] = int(lag); s["_pol"] = pol; s["_type"] = kind
    json.dump(s, open(os.path.join(RE, "amps", f"namx_{name}.json"), "w"), indent=1)
    if m.w is not None: m.w.detach().numpy().astype("<f4").tofile(os.path.join(RE, "irs", "out", f"namx_{name}_cab.f32"))


def measures(yh, t):
    w = FS // 10; n = min(len(yh), len(t)) // w
    rt = np.sqrt(np.mean(t[:n * w].reshape(n, w) ** 2, 1)); loud = rt >= np.percentile(rt, 70)
    def per(z):
        Z = z[:n * w].reshape(n, w)[loud]; X = np.abs(np.fft.rfft(Z * np.hanning(w), axis=1)) ** 2; f = np.fft.rfftfreq(w, 1 / FS)
        fz = 10 * np.log10(X[:, (f >= 4000) & (f < 10000)].sum() / X.sum())
        cr = np.mean(20 * np.log10(np.abs(Z).max(1) / (np.sqrt(np.mean(Z ** 2, 1)) + 1e-12)))
        return fz, cr, 20 * np.log10(np.sqrt(np.mean(Z ** 2)) + 1e-12)
    a, b = per(yh), per(t)
    return dict(fizz_db=round(a[0] - b[0], 2), crest_db=round(a[1] - b[1], 2), level_db=round(a[2] - b[2], 2))


def score(nam, name):
    import clone_score as S
    x, y = data(nam, "test"); s = json.load(open(os.path.join(RE, "amps", f"namx_{name}.json")))
    yh = AM.run(s, KN, x); cp = os.path.join(RE, "irs", "out", f"namx_{name}_cab.f32")
    if os.path.exists(cp): yh = np.convolve(yh, np.fromfile(cp, "<f4").astype(np.float64))[:len(yh)]
    yt = s.get("_pol", 1.0) * np.roll(y, int(s.get("_lag", 0)))
    r = S.compare(yh, yt); r.update(measures(yh, yt))
    lv = []                                                              # dynamics: same as clone_score
    for db in (-24, -18, -12, -6, 0, 6):
        z = AM.run(s, KN, x[:6 * FS] * 10 ** (db / 20))
        if os.path.exists(cp): z = np.convolve(z, np.fromfile(cp, "<f4").astype(np.float64))[:len(z)]
        tz = np.asarray(namrun.render(nam, x[:6 * FS] * 10 ** (db / 20))).ravel()[:len(z)]
        lv.append(20 * np.log10(np.std(z[FS:]) / np.std(tz[FS:])))
    r["gain_curve_db"] = round(float(np.ptp(lv)), 2); return r


def score_clone(clo, nam):
    """the same measures for a stock-format clone (Sonicake's or our v3), via the validated clone model"""
    import clone_score as S, pmclone as P
    x, y = data(nam, "test"); c = P.parse(open(clo, "rb").read()); yh = S.run(c, x * S.USB)
    r = S.compare(yh, y); n = 1 << 20; xc = np.fft.irfft(np.fft.rfft(y[:n], 2 * n) * np.conj(np.fft.rfft(yh[:n], 2 * n)))
    L = int(np.argmax(np.abs(np.r_[xc[-FS:], xc[:FS]]))) - FS; g = np.dot(np.roll(yh, L), y) / np.dot(yh, yh)
    r.update(measures(g * np.roll(yh, L), y)); r["level_db"] = None; return r


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "fit": fit(a[1], a[2], int(a[3]) if len(a) > 3 else 1500)
    elif a[0] == "score": print(json.dumps(score(a[1], a[2])))
    elif a[0] == "score_clone": print(json.dumps(score_clone(a[1], a[2])))


CAB_GAIN = 10 ** (-12.2 / 20)          # pedal cab stage at VOL 50: an int32 tap of 2^23 gives -12.2 dB (measured)


def make_clone(name, cab_ir=None):
    """PMAM clone file for the own engine: amp settings + (full rigs) the fitted cab as int32 taps at 0.99 full
    scale; the scale and the cab stage's fixed gain are moved into the amp's output level, so the clone plays at
    the capture's level."""
    import pmclone as P
    s = dict(json.load(open(os.path.join(RE, "amps", f"namx_{name}.json")))); cp = os.path.join(RE, "irs", "out", f"namx_{name}_cab.f32")
    if s.get("_type") == "full" and os.path.exists(cp):
        cab = np.fromfile(cp, "<f4").astype(float); sc = 0.99 / np.max(np.abs(cab))
        s["out"] = float(s["out"]) / (sc * CAB_GAIN); return P.build_pmam(s, cab * sc, True)
    if cab_ir is not None:                                       # amp only: bake the chosen cab in (int32 or float taps)
        h = np.asarray(cab_ir, float); h = h / 2 ** 23 if np.max(np.abs(h)) > 2 else h; sc = 0.99 / np.max(np.abs(h))
        s["out"] = float(s["out"]) / (sc * CAB_GAIN)
        return P.build_pmam(s, h * sc, False)                    # type stays "amp only" (the IR choice is ours)
    return P.build_pmam(s, None, False)
