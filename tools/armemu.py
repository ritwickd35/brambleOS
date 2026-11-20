#!/usr/bin/env python3
"""Run a pedal module binary (ARM Thumb, Cortex-M4F) in the Unicorn emulator, exactly as built for the pedal.
  armemu.py <module.bin> <link base hex> <sym file> <knob0> <knob1> <knob2> < in.f32 > out.f32
Calls lt_entry0(params) once, then lt_entry1(buf, 64, params, 0, &enable, 0, 0) per 64-frame block with the mono
input in the left channel of an interleaved stereo buffer; writes the left channel back out."""
import os, struct, sys
import numpy as np
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS
from unicorn.arm_const import *

code = open(sys.argv[1], "rb").read(); base = int(sys.argv[2], 16)
sym = {l.split()[2]: int(l.split()[0], 16) for l in open(sys.argv[3])}
knobs = [float(v) for v in sys.argv[4:7]] + [0.0] * 5
x = np.frombuffer(sys.stdin.buffer.read(), "<f4")
mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
mu.mem_map(base & ~0xFFFF, 0x10000); mu.mem_write(base, code)
RAM = 0x20000000; mu.mem_map(RAM, 0x10000)
SYS = 0xE0000000; mu.mem_map(SYS, 0x100000)                     # SCB/SysTick reads return 0
STOP = RAM + 0xF000                                             # return address: bx lr lands here
mu.mem_write(STOP, b"\x00\xbf" * 8)
CPACR = 0xE000ED88; mu.mem_write(CPACR, struct.pack("<I", 0xF << 20))
PRM, BUF, EN = RAM + 0x1000, RAM + 0x2000, RAM + 0x3000
mu.mem_write(PRM, struct.pack("<8f", *knobs)); mu.mem_write(EN, b"\x01")
try:
    mu.reg_write(UC_ARM_REG_FPEXC, 0x40000000)
except Exception:
    pass


def call(fn, args):
    regs = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3]
    sp = RAM + 0xE000
    stack = args[4:]
    sp -= 4 * len(stack); mu.mem_write(sp, struct.pack(f"<{len(stack)}I", *stack)) if stack else None
    for r, v in zip(regs, args[:4]): mu.reg_write(r, v)
    mu.reg_write(UC_ARM_REG_SP, sp); mu.reg_write(UC_ARM_REG_LR, STOP | 1)
    mu.emu_start(fn | 1, STOP, count=50_000_000)


from unicorn import UC_HOOK_CODE
NI = [0]
if os.environ.get("COUNT"):
    mu.hook_add(UC_HOOK_CODE, lambda uc, addr, size, ud: NI.__setitem__(0, NI[0] + 1))
call(sym["lt_entry0"], [PRM, 0])
out = np.zeros_like(x)
import os
E0 = int(os.environ.get('ENTRY0_EVERY', '0'))
for i in range(0, len(x) - 63, 64):
    if E0 and (i // 64) % E0 == 0: call(sym['lt_entry0'], [PRM, 0])
    blk = np.zeros(128, "<f4"); blk[0::2] = x[i:i + 64]
    mu.mem_write(BUF, blk.tobytes())
    call(sym["lt_entry1"], [BUF, 64, PRM, 0, EN, 0, 0])
    out[i:i + 64] = np.frombuffer(mu.mem_read(BUF, 512), "<f4")[0::2]
if os.environ.get("COUNT"):
    nb = len(x) // 64; sys.stderr.write(f"instructions per 64-frame block: {NI[0] / max(nb, 1):.0f}\n")
sys.stdout.buffer.write(out.astype("<f4").tobytes())
