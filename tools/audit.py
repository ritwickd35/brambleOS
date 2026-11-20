#!/usr/bin/env python3
"""Effect quality audit: plays a fixed test signal (Mac headphone jack -> pedal IN) through one effect at a time
and records the pedal's USB output. P08 (index 7) is used as the scratch preset and restored byte-identically.

  audit.py run            all configs (bypass, 7 drives x 2 gains, 6 amps, + clips with amp/cab)
  audit.py analyse <wav>  analyse one recording
  audit.py selftest       offline check of the metrics on synthetic distortion

Test signal (times after the sync burst):
  0.0-0.2  sync burst 1 kHz -12 dBFS        0.2-1.2  silence (noise floor)
  1.2-5.2  tones 2.5/4/6/8 kHz, -12 dBFS (harshness = aliasing)
  5.4-12.15 220 Hz, -54..-6 dBFS in 6 dB steps (how the drive builds up)
  12.4-17.4 low-level noise -40 dBFS (tone shape)   17.8-29.8 synthesised DI guitar (listening clip)
"""
import json, os, struct, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
FS = 44100
TAG = os.environ.get("AUDIT_TAG", "")          # e.g. "-cfw": keeps runs on other firmware apart
OUT = os.path.join(RE, "audio", "audit" + TAG)
LOG = os.path.join(RE, "logs", f"audit{TAG}.log")
JSON = "/Applications/Sonicake Manager.app/Contents/Frameworks/App.framework/Versions/A/Resources/flutter_assets/assets/data/qme10_module_data.json"
TONES = (2500, 4000, 6000, 8000)
LEVELS = list(range(-54, 0, 6))            # 9 steps
T_TONE, T_RAMP, T_NOISE, T_DI = 1.2, 5.4, 12.4, 17.8
DUR = 30.5


def db(x):
    return 20 * np.log10(np.maximum(x, 1e-12))


# ---------------------------------------------------------------- test signal
def karplus(f, dur, bright=0.5, seed=0):
    """Plucked string: noise burst in a delay line with an averaging (low-pass) loop filter."""
    rng = np.random.default_rng(seed)
    n = int(dur * FS); N = max(2, int(round(FS / f)))
    buf = list(np.convolve(rng.uniform(-1, 1, N), [bright, 1 - bright], "same"))
    out = np.zeros(n); i = 0
    for k in range(n):
        j = i + 1 if i + 1 < N else 0
        v = buf[i]; out[k] = v; buf[i] = 0.4985 * (v + buf[j]); i = j
    return out


def di_clip():
    x = np.zeros(int(12 * FS))
    def put(t, f, a, dur=2.5, seed=0):
        s = karplus(f, dur, 0.6, seed) * np.exp(-np.arange(int(dur * FS)) / FS / 1.2)
        k = int(t * FS); m = min(len(s), len(x) - k); x[k:k + m] += a * s[:m]
    E = (82.41, 123.47, 164.81, 207.65, 246.94, 329.63)
    A = (110.0, 164.81, 220.0, 277.18, 329.63)
    seed = 1
    for bar, chord in enumerate((E, A, E, A)):
        for s, f in enumerate(chord):                      # strummed chords, 1.5 s apart
            put(bar * 1.5 + s * 0.012, f, 0.22, 2.5, seed); seed += 1
    lick = (220.0, 261.63, 293.66, 329.63, 392.0, 440.0, 392.0, 329.63, 293.66, 261.63, 220.0, 196.0)
    for i, f in enumerate(lick):                           # single-note line
        put(6.2 + i * 0.4, f, 0.45, 1.2, seed); seed += 1
    put(11.0, 220.0, 0.45, 1.0, seed)
    return 0.25 * x / np.max(np.abs(x))                    # peaks at -12 dBFS (the input path clips between -12 and -6)


_SIG = None


def signal():
    global _SIG
    if _SIG is None:
        _SIG = _signal()
    return _SIG


def _signal():
    n = int(DUR * FS); x = np.zeros(n); t = np.arange(n) / FS
    def seg(t0, t1, y):
        k0, k1 = int(t0 * FS), int(t1 * FS); w = np.ones(k1 - k0); r = int(0.005 * FS)
        w[:r] = np.linspace(0, 1, r); w[-r:] = np.linspace(1, 0, r); x[k0:k1] = y[k0:k1] * w
    seg(0.0, 0.2, 0.25 * np.sin(2 * np.pi * 1000 * t))
    for i, f in enumerate(TONES):
        seg(T_TONE + i, T_TONE + i + 0.95, 0.25 * np.sin(2 * np.pi * f * t))
    for i, L in enumerate(LEVELS):
        seg(T_RAMP + i * 0.75, T_RAMP + i * 0.75 + 0.72, 10 ** (L / 20) * np.sin(2 * np.pi * 220 * t))
    rng = np.random.default_rng(7); nz = rng.standard_normal(n); nz *= 10 ** (-40 / 20) / np.std(nz)
    seg(T_NOISE, T_NOISE + 5.0, nz)
    d = di_clip(); k = int(T_DI * FS); x[k:k + len(d)] = d[:n - k]
    return x, nz


# ---------------------------------------------------------------- analysis
def sync(y):
    """Start of the sync burst: first 5 ms window clearly above the recording's noise."""
    w = 220; n = len(y) // w; env = np.sqrt(np.mean(y[:n * w].reshape(n, w) ** 2, 1))
    s0 = int(0.5 * FS / w)                    # the first ~0.25 s of a PortAudio recording can hold stale audio
    floor = np.median(env[s0:s0 + int(0.3 * FS / w)]) if n > 300 else 0
    thr = max(10 * floor, 0.01 * env.max())
    i = s0 + int(np.argmax(env[s0:] > thr)); return i * w / FS


def piece(y, t0, a, b):
    return y[int((t0 + a) * FS):int((t0 + b) * FS)]


def spectrum(s):
    w = np.hanning(len(s)); X = np.abs(np.fft.rfft(s * w)) ** 2; f = np.fft.rfftfreq(len(s), 1 / FS); return f, X


def harshness(s, f0):
    """Energy at frequencies that are NOT harmonics of f0 (aliasing + noise), relative to the harmonics, in dB.
    The actual f0 is estimated from the peak (the two clocks differ slightly)."""
    f, X = spectrum(s)
    band = (f > f0 * 0.98) & (f < f0 * 1.02)
    f0 = f[band][np.argmax(X[band])]
    harm = np.zeros_like(f, bool)
    for k in range(1, int(20000 / f0) + 1):
        harm |= np.abs(f - k * f0) < 12
    use = (f > 40) & (f < 20000)
    h = X[harm & use].sum(); o = X[~harm & use].sum()
    return float(10 * np.log10(o / h + 1e-15))


def thd(s, f0=220):
    f, X = spectrum(s)
    band = (f > f0 * 0.98) & (f < f0 * 1.02); f0 = f[band][np.argmax(X[band])]
    fund = X[np.abs(f - f0) < 6].sum(); tot = X[(f > 40) & (f < 20000)].sum()
    return float(100 * np.sqrt(max(tot - fund, 0) / (tot + 1e-20)))


def response(y, t0, nz):
    """Tone shape: transfer function from the noise segment, in octave bands, normalised to 1 kHz."""
    k0 = int(T_NOISE * FS); ref = nz[k0 + int(0.2 * FS):k0 + int(4.8 * FS)]
    seg = y[int((t0 + T_NOISE - 0.1) * FS):int((t0 + T_NOISE + 5.0) * FS)]
    c = np.abs(np.fft.irfft(np.fft.rfft(seg, 2 * len(seg)) * np.conj(np.fft.rfft(ref, 2 * len(seg)))))
    lag = int(np.argmax(c[:int(0.6 * FS)])); out = seg[lag:lag + len(ref)]
    if len(out) < len(ref): return None
    nf = 4096; win = np.hanning(nf); Pxx = 0; Pxy = 0
    for i in range(0, len(ref) - nf, nf // 2):
        a = np.fft.rfft(ref[i:i + nf] * win); b = np.fft.rfft(out[i:i + nf] * win)
        Pxx = Pxx + np.abs(a) ** 2; Pxy = Pxy + b * np.conj(a)
    H = np.abs(Pxy) / (Pxx + 1e-20); f = np.fft.rfftfreq(nf, 1 / FS)
    bands = [63, 125, 250, 500, 1000, 2000, 4000, 8000]
    v = {b: float(db(np.mean(H[(f > b / 1.414) & (f < b * 1.414)]))) for b in bands}
    ref1k = v[1000]
    fine = (f > 100) & (f < 8000)
    peak = float(f[fine][np.argmax(H[fine])])
    return dict(bands={b: round(v[b] - ref1k, 1) for b in bands}, peak_hz=round(peak))


def analyse(path, nz=None):
    import pmloadtest as L
    if nz is None: _, nz = signal()
    y = L.load(path); t0 = sync(y)
    noise = float(db(np.std(piece(y, t0, 0.35, 1.1))))
    harsh = {f: round(harshness(piece(y, t0, T_TONE + i + 0.15, T_TONE + i + 0.85), f), 1) for i, f in enumerate(TONES)}
    ramp = []
    for i, Lv in enumerate(LEVELS):
        s = piece(y, t0, T_RAMP + i * 0.75 + 0.15, T_RAMP + i * 0.75 + 0.65)
        ramp.append(dict(in_db=Lv, out_db=round(float(db(np.std(s) * np.sqrt(2))), 1), thd=round(thd(s), 1)))
    return dict(t0=round(t0, 3), noise_dbfs=round(noise, 1), harshness_db=harsh, ramp=ramp, tone=response(y, t0, nz))


def selftest():
    x, nz = signal(); import wave
    def drive(z, os_):
        if os_ > 1:
            from numpy.fft import rfft, irfft
            Z = rfft(z); Zu = np.zeros(len(z) * os_ // 2 + 1, complex); Zu[:len(Z)] = Z * os_
            u = irfft(Zu, len(z) * os_); u = np.tanh(8 * u)
            U = rfft(u)[:len(Z)] / os_; return irfft(U, len(z))
        return np.tanh(8 * z)
    os.makedirs(OUT, exist_ok=True)
    for name, os_ in (("naive", 1), ("oversampled x8", 8)):
        y = np.concatenate([np.zeros(int(0.5 * FS)), drive(x, os_)]) * 0.5 + 1e-5 * np.random.randn(len(x) + int(0.5 * FS))
        p = os.path.join(OUT, "_selftest.wav")
        with wave.open(p, "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(FS)
            q = np.clip(y * 32767, -32768, 32767).astype("<i2"); w.writeframes(np.stack([q, q], 1).tobytes())
        r = analyse(p, nz); print(name, "harshness", r["harshness_db"], "sync", r["t0"])
    os.remove(p)


# ---------------------------------------------------------------- pedal run
def log(*a):
    s = time.strftime("%H:%M:%S ") + " ".join(str(v) for v in a)
    print(s, flush=True); open(LOG, "a").write(s + "\n")


def defaults(name):
    d = json.load(open(JSON))["modules"]
    for m in d:
        for e in m["module"]:
            if e["name"] == name:
                p = [0.0] * 8
                for a in e["alg"]:
                    p[int(a["algId"])] = float(a["defaultValue"])
                return int(e["fxid"]) if isinstance(e["fxid"], int) else int(e["fxid"], 0), p
    raise KeyError(name)


DRIVES = ["Scream", "Butter OD", "JP Dist", "Shark", "Dark Mouse", "Grey Fuzz", "Red Fuzz"]
AMPS = ["TWD Deluxe", "Dark Twin", "Voks 30N", "Brit 800", "Sol 100 LD", "Calif DualM"]


def configs(orig):
    from cut1_matrix import set_mod, get_mod
    base = orig
    for m in range(10):
        base = set_mod(base, m, on=False)
    ir = get_mod(orig, 4)
    out = [("bypass", "bypass", base)]
    for n in DRIVES:
        fx, p = defaults(n)
        out.append((f"{n} (default gain {p[0]:.0f})", "measure", set_mod(base, 2, fx, p, True)))
        q = list(p); q[0] = 100.0
        out.append((f"{n} (gain 100)", "measure", set_mod(base, 2, fx, q, True)))
    for n in AMPS:
        fx, p = defaults(n)
        out.append((f"{n} (amp alone, defaults)", "measure", set_mod(base, 3, fx, p, True)))
    afx, ap = defaults("Dark Twin")
    for n in DRIVES:
        fx, p = defaults(n)
        r = set_mod(set_mod(set_mod(base, 2, fx, p, True), 3, afx, ap, True), 4, ir[0], ir[1], True)
        out.append((f"{n} into Dark Twin + cab", "clip", r))
    for n in AMPS:
        fx, p = defaults(n)
        out.append((f"{n} + cab", "clip", set_mod(set_mod(base, 3, fx, p, True), 4, ir[0], ir[1], True)))
    return out


def run():
    import sounddevice as sd, pmaudio, pmpreset
    from pmflash import Link
    from cut1_variants import read_p, describe
    from cut1_matrix import send
    if any(".app/Contents/MacOS/Sonicake" in l for l in os.popen("ps ax").read().splitlines()):
        sys.exit("Sonicake Manager is running; close it first")
    os.makedirs(OUT, exist_ok=True); open(LOG, "a").write("\n"); log("audit started")
    link = Link(); orig = read_p(link); link.close()
    x, nz = signal(); play = np.stack([x, x], 1).astype(np.float32)
    dev = pmaudio.out_device(os.environ.get("AUDIT_OUT", "External Headphones"))
    res = []
    try:
        for i, (label, kind, rec) in enumerate(configs(orig), 1):
            log(f"run {i}: {label}  (on: {describe(rec) or 'nothing'})")
            send(rec); time.sleep(2.0)
            fn = f"{i:02d} {label}.wav".replace("/", "-")
            path = os.path.join(OUT, fn)
            p = pmaudio.record(path, DUR + 3.5); time.sleep(1.0)   # lead-in before the test signal
            sd.play(play, samplerate=FS, device=dev); p.wait(); sd.stop()
            r = dict(label=label, kind=kind, wav=fn)
            try:
                r.update(analyse(path, nz))
            except Exception as e:
                r["error"] = str(e)
            log("   ", json.dumps({k: r[k] for k in ("noise_dbfs", "harshness_db", "tone") if k in r}))
            res.append(r); json.dump(res, open(os.path.join(RE, "cut1", f"audit-results{TAG}.json"), "w"), indent=1)
    finally:
        send(orig); time.sleep(0.5)
        link = Link(); back = read_p(link); link.close()
        log("P08 restored:", "OK (byte-identical)" if back[4:] == orig[4:] else "MISMATCH")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["run"]: run()
    elif a == ["selftest"]: selftest()
    elif len(a) == 2 and a[0] == "analyse": print(json.dumps(analyse(a[1]), indent=1))
    else: sys.exit(__doc__)
