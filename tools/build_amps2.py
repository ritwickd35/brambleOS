#!/usr/bin/env python3
"""All our amps with one shared copy of the amp code.
  build_amps2.py <base build dir> <out name> <slot>=<fit json> ... [--drop <slot,slot,...>]
Shared code (dsp/amp_core.c) goes raw into Bog XT's blob space (Bog XT is always dropped from the lists). Each
replaced amp gets a new blob (header + stub + its engine program) placed best-fit into module-image space that only
replaced or dropped stock amps used (logs/amp_reads.json, logs/amp_free_runs.json). Stock knob names map the knobs."""
import os, shutil, struct, subprocess, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import amps2, amp_capture as AC, ampmodel as AM
from build_cut import groups
from build_drives import drop_entry
DSP = os.path.join(RE, "dsp"); BOG = 19
REPOINT = {"Bog XT": "Flyman B1+", "Sol 100 OD": "Sol 100 LD", "Eng Power": "Halen 51", "Dizzy VH": "Dizzy VH+",
           "B-Man N": "B-Man B", "Brit 50JP": "Brit 50", "Eng 120": "Dizzy VH+", "Calif DualV": "Calif DualM",
           "Voks Bass": "A BassVT", "Calif Bass": "A BassVT", "Calif Star CL": "Dark Twin", "Superb CL": "Dark Twin",
           "Bog SV CL": "Dark Twin", "Doctor CL": "TWD Deluxe", "Supero 2 OD": "Brit 45", "Superb OD": "Brit 800",
           "Doctor OD": "Brit 45", "Flyman B1": "Flyman B1+", "Brit 900": "Brit 800", "Calif IV LD": "Calif IIC+",
           "Bog XT M": "Flyman B1+", "Tanger R100": "Calif DualM"}
LINEUP = {"tweed": 0, "twin": 2, "ac30n": 3, "jc120": 4, "jtm45": 5, "jcm800": 7, "bassman": 8, "ac30tb": 9, "5150": 13,
          "slo100": 14, "recto": 16, "friedman": 18, "svt": 20, "plexi": 26, "iicplus": 28, "vh4": 33}
DROP = [i for i in range(38) if i not in LINEUP.values()]
OURS = ["Gain", "Bass", "Middle", "Treble", "PRES", "VOL", "Bright"]; ALIAS = {"Tone": "Treble", "Presence": "PRES"}
FLAGS = ("-mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16 -Os -ffreestanding -nostdlib -fno-builtin "
         "-ffunction-sections -fdata-sections -fsingle-precision-constant -Wall -Wno-unused-function -Wno-unused-variable")


def docker(sh):
    subprocess.run(["sh", "-c", "sync; sleep 2"], check=True)
    subprocess.run(["docker", "run", "--rm", "-v", f"{DSP}:/w", "-w", "/w", "pmarm", "sh", "-c", f'set -e; F="{FLAGS}"; ' + sh], check=True)


def syms(f): return {l.split()[2]: int(l.split()[0], 16) for l in open(os.path.join(DSP, f)) if len(l.split()) == 3}


def build_code():
    amps2.export(os.path.join(RE, "amps", "jcm800.fit.json"), [0] * 7)          # engine addresses only
    docker("arm-none-eabi-gcc $F -c pmfx.c -o /tmp/p.o; arm-none-eabi-gcc $F -c amp.c -o /tmp/a.o; arm-none-eabi-gcc $F -c amp_core.c -o /tmp/c.o; "
           "arm-none-eabi-gcc $F -T link-ampcore.ld -Wl,--gc-sections -nostartfiles /tmp/p.o /tmp/a.o /tmp/c.o -o amp_core.elf -lgcc; "
           "arm-none-eabi-objcopy -O binary amp_core.elf amp_core.bin; arm-none-eabi-nm amp_core.elf > amp_core.sym; "
           "arm-none-eabi-gcc $F -c amp_stub.c -o /tmp/s.o; arm-none-eabi-gcc $F -T link-ampstub.ld -Wl,--gc-sections -nostartfiles /tmp/s.o -o amp_stub.elf; "
           "arm-none-eabi-objcopy -O binary amp_stub.elf amp_stub.bin; arm-none-eabi-nm amp_stub.elf > amp_stub.sym")
    core = open(os.path.join(DSP, "amp_core.bin"), "rb").read(); core += b"\0" * ((-len(core)) % 4)
    stub = bytearray(open(os.path.join(DSP, "amp_stub.bin"), "rb").read()); stub += b"\0" * ((-len(stub)) % 4)
    return core, syms("amp_core.sym"), stub, syms("amp_stub.sym")


CABKNOBS = "--cabknobs" in sys.argv
if CABKNOBS: sys.argv.remove("--cabknobs")


def cab_knobs(m, d, gm, gd, at_off):
    """CAB Low cut / High cut: dsp/cab_wrap.c runs in place from the module image at module offset at_off (spare space
    behind the shared amp code); the stock cab blob only gets new entry addresses. DB record with 3 knobs."""
    addr = 0x13000 + at_off
    open(os.path.join(DSP, "link-cab.ld"), "w").write(
        "ENTRY(cw_entry1)\nSECTIONS {\n  . = 0x%X;\n  .text : { KEEP(*(.text.cw_entry0)) KEEP(*(.text.cw_entry1)) *(.text*) *(.rodata*) }\n"
        "  .data : { *(.data*) *(.bss*) *(COMMON) }\n  _end = .;\n  /DISCARD/ : { *(.ARM.*) *(.comment) }\n}\nASSERT(SIZEOF(.data) == 0, \"no RAM data allowed\");\n" % addr)
    docker("arm-none-eabi-gcc $F -c pmfx.c -o /tmp/p.o; arm-none-eabi-gcc $F -c cab_wrap.c -o /tmp/c.o; arm-none-eabi-gcc $F -T link-cab.ld "
           "-Wl,--gc-sections -nostartfiles /tmp/p.o /tmp/c.o -o cab_wrap.elf -lgcc; arm-none-eabi-objcopy -O binary cab_wrap.elf cab_wrap.bin; "
           "arm-none-eabi-nm cab_wrap.elf > cab_wrap.sym")
    w = open(os.path.join(DSP, "cab_wrap.bin"), "rb").read(); sw = syms("cab_wrap.sym")
    o = gm[4][0]; hs, cs, ts, st = struct.unpack_from("<4I", m, o); assert (hs, cs, st) == (0x24, 0x830, 0x74C), (hs, cs, st)
    assert m[at_off:at_off + len(w)] == bytes(len(w)), "spare space not empty"
    m[at_off:at_off + len(w)] = w; struct.pack_into("<2I", m, o + 0x10, sw["cw_entry0"] | 1, sw["cw_entry1"] | 1)
    blob = w; fo = at_off
    # DB: 3-knob cab record (prefix 16 B, 24 B per knob, strings), VOL / LoCut / HiCut
    r = 0x10000 + gd[4][0]; rec = bytes(d[r:r + 60]); assert rec[8] == 1 and rec[56:60] == b"VOL\0"
    names = rec[40:56] + b"VOL\0LoCut\0HiCut\0"; k0 = bytearray(rec[16:40])
    pre = bytearray(rec[:16]); pre[8] = 3; blocks = b""
    for i, (off, df) in enumerate(((16, 50.0), (20, 0.0), (26, 0.0))):
        k = bytearray(k0); struct.pack_into("<H", k, 2, off); struct.pack_into("<f", k, 16, df); k[20] = i; blocks += bytes(k)
    new = bytes(pre) + blocks + names
    from build_bisect import zero_run
    z = zero_run(d, 0x10000, len(new) + 64, 0x20000); assert z > 0; at = (z + 16) & ~3
    d[at:at + len(new)] = new; dp_ = struct.unpack_from("<I", d, 0x10000 + 0x14 + 4 * 4)[0]; struct.pack_into("<I", d, 0x10000 + dp_ + 4, at - 0x10000)
    return f"cab: Low/High cut wrapper {len(blob)} bytes in place at {fo}; 3-knob DB record at {at - 0x10000}"


def main():
    a = sys.argv[1:]; drop = []
    if "--drop" in a: i = a.index("--drop"); drop = [int(v) for v in a[i + 1].split(",") if v]; a = a[:i] + a[i + 2:]
    if "--lineup" in a:                                            # all 16: fitted settings where done, else the start point
        a.remove("--lineup"); drop = DROP
        for nm, sl in LINEUP.items():
            f = os.path.join(RE, "amps", f"{nm}.fit.json"); a.append(f"{sl}={f if os.path.exists(f) else os.path.join(RE, 'amps', nm + '.json')}")
    base, name, jobs = a[0], a[1], [j.split("=") for j in a[2:]]
    out = os.path.join(RE, "build", name); src = os.path.join(out, "src"); shutil.rmtree(src, ignore_errors=True)
    shutil.copytree(os.path.join(base, "src"), src)
    mp = os.path.join(src, "1_dsp_modules_00240000.bin"); m = bytearray(open(mp, "rb").read())
    dp = os.path.join(src, "4_effect_db_presets_00190000.bin"); d = bytearray(open(dp, "rb").read())
    n0m, n0d = len(m), len(d); gm, gd = groups(m, 0), groups(d, 0x10000); stock = AC.stock_amps()
    ids = [struct.unpack_from("<I", d, 0x10000 + r)[0] for r in gd[3]]; byid = {v[0]: k for k, v in stock.items()}
    core, cs_, stub, ss = build_code()
    global DBREC; import dbrec; DBREC = dbrec.records(dp)
    # free space: Bog XT's blob for the shared code; own blocks of replaced + dropped amps for the per-amp blobs
    ob = gm[3][BOG]; hs, cs, ts, st = struct.unpack_from("<4I", m, ob); bog_own = ts + st; bog_hdr = bytes(m[ob:ob + hs])
    assert len(core) <= bog_own, (len(core), bog_own)
    reads = json.load(open(os.path.join(RE, "logs", "amp_reads.json"))); runs = json.load(open(os.path.join(RE, "logs", "amp_free_runs.json")))
    gone = {int(j[0]) for j in jobs} | set(drop) | {BOG}
    mine = set(b for i in gone for b in reads[str(i)])
    free = []
    for s0, ln in runs:                                            # keep the parts of each free run that belong to gone amps
        cur = None
        for b in range(s0, s0 + ln, 64):
            if b in mine: cur = [b, 64] if cur is None else [cur[0], cur[1] + 64]
            elif cur: free.append(tuple(cur)); cur = None
        if cur: free.append(tuple(cur))
    m[ob:ob + bog_own] = core + b"\0" * (bog_own - len(core))
    src_addr = 0x13000 + ob; cw = np.frombuffer(core, "<u4")
    log = [f"shared amp code: {len(core)} bytes at module offset {ob} (Bog XT's space, {bog_own})"]
    lptr = struct.unpack_from("<I", m, 0x14 + 4 * 3)[0]
    for slot, fit in jobs:
        slot = int(slot); s = json.load(open(fit)); nst = int(s["nst"]); s.setdefault("os", 4.0 if nst == 1 else 2.0)
        kn = stock[byid[ids[slot]]][1]
        pidx = {nm: j for g_, i_, fx_, t_, kl_ in DBREC if g_ == 3 and fx_ == ids[slot] for nm, _, _, j, *_ in kl_}   # real parameter index
        idx = [next((pidx.get(k, i) for i, k in enumerate(kn) if ALIAS.get(k, k) == o), -1) for o in OURS] + [-1]
        if "Tone Cut" in kn:                                       # AC30 cut control: treble (or presence) inverted
            t = 3 if idx[3] < 0 else 4
            if idx[t] < 0: idx[t] = 64 + pidx.get("Tone Cut", kn.index("Tone Cut"))
        prog, _ = amps2.assemble_amp(nst, int(s["os"])); prog = np.array(prog, "<u4").tobytes()
        b = bytearray(stub)
        di = ss["DESC"] - 0x10003800; struct.pack_into(f"<{AM.NAMES.__len__()}f", b, di, *[float(s.get(k, {"os": 4.0, "olp": 19000.0}.get(k, 0.0))) for k in AM.NAMES])
        struct.pack_into("<8b", b, di + 4 * len(AM.NAMES), *idx)
        struct.pack_into("<8I", b, ss["STAB"] - 0x10003800, 0x42415453, src_addr, 0x10003A00, len(cw), int(cw[0]), int(cw[-1]),
                         cs_["core_e0"] | 1, cs_["core_e1"] | 1)
        hdr = bytearray(bog_hdr); struct.pack_into("<6I", hdr, 0, len(hdr), len(b), len(hdr) + len(b), len(prog), ss["st_entry0"] | 1, ss["st_entry1"] | 1)
        blob = bytes(hdr) + bytes(b) + prog
        fit_ = sorted((ln, o) for o, ln in free if ln >= len(blob)); assert fit_, f"amp {slot}: no room for {len(blob)}"
        ln, o = fit_[0]; free.remove((o, ln)); used = (len(blob) + 63) & ~63
        if ln > used: free.append((o + used, ln - used))
        m[o:o + len(blob)] = blob; struct.pack_into("<I", m, lptr + 4 + 4 * slot, o)
        log.append(f"AMP {slot} {byid[ids[slot]]} -> {os.path.basename(fit)} (stages {nst}, {int(s['os'])}x): blob {len(blob)} at {o}, knobs {idx[:7]}")
    if CABKNOBS: log.append(cab_knobs(m, d, gm, gd, (ob + len(core) + 63) & ~63))
    # factory presets using a dropped amp -> its nearest kept amp, knob values carried over by knob name
    gone_ids = {ids[i]: i for i in set(drop) | {BOG}}; rep = []
    for i in range(50):
        o = 0x1000 + 0x400 * i
        if d[o:o + 2] != b"\xa5\x5a": continue
        fx = struct.unpack_from("<I", d, o + 38 + 12)[0]
        if fx not in gone_ids: continue
        src_nm = byid[fx]; dst_nm = REPOINT.get(src_nm); assert dst_nm, f"F{i + 1:02d} uses {src_nm}: no target"
        old = struct.unpack_from("<8f", d, o + 78 + 96)
        oi = {nm: j for g_, i_, fx_, t_, kl_ in DBREC if g_ == 3 and fx_ == fx for nm, _, _, j, *_ in kl_}
        ni = {nm: j for g_, i_, fx_, t_, kl_ in DBREC if g_ == 3 and fx_ == stock[dst_nm][0] for nm, _, _, j, *_ in kl_}
        new = [50.0] * 8
        for nm, j in ni.items(): new[j] = old[oi[nm]] if nm in oi else 50.0
        struct.pack_into("<I", d, o + 38 + 12, stock[dst_nm][0]); struct.pack_into("<8f", d, o + 78 + 96, *new)
        rep.append(f"F{i + 1:02d} {src_nm} -> {dst_nm}")
    log.append("presets re-pointed: " + ", ".join(rep))
    for i in sorted(set(drop) | {BOG}, reverse=True):
        drop_entry(m, 0, 3, i); drop_entry(d, 0x10000, 3, i)
    assert len(m) == n0m and len(d) == n0d
    free.append(((ob + len(core) + 63) & ~63, ob + bog_own - ((ob + len(core) + 63) & ~63)))
    json.dump(sorted(free, key=lambda r: -r[1]), open(os.path.join(out, "free_after.json"), "w"))
    open(mp, "wb").write(m); open(dp, "wb").write(d)
    binf = os.path.join(out, f"PocketMaster_CFW1.0.2+{name}.bin")
    subprocess.run([sys.executable, os.path.join(RE, "pmfw.py"), "pack", src, binf], check=True, stdout=subprocess.DEVNULL)
    open(os.path.join(out, "amps.txt"), "w").write("\n".join(log) + "\n"); print("\n".join(log)); print("built", os.path.relpath(binf, RE))


if __name__ == "__main__":
    main()
