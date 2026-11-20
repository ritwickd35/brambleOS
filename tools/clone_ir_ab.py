#!/usr/bin/env python3
"""Pedal test of an amp + cab conversion on the own clone engine: amp model -> clone slot 5, extracted cab ->
User IR 5, preset in NAM (clone) mode with the IR block on that IR. Scores the pedal against the real capture
and against our simulation (amp model + cab), saves listening clips.  clone_ir_ab.py <id> <capture.nam>"""
import os, sys, time, json
import numpy as np, soundfile as sf
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import clone_probe as C, clone_pedal_ab as AB, clone_score as S, pmclone as P, pmir as I, ampmodel as AM, namrun
FS = 44100; KN = [50, 50, 50, 50, 50, 50, 0]


def main():
    k, nam = sys.argv[1:3]; s = json.load(open(os.path.join(RE, "amps", f"namx_{k}.json")))
    cab = np.fromfile(os.path.join(RE, "irs", "out", f"namx_{k}_cab.f32"), "<f4").astype(float)
    x = AB.signal(); C.probe = lambda: x; a = int(0.4 * FS) + 100 + int(1.2 * FS); b = len(x) - int(0.6 * FS)
    C.SEG.clear(); C.SEG.update(click=(int(0.4 * FS), int(0.4 * FS) + 100), di=(a, b))
    import nam2amp; P.upload(nam2amp.make_clone(k), 5, f"NAM {k}"[:15]); rig = C.Rig()   # cab inside the clone
    try:
        xb = rig.take(rig.off); rig.send(rig.S(rig.clone, 9, C.CLO_FX - 1)); time.sleep(0.8)
        rec = rig.S(rig.S(rig.clone, 9, C.CLO_FX), 4, on=False); rig.send(rec); time.sleep(3)
        y = rig.take(rec)
        sim = np.convolve(AM.run(s, KN, xb / S.USB), cab)[:len(xb)]
        t = np.asarray(namrun.render(nam, xb[a:b] / S.USB)).ravel()
        st_ = AB.steady(y, sim, a, b); print("   recording steady:", st_, flush=True); yd = AB.dedrift(y, sim, a, b) if st_ else y
        r = dict(vs_capture=S.compare(yd[a:b], t), vs_simulation=S.compare(yd[a:b], sim[a:b]),
                 sim_vs_capture=S.compare(sim[a:b], t),
                 level_db_vs_capture=round(float(20 * np.log10(np.std(yd[a:b]) / S.USB / np.std(t))), 1))
        print(f"{time.strftime('%T')} PEDAL CLONE+IR {k}: {json.dumps(r)}", flush=True)
        for nm_, z in ((f"nam-{k}-ours-engine.wav", yd[a:b]), (f"nam-{k}-real-capture.wav", t)):
            sf.write(os.path.join(RE, "audio", "listen", nm_), z / (np.max(np.abs(z)) + 1e-9) * 0.7, FS)
    finally:
        P.upload(C.gen("fa=d0,fb=d0,p=100/100/0.01/0.01"), 5, "Empty")
        print("slot 5 reset; P08 restored", rig.restore(), flush=True)


if __name__ == "__main__":
    main()
