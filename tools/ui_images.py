#!/usr/bin/env python3
"""Find every LVGL image descriptor in the MCU app ({u32 header cf:5 w:11 h:11, u32 data_size, u32 data_ptr})
and export them as PNGs to ui/export/ plus ui/export/index.json and a contact sheet ui/contact.png.
CPU address = file offset + 0x10000. cf 4 = RGB565, cf 5 = RGB565 + 8-bit alpha (3 bytes/px)."""
import json, os, struct, sys
import numpy as np
from PIL import Image
RE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BPP = {4: 2, 5: 3}


def find(b):
    out = []
    for o in range(0, len(b) - 12, 4):
        h, sz, ptr = struct.unpack_from("<3I", b, o)
        cf, w, hh = h & 31, (h >> 10) & 0x7FF, (h >> 21) & 0x7FF
        if cf in BPP and 0 < w <= 320 and 0 < hh <= 320 and sz == w * hh * BPP[cf] and 0x10000 <= ptr - 0 and ptr - 0x10000 + sz <= len(b):
            out.append(dict(desc=o + 0x10000, cf=cf, w=w, h=hh, data=ptr))
    return out


def rgba(b, d):
    o = d["data"] - 0x10000; n = d["w"] * d["h"]
    if d["cf"] == 4:
        p = np.frombuffer(b, "<u2", n, o); a = np.full(n, 255, np.uint8)
    else:
        r = np.frombuffer(b, np.uint8, 3 * n, o).reshape(n, 3); p = r[:, 0].astype(np.uint16) | (r[:, 1].astype(np.uint16) << 8); a = r[:, 2]
    R = ((p >> 11) & 31) * 255 // 31; G = ((p >> 5) & 63) * 255 // 63; B = (p & 31) * 255 // 31
    return np.stack([R, G, B, a], 1).astype(np.uint8).reshape(d["h"], d["w"], 4)


def main():
    b = open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(RE, "build/dl14/src/3_mcu_app_00000000.bin"), "rb").read()
    ds = find(b); od = os.path.join(RE, "ui", "export"); os.makedirs(od, exist_ok=True)
    for i, d in enumerate(ds):
        d["file"] = f"{i:03d}_{d['w']}x{d['h']}.png"; Image.fromarray(rgba(b, d), "RGBA").save(os.path.join(od, d["file"]))
    json.dump(ds, open(os.path.join(od, "index.json"), "w"), indent=0)
    # contact sheet on a dark background, 2x scale
    W = 1400; x = y = 8; rowh = 0; sheet = []
    for d in ds:
        w, h = 2 * d["w"] + 8, 2 * d["h"] + 8
        if x + w > W: x = 8; y += rowh; rowh = 0
        sheet.append((x, y, d)); x += w; rowh = max(rowh, h)
    img = Image.new("RGBA", (W, y + rowh + 8), (40, 40, 40, 255))
    for x, y, d in sheet:
        im = Image.open(os.path.join(od, d["file"])).resize((2 * d["w"], 2 * d["h"]), Image.NEAREST); img.alpha_composite(im, (x, y))
    img.save(os.path.join(RE, "ui", "contact.png"))
    tot = sum(d["w"] * d["h"] * BPP[d["cf"]] for d in ds)
    print(f"{len(ds)} images ({sum(d['cf'] == 4 for d in ds)} plain, {sum(d['cf'] == 5 for d in ds)} with alpha), {tot // 1024} KB of pixels; largest {max(ds, key=lambda d: d['w'] * d['h'])['file']}")


if __name__ == "__main__":
    main()
