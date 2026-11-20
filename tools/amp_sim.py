#!/usr/bin/env python3
"""Run a stock AMP module offline: its ARM code (Unicorn, with the DSP kernel and module image mapped like on the
DSP) + its engine program (engine_emu). No pedal needed.
  amp_sim.py probe <amp#>                      load + one block, report what got copied where
  amp_sim.py run <amp#> <in.f32> <out.f32> [knob ...]   process mono float32 (44.1 kHz)"""
import os, struct, sys
import numpy as np
from unicorn import Uc, UcError, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_MEM_UNMAPPED
from unicorn.arm_const import *
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import engine_emu as E
from build_cut import groups, IMG_BASE

SRC = os.environ.get("AMP_SRC", os.path.join(RE, "build", "daily", "src"))
KER = open(os.path.join(SRC, "0_dsp_kernel_00200000.bin"), "rb").read()
MOD = open(os.path.join(SRC, "1_dsp_modules_00240000.bin"), "rb").read()
AMP_CODE, AMP_RAM, AMP_PROG = 0x10003800, 11 * 1024, 1280          # slot RAM; engine code word of the AMP block
CAB_PROG = 2816                                                    # next block's first engine code word
RAM = 0x20000000; STOP = RAM + 0x1F000; PRM = RAM + 0x1D000; BUF = RAM + 0x1B000; EN = RAM + 0x1A000


class Amp:
    def __init__(self, idx, trace=False, grp=3):
        self.mu = mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        mu.mem_map(0x0, 0x13000 + ((len(MOD) + 0xFFFF) & ~0xFFFF))         # kernel at 0x4000, modules at 0x13000
        mu.mem_write(0x4000, KER); mu.mem_write(IMG_BASE, MOD)
        mu.mem_map(0x10000000, 0x20000); mu.mem_map(RAM, 0x20000); mu.mem_map(0x28000000, 0x20000)
        mu.mem_map(0x29000000, 0xE0000); mu.mem_map(0xE0000000, 0x100000)
        mu.mem_write(0xE000ED88, struct.pack("<I", 0xF << 20)); mu.mem_write(STOP, b"\x00\xbf" * 8)
        try: mu.reg_write(UC_ARM_REG_FPEXC, 0x40000000)
        except Exception: pass
        k = 0xE3D0 - 0x4000; mu.mem_write(RAM, KER[k:k + 0x218C])        # kernel RAM code (scatter-load)
        self.bad = []
        def unm(uc, acc, addr, size, val, ud): self.bad.append(addr); return False
        mu.hook_add(UC_HOOK_MEM_UNMAPPED, unm)
        g = groups(MOD, 0)[grp]; o = g[idx]
        self.hdr = struct.unpack_from("<6I", MOD, o); self.o = o
        hs, cs, ts, st, e0, e1 = self.hdr
        if cs: mu.mem_write(AMP_CODE, MOD[o + hs:o + ts])
        if st: mu.mem_write(0x28004000 + 4 * AMP_PROG, MOD[o + ts:o + ts + st])     # engine code RAM, word 1280
        self.e0, self.e1 = e0, e1
        mu.mem_write(EN, b"\x01")

    def call(self, fn, args):
        mu = self.mu; sp = RAM + 0x19000; s = args[4:]; sp -= 4 * len(s)
        if s: mu.mem_write(sp, struct.pack(f"<{len(s)}I", *s))
        for r, v in zip([UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3], args[:4]): mu.reg_write(r, v)
        mu.reg_write(UC_ARM_REG_SP, sp); mu.reg_write(UC_ARM_REG_LR, STOP | 1)
        mu.emu_start(fn | 1, STOP, count=50_000_000)

    def params(self, knobs):
        self.mu.mem_write(PRM, struct.pack("<8f", *(list(knobs) + [0.0] * (8 - len(knobs)))))
        self.call(self.e0, [PRM, 0])

    def block(self, eng, x):
        self.call(self.e1, [BUF, 64, PRM, 0, EN, 0, 0])
        eng.d[:] = np.frombuffer(self.mu.mem_read(0x28000000, 0x4000), "<u4")
        eng.code[:] = np.frombuffer(self.mu.mem_read(0x28004000, 0x4000), "<u4")
        eng.code[CAB_PROG] = 0xA00E0000
        eng.d[0x13:0x53] = x.view(np.uint32)
        eng.steps = 0; eng.units = 0; eng.run(AMP_PROG, limit=5_000_000)
        y = eng.d[0x13:0x53].view(np.float32).copy()
        self.mu.mem_write(0x28000000, eng.d.astype("<u4").tobytes())
        return y, eng.units


def main():
    a = sys.argv[1:]
    if a[0] == "probe":
        amp = Amp(int(a[1])); print("header", amp.hdr)
        before = bytes(amp.mu.mem_read(0x28005400, 0x1800))
        try: amp.params([50.0] * 8)
        except UcError as e: print("entry0 stopped:", e, "pc", hex(amp.mu.reg_read(UC_ARM_REG_PC)), "unmapped", [hex(b) for b in amp.bad[:3]]); return
        code = np.frombuffer(amp.mu.mem_read(0x28005400, 0x1800), "<u4"); slot = np.frombuffer(amp.mu.mem_read(AMP_CODE, AMP_RAM), "<u4")
        print("after entry0: engine program words", int(np.count_nonzero(code)), "slot RAM words", int(np.count_nonzero(slot)))
        eng = E.Engine(); x = (0.1 * np.sin(2 * np.pi * 220 * np.arange(64) / 44100)).astype("<f4")
        try: y, u = amp.block(eng, x); print("block ok, units", u, "out rms", float(np.sqrt(np.mean(y ** 2))))
        except Exception as e: print("block stopped:", repr(e)[:200], "pc", hex(amp.mu.reg_read(UC_ARM_REG_PC)))
    elif a[0] == "run":
        amp = Amp(int(a[1])); x = np.fromfile(a[2], "<f4"); knobs = [float(v) for v in a[4:]] or [50.0] * 8
        amp.params(knobs); eng = E.Engine(); y = np.zeros_like(x); units = []
        for b in range(len(x) // 64):
            y[b * 64:(b + 1) * 64], u = amp.block(eng, x[b * 64:(b + 1) * 64]); units.append(u)
        y.astype("<f4").tofile(a[3]); print("units/block", int(np.mean(units)), "max", int(np.max(units)))


if __name__ == "__main__":
    main()
