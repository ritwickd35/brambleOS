#!/usr/bin/env python3
"""Resolve movw/movt constant pairs (and ldr-literal words) in an objdump -D Thumb listing.
  armrefs.py <file.dis> [lo hi]     prints address, register, constant (only constants in [lo, hi) if given)"""
import re, sys
L = open(sys.argv[1]).read().splitlines()
lo = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0
hi = int(sys.argv[3], 16) if len(sys.argv) > 3 else 1 << 32
pend = {}
rx = re.compile(r"\s*([0-9a-f]+):\s+(?:[0-9a-f]{4} ?){1,2}\s+(movw|movt)\s+(\w+), #(\d+)")
for ln in L:
    m = rx.match(ln)
    if not m: continue
    a, op, r, v = int(m.group(1), 16), m.group(2), m.group(3), int(m.group(4))
    if op == "movw": pend[r] = (a, v)
    elif r in pend:
        a0, v0 = pend.pop(r); c = (v << 16) | v0
        if lo <= c < hi: print(f"{a0:08x} {r:4s} {c:#010x}")
