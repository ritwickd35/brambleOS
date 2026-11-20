#!/usr/bin/env python3
"""Cut 7: engine capacity. DRV #7 probe in ENGINE RAMP mode (Treble 0, Bass 0) + EQ = Bass EQ (busy-loop program).
Reports the engine counter at N=0 and at the step where the engine first needs more than one block."""
import json, os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import bench_run as B, audit as A, cfwdb


def one(rec, label):
    import sounddevice as sd, pmaudio
    from cut1_matrix import send
    path = os.path.join(RE, "audio", time.strftime("%Y%m%d-%H%M%S") + "-engramp.wav")
    t = np.arange(int(44100 * 115)) / 44100; tone = (0.1 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
    p = pmaudio.record(path, 110); time.sleep(1.0)
    sd.play(np.stack([tone, tone], 1), samplerate=44100, device=pmaudio.out_device("External Headphones")); time.sleep(2.0)
    send(rec); p.wait(); sd.stop()
    y, res = B.decode(path, t_from=10.0)
    v = [x for _, x in res][:10]
    pair = lambda i: (v[i] << 16 | v[i + 1]) if len(v) > i + 1 and v[i] >= 0 and v[i + 1] >= 0 else None
    out = dict(label=label, wav=os.path.basename(path), magic_ok=bool(v and v[0] == 0xA55A),
               counter_n0=pair(1), counter_good=pair(3), n_over=v[5] if len(v) > 5 else None, counter_over=pair(6),
               overran=v[8] if len(v) > 8 else None, steps=v[9] if len(v) > 9 else None)
    print(time.strftime("%H:%M:%S"), json.dumps(out), flush=True)
    return out


def run():
    from pmflash import Link
    from cut1_variants import read_p
    from cut1_matrix import send, set_mod, get_mod
    eq = {e["name"]: e for e in cfwdb.effects(os.path.join(RE, "cfw", "src", "4_effect_db_presets_00190000.bin")) if e["group"] == "EQ"}
    link = Link(); orig = read_p(link); link.close()
    base = orig
    for m in range(10): base = set_mod(base, m, on=False)
    ramp = set_mod(set_mod(base, 2, 0x03000040, [50, 50, 50, 0, 0, 0, 0, 0], True), 5, eq["Bass EQ"]["fxid"], eq["Bass EQ"]["params"], True)
    ir = get_mod(orig, 4); fx, p = A.defaults("Calif DualM"); tw, tp = A.defaults("TWD Deluxe")
    jobs = [("engine ramp: DRV + EQ only", ramp),
            ("engine ramp: + TWD Deluxe + cab", set_mod(set_mod(ramp, 3, tw, tp, True), 4, ir[0], ir[1], True)),
            ("engine ramp: + Calif DualM + cab", set_mod(set_mod(ramp, 3, fx, p, True), 4, ir[0], ir[1], True))]
    res = []
    try:
        for label, rec in jobs:
            res.append(one(rec, label)); json.dump(res, open(os.path.join(RE, "cut1", "engine-ramp.json"), "w"), indent=1)
    finally:
        send(orig); time.sleep(0.5); link = Link(); back = read_p(link); link.close()
        print("P08 restored:", back[4:] == orig[4:], flush=True)


if __name__ == "__main__":
    run()
