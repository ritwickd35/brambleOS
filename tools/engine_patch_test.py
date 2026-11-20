#!/usr/bin/env python3
"""Cut 6 engine-code test: Bass EQ (EQ #2) runs our patched engine program (x0.5). Compares EQ off, Bass EQ
(patched) and GT EQ 1 (stock program) on the effects test signal: level and frequency response."""
import json, os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("AUDIT_TAG", "-cut6")
import audit_fx as F, cfwdb


def main():
    import sounddevice as sd, pmaudio
    from pmflash import Link
    from cut1_variants import read_p
    from cut1_matrix import send, set_mod
    eq = {e["name"]: e for e in cfwdb.effects(os.path.join(RE, "cfw", "src", "4_effect_db_presets_00190000.bin")) if e["group"] == "EQ"}
    link = Link(); orig = read_p(link); link.close()
    base = orig
    for m in range(10): base = set_mod(base, m, on=False)
    jobs = [("EQ off", base), ("Bass EQ (patched engine code)", set_mod(base, 5, eq["Bass EQ"]["fxid"], eq["Bass EQ"]["params"], True)),
            ("GT EQ 1 (stock engine code)", set_mod(base, 5, eq["GT EQ 1"]["fxid"], eq["GT EQ 1"]["params"], True)), ("EQ off (again)", base)]
    os.makedirs(os.path.join(RE, "audio", "cut6"), exist_ok=True); res = []
    dev = pmaudio.out_device("External Headphones"); sig = F.signal()[0]
    try:
        for i, (label, rec) in enumerate(jobs, 1):
            send(rec); time.sleep(2.0)
            path = os.path.join(RE, "audio", "cut6", f"{i:02d} {label}.wav")
            p = pmaudio.record(path, F.DUR + 3.5); time.sleep(1.0)
            sd.play(np.stack([sig, sig], 1).astype(np.float32), samplerate=44100, device=dev); p.wait(); sd.stop()
            r = F.analyse_fx(path); out = dict(label=label, level_db=r["level_db"], eq=r["eq"], spurious_db=r["spurious_db"])
            print(time.strftime("%H:%M:%S"), label, "level", r["level_db"], "dB  bands", r["eq"], flush=True); res.append(out)
            json.dump(res, open(os.path.join(RE, "cut1", "engine-patch-test.json"), "w"), indent=1)
    finally:
        send(orig); time.sleep(0.5); link = Link(); back = read_p(link); link.close()
        print("P08 restored:", back[4:] == orig[4:], flush=True)


if __name__ == "__main__":
    main()
