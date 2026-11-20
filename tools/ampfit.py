#!/usr/bin/env python3
"""Fit our amp model (dsp/amp.c) to recordings of a target amp.
  ampfit.py selftest <name>               target = dsp/host with perturbed settings; fit from amps/<name>.json
  ampfit.py fit <name> <captures.json>    captures: [{"in": f32 path, "out": f32 path, "knobs": [7 values]}, ...]
The fitter is a differentiable copy of the model: linear filters applied exactly in the frequency domain (their
bilinear responses), ADAA clippers vectorised, the model's own half-band all-pass resamplers. The
result is always re-checked with the real C model (dsp/host)."""
import json, math, os, sys
import numpy as np
import torch
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import ampmodel as AM
FS = 44100.0
torch.set_default_dtype(torch.float64)

FIT = ["gmin", "gmax", "brt_db", "pdrv", "pout", "pres_hz", "pres_db", "res_hz", "out", "olp"] + \
      [f"s{k}_{f}" for k in range(3) for f in ("hp", "lp", "gain", "out")]
SIGNED = [f"s{k}_bias" for k in range(3)] + ["res_db", "brt_db", "pres_db"]
TSK = ["R1", "R2", "R3", "R4", "C1", "C2", "C3"]


def onepole_H(kind, fc, fs, w):
    k = torch.tan(math.pi * torch.clamp(fc, 1.0, 0.49 * fs) / fs)
    z1 = torch.exp(-1j * w)
    if kind == "lp": b0 = k / (1 + k); b1 = b0
    else: b0 = 1 / (1 + k); b1 = -b0
    a1 = (k - 1) / (1 + k)
    return (b0 + b1 * z1) / (1 + a1 * z1)


def tstack_H(rc, t, m, l, fs, w):
    R1, R2, R3, R4, C1, C2, C3 = rc
    b1 = t*C1*R1 + m*C3*R3 + l*(C1*R2 + C2*R2) + (C1*R3 + C2*R3)
    b2 = (t*(C1*C2*R1*R4 + C1*C3*R1*R4) - m*m*(C1*C3*R3*R3 + C2*C3*R3*R3) + m*(C1*C3*R1*R3 + C1*C3*R3*R3 + C2*C3*R3*R3)
          + l*(C1*C2*R1*R2 + C1*C2*R2*R4 + C1*C3*R2*R4) + l*m*(C1*C3*R2*R3 + C2*C3*R2*R3) + (C1*C2*R1*R3 + C1*C2*R3*R4 + C1*C3*R3*R4))
    b3 = (l*m*(C1*C2*C3*R1*R2*R3 + C1*C2*C3*R2*R3*R4) - m*m*(C1*C2*C3*R1*R3*R3 + C1*C2*C3*R3*R3*R4)
          + m*(C1*C2*C3*R1*R3*R3 + C1*C2*C3*R3*R3*R4) + t*C1*C2*C3*R1*R3*R4 - t*m*C1*C2*C3*R1*R3*R4 + t*l*C1*C2*C3*R1*R2*R4)
    a1 = (C1*R1 + C1*R3 + C2*R3 + C2*R4 + C3*R4) + m*C3*R3 + l*(C1*R2 + C2*R2)
    a2 = (m*(C1*C3*R1*R3 - C2*C3*R3*R4 + C1*C3*R3*R3 + C2*C3*R3*R3) + l*m*(C1*C3*R2*R3 + C2*C3*R2*R3) - m*m*(C1*C3*R3*R3 + C2*C3*R3*R3)
          + l*(C1*C2*R2*R4 + C1*C2*R1*R2 + C1*C3*R2*R4 + C2*C3*R2*R4) + (C1*C2*R1*R4 + C1*C3*R1*R4 + C1*C2*R3*R4 + C1*C2*R1*R3 + C1*C3*R3*R4 + C2*C3*R3*R4))
    a3 = (l*m*(C1*C2*C3*R1*R2*R3 + C1*C2*C3*R2*R3*R4) - m*m*(C1*C2*C3*R1*R3*R3 + C1*C2*C3*R3*R3*R4)
          + m*(C1*C2*C3*R3*R3*R4 + C1*C2*C3*R1*R3*R3 - C1*C2*C3*R1*R3*R4) + l*C1*C2*C3*R1*R2*R4 + C1*C2*C3*R1*R3*R4)
    s = 2 * fs * (1 - torch.exp(-1j * w)) / (1 + torch.exp(-1j * w))         # bilinear map
    return (b1*s + b2*s**2 + b3*s**3) / (1 + a1*s + a2*s**2 + a3*s**3)


def filt(x, H_fn, fs):
    n = x.shape[-1]; N = 1 << int(math.ceil(math.log2(n + int(0.25 * fs))))
    w = torch.linspace(0, math.pi, N // 2 + 1)
    return torch.fft.irfft(torch.fft.rfft(x, N) * H_fn(w), N)[..., :n]


HB = [0.054217526, 0.196797970, 0.383087327, 0.573136411, 0.748720944, 0.914293710]   # dsp/hb_coefs.h
HB2 = [0.070224059, 0.285086280, 0.684541359]


def chain(cs, x):
    """cascade of first-order all-passes y = c (x - y1) + x1, i.e. H = (c + z^-1) / (1 + c z^-1), as in pmfx.c"""
    def H(w):
        z1 = torch.exp(-1j * w); h = torch.ones_like(z1)
        for c in cs: h = h * (c + z1) / (1 + c * z1)
        return h
    return filt(x, H, FS)


def inter(a, b): return torch.stack([a, b], -1).reshape(a.shape[:-1] + (-1,))


def up2(x, c=HB): return inter(chain(c[0::2], x), chain(c[1::2], x))
def down2(x, c=HB): return 0.5 * (chain(c[0::2], x[..., 1::2]) + chain(c[1::2], x[..., 0::2]))


def resample(x, f):
    """the model's own polyphase IIR half-band resamplers (pmfx.c os4 / hb), exact as linear filters"""
    if f == 4: return up2(up2(x), HB2)
    if f == -4: return down2(down2(x, HB2))
    if f == 2: return up2(x)
    if f == -2: return down2(x)
    raise ValueError(f)


def F(x): ax = x.abs(); return torch.where(ax < 1, x*x/2 - x**4/12, 2*ax/3 - 0.25)
def f(x): return torch.where(x.abs() < 1, x - x**3/3, torch.sign(x) * 2/3)


def adaa(x):
    xp = torch.cat([x[..., :1], x[..., :-1]], -1); d = x - xp
    safe = torch.where(d.abs() > 1e-4, d, torch.ones_like(d))
    return torch.where(d.abs() > 1e-4, (F(x) - F(xp)) / safe, f(0.5 * (x + xp)))


class Model(torch.nn.Module):
    def __init__(self, s):
        super().__init__(); s = dict(s); s.setdefault("olp", 19000.0); self.s0 = s; self.nst = int(s["nst"])
        self.lp = torch.nn.ParameterDict({k: torch.nn.Parameter(torch.tensor(math.log(max(s[k], 1e-6)))) for k in FIT if k not in SIGNED})
        self.sg = torch.nn.ParameterDict({k: torch.nn.Parameter(torch.tensor(float(s[k]))) for k in SIGNED})
        self.ts = torch.nn.Parameter(torch.zeros(7))                            # log corrections of the tone stack parts

    def v(self, k):
        if k in self.sg: return self.sg[k]
        if k in self.lp: return torch.exp(self.lp[k])
        return torch.tensor(float(self.s0[k]))

    def settings(self):
        out = dict(self.s0)
        for k in list(self.lp) + list(self.sg): out[k] = float(self.v(k))
        for i, k in enumerate(TSK): out[k] = float(self.s0[k] * math.exp(float(self.ts[i])))
        return out

    def forward(self, x, kn):
        v = self.v; g, bass, mid, tre, pres, vol = (k * 0.01 for k in kn[:6]); bright = kn[6] if len(kn) > 6 else 0
        x = filt(x, lambda w: onepole_H("hp", torch.tensor(20.0), FS, w), FS)
        if bright:
            G = 10 ** (v("brt_db") / 20) - 1; x = x + G * filt(x, lambda w: onepole_H("hp", v("brt_hz"), FS, w), FS)
        x = x * v("gmin") * torch.exp(g * torch.log(v("gmax") / v("gmin")))
        y = resample(x, 4)
        for k in range(self.nst):
            y = filt(y, lambda w: onepole_H("hp", v(f"s{k}_hp"), 4 * FS, w) * onepole_H("lp", v(f"s{k}_lp"), 4 * FS, w), 4 * FS)
            b = v(f"s{k}_bias"); y = (adaa(v(f"s{k}_gain") * y + b) - f(b)) * v(f"s{k}_out")
        y = resample(y, -4)
        rc = [self.s0[k] * torch.exp(self.ts[i]) for i, k in enumerate(TSK)]
        y = filt(y, lambda w: tstack_H(rc, tre, mid, math.exp((bass - 1) * 3.4), FS, w), FS)
        y = resample(adaa(v("pdrv") * resample(y, 2)) * v("pout"), -2)
        P = 10 ** (v("pres_db") * pres / 20) - 1; R = 10 ** (v("res_db") / 20) - 1
        y = filt(y, lambda w: (1 + P * onepole_H("hp", v("pres_hz"), FS, w)) * (1 + R * onepole_H("lp", v("res_hz"), FS, w)), FS)
        y = filt(y, lambda w: onepole_H("lp", torch.clamp(v("olp"), 200.0, 19000.0), FS, w), FS)
        return y * v("out") * 10 ** (40 * (vol - 0.5) / 20)


def stft_loss(y, t):
    out = 0
    for n in (256, 1024, 4096):
        win = torch.hann_window(n)
        Y = torch.stft(y, n, n // 4, window=win, return_complex=True).abs(); T = torch.stft(t, n, n // 4, window=win, return_complex=True).abs()
        e = 1e-4 * T.max().detach()                     # relative floor: quiet amps keep their treble in the loss
        out = out + (Y - T).norm() / (T.norm() + 1e-9) + (torch.log(Y + e) - torch.log(T + e)).abs().mean()
    return out


def esr(y, t): return float(((y - t) ** 2).sum() / ((t ** 2).sum() + 1e-12))


def fit(s, caps, steps=400, log=print):
    m = Model(s); opt = torch.optim.Adam(m.parameters(), lr=0.03)
    data = [(torch.tensor(c["x"]), torch.tensor(c["y"]), c["knobs"]) for c in caps]
    for it in range(steps):
        opt.zero_grad(); loss = 0
        for x, t, kn in data:
            y = m(x, kn); loss = loss + stft_loss(y, t)        # magnitude only: the stock amps' phase is not ours to copy
        loss.backward(); opt.step()
        if it % 50 == 0 or it == steps - 1: log(f"  step {it:4d} loss {float(loss):.4f}")
    return m.settings()


def di(n=3 * 44100, start=44100):
    return np.fromfile(os.path.join(RE, "audio", "di_reference_44100.f32"), "<f4")[start:start + n].astype(np.float64) * 2.87


KNOBSETS = [[30, 50, 50, 50, 50, 50, 0], [70, 50, 50, 50, 50, 50, 0], [100, 50, 50, 50, 50, 50, 0],
            [70, 0, 100, 0, 50, 50, 0], [70, 100, 0, 100, 100, 50, 1]]


def host_esr(s, caps):
    """per capture: spectral distance (same loss as the fit) of the real C model"""
    return [round(float(stft_loss(torch.tensor(AM.run(s, c["knobs"], c["x"])), torch.tensor(c["y"]))), 3) for c in caps]


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "agree":                    # differentiable copy vs the C model, same settings
        s0 = AM.load(a[1]); x = di(); m = Model(s0)
        for kn in KNOBSETS:
            with torch.no_grad(): y = m(torch.tensor(x), kn).numpy()
            c = AM.run(s0, kn, x); print(kn, "ESR torch vs C", round(esr(torch.tensor(y), torch.tensor(c)), 4))
    elif a[0] == "selftest":
        s0 = AM.load(a[1]); rng = np.random.default_rng(1); true = dict(s0)
        for k in FIT:
            if k not in SIGNED: true[k] = s0[k] * float(np.exp(rng.uniform(-0.4, 0.4)))
        for k in SIGNED: true[k] = s0[k] + float(rng.uniform(-0.1, 0.1)) * (5 if k.endswith("db") else 1)
        x = di(); caps = [dict(x=x, y=AM.run(true, kn, x), knobs=kn) for kn in KNOBSETS]
        print("start ESR (C model, per knob set):", host_esr(s0, caps))
        s = fit(s0, caps, steps=int(a[2]) if len(a) > 2 else 300)
        print("fitted ESR (C model, per knob set):", host_esr(s, caps))
        json.dump(s, open(os.path.join(RE, "logs", f"ampfit_selftest_{a[1]}.json"), "w"), indent=1)
    elif a[0] == "fit":                    # ampfit.py fit <our name> [steps]: uses audio/ampcap/<stock name>/spec.json
        import audit as AU, amp_capture as AC
        name = a[1]; stock = AM.LINEUP[name][0]; s0 = AM.load(name); kn_names = AC.stock_amps()[stock][1]
        spec = json.load(open(os.path.join(RE, "audio", "ampcap", stock.replace(" ", "_"), "spec.json")))
        segs = [(AU.T_RAMP, AU.T_RAMP + 6.8), (AU.T_DI, AU.T_DI + 4.0)]
        caps = []; lags = []
        for c in spec:
            xin = np.fromfile(c["in"], "<f4").astype(np.float64); yout = np.fromfile(c["out"], "<f4").astype(np.float64)
            eff = [50.0] * 6 + [0]                               # knobs the stock amp really has; the rest stay neutral
            for i, nm in enumerate(AC.OURS):
                if AC.ALIAS.get(nm, nm) in [AC.ALIAS.get(k, k) for k in kn_names]: eff[i] = c["knobs"][i]
            for t0, t1 in segs:
                i0, i1 = int(t0 * FS), int(t0 * FS) + (int((t1 - t0) * FS) // 4) * 4
                caps.append(dict(x=xin[i0:i1], y=yout[i0:i1], knobs=eff))
        print("start ESR:", host_esr(s0, caps)); s = fit(s0, caps, steps=int(a[2]) if len(a) > 2 else 200)
        print("fitted ESR:", host_esr(s, caps)); json.dump(s, open(os.path.join(AM.AMPS, f"{name}.fit.json"), "w"), indent=1)
