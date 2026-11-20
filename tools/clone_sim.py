#!/usr/bin/env python3
"""Run the pedal's stock Clone module offline (ARM code in Unicorn + its engine program in engine_emu).
  clone_sim.py <file.clo> <in.f32> <out.f32> [Gain VOL Bass Middle Treble]   (mono float32, 44.1 kHz)"""
import os, struct, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import amp_sim as S, engine_emu as E, pmclone

CLO_AT = 0x29080000
EQ_PROG = 0xE00                                   # chain: DRV 0x000, AMP/CLONE 0x500, CAB 0xB00, EQ 0xE00


class Clone:
    def __init__(self, clo, knobs=(50, 50, 50, 50, 50)):
        self.a = S.Amp(0, grp=9); self.eng = E.Engine()
        self.a.mu.mem_write(CLO_AT, pmclone.device_copy(clo)); self.set(knobs)

    def set(self, knobs):
        a = self.a; a.mu.mem_write(S.PRM, struct.pack("<8f", *(list(map(float, knobs)) + [0.0] * (8 - len(knobs)))))
        a.mu.mem_write(S.PRM + 64, struct.pack("<I", CLO_AT)); a.call(a.e0, [S.PRM, S.PRM + 64])

    def process(self, x):
        x = np.asarray(x, np.float32); y = np.zeros_like(x); n = len(x) // 64 * 64; units = []
        a, eng = self.a, self.eng
        for i in range(0, n, 64):
            a.call(a.e1, [S.BUF, 64, S.PRM, 0, S.EN, 0, 0])
            eng.d[:] = np.frombuffer(a.mu.mem_read(0x28000000, 0x4000), "<u4")
            eng.code[:] = np.frombuffer(a.mu.mem_read(0x28004000, 0x4000), "<u4")
            eng.code[EQ_PROG] = 0xA00E0000                   # the clone ends with a jump to the EQ slot: stop there
            eng.d[0x13:0x53] = x[i:i + 64].view(np.uint32)
            eng.steps = 0; eng.units = 0; eng.run(S.AMP_PROG, limit=5_000_000)
            y[i:i + 64] = eng.d[0x13:0x53].view(np.float32); units.append(eng.units)
            a.mu.mem_write(0x28000000, eng.d.astype("<u4").tobytes())
        return y, (int(np.mean(units)) if units else 0)


def main():
    clo, i, o = sys.argv[1:4]; k = [float(v) for v in sys.argv[4:]] or [50] * 5
    y, u = Clone(open(clo, "rb").read(), k).process(np.fromfile(i, "<f4")); y.astype("<f4").tofile(o)
    print(f"done, {u} engine units per block")


if __name__ == "__main__":
    main()
