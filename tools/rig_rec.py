#!/usr/bin/env python3
"""rig_rec.py <tag> "<label>|<amp name or fx id>|<cab fx id>" ...: record the audit signal through AMP + CAB on P08
(everything else off), save audio/rigs-<tag>/<label>.wav and a 12 s guitar clip in audio/listen/. P08 restored.
Amp knobs: stock defaults for a stock amp name, 50s for a numeric fx id."""
import os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import audit as A


def main():
    import sounddevice as sd, pmaudio, pmloadtest as L
    from pmflash import Link
    from cut1_variants import read_p
    from cut1_matrix import send, set_mod
    tag, jobs = sys.argv[1], [j.split("|") for j in sys.argv[2:]]; out = os.path.join(RE, "audio", f"rigs-{tag}"); os.makedirs(out, exist_ok=True)
    x, _ = A.signal(); play = np.stack([x, x], 1).astype(np.float32); dev = pmaudio.out_device("External Headphones")
    l = Link(); orig = read_p(l); l.close(); base = orig
    for k in range(10): base = set_mod(base, k, on=False)
    try:
        for job in jobs:
            label, amp, cab = job[:3]
            fx, p = (int(amp), [50.0] * 8) if amp.isdigit() else A.defaults(amp)
            rec = set_mod(base, 3, fx, p, True)
            if int(cab): rec = set_mod(rec, 4, int(cab), [50.0] + [0.0] * 7, True)
            if len(job) > 3: rec = set_mod(rec, 2, int(job[3]), [50.0, 50.0, 50.0, 0, 0, 0, 0, 0], True)   # drive in front
            send(rec); time.sleep(3.0); path = os.path.join(out, label + ".wav")
            pr = pmaudio.record(path, A.DUR + 3.5); time.sleep(1.0); sd.play(play, samplerate=A.FS, device=dev); pr.wait(); sd.stop()
            y = L.load(path); c = A.piece(y, A.sync(y), A.T_DI, A.T_DI + 12); lv = 20 * np.log10(np.std(c) + 1e-12)
            pmaudio.save(os.path.join(RE, "audio", "listen", f"pedal {tag} - {label}.wav"), np.stack([c, c], 1) / (np.max(np.abs(c)) + 1e-9) * 0.5)
            print(time.strftime("%H:%M:%S"), label, f"level {lv:.1f} dB", flush=True)
    finally:
        send(orig); time.sleep(0.5); l = Link(); back = read_p(l); l.close(); print("P08 restored:", back[4:] == orig[4:])


if __name__ == "__main__":
    main()
