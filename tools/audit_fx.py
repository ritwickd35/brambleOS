#!/usr/bin/env python3
"""Effect quality audit, part 2: modulation, wah/comp/boost, pitch, delay, reverb, EQ, gate (each alone, defaults)
and the remaining amps (via audit.py's signal). P08 is the scratch preset and is restored byte-identically.

  audit_fx.py run           record everything (about 55 min)
  audit_fx.py report        analyse the recordings in audio/audit-fx/

Effects signal (no sync burst: its echoes would spoil the click response):
  0 click (time anchor for echoes/decay) | 0-4 tail | 4.2-8.2 440 Hz -18 dBFS (anchor for the rest: its onset)
  8.4-12.4 noise -30 dBFS | 12.6-14.6 440 Hz at -40/-30/-20/-12 dBFS (0.5 s each) | 15.0-27.0 DI guitar (peaks -12 dBFS)
"""
import json, os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import audit as A
FS = 44100
OUT = os.path.join(RE, "audio", "audit-fx" + A.TAG)
LOG = os.path.join(RE, "logs", f"audit-fx{A.TAG}.log")
DUR = 27.6
T_CLICK, T_TONE, T_NOISE, T_STEPS, T_DI = 0.0, 4.2, 8.4, 12.6, 15.0
STEPS = (-40, -30, -20, -12)
GROUPS = {"FX1": 1, "FX2": 6, "DLY": 7, "RVB": 8, "EQ": 5, "NR": 0}
MORE_AMPS = ["B-Man N", "Jazz 120", "Brit 45", "Brit 50JP", "B-Man B", "Voks 30TB", "Sol 100 OD", "Dizzy VH", "Eng 120",
             "Halen 51", "Calif DualV", "Eng Power", "Flyman B1+", "Bog XT", "A BassVT", "Voks Bass"]


def log(*a):
    s = time.strftime("%H:%M:%S ") + " ".join(str(v) for v in a)
    print(s, flush=True); open(LOG, "a").write(s + "\n")


def effects():
    d = json.load(open(A.JSON))["modules"]; out = []
    for m in d:
        if m["name"] not in GROUPS: continue
        for e in m["module"]:
            if m["name"] == "FX2" and e["name"] not in ("Octave", "Pitch", "Detune"): continue
            p = [0.0] * 8
            for a in e["alg"]: p[int(a["algId"])] = float(a["defaultValue"])
            fx = int(e["fxid"]) if isinstance(e["fxid"], int) else int(e["fxid"], 0)
            out.append((m["name"], GROUPS[m["name"]], e["name"], fx, p))
    return out


_SIG = None


def signal():
    global _SIG
    if _SIG is not None: return _SIG
    n = int(DUR * FS); x = np.zeros(n); t = np.arange(n) / FS
    def seg(t0, t1, y):
        k0, k1 = int(t0 * FS), int(t1 * FS); w = np.ones(k1 - k0); r = int(0.005 * FS)
        w[:r] = np.linspace(0, 1, r); w[-r:] = np.linspace(1, 0, r); x[k0:k1] = y[k0:k1] * w
    x[0] = 0.5
    seg(T_TONE, T_TONE + 4.0, 10 ** (-18 / 20) * np.sin(2 * np.pi * 440 * t))
    rng = np.random.default_rng(7); nz = rng.standard_normal(n); nz *= 10 ** (-30 / 20) / np.std(nz)
    seg(T_NOISE, T_NOISE + 4.0, nz)
    for i, L in enumerate(STEPS):
        seg(T_STEPS + 0.5 * i, T_STEPS + 0.5 * i + 0.48, 10 ** (L / 20) * np.sin(2 * np.pi * 440 * t))
    d = A.di_clip(); k = int(T_DI * FS); x[k:k + len(d)] = d[:n - k]
    _SIG = (x, nz); return _SIG


# ------------------------------------------------------------------ analysis
def env(s, win=0.005):
    w = int(win * FS); n = len(s) // w; return np.sqrt(np.mean(s[:n * w].reshape(n, w) ** 2, 1))


def modulation(s):
    """Amplitude modulation (dB peak-to-peak, rate) and pitch modulation (cents p-p) of a steady 440 Hz tone."""
    e = env(s, 0.005); e = e[20:-20]; edb = 20 * np.log10(e + 1e-9)
    am = float(np.percentile(edb, 98) - np.percentile(edb, 2))
    E = np.abs(np.fft.rfft(edb - edb.mean(), 8 * len(edb))); fr = np.fft.rfftfreq(8 * len(edb), 0.005)
    band = (fr > 0.2) & (fr < 20); rate = float(fr[band][np.argmax(E[band])]) if am > 1 else 0.0
    zc = np.where((s[:-1] < 0) & (s[1:] >= 0))[0]
    if len(zc) > 100:
        fr0 = s[zc] / (s[zc] - s[zc + 1]); tz = (zc + fr0) / FS; f_inst = 1 / np.diff(tz)
        k = int(len(f_inst) * 0.05); f_inst = np.sort(f_inst)[k:-k] if k else f_inst
        fm = float(1200 * np.log2(f_inst.max() / f_inst.min()))
    else:
        fm = float("nan")
    return dict(am_db=round(am, 1), am_rate_hz=round(rate, 2), fm_cents=round(fm, 1))


def spurious(s, f0=440.0):
    """Energy not at harmonics of f0 and not within 60 Hz of them (modulation sidebands), dB re total."""
    f, X = A.spectrum(s); harm = np.zeros_like(f, bool)
    for k in range(1, 46): harm |= np.abs(f - k * f0) < 60
    use = (f > 40) & (f < 16000)
    return round(float(10 * np.log10(X[~harm & use].sum() / X[use].sum() + 1e-15)), 1)


def pitch_out(s):
    f, X = A.spectrum(s); idx = np.argsort(X)[::-1]; pk = []
    for j in idx:
        if f[j] < 50: continue
        if all(abs(f[j] - p) > 15 for p, _ in pk): pk.append((round(float(f[j]), 1), round(float(10 * np.log10(X[j] / X.max())), 1)))
        if len(pk) == 4: break
    return pk


def impulse(y, t0):
    """Click response: echoes (delay) / decay time (reverb)."""
    h = A.piece(y, t0, T_CLICK - 0.01, T_CLICK + 3.9)
    e = env(h, 0.002); edb = 20 * np.log10(e / (e.max() + 1e-12) + 1e-9)
    pk = []
    for i in range(1, len(edb) - 1):
        if edb[i] > -40 and edb[i] >= edb[i - 1] and edb[i] > edb[i + 1] and all(abs(i - j) > 25 for j, _ in pk):
            pk.append((i, edb[i]))
    pk = sorted(pk, key=lambda x: -x[1])[:6]; pk = sorted(pk)
    echoes = [(round(i * 0.002 - 0.01, 3), round(float(v), 1)) for i, v in pk]
    sch = np.cumsum((h ** 2)[::-1])[::-1]; sch = 10 * np.log10(sch / sch[0] + 1e-12)
    i5 = np.argmax(sch < -5); i25 = np.argmax(sch < -25)
    rt60 = float((i25 - i5) / FS * 3) if i25 > i5 else float("nan")
    tail = h[int(0.3 * FS):int(1.3 * FS)]
    if np.std(tail) > 1e-5:
        f, X = A.spectrum(tail); Xs = np.convolve(X, np.ones(40) / 40, "same"); band = (f > 200) & (f < 8000)
        ring = float(10 * np.log10(np.max(X[band] / (Xs[band] + 1e-20))))
    else:
        ring = float("nan")
    return dict(echoes=echoes, rt60_s=round(rt60, 2), ringing_db=round(ring, 1))


def comp_curve(y, t0):
    return [round(float(20 * np.log10(np.std(A.piece(y, t0, T_STEPS + 0.5 * i + 0.15, T_STEPS + 0.5 * i + 0.45)) * np.sqrt(2) + 1e-9)), 1)
            for i in range(len(STEPS))]


def response(y, t0, nz):
    k0 = int(T_NOISE * FS); ref = nz[k0 + int(0.2 * FS):k0 + int(3.8 * FS)]
    seg = y[int((t0 + T_NOISE - 0.1) * FS):int((t0 + T_NOISE + 4.0) * FS)]
    c = np.abs(np.fft.irfft(np.fft.rfft(seg, 2 * len(seg)) * np.conj(np.fft.rfft(ref, 2 * len(seg)))))
    lag = int(np.argmax(c[:int(0.6 * FS)])); out = seg[lag:lag + len(ref)]
    if len(out) < len(ref): return None
    nf = 4096; win = np.hanning(nf); Pxx = 0; Pxy = 0
    for i in range(0, len(ref) - nf, nf // 2):
        a = np.fft.rfft(ref[i:i + nf] * win); b = np.fft.rfft(out[i:i + nf] * win)
        Pxx = Pxx + np.abs(a) ** 2; Pxy = Pxy + b * np.conj(a)
    H = np.abs(Pxy) / (Pxx + 1e-20); f = np.fft.rfftfreq(nf, 1 / FS)
    v = {b: float(20 * np.log10(np.mean(H[(f > b / 1.414) & (f < b * 1.414)]) + 1e-12)) for b in (63, 125, 250, 500, 1000, 2000, 4000, 8000)}
    return {b: round(v[b] - v[1000], 1) for b in v}


def anchors(y):
    """t0 from the onset of the 440 Hz tone (first 5 ms window above 30 % of the loud part, searched from 2.5 s);
    tc = the click: largest sample in the 1.5 s before t0 + T_TONE - 4.2 + 0.6."""
    e = env(y, 0.005); i0 = int(2.5 / 0.005); seg = e[i0:i0 + int(7 / 0.005)]
    thr = 0.3 * np.percentile(seg, 98); on = i0 + int(np.argmax(seg > thr))
    t0 = on * 0.005 - T_TONE
    a, b = int(max(t0 - 0.9, 0) * FS), int((t0 + 0.6) * FS)
    tc = (a + int(np.argmax(np.abs(y[a:b])))) / FS if b > a else t0
    return t0, tc


def analyse_fx(path):
    import pmloadtest as L
    x, nz = signal(); y = L.load(path); t0, tc = anchors(y)
    tone = A.piece(y, t0, T_TONE + 0.3, T_TONE + 3.9)
    return dict(t0=round(t0, 3), tc=round(tc, 3), noise_dbfs=round(float(20 * np.log10(np.std(A.piece(y, tc, -0.9, -0.15)) + 1e-9)), 1),
                level_db=round(float(20 * np.log10(np.std(tone) * np.sqrt(2) + 1e-9)), 1),
                mod=modulation(tone), spurious_db=spurious(tone), pitch=pitch_out(tone),
                impulse=impulse(y, tc), comp=comp_curve(y, t0), eq=response(y, t0, nz))


# ------------------------------------------------------------------ pedal run
def run():
    import sounddevice as sd, pmaudio
    from pmflash import Link
    from cut1_variants import read_p, describe
    from cut1_matrix import send, set_mod, get_mod
    if any(".app/Contents/MacOS/Sonicake" in l for l in os.popen("ps ax").read().splitlines()):
        sys.exit("Sonicake Manager is running; close it first")
    os.makedirs(OUT, exist_ok=True); open(LOG, "a").write("\n"); log("fx audit started")
    link = Link(); orig = read_p(link); link.close()
    base = orig
    for m in range(10): base = set_mod(base, m, on=False)
    ir = get_mod(orig, 4)
    jobs = [("bypass", "fx", base)]
    if os.environ.get("AUDIT_SET") == "cfw-new":
        # the CFW's own additions (fxids the stock DB does not have), with the CFW DB's default knob values;
        # FX2 copies of the FX1 Smart Box modulations are skipped (same code)
        import cfwdb
        for e in cfwdb.new_in_cfw():
            if e["group"] == "FX2": continue
            if e["group"] == "AMP":
                r = set_mod(base, 3, e["fxid"], e["params"], True)
                jobs.append((f"AMP {e['name']} (alone)", "amp", r))
                jobs.append((f"AMP {e['name']} + cab", "amp", set_mod(r, 4, ir[0], ir[1], True)))
            else:
                jobs.append((f"{e['group']} {e['name']}", "fx", set_mod(base, e["module"], e["fxid"], e["params"], True)))
    elif os.environ.get("AUDIT_ONLY"):                       # e.g. AUDIT_ONLY="FX2 Octave,FX2 Pitch"
        want = os.environ["AUDIT_ONLY"].split(",")
        for grp, m, name, fx, p in effects():
            if f"{grp} {name}" in want: jobs.append((f"{grp} {name}", "fx", set_mod(base, m, fx, p, True)))
    else:
        for grp, m, name, fx, p in effects():
            jobs.append((f"{grp} {name}", "fx", set_mod(base, m, fx, p, True)))
        for n in MORE_AMPS:
            fx, p = A.defaults(n)
            jobs.append((f"AMP {n} (alone)", "amp", set_mod(base, 3, fx, p, True)))
            jobs.append((f"AMP {n} + cab", "amp", set_mod(set_mod(base, 3, fx, p, True), 4, ir[0], ir[1], True)))
    sig_fx = signal()[0]; sig_amp = A.signal()[0]
    dev = pmaudio.out_device(os.environ.get("AUDIT_OUT", "External Headphones"))
    try:
        for i, (label, kind, rec) in enumerate(jobs, 1):
            log(f"run {i}/{len(jobs)}: {label}  (on: {describe(rec) or 'nothing'})")
            send(rec); time.sleep(2.0)
            sig = sig_fx if kind == "fx" else sig_amp; dur = (DUR if kind == "fx" else A.DUR) + 3.5
            path = os.path.join(OUT, f"{i:02d} {label}.wav".replace("/", "-"))
            p = pmaudio.record(path, dur); time.sleep(1.0)   # 1 s of silence before the click
            sd.play(np.stack([sig, sig], 1).astype(np.float32), samplerate=FS, device=dev); p.wait(); sd.stop()
    finally:
        send(orig); time.sleep(0.5)
        link = Link(); back = read_p(link); link.close()
        log("P08 restored:", "OK (byte-identical)" if back[4:] == orig[4:] else "MISMATCH")


def report():
    import audit_report as R
    rows = []
    for f in sorted(os.listdir(OUT)):
        if not f.endswith(".wav"): continue
        p = os.path.join(OUT, f)
        try:
            d = dict(file=f, **(R.one(p) if " AMP " in f" {f[3:]}" else analyse_fx(p)))
        except Exception as e:
            d = dict(file=f, error=str(e))
        rows.append(d); print(json.dumps(d, default=str))
    json.dump(rows, open(os.path.join(RE, "cut1", f"audit-fx-report{A.TAG}.json"), "w"), indent=1, default=str)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["run"]: run()
    elif a == ["report"]: report()
    else: sys.exit(__doc__)
