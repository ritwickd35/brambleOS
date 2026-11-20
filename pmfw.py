#!/usr/bin/env python3
"""Sonicake Pocket Master "HTFW" firmware container tool (reverse engineered from V1.3.3).

  pmfw.py info    <fw.bin>             header, sections, CRC check
  pmfw.py unpack  <fw.bin> <outdir>    write sections + manifest.json
  pmfw.py pack    <outdir> <fw.bin>    rebuild container, recompute section CRCs
  pmfw.py modules <fw.bin>             DSP effect-module table (section @0x240000) + names (@0x190000)
  pmfw.py presets <fw.bin>             factory preset names (@0x190000)

Container layout (little endian):
  0x00 'HTFW'
  0x04 u16  BIG-endian CRC-16/MODBUS of file bytes 0x06..end (checked by Sonicake Manager's checkCrc)
  0x06 u16  0x0001 (kept verbatim)
  0x08 u32  total file size
  0x0C char[16] product name "Pocket Master"
  0x1C 'V', major, minor, patch
  0x20 u16  0, u16 section count
  0x24 u32  payload size (sum of section sizes)
  0x38 section[count] { u16 BIG-endian crc16/modbus of section data; u8 0x00; u8 type; u32 flash_addr; u32 offset; u32 size }
  0x88 payload (section offsets are relative to 0x88)
"""
import json, os, struct, sys

HDR = 0x88
TYPES = {0x63: "dsp_kernel", 0x67: "dsp_modules", 0x66: "cab_catalog", 0x62: "mcu_app", 0x65: "effect_db_presets"}
GROUPS = ["NR", "FX1", "DRV", "AMP", "CAB", "EQ", "FX2", "DLY", "RVB", "CLONE(NAM)", "SHARED"]


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def parse(fw: bytes):
    if fw[:4] != b"HTFW":
        sys.exit("not an HTFW file")
    unk, total = struct.unpack_from("<II", fw, 4)
    file_crc = struct.unpack_from(">H", fw, 4)[0]
    name = fw[0x0C:0x1C].split(b"\0")[0].decode()
    ver = fw[0x1C:0x20]
    _, count = struct.unpack_from("<HH", fw, 0x20)
    payload = struct.unpack_from("<I", fw, 0x24)[0]
    secs = []
    for i in range(count):
        crc, mid, typ, addr, off, size = struct.unpack_from(">HBB", fw, 0x38 + 16 * i) + struct.unpack_from("<III", fw, 0x3C + 16 * i)
        data = fw[HDR + off:HDR + off + size]
        secs.append(dict(index=i, type=typ, crc=crc, mid=mid,
                         flash_addr=addr, offset=off, size=size, data=data))
    return dict(unknown04=unk, file_crc=file_crc, file_crc_ok=crc16_modbus(fw[6:]) == file_crc, total=total, name=name, version=ver, payload=payload, sections=secs, raw=fw)


def cmd_info(path):
    h = parse(open(path, "rb").read())
    v = h["version"]
    print(f"{h['name']}  {chr(v[0])}{v[1]}.{v[2]}.{v[3]}  size={h['total']:#x}  payload={h['payload']:#x}  file-crc16={h['file_crc']:#06x} {'OK' if h['file_crc_ok'] else 'BAD'}")
    for s in h["sections"]:
        ok = crc16_modbus(s["data"]) == s["crc"]
        print(f"  [{s['index']}] type={s['type']:#04x} {TYPES.get(s['type'], '?'):18s} flash={s['flash_addr']:#08x} "
              f"size={s['size']:#08x} crc16={s['crc']:#06x} {'OK' if ok else 'BAD'}")


def cmd_unpack(path, out):
    h = parse(open(path, "rb").read())
    os.makedirs(out, exist_ok=True)
    man = dict(header_raw=h["raw"][:HDR].hex(), sections=[])
    for s in h["sections"]:
        fn = f"{s['index']}_{TYPES.get(s['type'], 'unknown')}_{s['flash_addr']:08x}.bin"
        open(os.path.join(out, fn), "wb").write(s["data"])
        man["sections"].append(dict(file=fn, type=s["type"], mid=s["mid"], flash_addr=s["flash_addr"]))
    json.dump(man, open(os.path.join(out, "manifest.json"), "w"), indent=2)
    print(f"unpacked {len(h['sections'])} sections to {out}")


def cmd_pack(src, path):
    man = json.load(open(os.path.join(src, "manifest.json")))
    hdr = bytearray(bytes.fromhex(man["header_raw"]))
    payload = bytearray()
    for i, s in enumerate(man["sections"]):
        data = open(os.path.join(src, s["file"]), "rb").read()
        struct.pack_into(">HBB", hdr, 0x38 + 16 * i, crc16_modbus(data), s["mid"], s["type"])
        struct.pack_into("<III", hdr, 0x3C + 16 * i, s["flash_addr"], len(payload), len(data))
        payload += data
    struct.pack_into("<HH", hdr, 0x20, 0, len(man["sections"]))
    struct.pack_into("<I", hdr, 0x24, len(payload))
    struct.pack_into("<I", hdr, 0x08, HDR + len(payload))
    out = bytearray(bytes(hdr) + payload)
    struct.pack_into(">H", out, 4, crc16_modbus(bytes(out[6:])))
    open(path, "wb").write(out)
    print(f"packed {path} ({len(out):#x} bytes), section CRCs and file CRC recomputed.")


def _groups(d, base, ngroups):
    ptrs = struct.unpack_from(f"<{ngroups}I", d, base + 0x14)
    out = []
    for p in ptrs:
        if p == 0:
            out.append([]); continue
        c = struct.unpack_from("<I", d, base + p)[0]
        out.append(list(struct.unpack_from(f"<{c}I", d, base + p + 4)))
    return out


def _effect_name(db, rec_off, next_off):
    """Effect record (inferred): ... ffffffff, u8 id ff ff ff, u16 0, u8 n?, u8 0, then N param blocks of 0x18 bytes
    {u16 0xffff, u16 ui_pos, f32 min, f32 max, f32 step, f32 default, u8 idx, u8 0xff, u8 0, u8 kind}, then
    NUL-terminated strings: effect name, [optional screen title], one name per param."""
    rec = db[rec_off:next_off]
    h = rec.find(b"\xff\xff\xff\xff")
    if h < 0:
        return []
    p, n = h + 12, 0
    while rec[p:p + 2] == b"\xff\xff" and p + 0x18 <= len(rec):
        p += 0x18; n += 1
    strs = []
    for x in rec[p:].split(b"\0"):
        if not x or not all(0x20 <= c < 0x7F for c in x):
            break
        strs.append(x.decode())
    return strs[:n + 2]


def cmd_modules(path):
    h = parse(open(path, "rb").read())
    sec = {s["flash_addr"]: s["data"] for s in h["sections"]}
    mods, db = sec[0x240000], sec[0x190000]
    code = _groups(mods, 0, 11)
    names = _groups(db, 0x10000, 11)
    for gi, offs in enumerate(code):
        print(f"{GROUPS[gi]}: {len(offs)} module(s)")
        for j, o in enumerate(offs):
            if gi == 10:
                print(f"   #{j} blob@{o:#07x} (shared code, no module header)"); continue
            hs, cs, ts, st, fi, fp = struct.unpack_from("<6I", mods, o)
            nm = ""
            if gi < len(names) and j < len(names[gi]):
                r = 0x10000 + names[gi][j]
                nxt = 0x10000 + names[gi][j + 1] if j + 1 < len(names[gi]) else r + 0x200
                p = _effect_name(db, r, nxt)
                nm = f"{p[0]}  strings={p[1:]}" if p else ""
            print(f"   #{j:2d} blob@{o:#07x} code={cs:#06x} state={st:#05x} entry0={fi:#010x} entry1={fp:#010x}  {nm}")


def cmd_presets(path):
    h = parse(open(path, "rb").read())
    db = {s["flash_addr"]: s["data"] for s in h["sections"]}[0x190000]
    for i, off in enumerate(range(0x1000, 0x10000, 0x400)):
        if db[off:off + 2] != b"\xa5\x5a":
            continue
        print(f"  {i + 1:2d} @{0x190000 + off:#08x}  {db[off + 0x0A:off + 0x15].split(b'\0')[0].decode(errors='replace')}")


if __name__ == "__main__":
    a = sys.argv[1:]
    cmds = {"info": cmd_info, "unpack": cmd_unpack, "pack": cmd_pack, "modules": cmd_modules, "presets": cmd_presets}
    if not a or a[0] not in cmds:
        sys.exit(__doc__)
    cmds[a[0]](*a[1:])
