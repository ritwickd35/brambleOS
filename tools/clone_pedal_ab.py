#!/usr/bin/env python3
"""Pedal A/B of clone conversions: play held-out guitar DI through Clone mode (slot 5, IR off, everything else off)
with Sonicake's clone and with ours, and score each pedal recording against the real NAM capture.
  clone_pedal_ab.py <id>=<nam>,<sonicake clo>,<our clo> ...
Recordings: audio/cloneab/<id>_{bypass,sonicake,ours}.npy, 12 s clips for listening in audio/listen/."""
import os, sys, time, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import clone_probe as C, pmclone as P, clone_score as S, namrun, di_set
FS = 44100; OUT = os.path.join(RE, "audio", "cloneab")


def signal():
    d = di_set.load("test", 16)                     # 4 s from each held-out take (every style)
    return np.concatenate([np.zeros(int(0.4 * FS)), np.r_[0.5, np.zeros(99)], np.zeros(int(1.2 * FS)), d, np.zeros(int(0.6 * FS))]).astype(np.float32)   # DI starts after the click search window


def lags(y, yh, a, b, w=FS):
    t, L, e = [], [], []
    for i in range(a + w, b - w, w):
        Y = y[i - 400:i + w + 400]; s = yh[i:i + w]; cc = np.correlate(Y, s, "valid")
        t.append(i + w / 2); L.append(int(np.argmax(np.abs(cc))) - 400); e.append(np.sum(s * s))
    k = np.array(e) >= np.median(e); return np.array(t)[k], np.array(L, float)[k]


def steady(y, yh, a, b):
    """True if no samples were lost (no lag jump > 2 between loud 1 s windows); a slow drift between the Mac's
    and the pedal's clocks (a few samples per 10 s) is fine and is removed by dedrift()."""
    t, L = lags(y, yh, a, b)
    if len(L) < 4: return False
    r = L - np.polyval(np.polyfit(t, L, 1), t)            # a lost block shows as a step off the straight drift line
    ok = np.max(np.abs(r)) <= 3
    if not ok: print(f"   lag off the drift line by up to {np.max(np.abs(r)):.0f} samples", flush=True)
    return ok


def dedrift(y, yh, a, b):
    t, L = lags(y, yh, a, b); p = np.polyfit(t, L, 1)               # lag(t) = p0 t + p1
    n = np.arange(len(y), dtype=float); return np.interp(n + np.polyval(p, n), n, y)


def main():
    os.makedirs(OUT, exist_ok=True); x = signal(); C.probe = lambda: x
    C.SEG.clear(); C.SEG.update(click=(int(0.4 * FS), int(0.4 * FS) + 100), di=(int(0.4 * FS) + 100 + int(1.2 * FS), len(x) - int(0.6 * FS)))
    rig = C.Rig(); a, b = C.SEG["di"]
    try:
        for attempt in range(3):
            xb = rig.take(rig.off)
            if xb is not None and steady(xb, x.astype(float) * 10 ** (-15.6 / 20), a, b): break
        np.save(os.path.join(OUT, "bypass.npy"), xb)
        for job in sys.argv[1:]:
            k, rest = job.split("="); nam, sclo, oclo = rest.split(",")
            if os.path.exists(os.path.join(OUT, f"{k}_ours.npy")) and os.path.exists(os.path.join(OUT, f"{k}_sonicake.npy")) and os.environ.get("SKIP_DONE"): continue
            t = np.asarray(namrun.render(nam, xb[a:b] / S.USB)).ravel()          # real capture on the same input
            row = {}
            pairs = [("sonicake", sclo)] if sclo != "-" else []
            for i, c_ in enumerate(oclo.split("+")): pairs.append((os.environ.get("TAGS", "ours").split("+")[i], c_))
            for who, clo in pairs:
                P.upload(open(clo, "rb").read(), C.SLOT, f"ab {who[:4]} {k}"[:15]); rig.send(rig.S(rig.clone, 9, C.CLO_FX - 1)); time.sleep(0.8)
                raw = open(clo, "rb").read(); pm = P.parse_pmam(raw)              # what the pedal should output
                if pm:
                    import ampmodel as AM
                    yh = AM.run(pm["settings"], [50, 50, 50, 50, 50, 50, 0], xb / S.USB) * S.USB
                else: yh = S.run(P.parse(raw), xb)
                for attempt in range(3):                                         # USB recordings sometimes drop
                    y = rig.take(rig.clone)                                      # samples mid-take: check the lag
                    if y is not None and steady(y, yh, a, b): break              # stays put, else record again
                    print(f"   {k} {who}: recording glitch, again", flush=True)
                if y is None: print(f"   {k} {who}: no usable recording", flush=True); continue
                np.save(os.path.join(OUT, f"{k}_{who}.npy"), y)
                yd = dedrift(y, yh, a, b)                                          # remove the clock drift
                r = S.compare(yd[a:b], t); row[who] = r
                import soundfile as sf
                sf.write(os.path.join(RE, "audio", "listen", f"nam-{k}-{who}.wav"), (y[a:b] / (np.max(np.abs(y[a:b])) + 1e-9) * 0.7), FS)
            sf.write(os.path.join(RE, "audio", "listen", f"nam-{k}-real-capture.wav"), (t / (np.max(np.abs(t)) + 1e-9) * 0.7), FS)
            print(f"{time.strftime('%T')} PEDAL AB {k}: {json.dumps(row)}", flush=True)
    finally:
        P.upload(C.gen("fa=d0,fb=d0,p=100/100/0.01/0.01"), C.SLOT, "Empty"); print("slot 5 reset; P08 restored", rig.restore(), flush=True)


if __name__ == "__main__":
    main()
