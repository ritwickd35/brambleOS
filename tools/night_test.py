#!/usr/bin/env python3
"""Overnight failure test for everything we changed. Runs unattended, writes only compact results.
  night_test.py run [rounds]     rounds of: all new drives/amps/cabs/FX2/delays at knob corners + random settings,
                                 full-chain combos, a 3-minute soak, all 50 factory presets
  night_test.py summary          failures per effect (reads logs/night/results.jsonl)
Each take: 3.2 s test sound (silence, 1 kHz burst, loud 220 Hz, noise, guitar phrase, silence).
Checks per take: dead (no output), clipping, DC offset, runaway (tail louder than the playing), NaN/stuck output,
engine/CPU overrun clicks (concentrated at one 64-sample phase), excessive noise in the silent part.
After every effect the plain bypass sound is checked; a dead pedal is re-flashed once (tools/reflash.sh) and logged.
P08 is the scratch preset and is restored at the end."""
import json, os, sys, time, wave, random, subprocess
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
FS = 44100; OUT = os.path.join(RE, "logs", "night"); RES = os.path.join(OUT, "results.jsonl")
BUILD = os.path.join(RE, "build", "dl14"); DB = os.path.join(BUILD, "src", "4_effect_db_presets_00190000.bin")
BIN = os.path.join(BUILD, "PocketMaster_CFW1.0.2+dl14.bin")
DRIVES = {"TS808", "Klon", "DS-1", "FFace", "RAT", "BMuff"}
DELAYS = {"Digital", "Slapback", "EP-3", "DM-2", "Echo+"}
FX2 = {"Octave", "Pitch"}
GRPNAME = {2: "DRV", 3: "AMP", 4: "CAB", 6: "FX2", 7: "DLY"}


def signal():
    rng = np.random.default_rng(11); t = lambda s: np.arange(int(s * FS)) / FS; parts = [np.zeros(int(0.3 * FS))]
    parts.append(0.25 * np.sin(2 * np.pi * 1000 * t(0.4)) * np.hanning(int(0.4 * FS)) ** 0.2)
    parts.append(0.6 * np.sin(2 * np.pi * 220 * t(0.5)))
    parts.append(0.1 * rng.standard_normal(int(0.3 * FS)))
    di = np.fromfile(os.path.join(RE, "audio", "di_reference_44100.f32"), "<f4")[FS:FS + int(1.0 * FS)].astype(float)
    parts.append(0.5 * di / (np.max(np.abs(di)) + 1e-9)); parts.append(np.zeros(int(0.7 * FS)))
    return np.concatenate(parts).astype(np.float32)


SIG = signal(); T_PLAY = (0.3, 2.5); T_QUIET = (0.05, 0.28); T_TAIL = (2.75, 3.2)


def targets():
    import dbrec
    out = []
    for g, i, fx, title, kn in dbrec.records(DB):
        t = title.strip()
        if (g == 2 and t in DRIVES) or g == 3 or (g == 6 and t in FX2) or (g == 7 and t in DELAYS):
            out.append(dict(group=g, idx=i, fx=fx, name=f"{GRPNAME[g]} {t}", knobs=[(n.strip(), df, mx, j, mn) for n, df, mx, j, mn in kn if j < 8]))
    import struct
    cb = open(os.path.join(BUILD, "src", "2_cab_catalog_00280000.bin"), "rb").read()      # factory cabs (catalog records)
    for r in range(26):
        k = struct.unpack_from("<I", cb, 72 * r + 20)[0] - 167772160; nm = cb[72 * r + 24:72 * r + 38].split(b"\0")[0].decode(errors="replace")
        if 0 < k < 0x100000: out.append(dict(group=4, idx=r, fx=167772160 + k, name=f"CAB {nm}", knobs=[("VOL", 50.0, 100.0, 0, 0.0)]))
    return out


def settings(e, rng, n_random):
    base = [0.0] * 8
    for n, df, mx, j, mn in e["knobs"]: base[j] = df
    yield "default", list(base)
    for n, df, mx, j, mn in e["knobs"]:
        if n in ("Trail", "Sync"): continue
        for v in (mn, mx):
            p = list(base); p[j] = v; yield f"{n}={v:g}", p
    for k in range(n_random):
        p = list(base)
        for n, df, mx, j, mn in e["knobs"]:
            if n == "Trail": continue
            p[j] = float(rng.choice([mn, mx])) if mx - mn <= 1 else round(float(rng.uniform(mn, mx)), 1)
        if e["group"] == 7 and rng.random() < 0.3: p[1] = float(rng.choice([250.0, 500.0, 1000.0, 20.0]))   # note values
        yield f"random{k}", p


def analyse(y, delayish=False, gainy=False):
    m = y.mean(1); seg = lambda a, b: m[int(a * FS):int(b * FS)]
    play, quiet, tail = seg(*T_PLAY), seg(*T_QUIET), seg(*T_TAIL)
    db = lambda s: float(20 * np.log10(np.sqrt(np.mean(s ** 2)) + 1e-12))
    lp, lq, lt = db(play), db(quiet), db(tail); f = []
    if not np.all(np.isfinite(y)): f.append("nan")
    if lp < -75: f.append("dead")
    if np.mean(np.abs(y) > 0.985) > 0.002: f.append("clipping")
    if abs(float(np.mean(play))) > 0.05: f.append("dc")
    if lt > lp + 3 and not delayish: f.append("runaway")
    if delayish and lt > lp + 6: f.append("runaway")
    if np.std(np.diff(play)) < 1e-6 and lp > -75: f.append("stuck")
    d = np.abs(np.diff(play)); big = np.where(d > 8 * np.percentile(d, 99.5))[0]
    if len(big) > 20 and np.bincount(big % 64, minlength=64).max() > 0.4 * len(big): f.append("overrun_clicks")
    if lt > (-25 if gainy else -45) and not delayish: f.append("noisy")   # drives/amps: input hum x gain; originals measure -31..-44 dB at Gain 100              # trailing silence (the start can hold stale audio)
    return f, dict(play=round(lp, 1), quiet=round(lq, 1), tail=round(lt, 1))


class Rig:
    def __init__(self):
        import sounddevice as sd, pmaudio
        from pmflash import Link
        from cut1_variants import read_p
        from cut1_matrix import send, set_mod
        self.sd, self.pa, self.Link, self.read_p, self.send, self.set_mod = sd, pmaudio, Link, read_p, send, set_mod
        self.dev = pmaudio.out_device("External Headphones")
        l = Link(); self.orig = read_p(l); l.close(); self.base = self.orig
        for k in range(10): self.base = set_mod(self.base, k, on=False)

    def take(self, rec, secs=None):
        self.send(rec); time.sleep(1.2); path = f"/tmp/night-{os.getpid()}.wav"; x = SIG if secs is None else np.tile(SIG, int(secs / 3.2) + 1)
        for attempt in range(3):                       # a failed recording must never fall back to an old file
            if os.path.exists(path): os.remove(path)
            p = self.pa.record(path, len(x) / FS + 0.6); time.sleep(0.25)
            self.sd.play(np.stack([x, x], 1), samplerate=FS, device=self.dev); p.wait(); self.sd.stop()
            if os.path.exists(path): break
            self.sd._terminate(); time.sleep(2); self.sd._initialize(); self.dev = self.pa.out_device("External Headphones")
        else:
            raise RuntimeError("recording failed 3 times (audio device lost)")
        w = wave.open(path); y = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2).astype(float) / 32768
        e = np.convolve(np.abs(y[:, 0]), np.ones(220) / 220, "same"); i = int(np.argmax(e > 0.3 * e[:int(1.5 * FS)].max())) if e[:int(1.5 * FS)].max() > 1e-4 else int(0.55 * FS)
        return y[max(i - int(0.3 * FS), 0):]

    def alive(self):
        y = self.take(self.base); return float(20 * np.log10(np.std(y[int(0.9 * FS):int(1.3 * FS)].mean(1)) + 1e-12)) > -60

    def restore(self):
        self.send(self.orig); time.sleep(0.5); l = self.Link(); b = self.read_p(l); l.close(); return b[4:] == self.orig[4:]


def log(row):
    open(RES, "a").write(json.dumps(row) + "\n")


PAUSE, PAUSED = os.path.join(OUT, "PAUSE"), os.path.join(OUT, "PAUSED")


def gate(rig):
    """pause point: if logs/night/PAUSE exists, restore P08, signal PAUSED and wait until PAUSE is removed
    (tools/night_ctl.sh pause|resume). Returns a fresh rig after a pause (the pedal may have been re-flashed)."""
    if not os.path.exists(PAUSE): return rig
    rig.restore(); open(PAUSED, "w").write(time.strftime("%H:%M:%S"))
    while os.path.exists(PAUSE): time.sleep(5)
    os.remove(PAUSED); time.sleep(3); return Rig()


def done_keys():
    if not os.path.exists(RES): return set()
    return {(r["round"], r["effect"], r["setting"]) for r in map(json.loads, open(RES))}


def main_run(rounds):
    os.makedirs(OUT, exist_ok=True); rig = Rig(); tg = targets(); events = os.path.join(OUT, "events.log")
    ev = lambda s: open(events, "a").write(time.strftime("%H:%M:%S ") + s + "\n")
    done = done_keys(); ev(f"start: {len(tg)} effects, {rounds} rounds, {len(done)} takes already done (resume)")
    amp_fx = [e["fx"] for e in tg if e["group"] == 3]; cab_fx = [e["fx"] for e in tg if e["group"] == 4]
    drv_fx = [e["fx"] for e in tg if e["group"] == 2]; dly_fx = [e["fx"] for e in tg if e["group"] == 7]
    try:
        for rnd in range(rounds):
            rng = np.random.default_rng(1000 + rnd)
            for e in tg:
                for label, p in settings(e, rng, 4 if e["group"] != 4 else 0):
                    if e["group"] == 4 and label != "default" and not label.startswith("VOL"): continue
                    if (rnd, e["name"], label) in done: continue
                    rig = gate(rig)
                    rec = rig.set_mod(rig.base, e["group"], e["fx"], p, True)
                    if e["group"] == 4: rec = rig.set_mod(rec, 3, amp_fx[7], [50.0] * 8, True)     # cab behind an amp
                    try: f, lv = analyse(rig.take(rec), e["group"] == 7, e["group"] in (2, 3))
                    except Exception as x: f, lv = ["take_error"], {"err": str(x)[:60]}
                    log(dict(round=rnd, effect=e["name"], setting=label, params=p, fail=f, **lv))
                if not rig.alive():
                    subprocess.run(["osascript", "-e", "set volume output volume 100 without output muted"])   # the Mac output got muted once
                    time.sleep(1)
                if not rig.alive():
                    ev(f"pedal not passing audio after {e['name']} -> re-flash")
                    subprocess.run(["sh", os.path.join(HERE, "reflash.sh"), BIN], capture_output=True)
                    log(dict(round=rnd, effect=e["name"], setting="AFTER", fail=["pedal_died"]))
                    rig = Rig()
            for k in range(25):                                             # full chains: drive + amp + cab + delay
                if (rnd, "CHAIN", f"chain{k}") in done: rng.random(); continue
                rig = gate(rig)
                rec = rig.set_mod(rig.base, 2, int(rng.choice(drv_fx)), [float(rng.uniform(0, 100)) for _ in range(3)] + [0] * 5, True)
                rec = rig.set_mod(rec, 3, int(rng.choice(amp_fx)), [float(rng.uniform(0, 100)) for _ in range(8)], True)
                rec = rig.set_mod(rec, 4, int(rng.choice(cab_fx)), [50.0] + [0.0] * 7, True)
                rec = rig.set_mod(rec, 7, int(rng.choice(dly_fx)), [float(rng.uniform(10, 60)), float(rng.uniform(80, 900)), float(rng.uniform(10, 70)), 0, 0, 25, 0, 0], True)
                f, lv = analyse(rig.take(rec), True); log(dict(round=rnd, effect="CHAIN", setting=f"chain{k}", fail=f, **lv))
            if (rnd, "SOAK 3 min", "TS808+5150+V30+EP-3") in done: continue
            rig = gate(rig)
            rec = rig.set_mod(rig.set_mod(rig.set_mod(rig.base, 2, drv_fx[0], [70, 50, 50, 0, 0, 0, 0, 0], True), 3, amp_fx[12], [70] + [50] * 7, True), 4, cab_fx[14], [50] + [0] * 7, True)
            y = rig.take(rig.set_mod(rec, 7, dly_fx[2], [30, 400, 40, 0, 0, 25, 0, 0], True), secs=180)      # soak
            fl = []
            for c in range(0, len(y) - int(3.2 * FS), int(3.2 * FS)):
                f, _ = analyse(y[c:c + int(3.2 * FS)], True); fl += f
            log(dict(round=rnd, effect="SOAK 3 min", setting="TS808+5150+V30+EP-3", fail=sorted(set(fl))))
            l = rig.Link(); cur = None
            for idx in range(50, 100):                                       # factory presets as stored
                import pmpreset
                if (rnd, "PRESET", f"F{idx - 49:02d}") in done: continue
                if os.path.exists(PAUSE): l.close(); rig = gate(rig); l = rig.Link()
                pmpreset.write_message(l, b"\x11\x43", idx.to_bytes(2, "little")); time.sleep(1.5); l.close()
                path = "/tmp/night.wav"; p = rig.pa.record(path, 3.8); time.sleep(0.25)
                rig.sd.play(np.stack([SIG, SIG], 1), samplerate=FS, device=rig.dev); p.wait(); rig.sd.stop()
                w = wave.open(path); y = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2).astype(float) / 32768
                f, lv = analyse(y[int(0.25 * FS):], True)   # presets may hold delays/reverbs
                log(dict(round=rnd, effect="PRESET", setting=f"F{idx - 49:02d}", fail=f, **lv)); l = rig.Link()
            pmpreset.write_message(l, b"\x11\x43", (7).to_bytes(2, "little")); l.close()
            ev(f"round {rnd} done")
    finally:
        ok = rig.restore(); ev(f"end, P08 restored {ok}")


def summary():
    rows = [json.loads(l) for l in open(RES)]; bad = [r for r in rows if r["fail"]]
    print(f"{len(rows)} takes, {len(bad)} with a failure")
    from collections import Counter, defaultdict
    by = defaultdict(Counter)
    for r in bad:
        for f in r["fail"]: by[r["effect"]][f] += 1
    for e, c in sorted(by.items(), key=lambda x: -sum(x[1].values())): print(f"  {e:22s} {dict(c)}")
    ex = defaultdict(list)
    for r in bad: ex[(r["effect"], r["fail"][0])].append(r["setting"])
    for (e, f), s in list(ex.items())[:30]: print(f"    e.g. {e} {f}: {s[:4]}")


if __name__ == "__main__":
    if sys.argv[1] == "run": main_run(int(sys.argv[2]) if len(sys.argv) > 2 else 3)
    else: summary()
