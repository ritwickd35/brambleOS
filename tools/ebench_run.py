#!/usr/bin/env python3
"""Cut 8c: engine cost benchmarks (DRV #7 harness + EQ = Bass EQ), record, decode, restore P08."""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import cfwdb


def main():
    import pmaudio, ebench_decode as D
    from pmflash import Link
    from cut1_variants import read_p
    from cut1_matrix import send, set_mod
    eq = {e["name"]: e for e in cfwdb.effects(os.path.join(RE, "cfw", "src", "4_effect_db_presets_00190000.bin")) if e["group"] == "EQ"}
    link = Link(); orig = read_p(link); link.close()
    base = orig
    for m in range(10): base = set_mod(base, m, on=False)
    rec = set_mod(set_mod(base, 2, 0x03000040, [50, 50, 50, 50, 50, 0, 0, 0], True), 5, eq["Bass EQ"]["fxid"], eq["Bass EQ"]["params"], True)
    path = os.path.join(RE, "audio", time.strftime("%Y%m%d-%H%M%S") + "-eprobe.wav")
    try:
        p = pmaudio.record(path, int(os.environ.get("EPROBE_SECONDS", "20"))); time.sleep(1.0); send(rec); p.wait()
    finally:
        send(orig); time.sleep(0.5); link = Link(); back = read_p(link); link.close()
        print("P08 restored:", back[4:] == orig[4:], flush=True)
    res = D.decode(path); names = json.load(open(os.path.join(RE, "logs", "ebench_plan.json"))); base = res.get(0, (0, 0))[0]
    out = {names[k]: dict(avg=a, max=m, minus_empty=a - base) for k, (a, m) in sorted(res.items()) if k < len(names)}
    json.dump(dict(wav=os.path.basename(path), bench=out), open(os.path.join(RE, "logs", "ebench.json"), "w"), indent=1)
    print(f"ebench: decoded {len(out)} of {len(names)}", flush=True)


if __name__ == "__main__":
    main()
