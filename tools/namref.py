# WaveNet forward pass for NAM models, taken from gp150-htfw (tools/nam2namb.py), MIT License,
# Copyright (c) egorcipa8-debug. Used here only to compute reference outputs offline.
import json
import numpy as np
class WaveNet(object):
    """NAM's WaveNet, offline. Weights are read in the order the C++ core
    flattens them: per layer array a 1x1 rechannel, then for every layer the
    dilated conv (out, in, tap) and its bias, the condition mixin, the 1x1 and
    its bias; then the array's head conv; then head_scale."""

    def __init__(self, model):
        if np is None:
            raise SystemExit("numpy is needed to run a model")
        cfg = model['config']
        w = model['weights']
        self.pos = [0]
        self.arrays = []
        for la in cfg['layers']:
            c = int(la['channels'])
            rech = self._take(w, c * int(la['input_size'])).reshape(c, -1)
            layers = []
            for k, d, act in zip(la['kernel_sizes'], la['dilations'],
                                 la['activation']):
                k, d = int(k), int(d)
                cw = self._take(w, c * c * k).reshape(c, c, k)
                cb = self._take(w, c)
                mw = self._take(w, c * int(la['condition_size'])).reshape(c, -1)
                ow = self._take(w, c * c).reshape(c, c)
                ob = self._take(w, c)
                if act.get('type') != 'LeakyReLU':
                    raise SystemExit("unsupported activation %r" % act.get('type'))
                layers.append((cw, cb, mw, ow, ob, d,
                               float(act.get('negative_slope', 0.01))))
            hd = la['head']
            hk, ho = int(hd['kernel_size']), int(hd['out_channels'])
            hw = self._take(w, ho * c * hk).reshape(ho, c, hk)
            hb = self._take(w, ho) if hd.get('bias') else np.zeros(ho)
            self.arrays.append((rech, layers, hw, hb, c))
        # head_scale is both a config field and the last weight in the vector
        tail = self._take(w, 1)
        self.head_scale = float(cfg['head_scale'])
        if abs(float(tail[0]) - self.head_scale) > 1e-6 * max(1.0, abs(self.head_scale)):
            raise SystemExit("head_scale disagrees: config %g, weights %g"
                             % (self.head_scale, tail[0]))
        self.used, self.total = self.pos[0], len(w)
        if self.used != self.total:
            raise SystemExit("weight layout mismatch: read %d of %d"
                             % (self.used, self.total))

    def _take(self, w, n):
        i = self.pos[0]
        self.pos[0] = i + n
        return np.asarray(w[i:i + n], dtype=np.float64)

    @staticmethod
    def _conv(h, w, b, dilation):
        c_out, _, k = w.shape
        n = h.shape[1]
        out = np.repeat(b[:, None], n, 1)
        for tap in range(k):
            back = (k - 1 - tap) * dilation
            if back >= n:
                continue
            if back:
                out[:, back:] += w[:, :, tap] @ h[:, :n - back]
            else:
                out += w[:, :, tap] @ h
        return out

    def process(self, x):
        cond = x[None, :]
        sig = cond
        y = None
        for rech, layers, hw, hb, c in self.arrays:
            h = rech @ sig
            head = np.zeros((c, sig.shape[1]))
            for cw, cb, mw, ow, ob, d, slope in layers:
                z = self._conv(h, cw, cb, d) + mw @ cond
                z = np.where(z >= 0.0, z, z * slope)
                head += z
                h = h + (ow @ z + ob[:, None])
            y = self._conv(head, hw, hb, 1)
            sig = h
        return (self.head_scale * y)[0]




def load(path):
    with open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def submodels(nam):
    """[(max_value, model)] - a plain capture is one submodel with no limit."""
    if nam.get('architecture') == 'SlimmableContainer':
        return [(float(s.get('max_value', 1.0)), s['model'])
                for s in nam['config']['submodels']]
    return [(1.0, nam)]


def pick(nam, slim):
    """The submodel Suite's converter would choose for this slim factor: the
    first whose max_value is at or above it."""
    subs = submodels(nam)
    for mv, m in subs:
        if slim <= mv:
            return mv, m
    return subs[-1]


