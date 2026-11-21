#!/usr/bin/env python3
"""ui_view.py <in.rgb565> <out.png>: panel-byte-order RGB565 (160x128) -> PNG (1x and 4x)."""
import sys, numpy as np
from PIL import Image
v = np.fromfile(sys.argv[1], ">u2").astype(np.uint32).reshape(128, 160)      # file holds the u16 as stored (byte-swapped value)
a = np.stack([(v >> 11) << 3, ((v >> 5) & 63) << 2, (v & 31) << 3], -1).astype(np.uint8); a |= a >> 5
im = Image.fromarray(a); im.save(sys.argv[2]); im.resize((640, 512), Image.NEAREST).save(sys.argv[2].replace(".png", "_4x.png"))
