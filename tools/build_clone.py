#!/usr/bin/env python3
"""Own clone engine: replace the stock CLONE module (group 9) with our multi-stage amp engine that reads its
settings from the clone slot ("PMAM" files). Base: a build dir with our shared amp code (amp_core) in place.
  build_clone.py <base build dir> <out name> [--check <file.clo>]
--check: run the new module offline (ARM code in Unicorn + engine program in engine_emu) against the C model."""
import os, shutil, struct, subprocess, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import amps2, build_amps2 as B
from build_cut import groups
DSP = os.path.join(RE, "dsp"); EQ_PROG = 0xE00
NEXT = int(os.environ.get("CLONE_NEXT", "0xE00"), 0)          # where the clone program continues: EQ (0xE00) or CAB (0xB00)


def build_stub():
    B.docker("arm-none-eabi-gcc $F -c clone_stub.c -o /tmp/cs.o; arm-none-eabi-gcc $F -T link-clonestub.ld -Wl,--gc-sections -nostartfiles "
             "/tmp/cs.o -o clone_stub.elf; arm-none-eabi-objcopy -O binary clone_stub.elf clone_stub.bin; arm-none-eabi-nm clone_stub.elf > clone_stub.sym")
    stub = bytearray(open(os.path.join(DSP, "clone_stub.bin"), "rb").read()); stub += b"\0" * ((-len(stub)) % 4)
    return stub, B.syms("clone_stub.sym")


def program():
    if os.environ.get("CLONE_LAYOUT") == "stock":                # keep the stock clone's jump words in place
        S0, O0, E0 = amps2.START, amps2.ORG, amps2.END; AT = 2128
        amps2.START = amps2.ORG = AT; amps2.END = 1684
        try: prog, _ = amps2.assemble_amp(3, 2)
        finally: amps2.START, amps2.ORG, amps2.END = S0, O0, E0
        img = np.zeros(AT - 1280 + len(prog), "<u4"); img[0] = 0xA0080000 | AT     # 1280: jmp to our code
        img[1305 - 1280] = 0xA0080E00; img[1684 - 1280] = 0xA0080E00                   # as in the stock program
        img[AT - 1280:] = prog; assert AT + len(prog) <= 2816
        return img.tobytes()
    end0 = amps2.END; amps2.END = NEXT
    try: prog, _ = amps2.assemble_amp(3, 2)
    finally: amps2.END = end0
    return np.array(prog, "<u4").tobytes()


def build_v2(m, g):
    """amp core linked for 0x10003C00 inside the image; cab code + cab engine program copied at run time."""
    B.docker("arm-none-eabi-gcc $F -c pmfx.c -o /tmp/p.o; arm-none-eabi-gcc $F -c amp.c -o /tmp/a.o; arm-none-eabi-gcc $F -c amp_core.c -o /tmp/c.o; "
             "arm-none-eabi-gcc $F -T link-ampcore-clone.ld -Wl,--gc-sections -nostartfiles /tmp/p.o /tmp/a.o /tmp/c.o -o ampcc.elf -lgcc; "
             "arm-none-eabi-objcopy -O binary ampcc.elf ampcc.bin; arm-none-eabi-nm ampcc.elf > ampcc.sym")
    core = open(os.path.join(DSP, "ampcc.bin"), "rb").read(); core += b"\0" * ((-len(core)) % 4); cs_ = B.syms("ampcc.sym")
    stub, ss = build_stub(); stub = bytearray(stub[:ss["_end_stub"] - 0x10003800]); assert len(stub) <= 0x400
    wc = np.frombuffer(core, "<u4"); ko = g[4][0]; khs, kcs, kts, kst = struct.unpack_from("<4I", m, ko)
    kc = m[ko + khs:ko + kts]; kc += b"\0" * ((-len(kc)) % 4); wk = np.frombuffer(kc, "<u4"); wp = np.frombuffer(m, "<u4", kst // 4, ko + kts)
    from build_cut import IMG_BASE
    struct.pack_into("<8I", stub, ss["STAB"] - 0x10003800, 0x42415453, 0x10003C00, 0x10003C00, len(wc), int(wc[0]), int(wc[-1]), cs_["core_e0"] | 1, cs_["core_e1"] | 1)
    struct.pack_into("<8I", stub, ss["CTAB"] - 0x10003800, 0x42415443, IMG_BASE + ko + khs, 0x10006400, len(wk), int(wk[0]), int(wk[-1]), 0, 0)
    struct.pack_into("<8I", stub, ss["PTAB"] - 0x10003800, 0x42415450, IMG_BASE + ko + kts, 0x28006C00, len(wp), int(wp[0]), int(wp[-1]), 0, 0)
    return bytes(stub) + bytes(0x400 - len(stub)) + core, ss


def add_cab_knob(src):
    """Clone DB record: 6th knob "Cab" (param 5): 0 = the capture's own cab, k = kernel cab index k - 1."""
    from build_bisect import zero_run
    dp = os.path.join(src, "4_effect_db_presets_00190000.bin"); d = bytearray(open(dp, "rb").read()); gd = groups(d, 0x10000)
    o = 0x10000 + gd[9][0]; rec = bytes(d[o:o + 260]); assert rec[8] == 5 and rec[136:141] == b"Empty"
    strs = rec[136:136 + rec[136:].index(b"Treble\0") + 7]; pre = bytearray(rec[:16]); pre[8] = 6
    k5 = bytearray(rec[16 + 4 * 24:40 + 4 * 24]); struct.pack_into("<H", k5, 2, len(strs)); struct.pack_into("<f", k5, 8, 26.0)
    struct.pack_into("<f", k5, 16, 0.0); k5[20] = 5
    new = bytes(pre) + rec[16:136] + bytes(k5) + strs + b"Cab\0"
    z = zero_run(d, 0x10000, len(new) + 64, 0x20000); at = (z + 16) & ~3; d[at:at + len(new)] = new
    gp = struct.unpack_from("<I", d, 0x10000 + 0x14 + 4 * 9)[0]; struct.pack_into("<I", d, 0x10000 + gp + 4, at - 0x10000)
    open(dp, "wb").write(d); print(f"clone DB record with a 6th knob 'Cab' at {at - 0x10000}")


def build(base, name):
    out = os.path.join(RE, "build", name); src = os.path.join(out, "src"); shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(os.path.join(base, "src"), src); mp = os.path.join(src, "1_dsp_modules_00240000.bin"); m = bytearray(open(mp, "rb").read())
    g = groups(m, 0); ao = g[3][0]; ahs = struct.unpack_from("<I", m, ao)[0]; _, _, _, ass = B.build_code()
    stab = struct.unpack_from("<8I", m, ao + ahs + ass["STAB"] - 0x10003800); assert stab[0] == 0x42415453, "base has no shared amp code"
    if os.environ.get("CLONE_V2"): stub, ss = build_v2(m, g)
    else: stub, ss = build_stub(); stub = bytearray(stub); struct.pack_into("<8I", stub, ss["STAB"] - 0x10003800, *stab)
    prog = program(); co = g[9][0]; hs, cs, ts, st, e0, e1 = struct.unpack_from("<6I", m, co); old = ts + st
    if os.environ.get("CLONE_CAB") and not os.environ.get("CLONE_V2"):                              # carry the pedal's cab code + engine program
        ko = g[4][0]; khs, kcs, kts, kst = struct.unpack_from("<4I", m, ko)
        code = m[ko + khs:ko + kts]; w = np.frombuffer(code + bytes((-len(code)) % 4), "<u4")   # copied at run time
        struct.pack_into("<8I", stub, ss["CTAB"] - 0x10003800, 0x42415443, 0x13000 + ko + khs, 0x10006400, len(w), int(w[0]), int(w[-1]), 0, 0)
        prog = prog + bytes((2816 - 1280) * 4 - len(prog)) + m[ko + kts:ko + kts + kst]    # cab program at 2816
    hdr = bytearray(m[co:co + hs]); struct.pack_into("<6I", hdr, 0, hs, len(stub), hs + len(stub), len(prog), ss["st_entry0"] | 1, ss["st_entry1"] | 1)
    if not os.environ.get("CLONE_V2"): stub = stub[:ss["_end_stub"] - 0x10003800] if "_end_stub" in ss else stub
    struct.pack_into("<I", hdr, 4, len(stub)); struct.pack_into("<I", hdr, 8, hs + len(stub))
    blob = bytes(hdr) + bytes(stub) + prog
    if len(blob) <= old: m[co:co + old] = blob + bytes(old - len(blob))
    else:                                                        # bigger than the stock clone: move to free space
        free = sorted(tuple(x) for x in json.load(open(os.path.join(base, "free_after.json"))))
        fo = next(o for o, ln in free if ln >= len(blob)); m[fo:fo + len(blob)] = blob
        gp = struct.unpack_from("<I", m, 0x14 + 4 * 9)[0]; struct.pack_into("<I", m, gp + 4, fo)
    open(mp, "wb").write(m)
    if os.environ.get("CLONE_V2"): add_cab_knob(src)
    binf = os.path.join(out, f"PocketMaster_CFW1.0.2+{name}.bin")
    subprocess.run([sys.executable, os.path.join(RE, "pmfw.py"), "pack", src, binf], check=True, stdout=subprocess.DEVNULL)
    print(f"clone module: stub {len(stub)} B, engine program {len(prog) // 4} words (code 1280..{1280 + len(prog) // 4}), "
          f"{len(blob)} of {old} B; built {os.path.relpath(binf, RE)}")
    return src


def check(src, clo):
    os.environ["AMP_SRC"] = src
    import importlib, amp_sim as S, engine_emu as E, pmclone as P, ampmodel as AM
    importlib.reload(S)
    raw = open(clo, "rb").read(); s = P.parse_pmam(raw)["settings"]
    a = S.Amp(0, grp=9); X = 0x29080000; a.mu.mem_write(X, raw)
    kn = [50.0, 50.0, 50.0, 50.0, 50.0, 0, 0, 0]                    # Gain VOL Bass Middle Treble
    a.mu.mem_write(S.PRM, struct.pack("<8f", *kn)); a.mu.mem_write(S.PRM + 64, struct.pack("<I", X)); a.call(a.e0, [S.PRM, S.PRM + 64])
    eng = E.Engine(); x = (0.2 * np.random.default_rng(3).standard_normal(64 * 12)).astype("<f4"); y = np.zeros_like(x); u = []
    for i in range(0, len(x), 64):
        a.call(a.e1, [S.BUF, 64, S.PRM, 0, S.EN, 0, 0])
        eng.d[:] = np.frombuffer(a.mu.mem_read(0x28000000, 0x4000), "<u4"); eng.code[:] = np.frombuffer(a.mu.mem_read(0x28004000, 0x4000), "<u4")
        eng.code[EQ_PROG] = 0xA00E0000; eng.d[0x13:0x53] = x[i:i + 64].view(np.uint32); eng.steps = 0; eng.units = 0
        eng.run(S.AMP_PROG, limit=5_000_000); y[i:i + 64] = eng.d[0x13:0x53].view(np.float32); u.append(eng.units)
        a.mu.mem_write(0x28000000, eng.d.astype("<u4").tobytes())
    ref = AM.run(s, [50, 50, 50, 50, 50, 50, 0], x).astype(np.float32)          # amp knobs: gain bass mid treble pres vol
    err = float(np.max(np.abs(y - ref)) / (np.max(np.abs(ref)) + 1e-12))
    print(f"check {os.path.basename(clo)}: new clone module vs C model rel err {err:.1e}, {int(np.mean(u))} engine units per block, unmapped {a.bad[:2]}")
    # a stock clone in the slot must give a clean pass-through
    a2 = S.Amp(0, grp=9); a2.mu.mem_write(X, open(os.path.join(RE, "cloFile.clo"), "rb").read()[:2696])
    a2.mu.mem_write(S.PRM, struct.pack("<8f", *kn)); a2.mu.mem_write(S.PRM + 64, struct.pack("<I", X)); a2.call(a2.e0, [S.PRM, S.PRM + 64])
    a2.call(a2.e1, [S.BUF, 64, S.PRM, 0, S.EN, 0, 0]); flag = struct.unpack("<I", a2.mu.mem_read(0x28000000 + 4 * 920, 4))[0]
    print(f"check stock clone in the slot: engine flag {flag} (0 = pass-through)")


if __name__ == "__main__":
    a = sys.argv[1:]; src = build(a[0], a[1])
    if "--check" in a: check(src, a[a.index("--check") + 1])
