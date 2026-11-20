#!/usr/bin/env python3
"""On-pedal tests for cut5 (CFW 1.0.2 + smart gate in NR + DS-1+ in FX1 + CPU ramp in DRV #7).
  test_cut5.py sound     DS-1+ (gain 50 / 100) and JP Dist, alone and into Dark Twin + cab; NR gate on the fx signal
  test_cut5.py cpu       headroom: CPU test alone, + DS-1+, + gate, + both (P08 scratch, restored)
Results: cut1/cut5-*.json, recordings in audio/cut5/."""
import json, os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("AUDIT_TAG", "-cut5")
import audit as A, audit_fx as F
FX1_DS1 = 0x05000008
OUT = os.path.join(RE, "audio", "cut5" + os.environ.get("AUDIT_TAG", "-cut5").replace("-cut5", ""))


def sound():
    import sounddevice as sd, pmaudio
    from pmflash import Link
    from cut1_variants import read_p
    from cut1_matrix import send, set_mod, get_mod
    os.makedirs(OUT, exist_ok=True)
    link = Link(); orig = read_p(link); link.close()
    base = orig
    for m in range(10): base = set_mod(base, m, on=False)
    ir = get_mod(orig, 4); afx, ap = A.defaults("Dark Twin"); jfx, jp = A.defaults("JP Dist")
    jobs = []
    for g in (50, 100):
        jobs.append((f"DS-1+ gain {g}", "drv", set_mod(base, 1, FX1_DS1, [g, 50, 50, 0, 0, 0, 0, 0], True)))
        q = list(jp); q[0] = g
        jobs.append((f"JP Dist gain {g}", "drv", set_mod(base, 2, jfx, q, True)))
    cab = lambda r: set_mod(set_mod(r, 3, afx, ap, True), 4, ir[0], ir[1], True)
    jobs.append(("DS-1+ into Dark Twin + cab", "drv", cab(set_mod(base, 1, FX1_DS1, [50, 50, 50, 0, 0, 0, 0, 0], True))))
    jobs.append(("JP Dist into Dark Twin + cab", "drv", cab(set_mod(base, 2, jfx, jp, True))))
    for t in (30, 50, 70):
        jobs.append((f"smart gate THRE {t}", "fx", set_mod(base, 0, 0x1b, [t, 0, 0, 0, 0, 0, 0, 0], True)))
    dev = pmaudio.out_device(os.environ.get("AUDIT_OUT", "External Headphones")); res = []
    try:
        for i, (label, kind, rec) in enumerate(jobs, 1):
            print(time.strftime("%H:%M:%S"), f"sound {i}/{len(jobs)}: {label}", flush=True)
            send(rec); time.sleep(2.0)
            sig = A.signal()[0] if kind == "drv" else F.signal()[0]
            dur = (A.DUR if kind == "drv" else F.DUR) + 3.5
            path = os.path.join(OUT, f"{i:02d} {label}.wav")
            p = pmaudio.record(path, dur); time.sleep(1.0)
            sd.play(np.stack([sig, sig], 1).astype(np.float32), samplerate=A.FS, device=dev); p.wait(); sd.stop()
            r = dict(label=label)
            try:
                if kind == "drv":
                    import audit_report as R; r.update(R.one(path))
                else:
                    r.update(F.analyse_fx(path))
            except Exception as e:
                r["error"] = str(e)
            res.append(r); json.dump(res, open(os.path.join(RE, "cut1", "cut5-sound.json"), "w"), indent=1, default=str)
    finally:
        send(orig); time.sleep(0.5); link = Link(); back = read_p(link); link.close()
        print("P08 restored:", back[4:] == orig[4:], flush=True)


def cpu():
    from pmflash import Link
    from cut1_variants import read_p
    from cut1_matrix import set_mod, run, send
    link = Link(); orig = read_p(link); link.close()
    base = orig
    for m in range(10): base = set_mod(base, m, on=False)
    test = set_mod(base, 2, *[0x03000040, [50, 50, 50, 50, 50, 0, 0, 0]], True)        # DRV #7 = CPU Test 2 (Treble 50)
    runs = [("CPU test alone", test),
            ("+ DS-1+ (FX1)", set_mod(test, 1, FX1_DS1, [50, 50, 50, 0, 0, 0, 0, 0], True)),
            ("+ smart gate (NR)", set_mod(test, 0, 0x1b, [50, 0, 0, 0, 0, 0, 0, 0], True)),
            ("CPU test alone (again)", test)]
    res = []
    try:
        for label, rec in runs:
            res.append(run(rec, label)); json.dump(res, open(os.path.join(RE, "cut1", "cut5-cpu.json"), "w"), indent=1)
    finally:
        send(orig); time.sleep(0.5); link = Link(); back = read_p(link); link.close()
        print("P08 restored:", back[4:] == orig[4:], flush=True)
    for r in res: print(f"{r['label']:24s} free {r['median']} %", flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["sound"]: sound()
    elif a == ["cpu"]: cpu()
    else: sys.exit(__doc__)
