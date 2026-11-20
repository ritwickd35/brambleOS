#!/usr/bin/env python3
"""LSTM amp capture for the engine (option B).
  lstmamp.py target            -> audio/nam_target_44100.f32 (NAM capture run on the 70 s DI, cached)
  lstmamp.py train H L [steps] -> logs/lstm_H{H}_L{L}.pt + .json   (H hidden units, L-tap output FIR = cab)
Stage 1 trains torch.nn.LSTM (fast). Stage 2 swaps in the engine activations
   T(x) = x / sqrt(1 + x^2)   (engine: rsqrt),   S(x) = 0.5 + 0.5 T(x / 2)
and fine-tunes, so what we deploy is exactly what was trained."""
import json, os, sys, time
import numpy as np
import torch
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
FS = 44100
NAM = "/Users/ritwickdas/Downloads/MES DRECF RD Gain2 BAL O808 CAB.nam"
TGT = os.path.join(RE, "audio", "nam_target_44100.f32")
torch.set_num_threads(8)


def data():
    x = np.fromfile(os.path.join(RE, "audio", "di_reference_44100.f32"), "<f4")
    t = np.fromfile(TGT, "<f4"); n = min(len(x), len(t)); return x[:n], t[:n]


def T(x): return x * torch.rsqrt(1.0 + x * x)
def S(x): return 0.5 + 0.5 * T(0.5 * x)


class Amp(torch.nn.Module):
    def __init__(self, H, L):
        super().__init__()
        self.H, self.L = H, L
        self.lstm = torch.nn.LSTM(1, H, batch_first=True)
        self.out = torch.nn.Linear(H, 1)
        self.skip = torch.nn.Parameter(torch.zeros(1))
        self.gain = torch.nn.Parameter(torch.zeros(1))          # log input gain
        fir = torch.zeros(L); fir[0] = 1.0
        self.fir = torch.nn.Parameter(fir)
        self.engine = False

    def cell_loop(self, x):                                     # engine activations, explicit loop
        W, U = self.lstm.weight_ih_l0, self.lstm.weight_hh_l0; b = self.lstm.bias_ih_l0 + self.lstm.bias_hh_l0
        B, N, _ = x.shape; H = self.H
        h = x.new_zeros(B, H); c = x.new_zeros(B, H); hs = []
        xw = x @ W.T + b                                        # (B, N, 4H)
        for n in range(N):
            z = xw[:, n] + h @ U.T
            i, f, g, o = S(z[:, :H]), S(z[:, H:2 * H]), T(z[:, 2 * H:3 * H]), S(z[:, 3 * H:])
            c = f * c + i * g; h = o * T(c); hs.append(h)
        return torch.stack(hs, 1)

    def forward(self, x):                                       # x (B, N)
        u = (x * torch.exp(self.gain)).unsqueeze(-1)
        h = self.cell_loop(u) if self.engine else self.lstm(u)[0]
        y = self.out(h).squeeze(-1) + self.skip * u.squeeze(-1)
        k = self.fir.flip(0).view(1, 1, -1)                     # causal FIR (cab)
        return torch.nn.functional.conv1d(torch.nn.functional.pad(y.unsqueeze(1), (self.L - 1, 0)), k).squeeze(1)


def esr(y, t): return float(((y - t) ** 2).sum() / (t ** 2).sum())


def batches(x, t, seg, bs, rng):
    idx = rng.integers(0, len(x) - seg - 1, bs)
    return torch.tensor(np.stack([x[i:i + seg] for i in idx])), torch.tensor(np.stack([t[i:i + seg] for i in idx]))


def evaluate(m, x, t, secs=8.0):
    with torch.no_grad():
        n = int(secs * FS); y = m(torch.tensor(x[:n]).unsqueeze(0)).squeeze(0).numpy()
    w = 4096; return float(np.sum((y[w:] - t[w:n]) ** 2) / np.sum(t[w:n] ** 2))


def train(H, L, steps):
    x, t = data(); sp = int(0.8 * len(x)); xt, tt, xv, tv = x[:sp], t[:sp], x[sp:], t[sp:]
    rng = np.random.default_rng(0); torch.manual_seed(0)
    m = Amp(H, L); opt = torch.optim.Adam(m.parameters(), 4e-3); warm = 1024
    log = []; t0 = time.time()
    for s in range(steps):                                      # stage 1: torch LSTM
        xb, tb = batches(xt, tt, 4096 + warm, 32, rng)
        y = m(xb); loss = ((y[:, warm:] - tb[:, warm:]) ** 2).mean() / (tb[:, warm:] ** 2).mean()
        opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step()
        if s == int(steps * 0.7): opt.param_groups[0]["lr"] = 1e-3
        if s % 250 == 0 or s == steps - 1:
            v = evaluate(m, xv, tv); log.append((s, float(loss), v))
            print(f"H{H} L{L} stage1 step {s} train {float(loss):.4f} val {v:.4f} ({time.time() - t0:.0f} s)", flush=True)
    v1 = evaluate(m, xv, tv)
    m.engine = True; v_swap = evaluate(m, xv, tv, 3.0)
    print(f"H{H} L{L} swap to engine activations: val {v_swap:.4f}", flush=True)
    opt = torch.optim.Adam(m.parameters(), 1e-3); fsteps = int(os.environ.get("FT_STEPS", "600"))
    for s in range(fsteps):                                      # stage 2: engine activations
        xb, tb = batches(xt, tt, 768 + 256, 24, rng)
        y = m(xb); loss = ((y[:, 256:] - tb[:, 256:]) ** 2).mean() / (tb[:, 256:] ** 2).mean()
        opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step()
        if s == int(fsteps * 0.7): opt.param_groups[0]["lr"] = 3e-4
        if s % 100 == 0 or s == fsteps - 1: print(f"H{H} L{L} stage2 step {s} train {float(loss):.4f} ({time.time() - t0:.0f} s)", flush=True)
    v2 = evaluate(m, xv, tv, 3.0)
    res = dict(H=H, L=L, val_stage1=v1, val_swap=v_swap, val_engine=v2, seconds=time.time() - t0, log=log)
    print(f"RESULT H{H} L{L}: torch-LSTM ESR {v1:.4f}, engine activations ESR {v2:.4f}", flush=True)
    base = os.path.join(RE, "logs", f"lstm_H{H}_L{L}"); torch.save(m.state_dict(), base + ".pt")
    json.dump(res, open(base + ".json", "w"), indent=1)


def make_target():
    import namfit
    x, y = namfit.reference(NAM, 1e9)
    y.astype("<f4").tofile(TGT); print("target written", len(y) / FS, "s", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "target": make_target()
    else: train(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else 3000)
