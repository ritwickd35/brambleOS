#!/usr/bin/env python3
"""DS-1+ debug mode (FX1 DS-1+ with VOL = 0): what does the firmware pass to entry0/entry1? Decodes 10 values."""
import os, sys, time, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fx1probe_run as P
P.NAMES = ["magic", "n", "entry0 calls", "entry1 c differs", "c[0] x100", "c[1] x100", "c[2] x100", "c ptr hi", "c ptr lo", "e byte"]
FX = 0x05000008


def main():
    import sounddevice as sd, pmaudio
    from pmflash import Link
    from cut1_variants import read_p
    from cut1_matrix import send, set_mod
    link = Link(); orig = read_p(link); link.close()
    rec = orig
    for m in range(10): rec = set_mod(rec, m, on=False)
    rec = set_mod(rec, 1, FX, [50, 50, 0, 0, 0, 0, 0, 0], True)
    path = os.path.join(RE, "audio", time.strftime("%Y%m%d-%H%M%S") + "-ds1debug.wav")
    t = np.arange(int(44100 * 40)) / 44100; tone = (0.1 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
    p = pmaudio.record(path, 36); time.sleep(1.0)
    sd.play(np.stack([tone, tone], 1), samplerate=44100, device=pmaudio.out_device("External Headphones")); time.sleep(2.0)
    try:
        send(rec); p.wait(); sd.stop()
    finally:
        send(orig); time.sleep(0.5); link = Link(); back = read_p(link); link.close()
    y, s, v = P.decode_runs(path)
    sv = [x if x is None or x < 32768 or i < 2 or i in (2, 3, 7, 8) else x - 65536 for i, x in enumerate(v)]
    print("DS-1+ debug:", json.dumps(dict(zip(P.NAMES, sv))), "| P08 restored:", back[4:] == orig[4:], flush=True)


if __name__ == "__main__":
    main()
