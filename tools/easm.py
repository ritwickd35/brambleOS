#!/usr/bin/env python3
"""Assembler for the Pocket Master audio co-processor (engine). Semantics: tools/engine_emu.py, cfw/isa/FINDINGS.md.
Syntax: one instruction per line, ';' comments, 'label:' lines, '.org N', '.word N', '.float F', '.equ NAME N'.
  ld rR,[N] / st [N],rR          direct data access
  ld rR,[rA] / ld rR,[rA]++      indexed load (post-increment)       st [rR],rA / st [rR]++,rA
  ldc rR,[rA] / ldc rR,[rA]++    load from code RAM (tables)
  mov rR,#N  add/sub/mul rR,#N   (integer)   movf rR,F (float literal, 2 words)   movhi/movlo rR,#N
  andh/orh/xorh rR,#N            hi16 bit ops (abs: andh #0x7fff, neg: xorh #0x8000)
  mov rR,rA  movlo rR,rA  movhi rR,rA
  fmul rD,rA,rR (rD=rA*rR)  fmac rD,rA,rR (rD+=rA*rR)  fadd rD,rR,rA  fsub rD,rR,rA (rD=rR-rA)
  iadd/isub/irsub/iand/ior/ishr/ishl rD,rR,rA [,h=0xNN]  imul rD,rR,rA
  rsqrt rD,rR                    rD = 1/sqrt(rR) (rR>0); clobbers r9,r10,r11
  skipbs/skipbc rR,bit,label     skip forward to label if bit set / clear
  skipge rR,rA,label  skipeq rR,rA,label    (signed integer compare)
  djnz rR,label  call rL,label  ret rL  jmp label  halt
  vcopy / vadd / vmulv / vmuls / vdot   vector ops: r9 src, r10 n, r11 dst, r8 scalar or 2nd src; vdot: r11 = sum r9[i]*r8[i]
Usage: easm.py file.s [base] -> prints words (hex) ; or import assemble(text, base)."""
import re, struct, sys


def f2u(f): return struct.unpack("<I", struct.pack("<f", float(f)))[0]


ALU = {"iadd": 0, "isub": 2, "iand": 4, "ior": 5, "irsub": 6, "ishr": 7, "ishl": 8}
VEC = {"vcopy": 0, "vadd": 3, "vmulv": 7, "vmuls": 8, "vdot": 0xD}


def reg(t):
    t = t.strip().lower()
    if not re.fullmatch(r"r\d+", t) or int(t[1:]) > 15: raise ValueError(f"bad register {t}")
    return int(t[1:])


def assemble(text, base=0, equ=None):
    equ = dict(equ or {}); lines = []
    for raw in text.split("\n"):
        l = raw.split(";")[0].strip()
        if not l: continue
        m = re.match(r"^([A-Za-z_]\w*):\s*(.*)$", l)
        if m:
            lines.append(m.group(1) + ":")
            if m.group(2): lines.append(m.group(2))
        else: lines.append(l)
    def num(t):
        t = t.strip().lstrip("#")
        if t in equ: return equ[t]
        return int(t, 0)
    # pass 1: sizes and labels
    labels, pc = {}, base
    for l in lines:
        if l.endswith(":"): labels[l[:-1]] = pc; continue
        op = l.split()[0].lower()
        if op == ".org": pc = num(l.split()[1]); continue
        if op == ".equ": _, n, v = l.split(); equ[n] = int(v, 0); continue
        pc += 2 if op == "movf" else 1
    def addr(t):
        t = t.strip()
        return labels[t] if t in labels else num(t)
    out, pc = [], base
    for l in lines:
        if l.endswith(":"): continue
        op, _, rest = l.partition(" "); op = op.lower(); a = [x.strip() for x in rest.split(",")] if rest.strip() else []
        if op == ".org": assert not out, ".org only before the first instruction"; pc = num(a[0]); continue
        if op == ".equ": continue
        ws = []
        if op == ".word": ws = [num(a[0])]
        elif op == ".float": ws = [f2u(float(a[0]))]
        elif op in ("ld", "st", "ldc"):
            if op == "st": dst, src = a[0], a[1]
            else: src, dst = a[1], a[0]
            m = re.fullmatch(r"\[(r\d+)\](\+\+)?", (src if op != "st" else dst).replace(" ", ""))
            if m:
                inc = bool(m.group(2))
                if op == "ld": ws = [((0xE0 | reg(dst)) << 24) | ((reg(m.group(1)) << 4 | (3 if inc else 2)) << 16)]
                elif op == "ldc": ws = [((0xE0 | reg(dst)) << 24) | ((reg(m.group(1)) << 4 | (7 if inc else 6)) << 16)]
                else: ws = [((0xE0 | reg(m.group(1))) << 24) | ((reg(src) << 4 | (5 if inc else 4)) << 16)]
            else:
                n = num((src if op != "st" else dst).strip("[]"))
                ws = [((0x50 | reg(dst if op == "ld" else src)) << 24) | ((0x00 if op == "ld" else 0x08) << 16) | (n & 0xFFF)]
        elif op in ("mov", "movhi", "movlo") and not a[1].startswith("#") and a[1].lower().startswith("r"):
            ws = [((0xF0 | reg(a[0])) << 24) | ((reg(a[1]) << 4 | 4) << 16) | {"mov": 0, "movlo": 0x4000, "movhi": 0x7000}[op]]
        elif op in ("mov", "add", "sub", "mul", "movhi", "movlo", "andh", "orh", "xorh"):
            b1 = {"mov": 6, "add": 0, "sub": 2, "mul": 4, "movhi": 0xC6, "movlo": 0x86, "andh": 0xC8, "orh": 0xCA, "xorh": 0xCC}[op]
            n = addr(a[1].lstrip("#")) if op == "mov" else num(a[1])
            ws = [((0x70 | reg(a[0])) << 24) | (b1 << 16) | (n & 0xFFFF)]
        elif op == "movf":
            u = f2u(float(a[1])); r = reg(a[0])
            ws = [((0x70 | r) << 24) | (0xC6 << 16) | (u >> 16), ((0x70 | r) << 24) | (0x86 << 16) | (u & 0xFFFF)]
        elif op in ("fmul", "fmac", "imul"):
            d, ra, rr = reg(a[0]), reg(a[1]), reg(a[2])
            if op == "imul": rr, ra = reg(a[1]), reg(a[2])
            ws = [((0x80 | rr) << 24) | ((ra << 4 | {"fmul": 6, "fmac": 0xA, "imul": 0}[op]) << 16) | d]
        elif op in ("fadd", "fsub"):
            d, rr, ra = reg(a[0]), reg(a[1]), reg(a[2])
            ws = [((0xC0 | rr) << 24) | ((ra << 4 | (0xE if op == "fadd" else 0xF)) << 16) | d]
        elif op in ALU:
            d, rr, ra = reg(a[0]), reg(a[1]), reg(a[2]); h = num(a[3].split("=")[1]) if len(a) > 3 else 0
            ws = [((0xC0 | rr) << 24) | ((ra << 4 | ALU[op]) << 16) | (h << 8) | d]
        elif op == "rsqrt":
            d, rr = reg(a[0]), reg(a[1]); ws = [((0xF0 | rr) << 24) | (0x0E << 16) | d]
        elif op in ("skipbs", "skipbc", "skipge", "skipeq"):
            here = pc + len(out); r = reg(a[0]); n = addr(a[2]) - (here + 1); assert 0 <= n < 512, l
            if op in ("skipbs", "skipbc"):
                k = num(a[1]); ws = [((0x90 | r) << 24) | ((8 if op == "skipbs" else 0xA) << 16) | (k << 9) | n]
            else:
                ws = [((0x90 | r) << 24) | ((reg(a[1]) << 4 | (2 if op == "skipge" else 4)) << 16) | n]
        elif op == "djnz": ws = [((0xA0 | reg(a[0])) << 24) | (0x04 << 16) | (addr(a[1]) & 0xFFF)]
        elif op == "call": ws = [((0xA0 | reg(a[0])) << 24) | (0x06 << 16) | 0x4000 | (addr(a[1]) & 0xFFF)]
        elif op == "ret": ws = [((0xA0 | reg(a[0])) << 24) | (0x0A << 16) | 0x4000]
        elif op == "jmp": ws = [0xA0080000 | (addr(a[0]) & 0xFFF)]
        elif op == "halt": ws = [0xA00E0000]
        elif op in VEC: ws = [0x20000000 | (VEC[op] << 16)]
        else: raise ValueError(f"unknown instruction: {l}")
        for w in ws: out.append(w)
    return [w & 0xFFFFFFFF for w in out], labels


if __name__ == "__main__":
    words, labels = assemble(open(sys.argv[1]).read(), int(sys.argv[2], 0) if len(sys.argv) > 2 else 0)
    print("\n".join(f"{w:08x}" for w in words))
