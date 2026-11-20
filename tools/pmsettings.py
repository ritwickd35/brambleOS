#!/usr/bin/env python3
"""Global settings (12 10 read, 11 11 write; formats from the public Pocket Master interoperability guide).
  pmsettings.py show
  pmsettings.py set <tag hex, e.g. 0205> <int value>     writes, then reads back and verifies
Known tags: 0203 brightness, 0205 boot anti-touch protection (1 on, 0 off)."""
import struct, sys, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pmpreset
from pmflash import Link

NAMES = {0x0101: "firmware", 0x0102: "preset format", 0x0201: "tuner", 0x0202: "master volume", 0x0203: "brightness",
         0x0204: "energy saving", 0x0205: "boot anti-touch protection", 0x0206: "battery-only mode", 0x0207: "tuner tool",
         0x0208: "loopback", 0x0301: "input level", 0x0401: "USB/FX record level", 0x0402: "USB monitor level",
         0x0403: "reamp", 0x0404: "USB record mode", 0x0405: "BT record level", 0x0406: "reamp mode"}


def read(link):
    r = None
    for _ in range(3):
        r = pmpreset.ask(link, 0x10, b"")
        if r: break
        time.sleep(0.5)
    if not r: raise RuntimeError("no settings reply")
    out, i = {}, 0
    while i + 4 <= len(r):
        t, n = struct.unpack_from("<HH", r, i); out[t] = r[i + 4:i + 4 + n]; i += 4 + n
    return out


def show(s):
    for t, v in s.items():
        val = int.from_bytes(v, "little", signed=True) if len(v) in (1, 2, 4) and t != 0x0101 else v.hex()
        print(f"  {t:04x} {NAMES.get(t, '?'):28s} = {val}")


if __name__ == "__main__":
    a = sys.argv[1:]
    link = Link()
    try:
        if a == ["show"]: show(read(link))
        elif len(a) == 3 and a[0] == "set":
            tag, val = int(a[1], 16), int(a[2])
            before = read(link).get(tag)
            pmpreset.write_message(link, b"\x11\x11", struct.pack("<Ii", tag, val)); time.sleep(0.5)
            after = read(link).get(tag)
            print(f"{tag:04x} {NAMES.get(tag, '?')}: before {before.hex() if before else None}, after {after.hex() if after else None}",
                  "-> OK" if after is not None and int.from_bytes(after, 'little', signed=True) == val else "-> NOT CHANGED")
        else: sys.exit(__doc__)
    finally:
        link.close()
