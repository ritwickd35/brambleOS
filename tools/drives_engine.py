#!/usr/bin/env python3
"""DS-1 / TS808 engine programs (DRV slot) + data images, validated against dsp/host (the offline C models).
  drives_engine.py dumpc              writes dsp/dumpcoefs.c (host: prints every coefficient/state as JSON)
  drives_engine.py check ds1|ts808    builds the engine program, runs engine_emu vs the host model
  drives_engine.py arm ds1|ts808      writes dsp/eng_<model>.h (ARM-side address/offset tables)
Register plan: r0-r7 survive rsqrt, r8-r11 are scratch (rsqrt clobbers r9-r11), r12 pointer, r13 = 0.5, r14 = 1.0."""
import json, os, subprocess, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
from easm import assemble
import engine_emu as E

FLAG = 0x193
BASE = 0x1A0
HB = [0.054217526, 0.196797970, 0.383087327, 0.573136411, 0.748720944, 0.914293710]
HB2 = [0.070224059, 0.285086280, 0.684541359]
CONSTS = {"one": 1.0, "half": 0.5, "third": 1.0 / 3, "two_third": 2.0 / 3, "quarter": 0.25, "eps": 1e-4,
          "c1_4": 1.4, "inv1_4": 1.0 / 1.4, "c1_6": 1.6, "c0_55": 0.55, "c1_8": 1.8, "c1_3": 1.3, "c0_6": 0.6, "c4": 4.0, "c1_5": 1.5, "c0_9": 0.9}
OPS = {"ds1": ["in_hp", "boost_hp", "op_hp", "op_lp", "clip_lp", "tone_lp", "tone_hp"],
       "ts808": ["in_hp", "fb_hp", "fb_lp", "post_lp", "tone_lp"],
       "rat": ["in_hp", "hp_a", "hp_b", "gain_lp", "gbw_lp", "tone_lp"],
       "fuzz": ["in_hp", "mid_hp", "out_lp", "out_hp"]}
CLIPPERS = {"ds1": ["diode"], "ts808": ["clip"], "rat": ["clip", "railc"], "fuzz": ["c1", "c2"]}
SCALARS = {"ds1": ["boost", "opgain", "tone", "level"], "ts808": ["gain", "tone", "level"],
           "rat": ["ga", "gb", "level"], "fuzz": ["g1", "g2", "b1", "b2", "o1", "o2", "level"]}
CHAINS = [("up1a", 3), ("up1b", 3), ("upa2", 2), ("upb2", 1), ("dn1a", 3), ("dn1b", 3), ("dna2", 2), ("dnb2", 1)]
CHAIN_EXPR = {"up1a": "up.s1.a", "up1b": "up.s1.b", "upa2": "up.a2", "upb2": "up.b2",
              "dn1a": "dn.s1.a", "dn1b": "dn.s1.b", "dna2": "dn.a2[0]", "dnb2": "dn.b2[0]"}


def spec(model):
    sp = [(f"hb{i}", None, HB[i]) for i in range(6)] + [(f"hb2_{i}", None, HB2[i]) for i in range(3)]
    sp += [(k, None, v) for k, v in CONSTS.items()]
    for pre, n in CHAINS:
        e = CHAIN_EXPR[pre]
        sp += [(f"{pre}_x{k}", f"{e}.x[{k}]", None) for k in range(n)] + [(f"{pre}_y{k}", f"{e}.y[{k}]", None) for k in range(n)]
    for f in OPS[model]:
        sp += [(f"{f}_{c}", f"{f}.{c}", None) for c in ("b0", "b1", "a1")]
        sp += [(f"{f}_{c}", f"{f}.{c}", None) for c in ("x1", "y1")]
    for ad in CLIPPERS[model]: sp += [(f"{ad}_x1", f"{ad}.x1", None), (f"{ad}_F1", f"{ad}.F1", None)]
    sp += [(k, k, None) for k in SCALARS[model]]
    sp += [(f"u{k}", None, None) for k in range(4)] + [(f"v{k}", None, None) for k in range(4)]
    return sp


class Gen:
    def __init__(self, model):
        self.model = model; self.sp = spec(model)
        self.addr = {k: BASE + i for i, (k, *_) in enumerate(self.sp)}
        self.n = 0; self.L = []

    def a(self, k): return self.addr[k]
    def w(self, s): self.L.append("    " + s)
    def mark(self, s): self.L.append(s + ":")
    def lab(self, p): self.n += 1; return f"{p}{self.n}"

    def onepole(self, f, rx):
        assert rx in ("r2", "r3", "r4", "r5", "r6", "r7"), rx
        a = self.a
        for s in [f"ld r8,[{a(f+'_b0')}]", f"fmul r9,r8,{rx}", f"ld r8,[{a(f+'_b1')}]", f"ld r10,[{a(f+'_x1')}]",
                  f"fmac r9,r8,r10", f"ld r8,[{a(f+'_a1')}]", f"ld r10,[{a(f+'_y1')}]", f"fmul r11,r8,r10",
                  f"fsub r9,r9,r11", f"st [{a(f+'_x1')}],{rx}", f"st [{a(f+'_y1')}],r9", f"mov {rx},r9"]:
            self.w(s)

    def ap(self, coef, pre, k, rx):
        a = self.a
        for s in [f"ld r8,[{a(coef)}]", f"ld r9,[{a(pre+'_y'+str(k))}]", f"fsub r9,{rx},r9", f"fmul r9,r8,r9",
                  f"ld r10,[{a(pre+'_x'+str(k))}]", f"fadd r9,r9,r10", f"st [{a(pre+'_x'+str(k))}],{rx}",
                  f"st [{a(pre+'_y'+str(k))}],r9", f"mov {rx},r9"]:
            self.w(s)

    def chain(self, pre, rx):
        n = dict(CHAINS)[pre]
        assert rx in ("r2", "r3", "r4", "r5", "r6", "r7"), rx
        idx = ([1, 3, 5] if pre.endswith("1b") else [0, 2, 4]) if n == 3 else [0, 2] if n == 2 else [1]
        fam = "hb2" if pre.endswith("a2") or pre.endswith("b2") else "hb"
        for k, i in zip(range(n), idx): self.ap(("hb2_" + str(i)) if fam == "hb2" else f"hb{i}", pre, k, rx)

    def mulc(self, rx, key):
        self.w(f"ld r8,[{self.a(key)}]"); self.w(f"fmul {rx},r8,{rx}")

    def cubic(self, rx):                                  # f(x) with clamp, result in rx (r8-r12 scratch)
        big, done = self.lab("cbig"), self.lab("cdone")
        self.w(f"mov r8,{rx}"); self.w("andh r8,#0x7fff"); self.w("fsub r12,r14,r8")
        self.w(f"skipbs r15,30,{big}")
        self.w(f"fmul r9,{rx},{rx}"); self.w(f"fmul r9,r9,{rx}")
        self.mulc("r9", "third"); self.w(f"fsub {rx},{rx},r9"); self.w(f"jmp {done}")
        self.mark(big)                                                   # +-2/3 with the sign of x
        self.w(f"mov r9,{rx}"); self.w("andh r9,#0x8000")                # sign bit only
        self.w(f"ld r10,[{self.a('two_third')}]"); self.w("ior r10,r10,r9,h=0x78"); self.w(f"mov {rx},r10")
        self.mark(done)

    def transistor(self, rx):                             # DS1_TRANS_ADAA = 0 path in ds1.c
        """x >= 0: cubic(x); x < 0: clamped cubic(1.4*x)/1.4."""
        neg, pos, done = self.lab("tneg"), self.lab("tpos"), self.lab("tdone")
        self.w("mov r8,#0"); self.w(f"fsub r12,r8,{rx}")     # -x: negative result means x > 0
        self.w(f"skipbs r15,30,{pos}")
        self.w(f"jmp {neg}")
        self.mark(pos); self.cubic(rx); self.w(f"jmp {done}")
        self.mark(neg); self.mulc(rx, "c1_4"); self.cubic(rx); self.mulc(rx, "inv1_4")
        self.mark(done)

    def adaa(self, name, rx):
        """dsp/pmfx.c adaa_cubic. rx = x. Safe regs across rsqrt: r0-r7; r9-r11 are scratch.
        r4 old F1, r5 new F / numerator, r6 old x1, r7 d, r0-r3 temp."""
        a = self.a; big, haveF, small, done = self.lab("abig"), self.lab("aF"), self.lab("asmall"), self.lab("adone")
        self.w(f"ld r6,[{a(name+'_x1')}]"); self.w(f"ld r4,[{a(name+'_F1')}]")
        self.w(f"st [{a(name+'_x1')}],{rx}")
        self.w(f"fsub r7,{rx},r6")                                        # d = x - x1
        self.w(f"mov r0,{rx}"); self.w("andh r0,#0x7fff"); self.w("fsub r12,r14,r0")
        self.w(f"skipbs r15,30,{big}")   # |x| >= 1 -> take the clamped branch (N set means 1-|x| < 0)
        self.w(f"fmul r9,{rx},{rx}"); self.w("fmul r10,r9,r9"); self.w("fmul r9,r13,r9")
        self.w(f"ld r11,[{a('third')}]"); self.w(f"ld r12,[{a('quarter')}]")
        self.w("fmul r11,r11,r12"); self.w("fmul r11,r11,r10"); self.w("fsub r9,r9,r11")
        self.w(f"jmp {haveF}")
        self.mark(big)
        self.w(f"ld r9,[{a('two_third')}]"); self.w("fmul r9,r9,r0")
        self.w(f"ld r11,[{a('quarter')}]"); self.w("fsub r9,r9,r11")
        self.mark(haveF)
        self.w(f"st [{a(name+'_F1')}],r9"); self.w("mov r5,r9")
        self.w("mov r0,r7"); self.w("andh r0,#0x7fff"); self.w(f"ld r12,[{a('eps')}]"); self.w("fsub r12,r0,r12")
        self.w(f"skipbs r15,30,{small}")                                  # |d| >= eps -> divide
        self.w("mov r0,r7"); self.w("andh r0,#0x7fff"); self.w("rsqrt r0,r0")
        self.w("fmul r0,r0,r0"); self.w("mov r1,r7"); self.w("andh r1,#0x8000"); self.w("ior r0,r0,r1,h=0x78")   # 1/d with the sign of d
        self.w("fsub r5,r5,r4"); self.w("fmul r5,r5,r0"); self.w(f"mov {rx},r5"); self.w(f"jmp {done}")
        self.mark(small)                                                  # y = f((x + x1)/2)
        self.w(f"fadd {rx},{rx},r6"); self.w(f"fmul {rx},r13,{rx}"); self.cubic(rx)
        self.mark(done)

    def build(self):
        m = self.model
        self.L.append("    mov r0,#0"); self.L.append("    st [0x10],r0")
        self.L.append(f"    ld r6,[{FLAG}]"); self.L.append("    skipbs r6,0,on"); self.L.append("    jmp bypass")
        self.mark("on"); self.L.append("    movf r13,0.5"); self.L.append("    movf r14,1.0")
        end = BASE + len(self.sp); assert end + 2 < 0x398, hex(end)
        self.PTR, self.CNT = end, end + 1                                # own slots, past the state area
        self.L.append("    mov r0,#0x13"); self.L.append(f"    st [{self.PTR}],r0")
        self.L.append("    mov r0,#64"); self.L.append(f"    st [{self.CNT}],r0")
        self.mark("sample")
        self.L.append(f"    ld r0,[{self.PTR}]"); self.L.append("    ld r2,[r0]")   # pointer/counter live in memory only
        self.onepole("in_hp", "r2")
        if m == "ds1": self.onepole("boost_hp", "r2"); self.mulc("r2", "boost")
        self.mark("tap_in")
        # 4x upsample: stage 1 (6 coefs split 0,2,4 / 1,3,5), stage 2 (3 coefs split 0,2 / 1)
        self.w("mov r4,r2"); self.chain("up1a", "r4")                   # m0 (r4, r5 survive the chains)
        self.w("mov r5,r2"); self.chain("up1b", "r5")                   # m1
        for j, mr in ((0, "r4"), (1, "r5")):
            self.w(f"mov r3,{mr}"); self.chain("upa2", "r3"); self.w(f"st [{self.a('u'+str(2*j))}],r3")
            self.w(f"mov r3,{mr}"); self.chain("upb2", "r3"); self.w(f"st [{self.a('u'+str(2*j+1))}],r3")
        self.mark("tap_u")
        ad = "diode" if m == "ds1" else "clip"
        for k in range(4):
            self.w(f"ld r2,[{self.a('u'+str(k))}]")
            if m == "ds1":
                self.transistor("r2")
                self.w("mov r3,r2"); self.onepole("op_hp", "r3"); self.mulc("r3", "opgain")
                self.w("fadd r2,r2,r3")
                self.onepole("op_lp", "r2"); self.onepole("clip_lp", "r2"); self.mulc("r2", "c1_6")
                self.adaa("diode", "r2")
            elif m == "rat":
                self.w("mov r3,r2"); self.onepole("hp_a", "r3"); self.mulc("r3", "ga")
                self.w("st [%d],r3" % self.a("v3"))                       # v3 is free until stored below
                self.w("mov r3,r2"); self.onepole("hp_b", "r3"); self.mulc("r3", "gb")
                self.w("ld r4,[%d]" % self.a("v3")); self.w("fadd r3,r3,r4")
                self.onepole("gain_lp", "r3"); self.w("fadd r2,r2,r3")
                self.onepole("gbw_lp", "r2"); self.mulc("r2", "quarter"); self.adaa("railc", "r2"); self.mulc("r2", "c4")
                self.mulc("r2", "c1_5"); self.adaa("clip", "r2"); self.mulc("r2", "c0_9")
            elif m == "fuzz":
                self.mulc("r2", "g1"); self.w(f"ld r8,[{self.a('b1')}]"); self.w("fadd r2,r2,r8")
                self.adaa("c1", "r2"); self.w(f"ld r8,[{self.a('o1')}]"); self.w("fsub r2,r2,r8")
                self.onepole("mid_hp", "r2")
                self.mulc("r2", "g2"); self.w(f"ld r8,[{self.a('b2')}]"); self.w("fadd r2,r2,r8")
                self.adaa("c2", "r2"); self.w(f"ld r8,[{self.a('o2')}]"); self.w("fsub r2,r2,r8")
            else:
                self.onepole("fb_hp", "r2"); self.mulc("r2", "gain"); self.onepole("fb_lp", "r2"); self.mulc("r2", "c1_8")
                self.adaa("clip", "r2"); self.mulc("r2", "c0_55")
                self.w(f"ld r3,[{self.a('u'+str(k))}]"); self.w("fadd r2,r3,r2")
            self.w(f"st [{self.a('v'+str(k))}],r2")
        self.mark("tap_v")
        # downsample: stage 2 pair, then stage 1 pair
        for j in (0, 1):
            self.w(f"ld r2,[{self.a('v'+str(2*j+1))}]"); self.chain("dna2", "r2"); self.w("mov r4,r2")
            self.w(f"ld r3,[{self.a('v'+str(2*j))}]"); self.chain("dnb2", "r3")
            self.w("fadd r2,r4,r3"); self.w("fmul r2,r13,r2"); self.w(f"st [{self.a('v'+str(j))}],r2")
        self.w(f"ld r2,[{self.a('v1')}]"); self.chain("dn1a", "r2"); self.w("mov r4,r2")
        self.w(f"ld r3,[{self.a('v0')}]"); self.chain("dn1b", "r3")
        self.w("fadd r2,r4,r3"); self.w("fmul r2,r13,r2")
        self.mark("tap_y")
        if m == "ds1":
            self.w("mov r3,r2"); self.onepole("tone_lp", "r3"); self.mulc("r3", "c1_3")
        # tone_hp uses the pre-filter signal (already in r2)     # low path *1.3
            self.w("mov r4,r3"); self.w("ld r5,[%d]" % self.a("tone")); self.w("mov r6,r14"); self.w("fsub r6,r6,r5")
            self.w("fmul r3,r6,r3")                                                          # (1-tone)*lo*1.3
            self.onepole("tone_hp", "r2"); self.mulc("r2", "c1_8")
            self.w("fmul r2,r5,r2"); self.w("fadd r2,r3,r2")
        elif m == "rat":
            self.onepole("tone_lp", "r2")
        elif m == "fuzz":
            self.onepole("out_lp", "r2"); self.onepole("out_hp", "r2")
        else:
            self.onepole("post_lp", "r2")
            self.w("mov r3,r2"); self.onepole("tone_lp", "r3")
            self.w("fsub r4,r2,r3"); self.w(f"ld r5,[{self.a('tone')}]"); self.mulc("r5", "c0_6")
            self.w("fmul r4,r5,r4"); self.w("fadd r2,r3,r4")
        self.mulc("r2", "level")
        self.w(f"ld r0,[{self.PTR}]"); self.w("st [r0],r2")          # write in place (0x13..)
        self.w("add r0,#1"); self.w(f"st [{self.PTR}],r0")
        self.w(f"ld r1,[{self.CNT}]"); self.w("sub r1,#1"); self.w(f"st [{self.CNT}],r1")
        self.w("mov r3,#0"); self.w("skipeq r1,r3,finish"); self.w("jmp sample")
        self.mark("finish"); self.w("jmp 0x500")
        self.mark("bypass"); self.w("jmp 0x500")
        return "\n".join(self.L) + "\n"


def build(model):
    g = Gen(model); src = g.build(); words, labels = assemble(src, 0)
    img = [(FLAG, 1)]
    return g, src, words, img


def dumpc():
    for m in ("ds1", "ts808"):
        sp = spec(m)
        print(f'// {m}', file=sys.stderr)
        print('{', ", ".join(f'["{k}"] = {json.dumps(e)}' for k, e, v in sp if e), '}')


if __name__ == "__main__" and sys.argv[1] == "check":
    model = sys.argv[2]; g, src, words, _ = build(model)
    open(os.path.join(RE, "logs", f"{model}_engine.s"), "w").write(src)
    vals = json.load(open(os.path.join(RE, "logs", f"{model}_coefs.json")))
    img = [(FLAG, 1)] + [(g.addr[k], E.f2u(vals[k])) for k, e, v in g.sp if k in vals]
    for k, e, v in g.sp:
        if v is not None: img.append((g.addr[k], E.f2u(v)))
    x = np.fromfile(os.path.join(RE, "audio", f"{model}_host_in.f32"), "<f4")[:64 * 64]
    ref = np.fromfile(os.path.join(RE, "audio", f"{model}_host_out.f32"), "<f4")[:len(x)]
    e = E.Engine(); e.load_code(0, words); e.code[0x500] = 0xA00E0000
    for a, v in img: e.d[a] = v
    y = np.zeros_like(x); un = []
    for b in range(len(x) // 64):
        e.d[0x13:0x53] = x[b * 64:(b + 1) * 64].view(np.uint32); e.units = 0
        e.run(0, limit=5_000_000); un.append(e.units); y[b * 64:(b + 1) * 64] = e.d[0x13:0x53].view(np.float32)
    err = float(np.max(np.abs(y - ref)) / (np.max(np.abs(ref)) + 1e-12))
    print(f"{model}: program {len(words)} words, state words {len(g.sp)}, est. units/block {int(np.mean(un))}, "
          f"max rel err vs host {err:.3e}, unknown {e.unknown}")


STATE_SUFFIX = ("_x1", "_y1", "_F1")


def is_state(k):
    return k.endswith(STATE_SUFFIX) or k[:4] in ("up1a", "up1b", "upa2", "upb2", "dn1a", "dn1b", "dna2", "dnb2") \
        or k in ("u0", "u1", "u2", "u3", "v0", "v1", "v2", "v3")


def arm_tables(models):
    """dsp/eng_drives.h: per model, data-word tables for the ARM module (addresses + struct offsets)."""
    h = ["/* generated by tools/drives_engine.py arm - do not edit */", "#include <stddef.h>", "#include <stdint.h>"]
    for m in models:
        g = Gen(m); g.build(); T = "ds1_t" if m == "ds1" else "ts808_t"
        coef = [(g.addr[k], e) for k, e, v in g.sp if e and not is_state(k)]
        const = [(g.addr[k], v) for k, e, v in g.sp if v is not None]
        zero = [g.addr[k] for k, e, v in g.sp if is_state(k)]
        h.append(f"static const uint16_t {m}_coef_addr[] = {{{', '.join(str(a) for a, _ in coef)}}};")
        h.append(f"static const uint16_t {m}_coef_off[] = {{{', '.join(f'offsetof({T}, {e}) / 4' for _, e in coef)}}};")
        h.append(f"static const uint16_t {m}_const_addr[] = {{{', '.join(str(a) for a, _ in const)}}};")
        h.append(f"static const float {m}_const_val[] = {{{', '.join(repr(float(v)) + 'f' for _, v in const)}}};")
        h.append(f"static const uint16_t {m}_zero_addr[] = {{{', '.join(str(a) for a in zero)}}};")
        h.append(f"#define {m.upper()}_NCOEF {len(coef)}\n#define {m.upper()}_NCONST {len(const)}\n#define {m.upper()}_NZERO {len(zero)}")
    open(os.path.join(RE, "dsp", "eng_drives.h"), "w").write("\n".join(h) + "\n")
    os.makedirs(os.path.join(RE, "build", "progs"), exist_ok=True)
    for m in models:
        _, _, words, _ = build(m)
        open(os.path.join(RE, "build", "progs", f"{m}.bin"), "wb").write(np.array(words, "<u4").tobytes())
        print(f"{m}: {len(words)} program words")


if __name__ == "__main__" and sys.argv[1] == "arm":
    arm_tables(sys.argv[2:] or ["ds1", "ts808"])


TYPES = {"ds1": ("ds1_t", "ds1"), "ts808": ("ts808_t", "ts808"), "rat": ("rat_t", "rat"), "fuzz": ("fuzz_t", "fuzz")}


def write_dumpc(models):
    """dsp/dumpcoefs.c: prints {key: value} JSON per model after <model>_init(50, 50, 50) (one line each)."""
    L = ["#include <stdio.h>", '#include "ds1.h"', '#include "ts808.h"', '#include "rat.h"', '#include "fuzz.h"',
         "int main(int argc, char **argv) {", "  float k0 = 50, k1 = 50, k2 = 50;",
         "  if (argc > 3) { sscanf(argv[1], \"%f\", &k0); sscanf(argv[2], \"%f\", &k1); sscanf(argv[3], \"%f\", &k2); }"]
    for m in models:
        T, f = TYPES[m]
        L.append(f"  {{ static {T} s; {f}_init(&s, k0, k1, k2); printf(\"{m} {{\");")
        keys = [(k, e) for k, e, v in spec(m) if e]
        for i, (k, e) in enumerate(keys):
            sep = "," if i < len(keys) - 1 else ""
            L.append(f"    printf(\"\\\"{k}\\\": %.9g{sep}\", (double)s.{e});")
        L.append("    printf(\"}\\n\"); }")
    L.append("  return 0; }")
    open(os.path.join(RE, "dsp", "dumpcoefs.c"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__" and sys.argv[1] == "dumpc":
    write_dumpc(sys.argv[2:] or ["ds1", "ts808", "rat", "fuzz"])
