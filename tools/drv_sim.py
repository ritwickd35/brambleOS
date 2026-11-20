#!/usr/bin/env python3
"""Run the built DRV #7 multi-drive blob end to end: ARM code (Unicorn) + engine model, module image mapped at
0x13000 like on the DSP. Compares DS-1 / TS808 output with dsp/host.  drv_sim.py <src dir of a build>"""
import os, struct, subprocess, sys
import numpy as np
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS
from unicorn.arm_const import *
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import engine_emu as E
from build_cut import groups, IMG_BASE

src = sys.argv[1]
m = open(os.path.join(src, "1_dsp_modules_00240000.bin"), "rb").read(); g = groups(m, 0); o = g[2][7]
hs, cs, ts, st, e0, e1 = struct.unpack_from("<6I", m, o)
mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
mu.mem_map(IMG_BASE & ~0xFFF, (len(m) + 0x2000) & ~0xFFF); mu.mem_write(IMG_BASE, m)
mu.mem_map(0x10000000, 0x10000); mu.mem_write(0x10002800, m[o + hs:o + ts])
RAM = 0x20000000; mu.mem_map(RAM, 0x10000); mu.mem_map(0xE0000000, 0x100000); mu.mem_map(0x28000000, 0x10000)
mu.mem_write(0xE000ED88, struct.pack("<I", 0xF << 20))
STOP = RAM + 0xF000; mu.mem_write(STOP, b"\x00\xbf" * 8)
try: mu.reg_write(UC_ARM_REG_FPEXC, 0x40000000)
except Exception: pass
mu.mem_write(0x28004000, m[o + ts:o + ts + st])                    # the loader puts the blob's program at code 0
PRM, EN = RAM + 0x1000, RAM + 0x3000; mu.mem_write(EN, b"\x01")


def call(fn, args):
    sp = RAM + 0xE000; s = args[4:]; sp -= 4 * len(s); mu.mem_write(sp, struct.pack(f"<{len(s)}I", *s))
    for r, v in zip([UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3], args[:4]): mu.reg_write(r, v)
    mu.reg_write(UC_ARM_REG_SP, sp); mu.reg_write(UC_ARM_REG_LR, STOP | 1); mu.emu_start(fn | 1, STOP, count=20_000_000)


def run(model_knob, knobs, x):
    p = [knobs[0], model_knob, knobs[2], 50.0, knobs[1]] + [0.0] * 3      # drive, model, level, -, tone
    mu.mem_write(PRM, struct.pack("<8f", *p)); call(e0, [PRM, 0])
    eng = E.Engine(); y = np.zeros_like(x); units = []
    for b in range(len(x) // 64):
        call(e1, [RAM + 0x2000, 64, PRM, 0, EN, 0, 0])
        eng.d[:] = np.frombuffer(mu.mem_read(0x28000000, 0x4000), "<u4")
        eng.code[:] = np.frombuffer(mu.mem_read(0x28004000, 0x4000), "<u4"); eng.code[0x500] = 0xA00E0000
        eng.d[0x13:0x53] = x[b * 64:(b + 1) * 64].view(np.uint32)
        eng.steps = 0; eng.units = 0; eng.run(0, limit=2_000_000); units.append(eng.units)
        y[b * 64:(b + 1) * 64] = eng.d[0x13:0x53].view(np.float32)
        mu.mem_write(0x28000000, eng.d.astype("<u4").tobytes())
    return y, int(np.mean(units))


x = (0.05 * np.random.default_rng(7).standard_normal(64 * 64)).astype("<f4")
for name, mk in (("ds1", 10.0), ("ts808", 80.0), ("ds1", 10.0)):
    k = (70.0, 40.0, 60.0)
    ref = np.frombuffer(subprocess.run([os.path.join(RE, "dsp", "host"), name, *map(str, k)], input=x.tobytes(),
                                       capture_output=True).stdout, "<f4")
    y, u = run(mk, (k[0], k[1], k[2]), x)
    err = float(np.max(np.abs(y - ref)) / np.max(np.abs(ref)))
    print(f"{name}: rel err vs C model {err:.2e}, engine units/block {u}")
