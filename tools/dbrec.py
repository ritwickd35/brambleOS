#!/usr/bin/env python3
"""Effect DB record parser (format from NOTES 45): returns [(group, index, fxid, title, [(knob, default, max)])]."""
import struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_cut import groups


def records(path):
    d = open(path, "rb").read(); g = groups(d, 0x10000); out = []
    for gi, gl in enumerate(g):
        for i, r in enumerate(gl):
            o = 0x10000 + r; n = d[o + 8]
            if not 0 < n <= 12: continue
            sbase = o + 16 + 24 * n
            def s(off): e = d.find(b"\0", sbase + off); return d[sbase + off:e].decode("latin-1")
            title = d[sbase:d.find(b"\0", sbase)].decode("latin-1"); kn = []
            for k in range(n):
                b = o + 16 + 24 * k; noff = struct.unpack_from("<H", d, b + 2)[0]
                mn, mx, df = struct.unpack_from("<f", d, b + 4)[0], struct.unpack_from("<f", d, b + 8)[0], struct.unpack_from("<f", d, b + 16)[0]
                kn.append((s(noff), df, mx, d[b + 20], mn))     # index = parameter the module reads; mn = minimum
            out.append((gi, i, struct.unpack_from("<I", d, o)[0], title, kn))
    return out


if __name__ == "__main__":
    for r in records(sys.argv[1]):
        if r[0] in (7, 8): print(r)
