#!/usr/bin/env python3
"""Compact drive programs for the co-processor: shared subroutine library + small main program per model.
  drives2.py check <model>      engine model vs dsp/host (needs logs/<model>_coefs.json, audio/<model>_host_*.f32)
  drives2.py sizes              program sizes
  drives2.py export             build/progs2/*.bin + dsp/eng2.h (addresses for the ARM side)
Registers: r0-r7 work (ADAA/TRANS clobber r0,r1,r4-r7), r8-r11 scratch, r12 record pointer,
r13 link for leaf routines, r14 link for ADAA/TRANS/CHAIN, r15 flags. Loop state lives in memory."""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
from easm import assemble
import engine_emu as E

FLAG, BASE, LIB = 403, 416, 1024
ORG = 0                                   # code address of the main program          # DRV enable word; data block start; library code address
HB = [0.054217526, 0.196797970, 0.383087327, 0.573136411, 0.748720944, 0.914293710]
HB2 = [0.070224059, 0.285086280, 0.684541359]
CONSTS = [("ONE", 1.0), ("HALF", 0.5), ("THIRD", 1 / 3), ("TWO_THIRD", 2 / 3), ("QUARTER", 0.25), ("TWELFTH", 1 / 12),
          ("EPS", 1e-4), ("C1_4", 1.4), ("INV1_4", 1 / 1.4), ("C1_6", 1.6), ("C1_3", 1.3), ("C1_8", 1.8), ("C0_55", 0.55),
          ("C0_6", 0.6), ("C4", 4.0), ("C1_5", 1.5), ("C0_9", 0.9)]
SCRATCH = ["PTR", "CNT", "KC", "KP", "T1", "T2", "X0", "M0", "M1", "U0", "U1", "U2", "U3", "V0", "V1", "V2", "V3"]
CHAINS = [("up1a", HB[0::2]), ("up1b", HB[1::2]), ("upa2", [HB2[0], HB2[2]]), ("upb2", [HB2[1]]),
          ("dn1a", HB[0::2]), ("dn1b", HB[1::2]), ("dna2", [HB2[0], HB2[2]]), ("dnb2", [HB2[1]])]
OPS = {"ds1": ["in_hp", "boost_hp", "op_hp", "op_lp", "clip_lp", "tone_lp", "tone_hp"],
       "ts808": ["in_hp", "fb_hp", "fb_lp", "post_lp", "tone_lp"],
       "rat": ["in_hp", "hp_a", "hp_b", "gain_lp", "gbw_lp", "tone_lp"],
       "fuzz": ["in_hp", "mid_hp", "out_lp", "out_hp"],
       "klon": ["in_hp", "drv_hp", "gain_lp", "tre_hp", "post_lp"],
       "muff": ["in_hp", "s1_hp", "s1_lp", "s2_hp", "s2_lp", "tone_lp", "tone_hp"]}
CLIPS = {"ds1": ["diode", "trans"], "ts808": ["clip"], "rat": ["clip", "railc"], "fuzz": ["c1", "c2"], "klon": ["clip"], "muff": ["c1", "c2"]}
SCAL = {"ds1": ["boost", "opgain", "tone", "level", "tb", "toff"], "ts808": ["gain", "tone", "level"],
        "rat": ["ga", "gb", "level"], "fuzz": ["g1", "g2", "b1", "b2", "o1", "o2", "level"],
        "klon": ["gd", "wd", "wc", "treb", "level"], "muff": ["g1", "g2", "lo", "hi", "level"]}

LIBRARY = """
OP:     ld r8,[r12]++
        fmul r9,r8,r2
        ld r8,[r12]++
        ld r10,[r12]++
        ld r11,[r12]
        fmac r9,r8,r11
        st [r12]++,r2
        ld r11,[r12]
        fmul r8,r10,r11
        fsub r9,r9,r8
        st [r12],r9
        mov r2,r9
        ret r13
AP:     ld r8,[r12]++
        ld r10,[r12]++
        ld r9,[r12]
        fsub r9,r2,r9
        fmul r9,r8,r9
        fadd r9,r9,r10
        sub r12,#1
        st [r12]++,r2
        st [r12]++,r9
        mov r2,r9
        ret r13
CHAIN:  call r13,AP
        djnz r3,CHAIN
        ret r14
CUBIC:  mov r8,r2
        andh r8,#32767
        ld r9,[ONE]
        fsub r10,r9,r8
        skipbs r15,30,CBIG
        fmul r9,r2,r2
        fmul r9,r9,r2
        ld r10,[THIRD]
        fmul r9,r10,r9
        fsub r9,r2,r9
        mov r2,r9
        ret r13
CBIG:   mov r9,r2
        andh r9,#32768
        ld r10,[TWO_THIRD]
        ior r10,r10,r9,h=120
        mov r2,r10
        ret r13
TRANS:  mov r9,#0
        fsub r9,r2,r9
        skipbs r15,30,TNEG
        call r13,CUBIC
        ret r14
TNEG:   ld r8,[C1_4]
        fmul r2,r8,r2
        call r13,CUBIC
        ld r8,[INV1_4]
        fmul r2,r8,r2
        ret r14
ADAA:   ld r6,[r12]++
        ld r4,[r12]
        sub r12,#1
        st [r12]++,r2
        fsub r7,r2,r6
        mov r0,r2
        andh r0,#32767
        ld r1,[ONE]
        fsub r1,r1,r0
        skipbs r15,30,ABIG
        fmul r9,r2,r2
        fmul r10,r9,r9
        ld r11,[HALF]
        fmul r9,r11,r9
        ld r11,[TWELFTH]
        fmul r11,r11,r10
        fsub r9,r9,r11
        jmp AF
ABIG:   ld r9,[TWO_THIRD]
        fmul r9,r9,r0
        ld r11,[QUARTER]
        fsub r9,r9,r11
AF:     st [r12],r9
        mov r5,r9
        mov r0,r7
        andh r0,#32767
        ld r1,[EPS]
        fsub r1,r0,r1
        skipbs r15,30,ASMALL
        rsqrt r0,r0
        fmul r0,r0,r0
        mov r1,r7
        andh r1,#32768
        ior r0,r0,r1,h=120
        fsub r5,r5,r4
        fmul r2,r5,r0
        ret r14
ASMALL: fadd r2,r2,r6
        ld r1,[HALF]
        fmul r2,r1,r2
        call r13,CUBIC
        ret r14
"""


def layout(model):
    """name -> data word address. Constants and scratch are shared, then the model's records."""
    A = {}; p = BASE
    for n, _ in CONSTS: A[n] = p; p += 1
    for n in SCRATCH: A[n] = p; p += 1
    A["MODEL_LO"] = p
    for f in OPS[model]: A[f] = p; p += 5                     # b0 b1 a1 x1 y1
    for c, cs in CHAINS: A[c] = p; p += 3 * len(cs)           # (c x y) per section
    for a in CLIPS[model]: A[a] = p; p += 2                   # x1 F1
    for s in SCAL[model]: A["s_" + s] = p; p += 1
    A["MODEL_HI"] = p
    assert p < 920, p                                          # stays below the AMP block
    return A


class Main:
    def __init__(self, model):                    # "fuzz#k": hardware bisect variants (see core/post)
        self.m, _, v = model.partition("#"); self.v = int(v or 0); self.A = layout(self.m); self.L = []; self.n = 0
    def w(self, *s): self.L += ["        " + x for x in s]
    def lab(self, s): self.L.append(s + ":")
    def at(self): return ORG + sum(1 for x in self.L if not x.endswith(":"))
    def pad(self, parity):          # [hw] skip-over-jmp loops only work with the skip at these parities (NOTES 41)
        if self.at() % 2 != parity: self.w("mov r8,#0")
    def op(self, f): self.w(f"mov r12,#{self.A[f]}", "call r13,OP")
    def chain(self, c): self.w(f"mov r12,#{self.A[c]}", f"mov r3,#{dict(CHAINS)[c].__len__()}", "call r14,CHAIN")
    def mul(self, key): self.w(f"ld r8,[{key}]", "fmul r2,r8,r2")
    def mulv(self, key): self.w(f"ld r8,[{self.A['s_' + key]}]", "fmul r2,r8,r2")
    def ld(self, k): self.w(f"ld r2,[{k}]")
    def st(self, k): self.w(f"st [{k}],r2")
    def addm(self, k): self.w(f"ld r8,[{k}]", "fadd r2,r8,r2")
    def adda(self, k): self.w(f"ld r8,[{self.A['s_' + k]}]", "fadd r2,r8,r2")
    def suba(self, k): self.w(f"ld r9,[{self.A['s_' + k]}]", "fsub r9,r2,r9", "mov r2,r9")   # only hardware-proven forms
    def adaa(self, a): self.w(f"mov r12,#{self.A[a]}", "call r14,ADAA")

    def core(self):
        m = self.m
        if m == "ds1":
            if self.v == 3: self.w("call r14,TRANS"); return          # bisect: transistor stage only
            if self.v == 0: self.adda("tb"); self.adaa("trans"); self.suba("toff")   # booster, biased ADAA [hw: TRANS/CUBIC stop the engine]
            elif self.v != 4: self.w("call r14,TRANSB" if self.v in (1, 2) else "call r14,TRANS")
            self.st("T1"); self.op("op_hp"); self.mulv("opgain"); self.addm("T1")
            self.op("op_lp"); self.op("clip_lp"); self.mul("C1_6"); self.adaa("diode")
        elif m == "ts808":
            self.st("T1"); self.op("fb_hp"); self.mulv("gain"); self.op("fb_lp"); self.mul("C1_8"); self.adaa("clip")
            self.mul("C0_55"); self.addm("T1")
        elif m == "rat":
            self.st("T1"); self.op("hp_a"); self.mulv("ga"); self.st("T2"); self.ld("T1"); self.op("hp_b"); self.mulv("gb")
            self.addm("T2"); self.op("gain_lp"); self.addm("T1"); self.op("gbw_lp"); self.mul("QUARTER"); self.adaa("railc")
            self.mul("C4"); self.mul("C1_5"); self.adaa("clip"); self.mul("C0_9")
        elif m == "klon":
            self.st("T1"); self.op("drv_hp"); self.mulv("gd"); self.op("gain_lp"); self.adaa("clip"); self.mulv("wd")
            self.st("T2"); self.ld("T1"); self.mulv("wc"); self.addm("T2")
        elif m == "muff":
            self.op("s1_hp"); self.mulv("g1"); self.adaa("c1"); self.op("s1_lp")
            self.op("s2_hp"); self.mulv("g2"); self.adaa("c2"); self.op("s2_lp")
        else:
            v = self.v
            if v == 1: self.mulv("g1"); return
            if v in (0, 2, 4): self.mulv("g1"); self.adda("b1"); self.adaa("c1"); self.suba("o1")
            if v == 2: return
            self.op("mid_hp"); self.mulv("g2"); self.adda("b2"); self.adaa("c2"); self.suba("o2")

    def post(self):
        m = self.m
        if m == "ds1":
            self.st("T1"); self.op("tone_lp"); self.mul("C1_3")
            self.w(f"ld r8,[{self.A['s_tone']}]", "ld r9,[ONE]", "fsub r9,r9,r8", "st [X0],r9", "ld r8,[X0]", "fmul r2,r8,r2"); self.st("T2")
            self.ld("T1"); self.op("tone_hp"); self.mul("C1_8"); self.mulv("tone"); self.addm("T2")
        elif m == "ts808":
            self.op("post_lp"); self.st("T1"); self.op("tone_lp"); self.st("T2")      # T2 = tl
            self.w("mov r10,r2", "ld r9,[T1]", "fsub r9,r9,r10", f"ld r8,[{self.A['s_tone']}]", "fmul r9,r8,r9", "ld r8,[C0_6]",
                   "fmul r9,r8,r9", "fadd r2,r2,r9")
        elif m == "rat":
            self.op("tone_lp")
        elif m == "klon":
            self.st("T1"); self.op("tre_hp"); self.mulv("treb"); self.addm("T1"); self.op("post_lp")
        elif m == "muff":
            self.st("T1"); self.op("tone_lp"); self.mulv("lo"); self.st("T2"); self.ld("T1"); self.op("tone_hp"); self.mulv("hi"); self.addm("T2")
        elif self.v != 4:
            self.op("out_lp"); self.op("out_hp")
        self.mulv("level")

    def build(self):
        self.w("mov r0,#0", "st [16],r0", f"ld r6,[{FLAG}]", "skipbs r6,0,ON", "jmp 1280")
        self.lab("ON"); self.w("mov r0,#19", "st [PTR],r0", "mov r0,#64", "st [CNT],r0")
        self.lab("SAMPLE"); self.w("ld r0,[PTR]", "ld r2,[r0]")
        self.op("in_hp")
        if self.m == "ds1": self.op("boost_hp"); self.mulv("boost")
        self.st("X0"); self.chain("up1a"); self.st("M0"); self.ld("X0"); self.chain("up1b"); self.st("M1")
        for j, mk in ((0, "M0"), (1, "M1")):
            self.ld(mk); self.chain("upa2"); self.st(f"U{2 * j}"); self.ld(mk); self.chain("upb2"); self.st(f"U{2 * j + 1}")
        self.w("mov r0,#4", "st [KC],r0", f"mov r0,#{self.A['U0']}", "st [KP],r0")
        self.lab("CORE"); self.w("ld r0,[KP]", "ld r2,[r0]")
        self.core()
        self.w("ld r0,[KP]", "add r0,#4", "st [r0],r2", "sub r0,#3", "st [KP],r0",
               "ld r1,[KC]", "sub r1,#1", "st [KC],r1", "mov r3,#0"); self.pad(1); self.w("skipeq r1,r3,DOWN", "jmp CORE")
        self.lab("DOWN")
        for j, mk in ((0, "M0"), (1, "M1")):
            self.ld(f"V{2 * j + 1}"); self.chain("dna2"); self.st("T1"); self.ld(f"V{2 * j}"); self.chain("dnb2")
            self.addm("T1"); self.mul("HALF"); self.st(mk)
        self.ld("M1"); self.chain("dn1a"); self.st("T1"); self.ld("M0"); self.chain("dn1b"); self.addm("T1"); self.mul("HALF")
        self.post()
        self.w("ld r0,[PTR]", "st [r0],r2", "add r0,#1", "st [PTR],r0", "ld r1,[CNT]", "sub r1,#1", "st [CNT],r1",
               "mov r3,#0"); self.pad(0); self.w("skipeq r1,r3,FIN", "jmp SAMPLE")
        self.lab("FIN"); self.w("jmp 1280")
        if self.at() % 2 == 0: self.w("mov r8,#0")        # library starts at an odd address, as in all working programs
        return "\n".join(self.L) + "\n"


def equ(A):
    return {k: v for k, v in A.items()}


TRANSB = """
TRANSB: mov r9,#0
        fsub r9,r2,r9
        skipbs r15,30,TNEGB
        call r13,CUBIC
        ret r14
TNEGB:  ld r8,[C1_4]
        fmul r2,r8,r2
        call r13,CUBIC
        ld r8,[INV1_4]
        fmul r2,r8,r2
        ret r14
"""


def assemble_model(model, lib_at=LIB):
    A = layout(model.partition("#")[0]); E_ = equ(A); v = model.partition("#")[2]
    text = LIBRARY + ("        mov r8,#0\n" if v == "2" else "") + TRANSB if model.startswith("ds1#") and v in ("1", "2") else LIBRARY
    lib, labs = assemble(text, lib_at, E_)
    E_.update({k: v for k, v in labs.items()})
    main, _ = assemble(Main(model).build(), 0, E_)
    assert len(main) <= lib_at and lib_at + len(lib) <= 1280, (len(main), len(lib))
    return main, lib, A


def assemble_packed(model):
    """One slot, one model: library right behind the main program, so the blob's program image is main + lib
    and the stock loader puts all of it at code 0. Returns (image words, lib_at)."""
    n = len(assemble_model(model)[0])
    main, lib, _ = assemble_model(model, n); assert len(main) == n
    return list(main) + list(lib), n


def data_image(model, vals):
    A = layout(model); img = {}
    for n, v in CONSTS: img[A[n]] = E.f2u(v)
    for f in OPS[model]:
        for i, c in enumerate(("b0", "b1", "a1")): img[A[f] + i] = E.f2u(vals[f"{f}_{c}"])
    for c, cs in CHAINS:
        for i, v in enumerate(cs): img[A[c] + 3 * i] = E.f2u(v)
    for s in SCAL[model]: img[A["s_" + s]] = E.f2u(vals.get(s, {"tb": 0.15, "toff": 0.148875}.get(s)))
    return img, A


def check(model, packed=False):
    main, lib, A = assemble_model(model, len(assemble_model(model)[0]) if packed else LIB)
    lib_at = len(main) if packed else LIB
    img, _ = data_image(model, json.load(open(os.path.join(RE, "logs", f"{model}_coefs.json"))))
    x = np.fromfile(os.path.join(RE, "audio", f"{model}_host_in.f32"), "<f4")[:64 * 64]
    ref = np.fromfile(os.path.join(RE, "audio", f"{model}_host_out.f32"), "<f4")[:len(x)]
    e = E.Engine(); e.load_code(0, main); e.load_code(lib_at, lib); e.code[1280] = 0xA00E0000
    for a, v in img.items(): e.d[a] = v
    e.d[FLAG] = 1; y = np.zeros_like(x); un = []
    for b in range(len(x) // 64):
        e.d[19:83] = x[b * 64:(b + 1) * 64].view(np.uint32); e.steps = 0; e.units = 0
        e.run(0, limit=3_000_000); un.append(e.units); y[b * 64:(b + 1) * 64] = e.d[19:83].view(np.float32)
    err = float(np.max(np.abs(y - ref)) / np.max(np.abs(ref)))
    print(f"{model}{' packed' if packed else ''}: main {len(main)} + library {len(lib)} words, units/block {int(np.mean(un))}, rel err vs C {err:.2e}")


if __name__ == "__main__":
    if sys.argv[1] == "check": [check(m) for m in sys.argv[2:]]
    elif sys.argv[1] == "checkpacked": [check(m, True) for m in sys.argv[2:]]
    elif sys.argv[1] == "sizes":
        for m in OPS: mn, lb, _ = assemble_model(m); print(m, "main", len(mn), "library", len(lb))


MODELS = ["ds1", "ts808", "rat", "fuzz", "klon", "muff"]


def export():
    """dsp/eng2.h (data addresses for the ARM side) and build/progs2/{lib,ds1,ts808,rat,fuzz}.bin"""
    h = ["/* generated by tools/drives2.py export - do not edit */", f"#define FLAG_W {FLAG}", f"#define LIB_AT {LIB}"]
    A0 = layout("ds1")
    for n, _ in CONSTS: h.append(f"#define K_{n} {A0[n]}")
    h.append("static const float CONST_VAL[] = {" + ", ".join(repr(float(v)) + "f" for _, v in CONSTS) + "};")
    h.append(f"#define CONST_LO {A0['ONE']}\n#define NCONST {len(CONSTS)}")
    chain_c = []
    for m in MODELS:
        A = layout(m); M = m.upper()
        for f in OPS[m]: h.append(f"#define {M}_{f.upper()} {A[f]}")
        for a in CLIPS[m]: h.append(f"#define {M}_CLIP_{a.upper()} {A[a]}")
        for s in SCAL[m]: h.append(f"#define {M}_S_{s.upper()} {A['s_' + s]}")
        h.append(f"#define {M}_LO {A['MODEL_LO']}\n#define {M}_HI {A['MODEL_HI']}")
        h.append(f"static const unsigned short {m}_chain_at[] = {{" +
                 ", ".join(str(A[c] + 3 * i) for c, cs in CHAINS for i in range(len(cs))) + "};")
    h.append("static const float CHAIN_C[] = {" + ", ".join(repr(float(v)) + "f" for c, cs in CHAINS for v in cs) + "};")
    h.append(f"#define NCHAIN {sum(len(cs) for _, cs in CHAINS)}")
    open(os.path.join(RE, "dsp", "eng2.h"), "w").write("\n".join(h) + "\n")
    out = os.path.join(RE, "build", "progs2"); os.makedirs(out, exist_ok=True)
    for m in MODELS:
        main, lib, _ = assemble_model(m)
        open(os.path.join(out, f"{m}.bin"), "wb").write(np.array(main, "<u4").tobytes())
    open(os.path.join(out, "lib.bin"), "wb").write(np.array(lib, "<u4").tobytes())
    print("exported; library", len(lib), "words")


if __name__ == "__main__" and sys.argv[1] == "export":
    export()
