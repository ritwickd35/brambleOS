#!/usr/bin/env python3
"""Convert a NAM capture into a pedal clone (.clo) for the stock clone engine (validated on the pedal, NOTES §50):
   y = post * bqB( FIRb_512( sat_p( g * FIRa_128( x ) ) ) )      g = 0.478 at DSP scale (knobs 50)
Fits FIRa, FIRb and the 4 saturator params to the capture rendered on Sonicake's own 70 s capture signal, with an
ESR + spectral loss (Sonicake: a re-capture as well, but we fit directly against the network).
Capture type (amp-only vs amp+cab) from the NAM gear_type tag, else the high-band test; stored in the clone name
suffix for now (" [A]" amp-only, " [F]" full rig) until the firmware reads a flag.
  nam2clo.py <file.nam> <out.clo> [steps]"""
import json, os, sys, time
import numpy as np, torch
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import pmclone as P, namrun, clone_score as S
FS = 44100; G_DSP = 3.0 * S.USB; NA, NB = 128, 512
DEV = os.environ.get("DEV", "mps" if torch.backends.mps.is_available() else "cpu")
DT = torch.float32 if DEV == "mps" else torch.float64          # the Apple GPU has no float64
BQB = np.array([1.0, 0, 0, 0, 0])                                  # no output biquad (matches the training model)


def capture_type(path, y_di):
    """amp-only vs full rig (amp+cab). Evidence, strongest first: the sound (level drop from 4 to 8 kHz; 11 captures:
    amp-only -4.9..-10.5 dB, full rigs -16.2..-35.3 dB), then words in the capture's name, then its gear_type tag
    (tags can be wrong: TONE3000 #32868 "Full Rig 5150 + Mesa 4x12" is tagged "amp")."""
    d = json.load(open(path)); m = d.get("metadata") or {}
    gt = (m.get("gear_type") or "").lower(); name = ((m.get("name") or "") + " " + os.path.basename(path)).lower()
    f = np.fft.rfftfreq(8192, 1 / FS); X = 0
    for i in range(0, len(y_di) - 8192, 4096): X = X + np.abs(np.fft.rfft(y_di[i:i + 8192] * np.hanning(8192))) ** 2
    band = lambda a, b: 10 * np.log10(X[(f >= a) & (f < b)].mean())
    r = band(7000, 9000) - band(3500, 4500)               # drop from 4 kHz to 8 kHz: a cab falls off steeply here
    words = any(w in name for w in ("full rig", "full_rig", "fullrig", "cab", "4x12", "2x12", "1x12", "4x10", "2x10", "1x15", " ir", "sm57", "md421", "r121"))
    if r < -15: return "full", f"sound (4->8 kHz {r:.1f} dB)"
    if r > -11: return "amp", f"sound (4->8 kHz {r:.1f} dB)"
    if words: return "full", f"name + sound ({r:.1f} dB)"
    if gt: return ("full" if "cab" in gt else "amp"), f"tag + sound ({r:.1f} dB)"
    return ("full" if r < -13 else "amp"), f"sound (4->8 kHz {r:.1f} dB)"


def tconv(x, h):                                      # x (B, T), h (K,) causal
    return torch.nn.functional.conv1d(torch.nn.functional.pad(x, (len(h) - 1, 0))[:, None], h.flip(0)[None, None])[:, 0]


def biquad(x, c):                                     # direct form, small batches: run with lfilter on numpy instead
    from scipy.signal import lfilter
    return lfilter(c[:3], np.r_[1, c[3:]], x)


def fit(nam, steps=3000, seed=0, init=None):
    torch.manual_seed(seed); rng = np.random.default_rng(seed)
    import soundfile as sf
    u, _ = sf.read(os.path.join(RE, "audio", "nam_input_wav.wav")); u = u[:, 0].astype(np.float64)
    import di_set
    d = di_set.load("train", 180); parts = [u]           # Sonicake's signal + guitar DI (held-out songs never used)
    for k, gdb in enumerate((-18, -6, 6)):               # each third of the DI at another input level (DSP scale)
        parts += [np.zeros(FS // 4), d[k * 60 * FS:(k + 1) * 60 * FS] * 10 ** (gdb / 20)]
    u = np.concatenate(parts); t = np.asarray(namrun.render(nam, u)).ravel()[:len(u)]
    post = torch.tensor(S.engine_post(), dtype=DT, device=DEV); W = 16384; H = NA + NB + len(post)
    U, T = torch.tensor(u, dtype=DT, device=DEV), torch.tensor(biquad(t, np.r_[1.0, 0, 0, 0, 0]), dtype=DT, device=DEV)
    fa = torch.zeros(NA, dtype=DT, device=DEV); fa[0] = 1.0
    fb = torch.zeros(NB, dtype=DT, device=DEV); fb[0] = 1.0
    lp = torch.tensor(np.log([0.06, 0.06, 546.0, 624.0]), dtype=DT, device=DEV)
    if init is not None:
        fa = torch.tensor(np.asarray(init["fa"]), dtype=DT, device=DEV); fb = torch.tensor(np.asarray(init["fb"][:NB]), dtype=DT, device=DEV); lp = torch.tensor(np.log(init["p"]), dtype=DT, device=DEV)
    lo = torch.tensor(0.0, dtype=DT, device=DEV)          # output level (folded into pm, nm at the end)
    for v in (fa, fb, lp, lo): v.requires_grad_()
    LR = float(os.environ.get("LR", "2e-3"))
    opt = torch.optim.Adam([{"params": [fa, fb], "lr": LR}, {"params": [lp, lo], "lr": 5 * LR}])
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps)
    win = torch.hann_window(2048, dtype=DT, device=DEV)

    def fwd(x):
        pm, nm, pr, nr = lp.exp()
        z = G_DSP * tconv(x, fa)
        z = torch.where(z >= 0, pm * (1 - torch.exp(-pr * z.clamp(min=0))), -nm * (1 - torch.exp(nr * z.clamp(max=0))))
        return lo.exp() * tconv(tconv(z, fb), post)

    def loss_of(yh, y):
        if os.environ.get("BAL", "1") == "1":            # v3: every segment counts the same, whatever its level,
            e = (y ** 2).sum(1); esr = (((yh - y) ** 2).sum(1) / (e + 0.1 * e.mean() + 1e-9)).mean()   # soft playing counts too;
            # the 0.1 x batch-mean floor keeps near-silent segments (hiss only) from dominating (v3a: 19 broke)
        else: esr = ((yh - y) ** 2).sum() / (y ** 2).sum()
        Yh = torch.stft(yh, 2048, 512, window=win, return_complex=True).abs(); Y = torch.stft(y, 2048, 512, window=win, return_complex=True).abs()
        spec = (torch.log(Yh + 1e-5) - torch.log(Y + 1e-5)).abs().mean()
        return esr + float(os.environ.get("SPEC", "0.3")) * spec, esr   # spectral term: clipping character

    if init is None:                                    # cold start: fb = least-squares FIR from sat(g x) to the capture
        from scipy.linalg import solve_toeplitz
        with torch.no_grad():
            pm, nm, pr, nr = lp.exp().cpu().numpy().astype(np.float64); z = G_DSP * u[:FS * 40]
            z = np.where(z >= 0, pm * (1 - np.exp(-pr * np.maximum(z, 0))), -nm * (1 - np.exp(nr * np.minimum(z, 0))))
            z = np.convolve(z, post.cpu().numpy().astype(np.float64))[64:64 + len(z)]; y = t[:len(z)]; n = 1 << int(np.ceil(np.log2(2 * len(z))))
            Z = np.fft.rfft(z, n); r = np.fft.irfft(Z * np.conj(Z), n)[:NB]; q = np.fft.irfft(np.fft.rfft(y, n) * np.conj(Z), n)[:NB]
            r[0] *= 1.001; fb.data = torch.tensor(solve_toeplitz(r, q), dtype=DT, device=DEV)
    with torch.no_grad():                               # delay of the model (post filter: 64) vs the capture
        a = fwd(U[None, :FS * 30])[0].cpu().numpy().astype(np.float64); b = T[:FS * 30].cpu().numpy().astype(np.float64)
        cc = [abs(np.dot(a[FS + D:FS * 29 + D], b[FS:FS * 29])) for D in range(-100, 200)]; D = int(np.argmax(cc)) - 100
        lo.data = torch.tensor(float(np.log(np.dot(np.roll(a, -D)[FS:FS * 29], b[FS:FS * 29]) / np.dot(a[FS:FS * 29], a[FS:FS * 29]))), dtype=DT, device=DEV)
    print(f"{time.strftime('%T')}   capture rendered, training starts (model-vs-capture delay {D} samples)", flush=True)
    t0 = time.time()
    for it in range(steps):
        idx = rng.integers(H + 200, len(u) - W - 200, 8)
        x = torch.stack([U[i - H:i + W] for i in idx]); y = torch.stack([T[i - D:i - D + W] for i in idx])
        opt.zero_grad(); yh = fwd(x)[:, H:]; L, esr = loss_of(yh, y); L.backward(); opt.step(); sched.step()
        if it % 500 == 0 or it == steps - 1:
            el = time.time() - t0; eta = el / max(it, 1) * (steps - 1 - it)
            print(f"{time.strftime('%T')}   {os.path.basename(os.path.dirname(nam)) or 'mes'}: step {it}/{steps - 1}, training error {esr.detach().item():.3f}, {el:.0f} s, ~{eta:.0f} s left", flush=True)
    # undo the "level free" gain: output level of the clone = that of the NAM (VOL 50 -> capture level)
    with torch.no_grad():
        x = U[:FS * 20][None]; yh = fwd(x)[0][200:]; y = T[200 - D:FS * 20 - D]
        k = float((yh * y).sum() / (yh * yh).sum())
    p = lp.exp().detach().cpu().numpy().astype(np.float64)
    k *= float(lo.exp())
    return dict(bqa=np.r_[1.0, 0, 0, 0, 0], bqb=BQB, p=np.r_[p[0] * k, p[1] * k, p[2], p[3]], fa=fa.detach().cpu().numpy().astype(np.float64), fb=fb.detach().cpu().numpy().astype(np.float64))


def main():
    nam, out = sys.argv[1:3]; steps = int(sys.argv[3]) if len(sys.argv) > 3 else 3000
    init = P.parse(open(os.environ["INIT"], "rb").read()) if os.environ.get("INIT") else None
    c = fit(nam, steps, init=init)
    if os.environ.get("TONEMATCH", "1") == "1":                 # final tone match (output EQ inside FIRb)
        import clo_tonematch
        c, t0, t1, _ = clo_tonematch.tonematch(c, nam); print(f"{time.strftime('%T')}   tone match {t0:.2f} -> {t1:.2f} dB", flush=True)
    open(out, "wb").write(P.build(c, 512))
    kind, why = capture_type(nam, np.asarray(namrun.render(nam, S.di(10) / S.USB)).ravel())
    json.dump(dict(type=kind, how=why), open(out + ".json", "w")); print(f"{time.strftime('%T')}   wrote {out}; capture type: {'amp + cab' if kind == 'full' else 'amp only'} ({why})", flush=True)


if __name__ == "__main__":
    main()
