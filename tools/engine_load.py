#!/usr/bin/env python3
"""Cut 6: engine (co-processor) load per preset. DRV #7 'CPU Test 2' with Treble 0 = probe mode (combo2): it reads
the engine counter the kernel stores every block and reports current / max / min / average as audio dips.
  engine_load.py run      a set of presets (P08 scratch, restored); results cut1/engine-load.json"""
import json, os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import bench_run as B, audit as A
FIELDS = {"current": 5, "max": 7, "min": 9, "raw 0x28008048": 11, "kernel max": 13, "average": 15}


def one(rec, label):
    import sounddevice as sd, pmaudio
    from cut1_matrix import send
    path = os.path.join(RE, "audio", time.strftime("%Y%m%d-%H%M%S") + "-engine.wav")
    t = np.arange(int(44100 * 82)) / 44100; tone = (0.1 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
    p = pmaudio.record(path, 78); time.sleep(1.0)
    sd.play(np.stack([tone, tone], 1), samplerate=44100, device=pmaudio.out_device("External Headphones")); time.sleep(2.0)
    send(rec); p.wait(); sd.stop()
    y, res = B.decode(path, t_from=7.5)
    v = [x for _, x in res]
    out = dict(label=label, wav=os.path.basename(path), magic_ok=bool(v and v[0] == 0xA55A))
    if out["magic_ok"]:
        for k, i in FIELDS.items():
            out[k] = (v[i] << 16 | v[i + 1]) if v[i] >= 0 and v[i + 1] >= 0 else None
    print(time.strftime("%H:%M:%S"), label, {k: out.get(k) for k in FIELDS}, flush=True)
    return out


def run():
    from pmflash import Link
    from cut1_variants import read_p
    from cut1_matrix import send, set_mod, get_mod
    import cfwdb
    link = Link(); orig = read_p(link); link.close()
    base = orig
    for m in range(10): base = set_mod(base, m, on=False)
    probe = set_mod(base, 2, 0x03000040, [50, 50, 50, 50, 0, 0, 0, 0], True)          # Treble 0 -> probe mode
    ir = get_mod(orig, 4)
    amp = lambda name: A.defaults(name)
    sb = {e["name"]: e for e in cfwdb.effects(os.path.join(RE, "cfw", "src", "4_effect_db_presets_00190000.bin")) if e["group"] == "AMP"}
    jobs = [("probe only", probe)]
    for n in ("TWD Deluxe", "Brit 800", "Calif DualM", "Flyman B1+"):
        fx, p = amp(n); r = set_mod(probe, 3, fx, p, True); jobs.append((f"{n}", r)); jobs.append((f"{n} + cab", set_mod(r, 4, ir[0], ir[1], True)))
    for n in ("Brit 900", "Calif IV LD"):
        e = sb[n]; r = set_mod(set_mod(probe, 3, e["fxid"], e["params"], True), 4, ir[0], ir[1], True); jobs.append((f"{n} (Smart Box) + cab", r))
    fx, p = amp("Calif DualM")
    jobs.append(("high gain + cab + EQ", set_mod(set_mod(set_mod(probe, 3, fx, p, True), 4, ir[0], ir[1], True), 5, *A.defaults("GT EQ 1") if False else get_mod(orig, 5), True)))
    res = []
    try:
        for label, rec in jobs:
            res.append(one(rec, label)); json.dump(res, open(os.path.join(RE, "cut1", "engine-load.json"), "w"), indent=1)
    finally:
        send(orig); time.sleep(0.5); link = Link(); back = read_p(link); link.close()
        print("P08 restored:", back[4:] == orig[4:], flush=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["run"]: run()
    else: sys.exit(__doc__)
