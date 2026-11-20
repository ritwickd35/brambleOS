#!/usr/bin/env python3
"""User IR slots (PROTOCOL.md §5).
  pmir.py list                         User IR slot names
  pmir.py upload <ir.f32|wav> <slot 1-5> <name>   float taps (1.0 = full scale) -> int32 peak 0.99 * 2^23
IR fx id in a preset (module 4) = 0x0A100000 + slot - 1."""
import os, re, struct, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
FX = lambda slot: 0x0A100000 + slot - 1


def to_int(h, peak=0.99):
    h = np.asarray(h, float)[:512]; h = np.r_[h, np.zeros(512 - len(h))]
    return np.round(h / np.max(np.abs(h)) * peak * 2 ** 23).astype("<i4"), np.max(np.abs(h)) / peak   # taps, scale divided out


def upload_int(taps, slot, name):
    import pmpreset
    from pmflash import Link
    msg = struct.pack("<II", 0, FX(slot)) + name.encode()[:15].ljust(16, b"\0") + bytes(48) + np.asarray(taps, "<i4").tobytes()
    for attempt in range(4):                        # the pedal sometimes NAKs while it is loading a preset
        link = Link()
        try: pmpreset.write_message(link, b"\x11\x21", msg); break
        except RuntimeError:
            if attempt == 3: raise
            time.sleep(2)
        finally: link.close()
    time.sleep(0.5)


def names():
    import pmpreset
    from pmflash import Link
    link = Link()
    try:
        r = pmpreset.ask(link, 0x20)
        if r is None: r = pmpreset.ask(link, 0x20)
    finally: link.close()
    return [s.decode() for s in re.findall(rb"[ -~]{1,16}", r or b"")]


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "list": print(names())
    elif a[0] == "upload":
        h = np.fromfile(a[1], "<f4") if a[1].endswith(".f32") else __import__("soundfile").read(a[1])[0]
        t, k = to_int(h); upload_int(t, int(a[2]), a[3]); print("scale divided out:", k, names())
