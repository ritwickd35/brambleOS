#!/usr/bin/env python3
"""Simulate cut 8 end to end: combo4.bin (ARM, Unicorn) + engine model (code 0xE00 only), produce the audio the
pedal would send, then decode it.  eprobe_sim.py [blocks] -> audio/eprobe_sim.f32, logs/eprobe_sim_runs.json"""
import os, struct, sys, json
import numpy as np
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS
from unicorn.arm_const import *
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import engine_emu as E

code = open(os.environ.get("EPROBE_BIN", os.path.join(RE, "cut1", "combo4.bin")), "rb").read()
mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
mu.mem_map(0x10000000, 0x10000); mu.mem_write(0x10002A00, code)
mu.mem_write(0x10002850, b"\x70\x47"); mu.mem_write(0x10002910, b"\x70\x47")      # stubs for the Red Fuzz entries
RAM = 0x20000000; mu.mem_map(RAM, 0x10000); mu.mem_map(0xE0000000, 0x100000); mu.mem_map(0x28000000, 0x10000)
mu.mem_write(0xE000ED88, struct.pack("<I", 0xF << 20))
STOP = RAM + 0xF000; mu.mem_write(STOP, b"\x00\xbf" * 8)
try: mu.reg_write(UC_ARM_REG_FPEXC, 0x40000000)
except Exception: pass


def call(fn, args):
    sp = RAM + 0xE000; st = args[4:]; sp -= 4 * len(st); mu.mem_write(sp, struct.pack(f"<{len(st)}I", *st))
    for r, v in zip([UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3], args[:4]): mu.reg_write(r, v)
    mu.reg_write(UC_ARM_REG_SP, sp); mu.reg_write(UC_ARM_REG_LR, STOP | 1); mu.emu_start(fn | 1, STOP, count=5_000_000)


eng = E.Engine()
call(0x10002A00, [RAM + 0x1000, 0])
nblk = int(sys.argv[1]) if len(sys.argv) > 1 else 80000
out = np.zeros(nblk * 64, np.float32); unk = {}
for b in range(nblk):
    call(0x10002A1C, [RAM + 0x2000, 64, RAM + 0x1000, 0, RAM + 0x3000, 0, 0])
    eng.d[:] = np.frombuffer(mu.mem_read(0x28000000, 0x4000), "<u4")
    eng.code[0xE00:] = np.frombuffer(mu.mem_read(0x28004000 + 4 * 0xE00, 0x800), "<u4")
    eng.steps = 0
    try: eng.run(0xE00, limit=20000)
    except RuntimeError: pass
    mu.mem_write(0x28000000, eng.d.astype("<u4").tobytes()); mu.mem_write(0x20002390, struct.pack("<I", eng.steps))
    out[b * 64:(b + 1) * 64] = eng.d[0x93:0xD3].view(np.float32)
    if b > 2000 and not out[(b - 600) * 64:b * 64].any(): out = out[:b * 64]; break
p = os.path.join(RE, "audio", "eprobe_sim.f32"); out.tofile(p)
if os.environ.get("EPROBE_BIN"): print("blocks", len(out) // 64); sys.exit(0)
import eprobe_decode as D
runs, bad, nf, tab = D.decode(p)
json.dump(dict(runs={str(k): v for k, v in runs.items()}, bad=bad), open(os.path.join(RE, "logs", "eprobe_sim_runs.json"), "w"))
print(f"blocks {len(out)//64} seconds {len(out)/44100:.0f} frames {nf} decoded {len(runs)} bad {bad} unknown-ops {len(eng.unknown)}")
