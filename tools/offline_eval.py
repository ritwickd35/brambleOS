#!/usr/bin/env python3
"""Offline evaluation of our own effects (dsp/host) with the same test signal and metrics as the pedal audit.
  offline_eval.py ds1 <dist> <tone> <level>      harshness, gain ramp, tone shape, writes audio/offline/*.wav
  offline_eval.py gate <thr> <decay> <range>     gate behaviour on a decaying note in noise
Input scaling: the pedal's DSP sees our test signal about +9 dB hotter than the Mac plays it (probe: 0.1 -> 0.287)."""
import os, subprocess, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import audit as A
FS = 44100; IN_GAIN = 2.87
HOST = os.path.join(RE, "dsp", "host")
OUT = os.path.join(RE, "audio", "offline")


def run(effect, knobs, x):
    p = subprocess.run([HOST, effect] + [str(k) for k in knobs], input=x.astype("<f4").tobytes(), capture_output=True, check=True)
    return np.frombuffer(p.stdout, "<f4").astype(np.float64)


def save(name, y):
    import pmaudio
    os.makedirs(OUT, exist_ok=True)
    s = y / (np.max(np.abs(y)) + 1e-9) * 0.7
    pmaudio.save(os.path.join(OUT, name), np.stack([s, s], 1))


def eval_drive(effect, knobs, tag=None):
    x, nz = A.signal(); y = run(effect, knobs, x * IN_GAIN)
    t0 = 0.0
    harsh = {f: round(A.harshness(A.piece(y, t0, A.T_TONE + i + 0.15, A.T_TONE + i + 0.85), f), 1) for i, f in enumerate(A.TONES)}
    ramp = []
    for i, L in enumerate(A.LEVELS):
        s = A.piece(y, t0, A.T_RAMP + i * 0.75 + 0.15, A.T_RAMP + i * 0.75 + 0.65)
        ramp.append((L, round(float(20 * np.log10(np.std(s) * np.sqrt(2) + 1e-12)), 1), round(A.thd(s), 1)))
    # tone shape: compare output noise segment with input noise segment (small signal)
    k0 = int(A.T_NOISE * FS); ref = nz[k0 + int(0.2 * FS):k0 + int(4.8 * FS)]
    out = y[k0 + int(0.2 * FS):k0 + int(4.8 * FS)]
    nf = 4096; w = np.hanning(nf); Pxx = 0; Pxy = 0
    for i in range(0, len(ref) - nf, nf // 2):
        a = np.fft.rfft(ref[i:i + nf] * w); b = np.fft.rfft(out[i:i + nf] * w); Pxx = Pxx + abs(a) ** 2; Pxy = Pxy + b * np.conj(a)
    H = np.abs(Pxy) / (Pxx + 1e-20); f = np.fft.rfftfreq(nf, 1 / FS)
    bands = {b: float(20 * np.log10(np.mean(H[(f > b / 1.414) & (f < b * 1.414)]) + 1e-12)) for b in (125, 250, 500, 1000, 2000, 4000, 8000)}
    tone = {b: round(v - bands[1000], 1) for b, v in bands.items()}
    d = A.di_clip() * IN_GAIN; yd = run(effect, knobs, d)
    save(f"{tag or effect}-{'-'.join(str(k) for k in knobs)}.wav", yd)
    return dict(harsh=harsh, ramp=ramp, tone=tone)


def eval_gate(knobs):
    """Plucked note decaying into -80 dBFS noise plus hum: report noise attenuation, how long the tail survives,
    and how often the gain direction flips (chatter)."""
    rng = np.random.default_rng(3); n = 4 * FS; t = np.arange(n) / FS
    note = 0.5 * np.exp(-t / 0.6) * np.sin(2 * np.pi * 196 * t) * (t < 3.0)
    noise = 10 ** (-75 / 20) * rng.standard_normal(n) * 3 + 10 ** (-70 / 20) * np.sin(2 * np.pi * 50 * t)
    x = np.concatenate([noise[:FS], note + noise])
    y = run("gate", knobs, x)
    w = 441; m = len(x) // w
    rx = np.sqrt(np.mean(x[:m * w].reshape(m, w) ** 2, 1)); ry = np.sqrt(np.mean(y[:m * w].reshape(m, w) ** 2, 1))
    gdb = np.repeat(20 * np.log10(ry / (rx + 1e-15) + 1e-9), w)
    pre = float(np.median(gdb[int(0.2 * FS):int(0.9 * FS)]))
    open_db = float(np.median(gdb[int(1.05 * FS):int(1.5 * FS)]))
    tail = np.where(gdb[FS:] < -6)[0]; close_t = float(tail[tail > int(0.3 * FS)][0] / FS) if np.any(tail > int(0.3 * FS)) else None
    note_db_at_close = float(20 * np.log10(0.5 * np.exp(-close_t / 0.6) + 1e-12)) if close_t else None
    closed = gdb[int(4.4 * FS):int(4.95 * FS):w]
    flips = round(float(np.std(closed)), 2)          # gain wobble (dB, std) while closed on noise
    save(f"gate-{'-'.join(str(k) for k in knobs)}.wav", y)
    return dict(noise_atten_db=round(pre, 1), open_gain_db=round(open_db, 2), closes_after_s=close_t,
                note_level_at_close_db=None if note_db_at_close is None else round(note_db_at_close, 1), closed_gain_wobble_db=flips)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "gate": print(eval_gate([float(v) for v in a[1:4]]))
    elif a: r = eval_drive(a[0], [float(v) for v in a[1:]]); [print(k, v) for k, v in r.items()]
    else: sys.exit(__doc__)
