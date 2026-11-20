#!/usr/bin/env python3
"""Cut 9 on the pedal: Multi Drv (DRV #7: DS-1 / TS808 on the co-processor) vs the stock JP Dist / Scream,
same audit signal and metrics as audit.py. P08 restored byte-identically.  Results: cut1/drv-audit.json"""
import json, os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
os.environ.setdefault("AUDIT_TAG", "-cut9")
import audit as A

MULTI = 0x03000040


NEW = []   # (fx id, label) from the command line: drv_audit.py <fxid>=<label> ...


def configs(orig):
    from cut1_matrix import set_mod
    base = orig
    for k in range(10): base = set_mod(base, k, on=False)
    out = [("bypass", base)]
    if NEW:                                                    # our single-model slots: knobs drive, tone, level
        for fx, name in NEW:
            for gain in (50.0, 100.0):
                out.append((f"new {name} gain {gain:.0f}", set_mod(base, 2, fx, [gain, 50.0, 50.0, 0, 0, 0, 0, 0], True)))
        return out
    for stock, model_knob, name in (("JP Dist", 10.0, "DS-1"), ("Scream", 80.0, "TS808")):
        fx, p = A.defaults(stock)
        for gain in (p[0], 100.0):
            q = list(p); q[0] = gain
            out.append((f"stock {stock} gain {gain:.0f}", set_mod(base, 2, fx, q, True)))
            out.append((f"new {name} gain {gain:.0f}", set_mod(base, 2, MULTI, [gain, model_knob, 50.0, 50.0, 50.0, 0, 0, 0], True)))
    return out


def main():
    import sounddevice as sd, pmaudio
    from pmflash import Link
    from cut1_variants import read_p
    from cut1_matrix import send
    link = Link(); orig = read_p(link); link.close()
    x, nz = A.signal(); play = np.stack([x, x], 1).astype(np.float32)
    dev = pmaudio.out_device("External Headphones"); os.makedirs(A.OUT, exist_ok=True); res = []
    try:
        for i, (label, rec) in enumerate(configs(orig), 1):
            send(rec); time.sleep(2.0)
            path = os.path.join(A.OUT, f"{i:02d} {label}.wav")
            p = pmaudio.record(path, A.DUR + 3.5); time.sleep(1.0)
            sd.play(play, samplerate=A.FS, device=dev); p.wait(); sd.stop()
            r = dict(label=label)
            try: r.update(A.analyse(path, nz))
            except Exception as e: r["error"] = str(e)
            res.append(r); json.dump(res, open(os.path.join(RE, "cut1", "drv-audit.json"), "w"), indent=1)
            h = r.get("harshness_db", {}); top = r.get("ramp", [{}])[-1].get("out_db")
            print(time.strftime("%H:%M:%S"), label, "| alias dB", list(h.values()), "| level at loudest step", top, flush=True)
    finally:
        send(orig); time.sleep(0.5); link = Link(); back = read_p(link); link.close()
        print("P08 restored:", back[4:] == orig[4:], flush=True)


if __name__ == "__main__":
    NEW[:] = [(int(a.split("=")[0], 0), a.split("=")[1]) for a in sys.argv[1:]]
    main()
