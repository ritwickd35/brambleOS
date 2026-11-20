"""Run any NAM capture on a mono float array: A1 WaveNet (.nam v0.5.x, own numpy forward pass following NAM's
WaveNet: rechannel, dilated conv + input mixer + activation, residual 1x1, head accumulated across arrays,
head_scale) and A2 SlimmableContainer (tools/namref.py). render(path, x, fs) -> y at fs."""
import json
import numpy as np


def _resample(x, a, b):
    n = int(round(len(x) * b / a)); X = np.fft.rfft(x); Y = np.zeros(n // 2 + 1, complex); k = min(len(X), len(Y)); Y[:k] = X[:k]
    return np.fft.irfft(Y, n) * n / len(x)


def _conv(h, w, b, d):
    co, ci, k = w.shape; n = h.shape[1]; out = np.zeros((co, n)) if b is None else np.repeat(b[:, None], n, 1)
    for tap in range(k):
        back = (k - 1 - tap) * d
        if back >= n: continue
        out[:, back:] += w[:, :, tap] @ h[:, :n - back]
    return out


ACT = {"Tanh": np.tanh, "ReLU": lambda z: np.maximum(z, 0), "Sigmoid": lambda z: 1 / (1 + np.exp(-z)),
       "Hardtanh": lambda z: np.clip(z, -1, 1), "LeakyReLU": lambda z: np.where(z >= 0, z, 0.01 * z)}


def wavenet_a1(model, x):
    cfg, w = model["config"], np.asarray(model["weights"], np.float64); pos = [0]
    def take(n): i = pos[0]; pos[0] += n; return w[i:i + n]
    cond = x[None, :]; sig = cond; head = None
    for la in cfg["layers"]:
        c, ci, k, gated = int(la["channels"]), int(la["input_size"]), int(la["kernel_size"]), bool(la.get("gated", False))
        act = ACT[la["activation"]]; mid = 2 * c if gated else c
        h = take(c * ci).reshape(c, ci, 1)[:, :, 0] @ sig
        for d in la["dilations"]:
            cw = take(mid * c * k).reshape(mid, c, k); cb = take(mid)
            mw = take(mid * int(la["condition_size"])).reshape(mid, -1); ow = take(c * c).reshape(c, c); ob = take(c)
            z = _conv(h, cw, cb, int(d)) + mw @ cond
            z = np.tanh(z[:c]) * (1 / (1 + np.exp(-z[c:]))) if gated else act(z)
            head = z if head is None else head + z
            h = h + ow @ z + ob[:, None]
        hs = int(la["head_size"]); hw = take(hs * c).reshape(hs, c); hb = take(hs) if la.get("head_bias") else np.zeros(hs)
        head = hw @ head + hb[:, None]; sig = h
    scale = float(take(1)[0]); assert pos[0] == len(w), (pos[0], len(w))
    return scale * head[0]


def render(path, x, fs=44100.0):
    d = json.load(open(path))
    if d.get("architecture") == "SlimmableContainer":
        import namref as N
        mv, model = N.submodels(d)[-1]; sr = float(model.get("sample_rate", d.get("sample_rate", 48000)) or 48000)
        y = np.asarray(N.WaveNet(model).process(_resample(x, fs, sr))).ravel()
    else:
        sr = float(d.get("sample_rate") or 48000); xr = _resample(x, fs, sr); out = []
        R = 1 + sum((int(la["kernel_size"]) - 1) * sum(la["dilations"]) for la in d["config"]["layers"])
        for i in range(0, len(xr), 480000):                             # chunks with receptive-field overlap
            a = max(0, i - R); out.append(wavenet_a1(d, xr[a:i + 480000])[i - a:])
        y = np.concatenate(out)
    return _resample(y, sr, fs)[:len(x)]
