# E1: Pocket Master "engine" instruction format (35 stock programs, `re/cfw/engine_progs.txt`)

Scripts (this folder): `load.py` (loader + program names), `dis.py` (hypothesis disassembler, `python3 dis.py <prog#>`),
`subs.py` (subroutine census), `trace.py` (per-program control-flow skeleton).
Not done: Smart Box / community programs (`re/cfw/src/...`) were not parsed; no device access. Everything below is from
`engine_progs.txt` (35 lines; I confirmed 35 programs, lengths 341 286 357 302 547 215 206 459 | 375 ... 138 | 467 | 93 93 93 | 840),
plus `amp0.dis`, `cab.dis`, `kernel_stock.dis`. Labels: **[C]** confirmed by statistics/cross-check, **[H]** hypothesis, **[U]** unknown.

## 1. Headline conclusions
1. Every word is `[op:8][b1:8][imm:16]`; `op = class<<4 | R` (R = a register number 0..13, r14 seen) and for reg-reg classes
   `b1 = A<<4 | S` (A = 2nd register, S = sub-op), `imm[3:0]` = 3rd register. **[C]** (imm==0 for 100% of class 2/e and 91% of f; class 8
   imm always <=0xd; class 5/7/a use imm as 16-bit address/constant.) 13274 words total; only ~600 words (c-5, fe, 9x, rare c/7 variants) are not understood.
2. There are **two address spaces** (Harvard). Data words: 0x000..0xFFF (ARM 0x28000000-0x28003FFF, ld/st/mov addresses never exceed 0xFD0).
   Code words: branch/call targets are `(ARM_off/4) - 0x1000`, i.e. **12-bit, relative to the code RAM at 0x28004000**:
   DRV slot=0x000, AMP/CLONE slot=0x500, CAB=0xB00, EQ=0xE00. Check: all 565 jmp/call/djnz targets across 35 programs land inside the program at
   `target - slot_base` (only misses are 6 `a00e0000` = halt, not a jump). **[C]**
3. Execution is a **chain with fixed slot entry addresses**: DRV end `a0080500` (jmp AMP base), AMP end `a0080b00` (jmp CAB), CAB end -> `0xE00` (EQ),
   EQ ends with `a00e0000` (halt). CLONE sits at 0x500 and jumps to 0xE00 (occupies AMP+CAB slots; state 9 KB = 0x900 words ends exactly at 0xE00). **[C]**
4. Every program starts with a **bypass test**: `ld r6,[flagaddr]; 96080001; a008<target>` ; target = the word that holds the "jmp next slot". **[C]** (structure) / **[H]** (the flag is the bypass/enable).
5. The engine is **mono-in-place float32**: DSP runs on the L buffer at word 0x13 (64 words) with in-place subroutines; the EQ (last) copies 0x13->0x93 and 0x13->0xD3
   (`20000000` copies) so both outputs get the same signal. R input 0x53 is touched only by BassDrive, A BassVT, Voks Bass, CLONE. **[C]** counts below. 
   ARM side passes float32: `kernel_stock.dis:16040-16110` multiplies interleaved L/R pairs with `vmul.f32` before calling run routine 0x1029A with r2=64 frames. **[C]**
6. I decoded the full biquad subroutine (30+25+... uses) and an `exp()` approximation by repeated squaring - these give high-confidence semantics for ld/st, fmul/fmac, add/sub, mov, djnz, call/ret (see 3).

## 2. Instruction table (op byte -> meaning)  [counts over all 35 programs]
Notation: rR = register in op low nibble; rA = b1 high nibble; S = b1 low nibble; rB = imm[3:0]; `N` = imm16.

| class (op) | b1 / S | imm | Mnemonic (my name) | status | evidence |
|---|---|---|---|---|---|
| 0x5R (3551) | b1=00 | N=data addr | `st [N], rR` | C | stores of r2..r9 at 0x1ac.. at entry, loads (b1=08) of same addrs at exit; |
| 0x5R | b1=08 | N | `ld rR, [N]` | C | `5a080113` param loads; biquad state spill/reload pairs |
| 0x7R b1=06 (1940) | | N | `mov rR, #N` (16-bit int; addresses, counts 0x40=64, 0x13, 0x113) | C | N distribution: 0x13 x577, 0x40 x405 (block len 64), 0x113, 0x153 |
| 0x7R b1=C6 (423) then 0x7R b1=86 (408), always adjacent, hi first | | hi16 / lo16 | `movhi rR,#h16` + `movlo rR,#l16` = float32 literal `h16:l16` | C | 404 adjacent pairs; values are sane floats (0x3f800000=1.0, 0x3eaaaaab=1/3, 0x396dc66d=2.26e-4) |
| 0x7R b1=C8 (198) | | 0x7FFF / 0x8000 only | `movhi.q rR,#0x7fff/#0x8000` -> 0x7fff0000 / 0x80000000 (looks like +/-1.0 in Q31 or clamp limits) | H | only those 2 imm values; always used in pairs (+lim,-lim) |
| 0x7R b1=00 (250) | | small N (1,4,6,8,0xb,14) | `add rR,#N` (pointer/index bump: `71000001` skip the "1.0" word; `7d000006` r13+=6 to reach state words) | C | used exactly as +record offset in biquad subs |
| 0x7R b1=02/04/CA/CC | rare (<30) | | variants of add/movhi.q | U | |
| 0xE R (2318, imm=0) | S=2 | b1 hi=rA | `ld rR,[rA]` | C | biquad sub |
| | S=3 | | `ld rR,[rA]++` (post-inc) | C | `e2130000 e3130000` stream coefficients from r1 |
| | S=4 | | `st [rR], rA` | C | `e6140000` ramp store |
| | S=5 | | `st [rR]++, rA` (**base is the op nibble, data is b1 hi**) | C | `e0b50000` = store y to [r0]++; `ed750000` state write back via r13 |
| 0x8R (1280) | S=6 | imm[3:0]=rB | `fmul rR = rA * rB` | C | biquad `8b26000b` b0*x; operands consistent in all 30+ biquad subs |
| | S=A | | `fmac rR += rA * rB` | C | `873a000b` rb += b1*x1, etc. |
| | S=0 (9 words) | | unknown | U | |
| 0xCR (711) | S=E (251) | rB | `fadd rR = rB + rA` | C | `c12e0001` ramp r1 += r2 ; `c67e0008` |
| | S=F (305) | rB | `fsub rR = rB - rA` | C | `cb8f000b` = y - a1*y1 |
| | S=5 (94), imm always 0x78xx | | **special**, e.g. `c5657805`; follows `fe` | U (div/rcp/sat?) | |
| | S=0,2,4 (~60) | | unknown | U | |
| 0xFR (730) | S=4 | imm=0 (b1 hi=rA) | `mov rR, rA` | C | delay-line shifts `f874 fa94 f9b4` |
| | S=E (65) imm=3/4/5 (==R) | | `fe rR,#N` unary op, always followed by fmul-self and `c-5` | U (float<->fixed? sqrt? saturate?) | |
| | b1=D4 imm 0x4000 (18) etc. | | variant of mov | U |
| 0xAR b1=04 (292) | R=counter reg | N=code addr | `djnz rR, N` (decrement, jump if !=0). Loops use r1 (a1), r4 (a4, count 64), r7, r10 (aa, 40), r12, r13, r14 (ae) | C | `74060040 ... a404051c` loops back to target (verified for 565 targets) |
| 0xAE b1=06 (283) | | 0x4xxx / 0x6xxx (low 12 bits = code addr) | `call N` | C | call target = first word after a `ret` |
| 0xAE b1=0A (139) | | 0x4000 / 0x6000 | `ret` | C | 32 `0x6xxx` calls are paired with 32 `0x6000` rets; bit13 meaning U (likely "context/wide" variant) |
| 0xA0 b1=08 | | N | `jmp N` (stage chaining 0x500/0xB00/0xE00, bypass jumps) | C |
| 0xA0 b1=0E (6 words, EQ only) | | 0 | `halt` (end of chain) | H |
| 0x20 b1=00/03/07/08/0D (199) | | 0 | block (vector) op over 64 samples, regs r8..r11 set by preceding movs: S=8 `r11[i]=r9[i]*r8(float)`; S=7 `r11[i]=r9[i]*mem[r8+i]` (vector*vector, r8=0x113 ramp); S=0 copy r9->r11 (len r10); S=D copy r9->r8 (len r10, TWD copies 40-word table 0x41a); S=3 unknown | C (7/8), H (0/D), U (3) | preceding setup `79060013 7a060040 7b060013` = src 0x13, n=64, dst 0x13 |
| 0x9R (111) | b1=08 imm=1 (33x at program start) | | `test rR` (bypass flag) before `a008` | H |
| | b1=0A imm=0x3c01/0x3e15 (45) | | op follows an `exp` / saturation compute | U |
| 0x3x/0xBx words (252) | | | raw float32 table data (only in CAB and CLONE: 128 words each, starts 0x00000000 0x3d48fb30 ...; CAB @0xb6, CLONE @0x195) | C |
| 0x00000000 (2) | | | pad / table word | C |

Notes: r13/r14 hold pointers/counters; r0,r1 = in/out pointer & record pointer; r2..r11 = work registers. 14-16 registers. `r14` may also be implicit return state [U].

### Evidence that b1/imm are as stated (key statistics)
* Class 0x2 (block ops): imm==0 in 199/199, b1 only in {0,3,7,8,0xd}.
* Class 0xE: imm==0 in 2318/2318, b1 low nibble only 2,3,4,5 (+ 6/7 once or twice).
* Class 0x8: b1 low nibble only 6 (980), 0xA (291), 0 (9); imm in 0x2..0xD (a register).
* Class 0xC: b1 low nibble 0xE (251) / 0xF (305) / 5 (94); imm<=0xD except `78xx` for S=5.
* Class 0xF: b1 low nibble 4 (663) / 0xE (65); imm==0 in 635/730.
* Class 0x5: b1 only 0x00/0x08; imm = data address < 0x1000.

## 3. Decoded building blocks
### 3.1 Biquad subroutine (30+ uses) **[C]**
`TWD 0x631 (idx 0x131)`: `fd140000 (r13=r1) e2..e4 (ld b0,b1,b2 ++) 71000001 (skip "1.0") e5..e9,ea (ld a1,a2,x1,x2,y1,y2) 71060040 (n=64)` then per sample:
`eb02 ld x`, `8b26000b fmul`, `873a000b fmac`, `884a000b fmac`, `89560008 fmul(a1*y1)`, `cb8f000b fsub`, `8a660008 fmul(a2*y2)`, `cb8f000b fsub`,
state shift `f874 e702 fa94 f9b4`, `e0b5 st y,[r0]++`, `a104063d djnz r1`; epilogue `7d000006 (r13+=6) ed75 ed85 ed95 eda4` write back 4 states, `ae0a4000 ret`.
=> y = b0 x + b1 x1 + b2 x2 - a1 y1 - a2 y2 (direct form 1), 10-word record {b0,b1,b2,1.0,a1,a2,x1,x2,y1,y2}; in place on [r0] (r0 ends = 0x13+64).
ARM matches: `amp0.dis:0x100038ce..0x10003a1c` writes records exactly so (stmia {b0,b1,b2,1.0} at +4, strd {a1,a2} at +20; next record +0x2c; floats like a1=-1.08, a2=0.083 are typical).
Variants (by `subs.py`): 32-word (30 uses), **38-word** (25; reads word[3] as an extra gain via `fe/c-5` instead of skipping the 1.0 - e.g. ARM tone stack writes a non-1.0 value to slot 3), 21-/28-word (fewer coeffs; TDF2-style `ld r8 ; fmul/fmac/fmac ; mov chain`), 63-word 2-section (DarkMouse etc.).
### 3.2 Nonlinearity subroutine **[H]** (139-173 words, one per amp preamp stage; absent in Jazz 120, A BassVT, Voks Bass, CAB, EQ)
Starts `56xxxxxx 57xxxxxx 7ac63eaa 7a86aaab (1/3) c76f0007 87a60007 ...`. Builds 4 points spaced by (r7-r6)/3 (cubic/Lagrange-like interpolation in a small table), then evaluates
`exp(x)` as `(1 + x/1024)^1024` : `89460009 (x*r4) c93e0009 (+1)` then **10x `89960009` (square)**, `c9b57809` (division/other `c-5`), clamp constants `7cc6c4ff 7c86e000` (=-2047) and `9f0a3c01`. So the waveshaper is **computed per sample with exp(), not a lookup table**; it is called in a 64-iteration loop (`a4040xxx`, 7-word body). TWD example: sub at 0x5a1, call `ae0665a1`.
### 3.3 Gain smoothing ramp **[H]**
`72c6396d 7286c66d c01f0003 82360002 74060040 75060113 76060443 c12e0001 e6140000 e5150000 a404051c` : build 64-sample ramp at 0x113.. (r1 += r2 per step, store last value to [0x443], ramp into scratch buffer 0x113), then `20070000` multiplies signal by that ramp (vector*vector). 0x443/0x445 are written by ARM (`amp0.dis:100038d4.. str r0,[r5,#0x2ac]` -> word 0x398+171=0x443 and `#0x2b4` -> 0x445). **[C]** for the address match.
### 3.4 Delay/shift structures
TWD `50000415 50080419 50000414 50080418 ...` (80 instructions, `aa0405bd` = djnz r10, r10=40 set by `7a060028`): 40-word table shuffle using ld/st pairs, seeded by `200d0000` (copy 40 words from 0x41a = ARM table at 0x28001068 to 0x3f2). **[C]** address match, **[H]** purpose (40-tap = 160 B table is a FIR/shaper curve).
No hardware-looking FIR/delay instruction exists: CAB (467 words) and CLONE use plain `ld/mac` loops with pointers to 0x580.. (CAB) / 0x398.. (CLONE) offset by 0x208 words (0x78b, 0x993, 0xb9b, 0xda3 for CAB; 0x5a3, 0x7ab, 0x9b3 for CLONE): partitioned 512-tap convolution blocks (0x208 = 520 = 512+8). **[H]**

## 4. Data-RAM address map inferred from the programs  (word index; ARM addr = 0x28000000 + 4*w  **[C]** for 0x398->0x28000E60 etc.)
| word range | meaning | evidence |
|---|---|---|
| 0x10 | read at DRV entry (`50080010`), purpose unknown | U |
| 0x13..0x52 | L in, also in-place working buffer through the entire chain | `70060013` ~15-27x/program |
| 0x53..0x92 | R in | `0x53` only in BassDrive, A BassVT, Voks Bass, CLONE |
| 0x93..0xD2 / 0xD3..0x112 | L / R out | only EQ1-3 (`7b060093`, `7b0600d3`, `20000000` copies) |
| 0x113..0x152, 0x153..0x192 | scratch buffers (ramp, 2nd path, parallel branch); first words also used as scalar temps in DRV | `70060113`, `20070000`, `74060153` |
| 0x193.. (DRV) | DRV bypass flag word 0x193, biquad records from 0x194 (10 words each: 0x194,0x19a(?),0x1a4,...), saved regs 0x1a5.. | RedFuzz: `75060193 e6520000`, `71060194 ae064099` |
| 0x398 (0x28000E60) | AMP flag word (ARM writes 0 at start: `str r6,[r5]`); AMP records at 0x399, 0x3a3, 0x3ad(tone stack, ARM func @0xEB4=word 0x3AD), 0x3b7, 0x3c5, 0x3cf | `amp0.dis` 0x100038c4-3a1c vs TWD movs `71060399/3a3/3ad/3b7/3c5/3cf` |
| 0x3d9..0x419 | AMP working state/delay line | TWD ld/st |
| 0x41a..0x441 (0x28001068) | ARM 160-byte table (40 words) | `amp0.dis:100039f8..3a2a` copy; TWD `7906041a`,`7a060028`,`200d0000` |
| 0x442..0x445 | ARM-written smoothing targets (0x443, 0x445) | `str.w r0,[r5,#684]`/`#692` |
| 0x580..0xF7E | CAB: flag/params at 0x580..0x583 (ARM sets [0x581]=8, memset 0x27F8 bytes from 0x581), tap blocks at +0x20b stride, `0xF7D/F7E` level; | `cab.dis:64c4-6818`, CAB ldst max 0xF7E |
| 0xF9C..0xFD0 | EQ: flag 0xF9C, 5 biquad records (0xF9D,0xFA7,0xFB1,0xFBB,0xFC5), smoothing state 0xFCF/0xFD0 | EQ1 `75060f9c`, `71060f9d` etc. |
Slots (code, ARM): DRV 0x28004000+5KB, AMP 0x28005400+6KB, CAB 0x28006C00+3KB, EQ 0x28007800+2KB (as in the brief) = code addr 0/0x500/0xB00/0xE00. **[C]**
Note: the data RAM is only 0x1000 words; code RAM is the upper half. The state area ("state_size") covers code AND workspace words beyond the program (CLONE refs 0xD80-0xDC6 are > 0x500+840), so programs have uninitialised work RAM after the code.

## 5. Program structure
Prologue (DRV): `70060000 50080010 75060193 e6520000 96080001 a008<bypass>`; AMP: `75060398 e6520000 96080001 a008<bypass>` (jazz/bass amps differ: `500003af 510003b0 90140004 ...`).
Epilogue: `... 20080000/20070000 ; a0080500 ; a0080500` (the second `jmp` is the bypass landing pad; AMP: `a0080b00 x2`). Subroutines are located after the main path (`ret = ae0a4000/6000`), the nonlinearity sub and biquads are shared code *copies* per program (not shared across slots).
Block loop: counts via `7a060040` / `74060040` / `71060040` (=64) and `djnz`; no hardware loop op besides djnz and the 0x20 vector ops.
Skeleton table (`trace.py`): e.g. TWD = `jmp(bypass) , vs(input gain) , 3 biquad calls, ramp loop, vv (smooth gain), biquad ..., CALL(nonlinear) in 64-loop, ... vs vv vs, jmp 0xB00`. Sequence of calls shows amp = [input filters] -> [per-sample nonlinearity loop (1 or 2 stages)] -> [tone/EQ biquads (5-9)] -> [output gain].
Drive diff (GreyFuzz vs RedFuzz, `difflib`, ratio 0.80): identical code skeleton; differences are only (a) state-slot addresses (0x1a6.. vs 0x1ac..) (b) float literals (400.0 vs 50.0 input gain) (c) one extra biquad call in RedFuzz (inserted at 0x21) (d) branch target shifts. => **programs are generated from the same template; state addresses are packed sequentially (0x1ab..0x1b3 reg-save, then 0x1b4..)**. **[C]**
All 22 amps share the identical prologue/epilogue and the 3 biquad subs; the nonlinearity sub differs only in size (131-173 words), i.e. per-model waveshaper variants; Jazz 120 / A BassVT / Voks Bass have none (consistent with clean amps). **[C]**

## 6. Answers to your explicit hypotheses
* `0x75060398 ... 0xA00805A0` (TWD): `mov r5,#0x398` = **data word 0x398 = 0x28000E60** (ARM flag/header word written 0 at `amp0.dis:100038d2`). **[C]** `a00805a0` = jump to code 0x5A0 = the second copy of `a0080b00` (bypass landing -> CAB). **[C]**
* Red Fuzz `0x75060193 / 0xA0080098`: r5=0x193 data flag word; `a0080098` = jump to code address 0x98 = `a0080500` (landing pad before AMP). **[C]**
* Records at 0x28000E60: layout confirmed {flag word at 0x398}, then 10-word records `{b0,b1,b2,1.0,a1,a2,x1,x2,y1,y2}` starting at 0x399 (0x28000E64), record stride 10 words (=0x28 bytes) - **[C]** from ARM stmia/strd offsets and from engine's biquad sub. Exception: record 3 at 0x3AD (=0x28000EB4) is written by the tone-stack function with word[3] = a non-1.0 value consumed by the 38-word variant. **[C]**
* 160 B table at 0x28001068 = word 0x41A: **[C]** referenced (`7906041a`, copy 40 words).
* 0x28001600 = word 0x580 (CAB): **[C]** (`75060580 e6520000` CAB prologue).
* I/O words 0x13/0x53/0x93/0xD3: confirmed as float32 mono-chain buffers; R is hardly used. **[C]** (float: ARM `vmul.f32` on the buffer before `bl 0x1029a`)
* Engine run routine `kernel_stock.dis:17331 (0x1029A)`: r4=0x28008000; waits until `[r4+0x40]&2==0`, copies r2 frames: L to 0x13+i, R to 0x53+i (word stores), pulses `[r4]=0;=1`, polls `[r4]!=0`, sets `[r4+0x40]|=1`, reads outputs 0x93+i,0xD3+i (cycle count at `[r4+0x48]` stored to a stats struct). **[C]** (read of the code). Entry PC is not set by ARM here -> engine starts at code 0 (DRV slot) and chains by `jmp`. **[H]**

## 7. Risks / unknowns
* Exact semantics of: `c-5` (imm 0x78xx), `fe`, `9x` ops, `7R c8`, `20 03`, `ae` bit13, `a0 0e`, `a2..a8`, the `ae04` (djnz r14) vs call/ret register use, `83xx` S=0 forms. Treat any emulator as incomplete until these are tested.
* Whether fixed-point (Q31) values coexist with float32 (the `0x7fff0000/0x80000000` constants and `fe`).
* `ae0a4000` vs `6000` difference unknown; engine hardware behaviour of r13/r14/stack, call depth, and whether `djnz` tests before/after decrement.
* The 16 Smart Box programs in `re/cfw/src/...` were not examined (task-scoped to stock 35); because the format is template-generated they should follow the same skeleton - **unverified**.
* Which ARM-side address the ARM writes for DRV (0x193...) was not checked (DRV ARM code not in the supplied dis); only AMP/CAB were cross-checked.
* Time/cycle model of ops unknown (needed for CPU budget in custom programs).

## Confidence: medium-high for format fields, control flow, address spaces, biquad; medium for the nonlinearity (exp via squaring) ; low for c-5/fe/9x ops.
Why: statistics are unambiguous for field layout; semantic cross-validation against ARM code (record layout, 0x443/0x445, 0x41A, 0x580, 0xF9C, 0x398) matches exactly; the remaining ops have too few contexts.
