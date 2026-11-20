#!/usr/bin/env python3
"""Engine program for our amp model (dsp/amp.c), AMP block: program at code 1280, ends with jmp 2816,
enable flag = data word 920 bit 0 (as the stock amps), our data from 921 up (below the cab block at 1408).
  amps2.py sizes                  program size per stage count
  amps2.py check <name> [knobs]   engine model vs dsp/host for amps/<name>.json
Shares the subroutine library (OP, AP, CHAIN, CUBIC, ADAA) with tools/drives2.py; the library is packed right
behind the main program."""
import json, math, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
from easm import assemble
import engine_emu as E
import drives2 as D2
import ampmodel as AM

START, END, FLAG, BASE, TOP = 1280, 2816, 920, 921, 1408
ORG = START
PCH = [("pu1a", D2.HB[0::2]), ("pu1b", D2.HB[1::2]), ("pd1a", D2.HB[0::2]), ("pd1b", D2.HB[1::2])]
CHAINS = D2.CHAINS + PCH
OPS = ["in_hp", "brt_hp", "s0_hp", "s0_lp", "s1_hp", "s1_lp", "s2_hp", "s2_lp", "pres_hp", "res_lp", "out_lp"]
CLIPS = ["c0", "c1", "c2", "pw"]
SCAL = ["gin", "brtg", "s0_g", "s0_b", "s0_off", "s0_o", "s1_g", "s1_b", "s1_off", "s1_o", "s2_g", "s2_b", "s2_off", "s2_o",
        "pdrv", "pout", "presg", "resg", "level"]
TSW = ["tb0", "tb1", "tb2", "tb3", "ta1", "ta2", "ta3", "tz1", "tz2", "tz3"]


def layout():
    A = {}; p = BASE
    for n, _ in D2.CONSTS: A[n] = p; p += 1
    for n in D2.SCRATCH + ["Q0", "Q1"]: A[n] = p; p += 1
    A["LO"] = p
    for f in OPS: A[f] = p; p += 5
    for c, cs in CHAINS: A[c] = p; p += 3 * len(cs)
    for a in CLIPS: A[a] = p; p += 2
    for s in SCAL: A["s_" + s] = p; p += 1
    for t in TSW: A[t] = p; p += 1
    A["HI"] = p; assert p <= TOP, p
    return A


class Main:
    def __init__(self, nst, os_=4): self.nst = nst; self.os = os_; self.A = layout(); self.L = []
    def w(self, *s): self.L += ["        " + x for x in s]
    def lab(self, s): self.L.append(s + ":")
    def at(self): return ORG + sum(1 for x in self.L if not x.endswith(":"))
    def pad(self, parity):          # [hw] skip-over-jmp loops only work with the skip at these parities (NOTES 41)
        if self.at() % 2 != parity: self.w("mov r8,#0")
    def op(self, f): self.w(f"mov r12,#{self.A[f]}", "call r13,OP")
    def chain(self, c): self.w(f"mov r12,#{self.A[c]}", f"mov r3,#{len(dict(CHAINS)[c])}", "call r14,CHAIN")
    def mul(self, k): self.w(f"ld r8,[{k}]", "fmul r2,r8,r2")
    def mulv(self, k): self.w(f"ld r8,[{self.A['s_' + k]}]", "fmul r2,r8,r2")
    def ld(self, k): self.w(f"ld r2,[{k}]")
    def st(self, k): self.w(f"st [{k}],r2")
    def addm(self, k): self.w(f"ld r8,[{k}]", "fadd r2,r8,r2")
    def adda(self, k): self.w(f"ld r8,[{self.A['s_' + k]}]", "fadd r2,r8,r2")
    def suba(self, k): self.w(f"ld r9,[{self.A['s_' + k]}]", "fsub r9,r2,r9", "mov r2,r9")   # hardware-proven forms only
    def adaa(self, a): self.w(f"mov r12,#{self.A[a]}", "call r14,ADAA")
    def shelf(self, f, g): self.st("T1"); self.op(f); self.mulv(g); self.addm("T1")

    def tstack(self):          # transposed direct form II, 3rd order (amp.c ts_run), proven forms only (tools/elint.py)
        A = self.A
        self.st("T1"); self.mul(A["tb0"]); self.addm(A["tz1"]); self.st("T2")                 # y = b0 x + z1
        for b, a_, zi, zn in (("tb1", "ta1", "tz1", "tz2"), ("tb2", "ta2", "tz2", "tz3"), ("tb3", "ta3", "tz3", None)):
            self.ld("T2"); self.mul(A[a_]); self.st("Q0")                                          # a y
            self.ld("T1"); self.mul(A[b]); self.w("ld r9,[Q0]", "fsub r9,r2,r9", "mov r2,r9")      # b x - a y
            if zn: self.addm(A[zn])
            self.st(A[zi])
        self.ld("T2")

    def build(self):
        A = self.A
        self.w(f"ld r6,[{FLAG}]", "skipbs r6,0,ON", f"jmp {END}")
        self.lab("ON"); self.w("mov r0,#19", "st [PTR],r0", "mov r0,#64", "st [CNT],r0")
        self.lab("SAMPLE"); self.w("ld r0,[PTR]", "ld r2,[r0]")
        self.op("in_hp"); self.shelf("brt_hp", "brtg"); self.mulv("gin")
        self.st("X0"); self.chain("up1a"); self.st("M0"); self.ld("X0"); self.chain("up1b"); self.st("M1")
        if self.os == 4:
            for j, mk in ((0, "M0"), (1, "M1")):
                self.ld(mk); self.chain("upa2"); self.st(f"U{2 * j}"); self.ld(mk); self.chain("upb2"); self.st(f"U{2 * j + 1}")
            self.w("mov r0,#4", "st [KC],r0", f"mov r0,#{A['U0']}", "st [KP],r0")
        else:                                          # 2x: the two half-band phases are the oversampled pair
            self.ld("M0"); self.st("U0"); self.ld("M1"); self.st("U1")
            self.w("mov r0,#2", "st [KC],r0", f"mov r0,#{A['U0']}", "st [KP],r0")
        self.lab("CORE"); self.w("ld r0,[KP]", "ld r2,[r0]")
        for k in range(self.nst):
            self.op(f"s{k}_hp"); self.op(f"s{k}_lp"); self.mulv(f"s{k}_g"); self.adda(f"s{k}_b"); self.adaa(f"c{k}")
            self.suba(f"s{k}_off"); self.mulv(f"s{k}_o")
        self.w("ld r0,[KP]", "add r0,#4", "st [r0],r2", "sub r0,#3", "st [KP],r0",
               "ld r1,[KC]", "sub r1,#1", "st [KC],r1", "mov r3,#0"); self.pad(1); self.w("skipeq r1,r3,DOWN", "jmp CORE")
        self.lab("DOWN")
        if self.os == 4:
            for j, mk in ((0, "M0"), (1, "M1")):
                self.ld(f"V{2 * j + 1}"); self.chain("dna2"); self.st("T1"); self.ld(f"V{2 * j}"); self.chain("dnb2")
                self.addm("T1"); self.mul("HALF"); self.st(mk)
        else:
            self.ld("V0"); self.st("M0"); self.ld("V1"); self.st("M1")
        self.ld("M1"); self.chain("dn1a"); self.st("T1"); self.ld("M0"); self.chain("dn1b"); self.addm("T1"); self.mul("HALF")
        self.tstack()
        self.st("X0"); self.chain("pu1a"); self.mulv("pdrv"); self.adaa("pw"); self.mulv("pout"); self.st("Q0")
        self.ld("X0"); self.chain("pu1b"); self.mulv("pdrv"); self.adaa("pw"); self.mulv("pout"); self.st("Q1")
        self.ld("Q1"); self.chain("pd1a"); self.st("T1"); self.ld("Q0"); self.chain("pd1b"); self.addm("T1"); self.mul("HALF")
        self.shelf("pres_hp", "presg"); self.shelf("res_lp", "resg"); self.op("out_lp"); self.mulv("level")
        self.w("ld r0,[PTR]", "st [r0],r2", "add r0,#1", "st [PTR],r0", "ld r1,[CNT]", "sub r1,#1", "st [CNT],r1",
               "mov r3,#0"); self.pad(0); self.w("skipeq r1,r3,FIN", "jmp SAMPLE")
        self.lab("FIN"); self.w(f"jmp {END}")
        if self.at() % 2 == 0: self.w("mov r8,#0")        # library at an odd address (NOTES 41)
        return "\n".join(self.L) + "\n"


def assemble_amp(nst, os_=4):
    """main at 1280, library right behind it: one image the AMP loader copies to code 1280."""
    A = layout(); eq = dict(A); n = 400
    while True:
        lib, labs = assemble(D2.LIBRARY, START + n, eq); e2 = dict(eq); e2.update(labs)
        main, _ = assemble(Main(nst, os_).build(), START, e2)
        if len(main) == n: break
        n = len(main)
    assert START + len(main) + len(lib) <= max(END, 2816)
    return list(main) + list(lib), A


# ---- coefficients exactly as the C side computes them (dsp/ampdump), for the offline check
def data_image(s, kn):
    import subprocess, tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("\n".join(repr(float(s.get(k, {"os": 4.0, "olp": 19000.0}.get(k, 0.0)))) for k in AM.NAMES) + "\n"); path = f.name
    try:
        out = subprocess.run([os.path.join(RE, "dsp", "ampdump"), path] + [str(float(v)) for v in kn[:6]] + [str(int(kn[6]) if len(kn) > 6 else 0)],
                             capture_output=True, text=True, check=True).stdout
    finally: os.unlink(path)
    c = json.loads(out); A = layout(); img = {}
    for nm, v in D2.CONSTS: img[A[nm]] = E.f2u(v)
    for ch, cs in CHAINS:
        for i, v in enumerate(cs): img[A[ch] + 3 * i] = E.f2u(v)
    for f in OPS:
        for i, v in enumerate(c[f]): img[A[f] + i] = E.f2u(v)
    for k in range(3):
        for nm, v in zip(("g", "b", "off", "o"), c[f"s{k}"]): img[A[f"s_s{k}_{nm}"]] = E.f2u(v)
    for nm in ("gin", "brtg", "pdrv", "pout", "presg", "resg", "level"): img[A["s_" + nm]] = E.f2u(c[nm])
    for nm, v in zip(["tb0", "tb1", "tb2", "tb3", "ta1", "ta2", "ta3"], c["tb"] + c["ta"]): img[A[nm]] = E.f2u(v)
    return img, A


def check(name, kn):
    s = AM.load(name) if not name.endswith(".json") else json.load(open(name)); prog, A = assemble_amp(int(s["nst"]), int(s.get("os", 4))); img, _ = data_image(s, kn)
    x = (0.05 * np.random.default_rng(7).standard_normal(64 * 64)).astype("<f4") * 4
    ref = AM.run(s, kn, x).astype(np.float32)
    e = E.Engine(); e.load_code(START, prog); e.code[END] = 0xA00E0000
    for a_, v in img.items(): e.d[a_] = v
    e.d[FLAG] = 1; y = np.zeros_like(x); un = []
    for b in range(len(x) // 64):
        e.d[19:83] = x[b * 64:(b + 1) * 64].view(np.uint32); e.steps = 0; e.units = 0
        e.run(START, limit=5_000_000); un.append(e.units); y[b * 64:(b + 1) * 64] = e.d[19:83].view(np.float32)
    err = float(np.max(np.abs(y - ref)) / (np.max(np.abs(ref)) + 1e-12))
    print(f"{name} (stages {int(s['nst'])}): program {len(prog)} words, units/block {int(np.mean(un))}, rel err vs C {err:.2e}"
          + (f", unknown ops {e.unknown}" if e.unknown else ""))
    return err


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "sizes":
        for n in (1, 2, 3): p, A = assemble_amp(n); print(f"stages {n}: {len(p)} words; data {A['HI'] - BASE} words")
    elif a[0] == "check":
        check(a[1], [float(v) for v in a[2:]] or [70, 50, 50, 50, 50, 50, 0])


def export(name, knob_index):
    """dsp/amp_eng.h for one amp: engine data addresses, the amp's settings, knob positions in its preset record"""
    A = layout(); s = AM.load(name) if not name.endswith(".json") else json.load(open(name))
    h = ["/* generated by tools/amps2.py export - do not edit */", f"#define AFLAG {FLAG}", f"#define A_LO {A['LO']}", f"#define A_HI {A['HI']}"]
    for f in OPS: h.append(f"#define A_{f.upper()} {A[f]}")
    for c in CLIPS: h.append(f"#define A_CLIP_{c.upper()} {A[c]}")
    for c in SCAL: h.append(f"#define A_S_{c.upper()} {A['s_' + c]}")
    for t in TSW: h.append(f"#define A_{t.upper()} {A[t]}")
    h.append("static const uint16_t A_CONST_AT[] = {" + ", ".join(str(A[n]) for n, _ in D2.CONSTS) + "};")
    h.append("static const float A_CONST_VAL[] = {" + ", ".join(repr(float(v)) + "f" for _, v in D2.CONSTS) + "};")
    at, cv = [], []
    for c, cs in CHAINS:
        for i, v in enumerate(cs): at.append(A[c] + 3 * i); cv.append(v)
    h.append("static const uint16_t A_CHAIN_AT[] = {" + ", ".join(map(str, at)) + "};")
    h.append("static const float A_CHAIN_C[] = {" + ", ".join(repr(float(v)) + "f" for v in cv) + "};")
    h.append(f"#define A_NCONST {len(D2.CONSTS)}\n#define A_NCHAIN {len(cv)}")
    h.append("static const float A_PAR[AMP_NPAR] = {" + ", ".join(repr(float(s.get(k, {"os": 4.0, "olp": 19000.0}.get(k, 0.0)))) + "f" for k in AM.NAMES) + "};")
    h.append("static const int8_t A_KNOB[7] = {" + ", ".join(str(i) for i in knob_index) + "};   /* gain bass mid treble pres vol bright -> param index, -1 = fixed */")
    open(os.path.join(RE, "dsp", "amp_eng.h"), "w").write("\n".join(h) + "\n")
