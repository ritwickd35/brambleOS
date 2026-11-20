#!/usr/bin/env python3
"""Tiny-WaveNet experiment: how good can a capture model be that fits the engine (16 KB data RAM, ~25-60k MACs
per 64-sample block)? Trains small WaveNets (distillation) to imitate a full NAM model on a real guitar DI.
  tinynet.py <file.nam> [seconds]
Prints held-out ESR, MACs per sample, weights, and history floats for each configuration."""
import os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import torch
import namfit as F


class Tiny(torch.nn.Module):
    """NAM-style WaveNet block: per layer z = act(dilated conv(h) + mix(x)); h += 1x1(z); head = sum z -> linear."""
    def __init__(self, ch, k, dil, act="tanh"):
        super().__init__()
        self.ch, self.k, self.dil = ch, k, dil
        self.inp = torch.nn.Conv1d(1, ch, 1, bias=False)
        self.conv = torch.nn.ModuleList([torch.nn.Conv1d(ch, ch, k, dilation=d) for d in dil])
        self.mix = torch.nn.ModuleList([torch.nn.Conv1d(1, ch, 1, bias=False) for _ in dil])
        self.res = torch.nn.ModuleList([torch.nn.Conv1d(ch, ch, 1) for _ in dil])
        self.head = torch.nn.Conv1d(ch, 1, 1)
        self.act = torch.tanh
        self.rf = 1 + sum((k - 1) * d for d in dil)

    def forward(self, x):                       # x: (N,) -> (N,), causal
        x = x[None, None, :]; h = self.inp(x); head = 0
        for c, m, r, d in zip(self.conv, self.mix, self.res, self.dil):
            pad = (self.k - 1) * d
            z = self.act(c(torch.nn.functional.pad(h, (pad, 0))) + m(x))
            head = head + z; h = h + r(z)
        return self.head(head)[0, 0]

    def cost(self):
        L = len(self.dil); ch, k = self.ch, self.k
        macs = ch + L * (ch * ch * k + ch + ch * ch) + ch
        weights = sum(p.numel() for p in self.parameters())
        hist = sum((k - 1) * d * ch for d in self.dil)
        return macs, weights, hist


def train(m, X, T, XV, TV, steps):
    opt = torch.optim.Adam(m.parameters(), lr=1e-3); seg = 8192 + m.rf
    for s in range(steps):
        i = np.random.randint(0, len(X) - seg); y = m(X[i:i + seg])
        loss = torch.sum((y[m.rf:] - T[i + m.rf:i + seg]) ** 2) / torch.sum(T[i + m.rf:i + seg] ** 2)
        opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(m.parameters(), 0.5); opt.step()
        if s in (steps // 2, 4 * steps // 5):
            for g in opt.param_groups: g["lr"] *= 0.3
    with torch.no_grad():
        y = m(XV); return F.esr(y[m.rf:], TV[m.rf:])


def main():
    path = sys.argv[1]; secs = float(sys.argv[2]) if len(sys.argv) > 2 else 60
    steps = int(os.environ.get("TINY_STEPS", "3000"))
    x, y = F.reference(path, secs); sp = int(0.75 * len(x))
    X, T, XV, TV = map(torch.tensor, (x[:sp], y[:sp], x[sp:], y[sp:]))
    torch.manual_seed(0); np.random.seed(0)
    cfgs = [] if os.environ.get("TINY_ONLY") else []
    cfgs = [("4ch k3 d1-32", 4, 3, [1, 2, 4, 8, 16, 32]),
            ("6ch k3 d1-64", 6, 3, [1, 2, 4, 8, 16, 32, 64]),
            ("8ch k3 d1-64", 8, 3, [1, 2, 4, 8, 16, 32, 64]),
            ("8ch k3 d1-128 x2", 8, 3, [1, 2, 4, 8, 16, 32, 64, 128] * 2)]
    if os.environ.get("TINY_ONLY"): cfgs = [c for c in cfgs if c[0] in os.environ["TINY_ONLY"].split(",")]
    print(f"{'model':18s} {'ESR':>7s} {'MAC/smp':>8s} {'MAC/blk':>8s} {'weights':>8s} {'history':>8s}  (data RAM floats total)")
    for name, ch, k, dil in cfgs:
        m = Tiny(ch, k, dil); t0 = time.time(); e = train(m, X, T, XV, TV, steps); mac, w, h = m.cost()
        print(f"{name:18s} {e:7.4f} {mac:8d} {mac * 64:8d} {w:8d} {h:8d}  {w + h + 128:6d}   ({time.time() - t0:.0f} s)", flush=True)
        torch.save(m.state_dict(), os.path.join(RE, "cut1", f"tiny-{name.replace(' ', '_')}.pt"))


if __name__ == "__main__":
    main()
