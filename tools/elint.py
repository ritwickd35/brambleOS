#!/usr/bin/env python3
"""Engine lint: float/move encodings a program executes (emulator trace) that the hardware-proven programs
(RAT, TS808 as running on the pedal) never executed.  elint.py <model|amp:name> ..."""
import sys, os, json, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import drives2 as D, engine_emu as E
PROVEN = ("rat", "ts808")


def key(w):
    op, b1, imm = w >> 24, (w >> 16) & 255, w & 0xFFFF; c = op >> 4
    if c in (8, 0xC, 0xF): return (c, b1 & 15, op & 15, b1 >> 4, imm & 15, imm >> 8)
    if c == 0xE: return (c, b1 & 15, op & 15, b1 >> 4)
    if c == 9: return (c, b1, op & 15, b1 >> 4, imm >> 9)
    if c in (7, 0xA, 0xD): return (c, b1, op & 15)
    return (c, b1)


def trace(e, start, end, blocks, feed):
    seen = set()
    for b in range(blocks):
        feed(e, b); pc = start; e.steps = 0
        while True:
            seen.add(pc)
            try: e.run(pc, limit=e.steps + 1); break
            except RuntimeError as ex: pc = int(str(ex).split("pc ")[1].split(",")[0], 16)
    return seen


def drive_forms(m):
    prog, _ = D.assemble_packed(m); cf = os.path.join(RE, "logs", f"{m}_coefs.json")
    class V(dict):
        def __missing__(self, k): return 0.3
        def get(self, k, d=None): return 0.3
    img = D.data_image(m, json.load(open(cf)) if os.path.exists(cf) else V())[0]
    e = E.Engine(); e.load_code(0, prog); e.code[1280] = 0xA00E0000
    for a, v in img.items(): e.d[a] = v
    e.d[403] = 1; x = (0.2 * np.sin(np.arange(128) * 0.3)).astype("<f4")
    def feed(e, b): e.d[19:83] = x[b * 64:(b + 1) * 64].view(np.uint32)
    return {key(int(prog[p])): p for p in trace(e, 0, 1280, 2, feed) if p < len(prog)}


def amp_forms(name, kn=(70, 50, 50, 50, 50, 50, 0)):
    import amps2, ampmodel as AM
    s = AM.load(name); prog, A = amps2.assemble_amp(int(s["nst"])); img, _ = amps2.data_image(s, list(kn))
    e = E.Engine(); e.load_code(amps2.START, prog); e.code[amps2.END] = 0xA00E0000
    for a, v in img.items(): e.d[a] = v
    e.d[amps2.FLAG] = 1; x = (0.2 * np.sin(np.arange(128) * 0.3)).astype("<f4")
    def feed(e, b): e.d[19:83] = x[b * 64:(b + 1) * 64].view(np.uint32)
    return {key(int(prog[p - amps2.START])): p for p in trace(e, amps2.START, amps2.END, 2, feed) if amps2.START <= p < amps2.START + len(prog)}


if __name__ == "__main__":
    good = set()
    for m in PROVEN: good |= set(drive_forms(m))
    for t in sys.argv[1:]:
        f = amp_forms(t[4:]) if t.startswith("amp:") else drive_forms(t)
        bad = sorted(k for k in f if k not in good)
        print(t, "OK (only proven forms)" if not bad else f"UNPROVEN forms {bad} at {[f[k] for k in bad]}")
