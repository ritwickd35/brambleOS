#!/usr/bin/env python3
"""Cut 1 measurement matrix: CPU headroom for a 'MAX' stress preset, MAX minus each block, and factory presets.
All runs: write variant into P08 (index 7, DRV = test effect), select P08 (restarts the test), record 120 s.
Metric per cycle: extra load (% of one 64-frame block) at which audible dips start, measured from the cycle's marker.
P08 is restored byte-identically at the end. Log: logs/cut1-matrix.log, summary: cut1/matrix-results.json
"""
import json, os, struct, subprocess, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pmpreset, pmloadtest as L, cut1_resid
from pmflash import Link
from cut1_variants import tlv, offsets, read_p, describe
PY = os.path.join(HERE, ".venv", "bin", "python")
IDX, FS = 7, 44100
BK = os.path.join(RE, "backups", "20261117-163745", "presets")
LOG = os.path.join(RE, "logs", "cut1-matrix.log")
NAMES = ["NR", "FX1", "DRV", "AMP", "IR", "EQ", "FX2", "DLY", "RVB", "CLONE"]


def log(*a):
    s = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
    print(s, flush=True); open(LOG, "a").write(s + "\n")


def preset(name_prefix):
    f = next(x for x in sorted(os.listdir(BK)) if x.startswith(name_prefix))
    return open(os.path.join(BK, f), "rb").read()


def get_mod(rec, m):
    o = offsets(rec)
    return struct.unpack_from("<I", rec, o[0x3003] + 4 * m)[0], struct.unpack_from("<8f", rec, o[0x3004] + 32 * m)


def set_mod(rec, m, fx=None, params=None, on=None):
    r = bytearray(rec); o = offsets(rec)
    if fx is not None: struct.pack_into("<I", r, o[0x3003] + 4 * m, fx)
    if params is not None: struct.pack_into("<8f", r, o[0x3004] + 32 * m, *params)
    if on is not None:
        en = struct.unpack_from("<I", r, o[0x3001])[0]
        en = en | (1 << m) if on else en & ~(1 << m)
        struct.pack_into("<I", r, o[0x3001], en)
    return bytes(r)


def with_test_drv(rec, test):
    fx, prm = get_mod(test, 2)
    return set_mod(rec, 2, fx, prm, True)


def episodes(path, rel=0.85):
    """Dips relative to the recording's own normal envelope (pitch/chorus effects make the normal envelope uneven):
    per 0.125 s window take min envelope / median envelope; 'normal' = median of those minima;
    a window is degraded when it falls below rel x normal."""
    y = L.load(path); w = 32; n = len(y) // w
    env = np.sqrt(np.mean(y[:n * w].reshape(n, w) ** 2, 1)); med = np.median(env)
    q = int(0.125 * FS / w); m = n // q
    mins = np.array([env[i * q:(i + 1) * q].min() / med for i in range(m)]); t = np.arange(m) * 0.125
    normal = np.median(mins[t > 6]) if np.any(t > 6) else np.median(mins)
    ev = []
    for i in np.where(mins < rel * normal)[0]:
        if ev and t[i] - ev[-1][1] <= 0.5: ev[-1][1] = t[i]
        else: ev.append([t[i], t[i]])
    return [(float(a), float(b) + 0.125) for a, b in ev]


def onsets(ev):
    """Cycle timing (no markers needed): episode 0 = preset switch. Each cycle: 0.14 s measure + 2 s rest, then the
    ramp (+1 % per 0.25 s) until overrun, 4 s rest. Ramp episodes = episodes >= 0.75 s long; shorter ones are
    markers/echoes and ignored. onset k = (episode start - ramp start) / 0.25 s."""
    if not ev:
        return []
    start = ev[0][1]                                   # end of the preset-switch dropout = cycle 1 start
    longs = [e for e in ev[1:] if e[1] - e[0] >= 0.75]
    ks = []
    for a, b in longs[:3]:
        ramp0 = start + 0.14 + 2.0
        k = (a - ramp0) / 0.25
        if 0 <= k <= 150:
            ks.append(round(k))
        start = b + 4.0
    return ks


def send(rec):
    """Write rec into P08 and select it; retry the whole exchange on a missing ACK."""
    for attempt in range(4):
        link = Link()
        try:
            pmpreset.write_message(link, b"\x11\x4f", struct.pack("<I", IDX) + rec[4:]); time.sleep(0.5)
            pmpreset.write_message(link, b"\x11\x43", struct.pack("<I", IDX))
            return
        except RuntimeError as e:
            log(f"   write attempt {attempt + 1} failed: {e}"); time.sleep(2)
        finally:
            link.close()
    raise RuntimeError("pedal did not accept the preset after 4 attempts")


def run(rec, label):
    log(f"--- {label}: on = {describe(rec)}")
    p = subprocess.Popen([PY, "-u", os.path.join(HERE, "pmloadtest.py"), "run", "120"],
                         stdout=open(os.path.join(RE, "logs", "cut1-matrix-rec.log"), "w"), stderr=subprocess.STDOUT)
    time.sleep(5)
    send(rec)
    p.wait()
    wav = sorted(f for f in os.listdir(L.OUT) if f.endswith("-cputest.wav"))[-1]
    try:
        ks = cut1_resid.cycles(os.path.join(L.OUT, wav))
    except Exception as e:
        ks = []; log("   analysis failed:", e)
    med = float(np.median(ks)) if ks else None
    log(f"   {wav}: headroom per cycle {ks} -> median {med}")
    return dict(label=label, blocks=describe(rec), wav=wav, onsets=ks, median=med)


def main():
    open(LOG, "a").write("\n"); log("matrix started")
    link = Link(); orig = read_p(link); link.close()
    test = orig                                          # P08 test variant (DRV = test effect)
    # MAX: heaviest choice per block taken from factory presets
    mx = test
    # heaviest factory choice per block that does not modulate the level (no phaser/tremolo/vibrato)
    for m, src in ((1, "081"), (3, "068"), (4, "081"), (5, "081"), (6, "030"), (7, "016"), (8, "038"), (0, "081")):
        fx, prm = get_mod(preset(src), m)
        prm = list(prm)
        if m in (7, 8):
            prm[0] = 1.0                               # delay / reverb mix 1 %: same processing, no loud echoes
        mx = set_mod(mx, m, fx, prm, True)
    mx = set_mod(mx, 9, on=False)
    runs = [("MAX (all heavy)", mx)]
    for m in (0, 1, 3, 4, 5, 6, 7, 8):
        runs.append((f"MAX without {NAMES[m]}", set_mod(mx, m, on=False)))
    for pfx, nm in (("081", "factory GoodOldDay"), ("040", "factory Maj Key"), ("038", "factory Noise Wall")):
        runs.append((nm + " (DRV = test)", with_test_drv(preset(pfx), test)))
    out_json = os.environ.get("MATRIX_JSON", "matrix-results-run2.json")
    if sys.argv[1:] == ["pairs"]:
        # factory presets with delay/reverb mix 1 % (same processing, no tails), each next to a MAX reference
        def low_mix(rec):
            for m in (7, 8):
                fx, prm = get_mod(rec, m); prm = list(prm); prm[0] = 1.0; rec = set_mod(rec, m, fx, prm)
            return rec
        def mix15(rec):
            for m in (7, 8):
                fx, prm = get_mod(rec, m); prm = list(prm); prm[0] = 15.0; rec = set_mod(rec, m, fx, prm)
            return rec
        runs = [("MAX (reference)", mx)]
        for pfx, nm in (("081", "factory GoodOldDay"), ("038", "factory Noise Wall"), ("040", "factory Maj Key")):
            runs += [(nm + " (DRV = test, DLY/RVB mix 1 %)", low_mix(with_test_drv(preset(pfx), test))), ("MAX (reference)", mx)]
        runs += [("MAX with DLY/RVB mix 15 % (control)", mix15(mx)), ("MAX (reference)", mx)]
        out_json = os.environ.get("PAIRS_JSON", "matrix-results-pairs.json")
    skip = int(os.environ.get("MATRIX_SKIP", "0"))       # resume after an interruption
    if skip:
        try: results = json.load(open(os.path.join(RE, "cut1", out_json)))[:skip]
        except Exception: results = []
    else:
        results = []
    for i, (label, rec) in enumerate(runs, 1):
        if i <= skip: continue
        log(f"run {i}/{len(runs)}")
        try:
            results.append(run(rec, label))
        except Exception as e:
            log(f"   run failed: {e}"); results.append(dict(label=label, error=str(e), median=None))
        json.dump(results, open(os.path.join(RE, "cut1", out_json), "w"), indent=1)
    send(orig); time.sleep(0.5)
    link = Link(); back = read_p(link); link.close()
    log("P08 restored:", "OK (byte-identical)" if back[4:] == orig[4:] else "MISMATCH")
    base = results[0]["median"]
    for r in results:
        cost = (round(r["median"] - base, 1) if (r["median"] is not None and base is not None and r["label"].startswith("MAX without")) else "")
        log(f"SUMMARY {r['label']:32s} free {r['median']} %  {('-> block cost ~' + str(cost) + ' %') if cost != '' else ''}")


if __name__ == "__main__":
    main()
