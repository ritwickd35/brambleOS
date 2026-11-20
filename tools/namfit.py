#!/usr/bin/env python3
"""How close can the pedal's capture engine get to a real NAM model? Offline experiment.
Reference: a NAM WaveNet (namref.py) run on a real 70 s guitar DI (SonicMaster's reference DI, 44.1 kHz).
Models fitted with gradient descent (torch), all at 44.1 kHz, scored by ESR on held-out audio:
  wh1  stock clone structure: FIR 128 -> asymmetric exp saturator -> FIR 512       (what the pedal runs today)
  wh2  two nonlinear stages:  FIR 64 -> sat -> FIR 64 -> sat -> FIR 512            (needs a new engine program)
  wh3  three stages:          FIR 48 -> sat -> FIR 48 -> sat -> FIR 48 -> sat -> FIR 512
Costs (multiply-adds per sample on the engine) are printed next to each result.
  namfit.py <file.nam> [seconds]"""
import os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import torch
import namref as N
FS = 44100


def resample(x, a, b):
    n = int(round(len(x) * b / a)); X = np.fft.rfft(x); Y = np.zeros(n // 2 + 1, complex); k = min(len(X), len(Y)); Y[:k] = X[:k]
    return np.fft.irfft(Y, n) * n / len(x)


def reference(path, secs):
    x = np.fromfile(os.path.join(RE, "audio", "di_reference_44100.f32"), "<f4").astype(np.float64)[:int(secs * FS)]
    nam = N.load(path); subs = N.submodels(nam); mv, model = subs[-1]
    sr = float(model.get("sample_rate", nam.get("sample_rate", 48000)) or 48000)
    net = N.WaveNet(model)
    t = time.time(); y = net.process(resample(x, FS, sr)); y = resample(np.asarray(y).ravel(), sr, FS)[:len(x)]
    print(f"reference: {len(x) / FS:.0f} s through the widest submodel ({sr:.0f} Hz) in {time.time() - t:.0f} s")
    if len(subs) > 1:                       # quality bar: the capture's own small (A2-Lite) submodel
        mv0, m0 = subs[0]; y0 = resample(np.asarray(N.WaveNet(m0).process(resample(x, FS, sr))).ravel(), sr, FS)[:len(x)]
        sp = int(0.75 * len(x)); print(f"NAM's own small submodel (A2-Lite class) vs the full model: ESR {np.sum((y0[sp:] - y[sp:]) ** 2) / np.sum(y[sp:] ** 2):.4f}")
    return x.astype(np.float32), y.astype(np.float32)


class Sat(torch.nn.Module):
    """The pedal's asymmetric exponential saturator: x>0: pm*(1-exp(-pr*x)), x<0: -nm*(1-exp(nr*x))."""
    def __init__(self):
        super().__init__(); self.p = torch.nn.Parameter(torch.tensor([-1.0, -1.0, 3.0, 3.0]))   # start: strong drive, output 0.37   # log pm, nm, pr, nr
    def forward(self, x):
        pm, nm, pr, nr = torch.exp(self.p)
        xp = torch.clamp(x, min=0.0); xn = torch.clamp(x, max=0.0)       # both branches stay finite
        return pm * (1 - torch.exp(-pr * xp)) - nm * (1 - torch.exp(nr * xn))


class FIR(torch.nn.Module):
    def __init__(self, n, init="delta"):
        super().__init__(); w = torch.zeros(n); w[0] = 1.0; self.w = torch.nn.Parameter(w)
    def forward(self, x):                         # causal FIR via FFT
        n = x.shape[-1] + self.w.shape[0]; nf = 1 << (n - 1).bit_length()
        return torch.fft.irfft(torch.fft.rfft(x, nf) * torch.fft.rfft(self.w, nf), nf)[..., :x.shape[-1]]


class WH(torch.nn.Module):
    def __init__(self, stages, pre, post=512):
        super().__init__()
        self.f = torch.nn.ModuleList([FIR(pre) for _ in range(stages)]); self.s = torch.nn.ModuleList([Sat() for _ in range(stages)])
        self.g = torch.nn.Parameter(torch.ones(stages)); self.out = FIR(post)
    def forward(self, x):
        for f, s, g in zip(self.f, self.s, self.g): x = s(g * f(x))
        return self.out(x)
    def macs(self): return sum(f.w.shape[0] for f in self.f) + self.out.w.shape[0] + 10 * len(self.s)


def esr(y, t): return float(torch.sum((y - t) ** 2) / torch.sum(t ** 2))


def fit(model, x, t, xv, tv, steps=int(os.environ.get('NAMFIT_STEPS', '6000'))):
    opt = torch.optim.Adam(model.parameters(), lr=1e-2); seg = 16384
    for k in range(steps):
        i = np.random.randint(0, len(x) - seg)
        xb, tb = x[i:i + seg], t[i:i + seg]; y = model(xb)
        loss = torch.sum((y[2048:] - tb[2048:]) ** 2) / torch.sum(tb[2048:] ** 2)
        opt.zero_grad(); loss.backward(); opt.step()
        if k in (steps // 2, 5 * steps // 6):
            for gp in opt.param_groups: gp["lr"] *= 0.2
    with torch.no_grad(): return esr(model(xv)[2048:], tv[2048:])


def main():
    path = sys.argv[1]; secs = float(sys.argv[2]) if len(sys.argv) > 2 else 40
    x, y = reference(path, secs)
    split = int(0.75 * len(x))
    X, T = torch.tensor(x[:split]), torch.tensor(y[:split]); XV, TV = torch.tensor(x[split:]), torch.tensor(y[split:])
    torch.manual_seed(0); np.random.seed(0)
    print(f"DI rms {float(np.std(x)):.3f}, NAM out rms {float(np.std(y)):.3f}")
    # linear baseline: least-squares 512-tap FIR (how much of the target is plain filtering)
    lin = FIR(512); ol = torch.optim.Adam(lin.parameters(), lr=1e-2)
    for k in range(1500):
        i = np.random.randint(0, split - 16384); yb = lin(X[i:i + 16384]); l = torch.sum((yb - T[i:i + 16384]) ** 2) / torch.sum(T[i:i + 16384] ** 2)
        ol.zero_grad(); l.backward(); ol.step()
    with torch.no_grad(): print(f"linear 512-tap FIR only: ESR {esr(lin(XV), TV):.4f}")
    print(f"{'model':6s} {'ESR (held out)':>14s} {'MACs/sample':>12s}")
    for name, m in (("wh1", WH(1, 128)), ("wh2", WH(2, 64)), ("wh3", WH(3, 48))):
        t0 = time.time(); e = fit(m, X, T, XV, TV)
        print(f"{name:6s} {e:14.4f} {m.macs():12d}   ({time.time() - t0:.0f} s)", flush=True)
        torch.save(m.state_dict(), os.path.join(RE, "cut1", f"namfit-{name}.pt"))


if __name__ == "__main__":
    main()
