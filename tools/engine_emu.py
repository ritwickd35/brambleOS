#!/usr/bin/env python3
"""Reference model of the audio co-processor ("engine"); semantics from cfw/isa/FINDINGS.md plus on-device checks
(NOTES.md). Raw 32-bit data and registers; float ops reinterpret the bits.
Word = [op:8][b1:8][imm:16], op = class<<4 | R, b1 = A<<4 | S, rB = imm & 15.
Data RAM 4096 words; code RAM 4096 words. Unknown words are no-ops and counted in .unknown."""
import struct
import numpy as np

f2u = lambda f: struct.unpack("<I", struct.pack("<f", float(f)))[0]
u2f = lambda u: struct.unpack("<f", struct.pack("<I", int(u) & 0xFFFFFFFF))[0]
F32 = np.float32
sx = lambda u: u - (1 << 32) if u & 0x80000000 else u
ALU = {0: lambda a, b: a + b, 2: lambda a, b: a - b, 4: lambda a, b: a & b, 5: lambda a, b: a | b,
       6: lambda a, b: b - a, 7: lambda a, b: a >> (b & 31), 8: lambda a, b: a << (b & 31)}
ftz = lambda v: np.float32(0.0) if abs(float(v)) < 1.1754944e-38 else np.float32(v)   # denormals flush to zero [hw]


class Engine:
    def __init__(self):
        self.d = np.zeros(4096, np.uint32)
        self.code = np.zeros(4096, np.uint32)
        self.r = [0] * 16
        self.unknown = {}
        self.steps = 0
        self.units = 0.0         # cost estimate from the cut8c bench (logs/ebench.json)
        self.sem = {}            # optional overrides: key "op:b1" -> fn(engine, w) returning next pc or None

    def load_code(self, addr, words): self.code[addr:addr + len(words)] = np.array(words, np.uint32)
    def fd(self, a): return self.d[a & 0xFFF:(a & 0xFFF) + 1].view(np.float32)[0]
    def setd(self, a, u): self.d[a & 0xFFF] = int(u) & 0xFFFFFFFF
    def f(self, k): return ftz(np.array([self.r[k]], np.uint32).view(np.float32)[0])
    def setf(self, k, v): self.r[k] = int(np.array([ftz(v)], np.float32).view(np.uint32)[0])
    def seti(self, k, v): self.r[k] = int(v) & 0xFFFFFFFF

    def run(self, pc=0, limit=2_000_000):
        while self.steps < limit:
            w = int(self.code[pc & 0xFFF]); op, b1, imm = w >> 24, (w >> 16) & 0xFF, w & 0xFFFF
            c, R = op >> 4, op & 0xF; A, S = b1 >> 4, b1 & 0xF; B = imm & 0xF
            self.steps += 1; npc = pc + 1
            self.units += 2 if (c == 8 and S == 0xA) else 11 if (c == 0xF and S == 0xE) else 7 if (c == 0xE and S in (6, 7)) \
                else 1.5 if c == 9 else 3 * (self.r[10] & 0xFFF) if op == 0x20 else 1
            key = f"{op:02x}{b1:02x}"
            if key in self.sem:
                v = self.sem[key](self, w, pc)
                if v == "halt": return pc
                if v is not None: npc = v
            elif c == 0x5 and b1 == 0x00: self.r[R] = int(self.d[imm & 0xFFF])          # ld rR,[N]
            elif c == 0x5 and b1 == 0x08: self.setd(imm, self.r[R])                     # st [N],rR
            elif c == 0x7 and b1 == 0x06: self.seti(R, imm)                             # mov #N
            elif c == 0x7 and b1 == 0x00: self.seti(R, self.r[R] + imm)                 # add #N (int)
            elif c == 0x7 and b1 == 0x02: self.seti(R, self.r[R] - imm)                 # sub #N (int)   [hw]
            elif c == 0x7 and b1 == 0x04: self.seti(R, self.r[R] * imm)                 # mul #N (int; only N=2 seen) [hw]
            elif c == 0x7 and b1 == 0xC6: self.seti(R, (imm << 16) | (self.r[R] & 0xFFFF))  # movhi, keeps lo [hw]
            elif c == 0x7 and b1 == 0x86: self.seti(R, (self.r[R] & 0xFFFF0000) | imm)  # movlo, keeps hi [hw]
            elif c == 0x7 and b1 == 0xC8: self.seti(R, self.r[R] & ((imm << 16) | 0xFFFF))  # and hi16 [hw]
            elif c == 0x7 and b1 == 0xCA: self.seti(R, self.r[R] | (imm << 16))         # or hi16  [hw]
            elif c == 0x7 and b1 == 0xCC: self.seti(R, self.r[R] ^ (imm << 16))         # xor hi16 [hw]
            elif c == 0xE and S == 2:
                if not 0x13 <= (self.r[A] & 0xFFF) <= 0x400: pass
                self.r[R] = int(self.d[self.r[A] & 0xFFF])
            elif c == 0xE and S == 3: self.r[R] = int(self.d[self.r[A] & 0xFFF]); self.seti(A, self.r[A] + 1)
            elif c == 0xE and S == 4: self.setd(self.r[R], self.r[A])
            elif c == 0xE and S == 5: self.setd(self.r[R], self.r[A]); self.seti(R, self.r[R] + 1)
            elif c == 0xE and S == 6: self.r[R] = int(self.code[self.r[A] & 0xFFF])    # ld from code RAM [hw]
            elif c == 0xE and S == 7: self.r[R] = int(self.code[self.r[A] & 0xFFF]); self.seti(A, self.r[A] + 1)
            elif c == 0x8 and S == 6: self.setf(B, self.f(A) * self.f(R)); self.fl(B)      # rB = rA*rR [hw]
            elif c == 0x8 and S == 0xA: self.setf(B, self.f(B) + self.f(A) * self.f(R)); self.fl(B)
            elif c == 0x8 and S == 0: self.seti(B, self.r[R] * self.r[A])                 # int mul [hw]
            elif c == 0xC and S == 0xE: self.setf(B, self.f(R) + self.f(A)); self.fl(B)    # rB = rR+rA [hw]
            elif c == 0xC and S == 0xF: self.setf(B, self.f(R) - self.f(A)); self.fl(B)    # rB = rR-rA [hw]
            elif c == 0xC and S in ALU: self._alu(S, R, A, B, imm >> 8)
            elif c == 0xD and S == 2: self.seti(B, self.r[R] << 1)                        # seen as x2 only (CAB)
            elif c == 0xF and S == 4 and imm == 0: self.r[R] = self.r[A]
            elif c == 0xF and S == 4 and imm == 0x4000: self.r[R] = (self.r[R] & 0xFFFF0000) | (self.r[A] & 0xFFFF)
            elif c == 0xF and S == 4 and imm == 0x7000: self.r[R] = (self.r[R] & 0xFFFF) | (self.r[A] & 0xFFFF0000)
            elif c == 0xF and S == 0xC:                                                   # bit-reverse rR in w bits -> rB
                wdt = (imm >> 5) & 7 or 8; v = self.r[R] & ((1 << wdt) - 1)                 # (FFT index; w = imm[7:5]) [inferred]
                self.seti(B, int(format(v, f"0{wdt}b")[::-1], 2))
            elif c == 0xF and S == 0xE:                                                   # rsqrt macro, r9..r11 temps [hw]
                x = self.f(R); self.setf(9, x * F32(0.5))
                self.setf(B, F32(1.0) / np.sqrt(x) if x > 0 else F32(np.inf)); self.r[10] = self.r[B]; self.setf(11, 1.0)
            elif c == 0xA and b1 == 0x04:                                                 # djnz
                if imm & 0x6000:                                      # 16-bit counter: 0x4000 = 16-bit mode,
                    sh = 16 if imm & 0x2000 else 0                    # 0x2000 = high half (same flags as call/ret;
                    v = ((self.r[R] >> sh) - 1) & 0xFFFF              # the clone packs two fields) [inferred]
                    self.r[R] = (self.r[R] & ~(0xFFFF << sh) & 0xFFFFFFFF) | (v << sh)
                    if v != 0: npc = imm & 0xFFF
                else:
                    self.seti(R, self.r[R] - 1)
                    if self.r[R] != 0: npc = imm & 0xFFF
            elif c == 0xA and b1 == 0x06:                                                 # call, link in rR [hw]
                self.r[R] = ((npc << 16) | (self.r[R] & 0xFFFF)) if imm & 0x2000 else ((self.r[R] & 0xFFFF0000) | npc)
                npc = imm & 0xFFF
            elif c == 0xA and b1 == 0x0A: npc = (self.r[R] >> 16 if imm & 0x2000 else self.r[R]) & 0xFFF   # ret via rR (0x2000: link in high half, matches call) [inferred]
            elif op == 0xA0 and b1 == 0x08: npc = imm & 0xFFF
            elif op == 0xA0 and b1 == 0x0E: return pc
            elif c == 0x9 and S in (8, 0xA, 2, 4):                            # conditional skip [hw]
                n, k = imm & 0x1FF, (imm >> 9) & 31
                if S == 8: t = (self.r[R] >> k) & 1
                elif S == 0xA: t = not ((self.r[R] >> k) & 1)
                elif S == 2: t = sx(self.r[R]) >= sx(self.r[A])
                else: t = self.r[R] == self.r[A]
                if t: npc = pc + 1 + n
            elif op == 0x20 and S in (0, 3, 7, 8, 0xD): self._vec(S)
            else: self.unknown[key] = self.unknown.get(key, 0) + 1
            pc = npc
        raise RuntimeError(f"step limit at pc {pc:#x}, r1 {self.r[1]}, r0 {self.r[0]}, steps {self.steps}, limit {limit}")

    def fl(self, k, integer=False):
        """flags in r15 after float / integer ALU results: bit30 negative, bit29 zero (bit31 also set for a
        negative integer result) [hw]"""
        v = self.r[k]
        if integer: n = v >> 31; z = v == 0; self.r[15] = (n << 31) | (n << 30) | (z << 29)
        else: f = self.f(k); self.r[15] = (int(f < 0) << 30) | (int(f == 0) << 29)

    def _alu(self, S, R, A, B, h):
        """integer ALU, dest rB; h = imm[15:8]: 0 = 32-bit, bit6 = 16-bit mode (bit5 dest hi, bit4 rA hi, bit3 rR hi) [hw]"""
        if h & 0x40:
            a = (self.r[R] >> 16) if h & 8 else self.r[R] & 0xFFFF
            b = (self.r[A] >> 16) if h & 0x10 else self.r[A] & 0xFFFF
            if S in (7, 8): b &= 15                      # 16-bit shifts use the low 4 bits [hw]
            v = ALU[S](a, b) & 0xFFFF
            self.r[B] = ((v << 16) | (self.r[B] & 0xFFFF)) if h & 0x20 else ((self.r[B] & 0xFFFF0000) | v)
        else: self.seti(B, ALU[S](self.r[R], self.r[A])); self.fl(B, True)

    def _vec(self, S):
        """vector ops over n = r10 words; pointers advance like a DMA [hw]: r9/r11 (+r8 for two-source ops) += n, r10 = 0.
        S=0 copy r9->r11, 3 add r9+r8->r11, 7 mul r9*r8->r11, 8 scale r9*f(r8)->r11, D dot: r11 = sum r9[i]*r8[i]
        (dot: r8, r9 advance n+1)"""
        r8, r9, r11, n = (self.r[i] & 0xFFF for i in (8, 9, 11, 10)); n = self.r[10] & 0xFFF
        dv = self.d.view(np.float32)
        if S == 8: dv[r11:r11 + n] = dv[r9:r9 + n] * self.f(8)
        elif S == 7: dv[r11:r11 + n] = dv[r9:r9 + n] * dv[r8:r8 + n]
        elif S == 3: dv[r11:r11 + n] = dv[r9:r9 + n] + dv[r8:r8 + n]
        elif S == 0: self.d[r11:r11 + n] = self.d[r9:r9 + n].copy()
        if S == 0xD:
            self.setf(11, np.dot(dv[r9:r9 + n].astype(np.float64), dv[r8:r8 + n]))
            self.seti(8, self.r[8] + n + 1); self.seti(9, self.r[9] + n + 1)
        else:
            self.seti(9, self.r[9] + n); self.seti(11, self.r[11] + n)
            if S in (3, 7): self.seti(8, self.r[8] + n)
        self.r[10] = 0
