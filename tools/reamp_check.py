#!/usr/bin/env python3
"""Does USB re-amp work (setting 0403)? Plays a 440 Hz tone over USB with re-amp on and off, P08 = all blocks off.
Prints level and noise floor for both. Restores the setting and P08."""
import os, sys, time, struct
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pmaudio, pmsettings, pmpreset
import sounddevice as sd
from pmflash import Link
from cut1_variants import read_p
from cut1_matrix import send, set_mod
FS = 44100


def measure(tag):
    path = f"/tmp/reamp-{tag}.wav"; t = np.arange(int(FS * 6)) / FS
    x = np.zeros_like(t); x[FS:4 * FS] = 0.1 * np.sin(2 * np.pi * 440 * t[FS:4 * FS])
    p = pmaudio.record(path, 6.5); time.sleep(0.5)
    sd.play(np.stack([x, x], 1).astype(np.float32), samplerate=FS, device=pmaudio.out_device("Pocket Master")); p.wait(); sd.stop()
    import wave
    with wave.open(path) as w: y = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2)[:, 0] / 32768.0
    on = y[int(2 * FS):int(3.5 * FS)]; off = y[int(4.6 * FS):int(5.8 * FS)]
    return round(float(20 * np.log10(np.std(on) + 1e-9)), 1), round(float(20 * np.log10(np.std(off) + 1e-9)), 1)


link = Link(); orig = read_p(link); s0 = pmsettings.read(link).get(0x0403); link.close()
base = orig
for m in range(10): base = set_mod(base, m, on=False)
send(base); time.sleep(1)
try:
    for v in (0, 1):
        link = Link(); pmpreset.write_message(link, b"\x11\x11", struct.pack("<Ii", 0x0403, v)); time.sleep(0.5)
        got = pmsettings.read(link).get(0x0403); link.close(); time.sleep(1)
        lv, nf = measure(f"r{v}")
        print(f"reamp setting {v} (read back {got.hex() if got else None}): tone {lv} dB, noise floor {nf} dB", flush=True)
finally:
    link = Link(); pmpreset.write_message(link, b"\x11\x11", struct.pack("<Ii", 0x0403, int.from_bytes(s0 or b"\0", "little"))); link.close()
    send(orig); time.sleep(0.5); link = Link(); back = read_p(link); link.close()
    print("restored reamp =", (s0 or b"").hex(), "| P08 restored:", back[4:] == orig[4:], flush=True)
