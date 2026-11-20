#!/usr/bin/env python3
"""Pocket Master preset tool (write commands confirmed from Sonicake Manager captures).

  pmpreset.py current                      read the current preset index (12 43)
  pmpreset.py write <index0> <file.bin>    write a 494-byte preset record (as saved by pmbackup.py) into slot index0 (11 4F)
  pmpreset.py select <index0>              switch the pedal to preset index0 (11 43, u16 index)

index0 is 0-based (P01 = 0). Refuses to run while Sonicake Manager is open.
"""
import os, struct, subprocess, sys, time
sys.path.insert(0, os.path.dirname(__file__))
import pmsysex as P
from pmflash import Link


def guard():
    if subprocess.run(["pgrep", "-f", "Sonicake Manager.app"], capture_output=True).returncode == 0:
        sys.exit("Sonicake Manager is running. Quit it first.")


def ask(link, obj, data=b"", timeout=1.5):
    cmd = bytes((0x12, obj))
    for fr in P.build_message(cmd, data):
        link.out.send(link.mido.Message.from_bytes(list(fr)))
    t_end = time.time() + timeout
    buf, expect = bytearray(), None
    while time.time() < t_end:
        m = link.inp.poll()
        if m is None:
            time.sleep(0.002); continue
        if m.type != "sysex":
            continue
        f = P.parse_frame(bytes([0xF0]) + bytes(m.data) + b"\xf7")
        p = f["payload"]
        if f["index"] == 0 and p[:2] in (cmd, bytes((0x11, obj))):
            buf, expect = bytearray(p), f["count"]
        elif expect is not None:
            buf += p
        if expect is not None and f["index"] == expect - 1:
            return bytes(buf[2:])
    return None


def write_message(link, cmd, data):
    for fr in P.build_message(cmd, data):
        r = link.send(fr, 2)
        if r != b"\x14\x08\x00":
            raise RuntimeError(f"no/negative ACK ({r.hex() if r else None})")


def current(link):
    r = ask(link, 0x43)
    if r is None:
        r = ask(link, 0x43)                         # the first request after opening the port is sometimes lost
    if not r:
        return None
    return struct.unpack_from("<H", r)[0] if len(r) >= 2 else r[0]


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    guard()
    link = Link()
    if a[0] == "current":
        print("current preset index:", current(link))
    elif a[0] == "write" and len(a) == 3:
        rec = open(a[2], "rb").read()
        if len(rec) != 494:
            sys.exit("preset record must be 494 bytes")
        write_message(link, b"\x11\x4f", struct.pack("<I", int(a[1])) + rec[4:])
        time.sleep(0.3)
        print("written; current preset now", current(link))
    elif a[0] == "select" and len(a) == 2:
        write_message(link, b"\x11\x43", struct.pack("<I", int(a[1])))
        time.sleep(0.3)
        print("current preset now", current(link))
    else:
        sys.exit(__doc__)
    link.close()


if __name__ == "__main__":
    main()
