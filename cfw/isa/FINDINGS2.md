# E2: engine instruction set, measured on the pedal (cut 8 / 8b, 2026-11-18)

Method: `cut1/combo4.c` (DRV #7 host) writes test programs into engine code RAM (EQ slot, needs EQ = Bass EQ), reads
the register dump, and sends the results as tones through the audio output (`tools/eprobe_decode.py`).
1416 runs decoded (`logs/eprobe_report.txt`, `logs/eprobe_report2.txt`). Model: `tools/engine_emu.py`
(agrees with every deterministic run). Assembler: `tools/easm.py`.

Word = [op:8][b1:8][imm:16]; op = class<<4 | R; b1 = A<<4 | S; B = imm & 15. Registers r0..r15 are raw 32-bit;
r15 = flags. Denormals flush to zero. Addresses use the low 12 bits.

| class | form | meaning |
|---|---|---|
| 5 | b1 00 / 08 | ld rR,[N] / st [N],rR  (FINDINGS.md had these swapped) |
| 7 | b1 06 00 02 04 | mov #N / add #N / sub #N / mul #N (integer, raw bits) |
| 7 | b1 C6 / 86 | movhi / movlo: set one half, keep the other |
| 7 | b1 C8 CA CC | and / or / xor of the high half with N (abs = and 7FFF, neg = xor 8000) |
| E | S 2 3 4 5 | ld rR,[rA] / ld rR,[rA]++ / st [rR],rA / st [rR]++,rA |
| E | S 6 7 | load from code RAM: rR = code[rA] (++): tables can live in code RAM |
| 8 | S 6 / A / 0 | rB = rA*rR / rB += rA*rR (float) / rB = rR*rA (integer) |
| C | S E / F | rB = rR + rA / rB = rR - rA (float) |
| C | S 0 2 4 5 6 7 8 | integer add, sub (rR-rA), and, or, rsub (rA-rR), shr, shl; dest rB. imm[15:8]: 0 = 32-bit; 0x40 bit set = 16-bit op, 0x20 dest high half, 0x10 rA high half, 0x08 rR high half (e.g. 0x78 = OR of the high halves = copysign) |
| F | S 4 | mov rR,rA (imm 0); 0x4000 low half only; 0x7000 high half only |
| F | S E | rB = 1/sqrt(rR) (rR > 0), macro: overwrites r9 (= x/2), r10, r11 |
| 9 | S 8 / A | skip the next n words if bit k of rR is set / clear; n = imm & 0x1FF, k = imm >> 9 |
| 9 | S 2 / 4 | skip n if rR >= rA (signed integer) / if rR == rA |
| 9 | S 6 | unknown: running it stopped all engine audio until reboot (CAB-only, avoid) |
| A | b1 04 | djnz rR,addr (decrement, jump if not zero) |
| A | b1 06 | call: link to rR (imm bit13: high half, else low half) ; b1 0A ret via rR ; A0 08 jmp ; A0 0E halt |
| 2 | S 0 3 7 8 D | vectors over n = r10: copy r9->r11, add r9+r8, mul r9*r8, scale r9*r8(float), D = dot product: r11 = sum r9[i]*r8[i]. Pointers advance (r8, r9, r11 += n; dot: r8, r9 += n+1), r10 = 0 |

Flags (r15) after float and integer ALU results: bit30 negative, bit29 zero (bit31 too for negative integers);
immediate ops do not change them. Example from the stock drives: `fsub r5,r2,r3 ; skipbc r15,30,+1 ; mov r3,r2` = min.

Not decoded (CAB / clone only): class 9 S 6, F S C (`f10c00e3`), D class. Cost per instruction not yet measured.
