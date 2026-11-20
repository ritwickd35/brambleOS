#!/usr/bin/env python3
"""Clone (.clo) files and clone slots.
  pmclone.py list                              clone slot names on the pedal
  pmclone.py upload <file.clo> <slot 1-5> <name>   write a clone into a slot (desktop or device .clo accepted)
  pmclone.py clear <slot 1-5>                  put an identity clone named "Empty" back
Format (PROTOCOL.md §6): "VTSI", u32 size, CRC-16/MODBUS over 0x0C.. stored big-endian at 0x08, u32 data size at
0x14, f64[5] biquad A @0x18, f64[5] biquad B @0x40, f32[4] @0x68, u32[4] {0, 128, 128, N} @0x78, f32[128], f32[N]."""
import os, struct, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)


def crc16(d):
    c = 0xFFFF
    for x in d:
        c ^= x
        for _ in range(8): c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
    return c


def parse(b):
    assert b[:4] == b"VTSI", "not a .clo file"
    n = struct.unpack_from("<4I", b, 0x78)[3]
    return dict(bqa=np.array(struct.unpack_from("<5d", b, 0x18)), bqb=np.array(struct.unpack_from("<5d", b, 0x40)),
                p=np.array(struct.unpack_from("<4f", b, 0x68)), fa=np.frombuffer(b, "<f4", 128, 0x88).copy(),
                fb=np.frombuffer(b, "<f4", n, 0x88 + 512).copy())


def build(c, n=512):
    fb = np.zeros(n, "<f4"); k = min(n, len(c["fb"])); fb[:k] = c["fb"][:k]
    body = bytearray(0x88); body[:4] = b"VTSI"
    struct.pack_into("<I", body, 0x14, 512 + 4 * n)
    struct.pack_into("<5d", body, 0x18, *c["bqa"]); struct.pack_into("<5d", body, 0x40, *c["bqb"])
    struct.pack_into("<4f", body, 0x68, *c["p"]); struct.pack_into("<4I", body, 0x78, 0, 128, 128, n)
    b = bytes(body) + np.asarray(c["fa"], "<f4").tobytes() + fb.tobytes()
    b = bytearray(b); struct.pack_into("<I", b, 4, len(b)); struct.pack_into(">H", b, 8, crc16(b[0x0C:]))
    return bytes(b)


def device_copy(b):
    return build(parse(b), 512)


def upload(clo, slot, name):
    import pmpreset
    from pmflash import Link
    dev = clo if clo[0x18:0x1C] == b"PMAM" else device_copy(clo); assert len(dev) == 2696
    msg = struct.pack("<II", 0, 0x0F000000 + slot - 1) + name.encode()[:15].ljust(16, b"\0") + bytes(48) + dev
    link = Link()
    try: pmpreset.write_message(link, b"\x11\x25", msg)
    finally: link.close()
    time.sleep(0.5)


def names():
    import pmpreset, re
    from pmflash import Link
    link = Link()
    try:
        r = pmpreset.ask(link, 0x24)
        if r is None: r = pmpreset.ask(link, 0x24)
    finally: link.close()
    return [s.decode() for s in re.findall(rb"[ -~]{1,16}", r or b"")]


def main():
    a = sys.argv[1:]
    if a[0] == "list": print(names())
    elif a[0] == "upload": upload(open(a[1], "rb").read(), int(a[2]), a[3]); print(names())
    elif a[0] == "clear":
        ident = dict(bqa=np.r_[1.0, 0, 0, 0, 0], bqb=np.r_[1.0, 0, 0, 0, 0], p=np.zeros(4), fa=np.r_[1.0, np.zeros(127)], fb=np.r_[1.0, np.zeros(511)])
        upload(build(ident), int(a[1]), "Empty"); print(names())


if __name__ == "__main__":
    main()


# ---- our own clone format ("PMAM", read by the planned own clone engine; NAM_PLAN.md) ------------------------
# same VTSI container (size, CRC, data size 0xA00 as a device copy) so the pedal's slot storage and upload accept it
#   0x18 "PMAM", u32 version, u32 type (0 amp only, 1 amp + cab), u32 n_params, u32 has_fir
#   0x88 f32 params[n] (ampmodel.NAMES order)              (where the stock clone keeps its 128-tap filter)
#   0x288 i32 fir[512] (cab for amp + cab captures, 2^23 = full scale, the pedal's cab format); unused otherwise
PMAM_VER = 1


def build_pmam(settings, fir=None, full=False):
    import ampmodel as AM
    b = bytearray(0x88 + 512 + 2048); b[:4] = b"VTSI"; struct.pack_into("<I", b, 0x14, 512 + 4 * 512)
    p = [float(settings.get(k, {"os": 2.0, "olp": 19000.0}.get(k, 0.0))) for k in AM.NAMES]
    struct.pack_into("<4s4I", b, 0x18, b"PMAM", PMAM_VER, 1 if full else 0, len(p), 1 if fir is not None else 0)
    struct.pack_into("<4I", b, 0x78, 0, 128, 128, 512)
    struct.pack_into(f"<{len(p)}f", b, 0x88, *p)
    h = np.zeros(512, "<i4"); h[0] = 1 << 23
    if fir is not None:
        f = np.zeros(512); f[:min(512, len(fir))] = np.asarray(fir, float)[:512]
        h = np.clip(np.round(f * 2 ** 23), -8388607, 8388607).astype("<i4")
    b[0x288:0x288 + 2048] = h.tobytes(); struct.pack_into("<I", b, 4, len(b)); struct.pack_into(">H", b, 8, crc16(b[0x0C:]))
    return bytes(b)


def parse_pmam(b):
    import ampmodel as AM
    if b[0x18:0x1C] != b"PMAM": return None
    ver, typ, n, hf = struct.unpack_from("<4I", b, 0x1C)
    s = dict(zip(AM.NAMES, struct.unpack_from(f"<{n}f", b, 0x88))); s["nst"] = int(round(s["nst"]))
    return dict(version=ver, full=bool(typ), settings=s, fir=np.frombuffer(b, "<i4", 512, 0x288).astype(float) / 2 ** 23 if hf else None)
