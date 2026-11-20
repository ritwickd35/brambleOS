#!/usr/bin/env python3
"""Which step silences the pedal? Plays a 220 Hz tone and records 4 s per state; prints the level per state."""
import os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import audit as A


def level(path):
    import eprobe_decode as D
    x = D.load(path); return round(float(20 * np.log10(np.sqrt(np.mean(x[44100:] ** 2)) + 1e-12)), 1)


def main():
    import sounddevice as sd, pmaudio
    from pmflash import Link
    from cut1_variants import read_p
    from cut1_matrix import send, set_mod
    link = Link(); orig = read_p(link); link.close()
    base = orig
    for k in range(10): base = set_mod(base, k, on=False)
    jp, jpp = A.defaults("JP Dist")
    states = [("P08 as stored", orig), ("all off", base), ("stock JP Dist", set_mod(base, 2, jp, jpp, True)),
              ("all off", base), ("Multi DS-1", set_mod(base, 2, 0x03000040, [50, 10, 50, 50, 50, 0, 0, 0], True)),
              ("all off", base), ("Multi TS808", set_mod(base, 2, 0x03000040, [50, 80, 50, 50, 50, 0, 0, 0], True)),
              ("all off", base)]
    t = np.arange(int(44100 * 5)) / 44100; tone = (0.1 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    dev = pmaudio.out_device("External Headphones"); os.makedirs(os.path.join(RE, "audio", "iso"), exist_ok=True)
    try:
        for i, (label, rec) in enumerate(states):
            send(rec); time.sleep(1.5)
            path = os.path.join(RE, "audio", "iso", f"{i}.wav")
            p = pmaudio.record(path, 4); time.sleep(0.3)
            sd.play(np.stack([tone, tone], 1), samplerate=44100, device=dev); p.wait(); sd.stop()
            print(time.strftime("%H:%M:%S"), f"{label:16s} level {level(path)} dB", flush=True)
    finally:
        send(orig); time.sleep(0.5); link = Link(); back = read_p(link); link.close()
        print("P08 restored:", back[4:] == orig[4:], flush=True)


if __name__ == "__main__":
    main()
