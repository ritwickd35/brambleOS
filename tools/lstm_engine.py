#!/usr/bin/env python3
"""Engine program for the LSTM amp (DRV slot, code base 0) + data image, from a lstmamp.py state dict.
  lstm_engine.py logs/lstm_H8_L128.pt   -> checks the engine model against torch, writes logs/lstm_engine_*.json
Data map (words): 0x193 enable flag (ARM) | 0x194 level | 0x195.. weights: per gate row [b, wx, U(H)] x 4H,
w_out(H), b_out, skip, FIR reversed (L) | state h(H) c(H) pre(4H) | FIR history (L-1+64)."""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
from easm import assemble
import engine_emu as E

FLAG, LEVEL, WBASE = 0x193, 0x194, 0x195


def layout(H, L):
    rows = WBASE; nrow = 4 * H * (H + 2)
    wout = rows + nrow; fir = wout + H + 2
    h = fir + L; c = h + H; pre = c + H; hist = pre + 4 * H + 3; end = hist + L - 1 + 64   # +3 spill words
    return dict(rows=rows, wout=wout, fir=fir, h=h, c=c, pre=pre, hist=hist, end=end)


def weights(sd, H, L, gain=1.0):
    """data words (floats) from rows .. h (exclusive), engine order; gain folds the input level into wx and skip"""
    W = sd["lstm.weight_ih_l0"].numpy()[:, 0]; U = sd["lstm.weight_hh_l0"].numpy()
    b = (sd["lstm.bias_ih_l0"] + sd["lstm.bias_hh_l0"]).numpy(); g = float(np.exp(sd["gain"].numpy()[0])) * gain
    out = []
    for k in range(4 * H): out += [b[k], W[k] * g] + list(U[k])
    out += list(sd["out.weight"].numpy()[0]) + [float(sd["out.bias"].numpy()[0]), float(sd["skip"].numpy()[0]) * g]
    out += list(sd["fir"].numpy()[::-1])                       # reversed: dot over history window
    return np.array(out, np.float32)


def program(H, L):
    A = layout(H, L)                                           # h in r0..r(H-1), H <= 8
    assert H <= 8
    s = [f"""; LSTM amp, H={H}, L={L}
    mov r0,#0
    st [0x10],r0
    mov r5,#{FLAG}
    ld r6,[r5]
    skipbs r6,0,on
    jmp bypass
on: mov r13,#{A['hist'] + L - 1}           ; LSTM output -> history[L-1+n]
    st [{A['pre'] + 4 * H}],r13             ; spill slot (outside pre) for the output pointer
    mov r12,#0x13
    st [{A['pre'] + 4 * H + 1}],r12         ; input pointer
    mov r14,#64
    st [{A['pre'] + 4 * H + 2}],r14         ; sample counter
sample:"""]
    s += [f"    ld r{j},[{A['h'] + j}]" for j in range(H)]
    s += [f"""    ld r12,[{A['pre'] + 4 * H + 1}]
    ld r8,[r12]++
    st [{A['pre'] + 4 * H + 1}],r12
    mov r12,#{A['rows']}
    mov r13,#{A['pre']}
    mov r14,#{4 * H}
row: ld r9,[r12]++
    ld r10,[r12]++
    fmac r9,r10,r8"""]
    for j in range(H): s += [f"    ld r10,[r12]++", f"    fmac r9,r10,r{j}"]
    s += ["    st [r13]++,r9", "    djnz r14,row"]
    # activations per unit j (r9-r11 are clobbered by rsqrt; r12 scratch; r13 = 0.5, r14 = 1.0)
    def Tr(src, dst): return [f"    fmul r12,{src},{src}", "    fadd r12,r12,r14", "    rsqrt r12,r12", f"    fmul {dst},{src},r12"]
    def Sm(addr, dst): return [f"    ld {dst},[{addr}]", f"    fmul {dst},r13,{dst}"] + Tr(dst, dst) + [f"    fmul {dst},r13,{dst}", f"    fadd {dst},{dst},r13"]
    s += ["    movf r13,0.5", "    movf r14,1.0"]
    for j in range(H):
        pi, pf, pg, po = (A["pre"] + q * H + j for q in range(4))
        s += Sm(pi, "r0") + [f"    ld r1,[{pg}]"] + Tr("r1", "r1") + Sm(pf, "r2") + Sm(po, "r3")
        s += [f"    ld r4,[{A['c'] + j}]", "    fmul r4,r2,r4", "    fmac r4,r0,r1", f"    st [{A['c'] + j}],r4"]
        s += Tr("r4", "r5") + ["    fmul r6,r3,r5", f"    st [{A['h'] + j}],r6"]
    # output y = b_out + w_out . h + skip * x
    s += [f"    ld r12,[{A['pre'] + 4 * H + 1}]", "    sub r12,#1", "    ld r8,[r12]",
          f"    ld r9,[{A['wout'] + H}]", f"    ld r10,[{A['wout'] + H + 1}]", "    fmac r9,r10,r8"]
    for j in range(H): s += [f"    ld r8,[{A['h'] + j}]", f"    ld r10,[{A['wout'] + j}]", "    fmac r9,r10,r8"]
    s += [f"    ld r13,[{A['pre'] + 4 * H}]", "    st [r13]++,r9", f"    st [{A['pre'] + 4 * H}],r13",
          f"    ld r14,[{A['pre'] + 4 * H + 2}]", "    djnz r14,more", "    jmp fir",
          f"more: st [{A['pre'] + 4 * H + 2}],r14", "    jmp sample"]
    # FIR over the history window, 64 outputs to 0x13.., then shift history and apply level
    s += [f"""fir: mov r12,#{A['hist']}
    mov r13,#0x13
    mov r14,#64
firl: mov r8,#{A['fir']}
    mov r9,r12
    mov r10,#{L}
    vdot
    st [r13]++,r11
    add r12,#1
    djnz r14,firl
    mov r9,#{A['hist'] + 64}
    mov r10,#{L - 1}
    mov r11,#{A['hist']}
    vcopy
    ld r8,[{LEVEL}]
    mov r9,#0x13
    mov r10,#64
    mov r11,#0x13
    vmuls
    jmp 0x500
bypass: jmp 0x500"""]
    return "\n".join(s) + "\n", A


def emulate(words, data_img, A, x):
    e = E.Engine(); e.load_code(0, words)
    e.code[0x500] = 0xA00E0000
    for a, v in data_img: e.d[a] = v
    y = np.zeros_like(x); steps = []
    for b in range(len(x) // 64):
        e.d[0x13:0x53] = x[b * 64:(b + 1) * 64].astype(np.float32).view(np.uint32)
        e.steps = 0; e.units = 0; e.run(0, limit=10_000_000); steps.append(e.units)
        y[b * 64:(b + 1) * 64] = e.d[0x13:0x53].view(np.float32)
    return y, steps, e


def build(pt, gain=1.0, level=1.0):
    import torch
    sd = torch.load(pt); H = sd["lstm.weight_hh_l0"].shape[1]; L = sd["fir"].shape[0]
    src, A = program(H, L); words, labels = assemble(src, 0)
    w = weights(sd, H, L, gain)
    img = [(FLAG, 1), (LEVEL, E.f2u(level))] + [(A["rows"] + i, E.f2u(v)) for i, v in enumerate(w)]
    return words, img, A, H, L, sd


if __name__ == "__main__":
    import torch, lstmamp
    pt = sys.argv[1]; words, img, A, H, L, sd = build(pt)
    x, t = lstmamp.data(); sp = int(0.8 * len(x)); n = 64 * 400
    xs = x[sp:sp + n]
    y, steps, e = emulate(words, img, A, xs)
    m = lstmamp.Amp(H, L); m.load_state_dict(sd); m.engine = True
    with torch.no_grad(): yt = m(torch.tensor(xs).unsqueeze(0)).squeeze(0).numpy()
    err = float(np.max(np.abs(y - yt)) / (np.max(np.abs(yt)) + 1e-9))
    res = dict(pt=os.path.basename(pt), H=H, L=L, program_words=len(words), data_end=A["end"],
               engine_units_per_block=int(np.mean(steps)), max_rel_err_vs_torch=err, unknown_ops=e.unknown)
    json.dump(res, open(os.path.join(RE, "logs", "lstm_engine_" + os.path.basename(pt).replace(".pt", ".json")), "w"), indent=1)
    open(os.path.join(RE, "logs", "lstm_engine.s"), "w").write(program(H, L)[0])
    print(f"program {len(words)} words, data up to word {A['end']}, est. engine units/block {int(np.mean(steps))}, max rel err vs torch {err:.2e}")
