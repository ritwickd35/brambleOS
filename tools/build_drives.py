#!/usr/bin/env python3
"""Daily firmware + our drives, one model per stock DRV slot, each strictly inside the slot's own footprint
(header + code + program = ts + st of the stock blob). No list, count or section size changes.

  build_drives.py <name> <slot>=<model> [...]      e.g. build_drives.py rat 4=rat
Slots: 0 Scream, 2 JP Dist, 3 Shark, 4 Dark Mouse.  Models: ds1 ts808 rat fuzz.  Output build/drives-<name>/."""
import os, shutil, struct, subprocess, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import drives2
from build_cut import groups
DSP = os.path.join(RE, "dsp")
MODEL = {"ds1": 0, "ts808": 1, "rat": 2, "fuzz": 3, "klon": 4, "muff": 5}
# per slot: stock name -> new name, knob renames (always same byte length, space padded)
NAMES = {0: [(b"Scream\0", b"TS808 \0")],
         2: [(b"JP Dist\0", b"DS-1   \0")],
         3: [(b"Shark\0", b"FFace\0"), (b"Gain\0", b"Fuzz\0")],
         4: [(b"Dark Mouse\0", b"RAT       \0"), (b"Filter\0", b"Tone  \0")],
         7: [(b"Bass Drive\0", b"Test 7    \0")]}
# test variants: "<model>x" = same blob, but the engine program's first word jumps straight to the next block
# (the engine part never runs; isolates the ARM side)
FLAGS = ("-mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16 -Os -ffreestanding -nostdlib -fno-builtin "
         "-ffunction-sections -fdata-sections -fsingle-precision-constant -Wall -Wno-unused-function")


def compile_model(model):
    """ARM code for one model -> (bytes linked at 0x10002800, entry0, entry1)."""
    m = MODEL[model]; o = f"mod_one_{model}"
    sh = (f'set -e; F="{FLAGS}"; arm-none-eabi-gcc $F -DMODEL={m} -c pmfx.c -o /tmp/pmfx.o; '
          f'arm-none-eabi-gcc $F -DMODEL={m} -c mod_one.c -o /tmp/one.o; '
          f'arm-none-eabi-gcc $F -T link-drv3.ld -Wl,--gc-sections -nostartfiles /tmp/pmfx.o /tmp/one.o -o {o}.elf -lgcc; '
          f'arm-none-eabi-objcopy -O binary {o}.elf {o}.bin; arm-none-eabi-nm {o}.elf > {o}.sym')
    subprocess.run(["sh", "-c", "sync; sleep 2"], check=True)
    subprocess.run(["docker", "run", "--rm", "-v", f"{DSP}:/w", "-w", "/w", "pmarm", "sh", "-c", sh], check=True)
    code = open(os.path.join(DSP, f"{o}.bin"), "rb").read()
    sym = {l.split()[2]: int(l.split()[0], 16) for l in open(os.path.join(DSP, f"{o}.sym")) if len(l.split()) == 3}
    assert sym["drv_entry0"] >= 0x10002800 and 0x10002800 + len(code) <= 0x10003800
    return code, sym["drv_entry0"] | 1, sym["drv_entry1"] | 1


FUZZ_FACE, RED_FUZZ = 50331696, 50331684
NEWREC = {1: (0, "Klon"), 5: (3, "BMuff")}                     # slot -> (record to copy, display name)
from build_bisect import zero_run


def drop_entry(b, base, grp, idx):
    """remove entry idx from list grp in place (count - 1, later entries move up); the blob/record stays as free space"""
    ptr = struct.unpack_from("<I", b, base + 0x14 + 4 * grp)[0]; n = struct.unpack_from("<I", b, base + ptr)[0]
    e = list(struct.unpack_from(f"<{n}I", b, base + ptr + 4)); del e[idx]
    struct.pack_into(f"<I{n - 1}I", b, base + ptr, n - 1, *e); struct.pack_into("<I", b, base + ptr + 4 * n, 0)


THREE = {}


def repoint_factory(d):
    """factory presets (image records at 0x1000 + 0x400 i): DRV Red Fuzz -> our Fuzz Face, knobs Fuzz/VOL -> drive/tone/level"""
    out = []
    for i in range(50):
        o = 0x1000 + 0x400 * i
        if d[o:o + 2] != b"\xa5\x5a": continue
        fx, pr = o + 38 + 4 * 2, o + 78 + 32 * 2
        f0 = struct.unpack_from("<I", d, fx)[0]
        if f0 in (50331650, 50331682) and THREE.get(f0):              # Butter OD / Grey Fuzz: [knob, VOL] -> [knob, 50, VOL]
            p = struct.unpack_from("<8f", d, pr); struct.pack_into("<8f", d, pr, p[0], 50.0, p[1], 0, 0, 0, 0, 0); out.append(f"F{i + 1:02d}*")
        if f0 == RED_FUZZ:
            p = struct.unpack_from("<8f", d, pr); struct.pack_into("<I", d, fx, FUZZ_FACE)
            struct.pack_into("<8f", d, pr, p[0], 50.0, p[1], 0, 0, 0, 0, 0); out.append(f"F{i + 1:02d}")
    return out


def main():
    drop = "--drop-red" in sys.argv; sys.argv = [a for a in sys.argv if a != "--drop-red"]
    name, jobs = sys.argv[1], [a.split("=") for a in sys.argv[2:]]
    out = os.path.join(RE, "build", f"drives-{name}"); src = os.path.join(out, "src")
    if os.path.exists(src): shutil.rmtree(src)
    shutil.copytree(os.path.join(RE, "build", "daily", "src"), src)
    mp = os.path.join(src, "1_dsp_modules_00240000.bin"); m = bytearray(open(mp, "rb").read())
    dp = os.path.join(src, "4_effect_db_presets_00190000.bin"); d = bytearray(open(dp, "rb").read())
    n0m, n0d = len(m), len(d); gm, gd = groups(m, 0), groups(d, 0x10000)
    free = []                                                     # (offset, size) left over inside replaced slots
    MOVE = set()                                                  # slots whose blob may live anywhere free
    if drop:                                                      # Butter OD and Grey + Red Fuzz become one free pool
        MOVE = {s_ for s_ in (1, 5) if str(s_) in [j[0] for j in jobs]}
        free += [(gm[2][5], gm[2][7] - gm[2][5])] if 5 in MOVE else [(gm[2][6], gm[2][7] - gm[2][6])]
        if 1 in MOVE: hs1, cs1, ts1, st1 = struct.unpack_from("<4I", m, gm[2][1]); free.append((gm[2][1], ts1 + st1))
        jobs = [j for j in jobs if int(j[0]) not in MOVE] + [j for j in jobs if int(j[0]) in MOVE]
    for slot, model in jobs:
        slot = int(slot); o = gm[2][slot]
        hs, cs, ts, st = struct.unpack_from("<4I", m, o); own = ts + st
        if slot in MOVE: own = 0
        base_model, at = (model.split("@") + [None])[:2]; base_model = base_model.rstrip("x"); prog_model = base_model; base_model = base_model.partition("#")[0]
        code, e0, e1 = compile_model(base_model); code += b"\0" * ((-len(code)) % 4)
        if at:                                                   # "<model>@N": library at code word N (gap = zeros)
            mn, lb, _ = drives2.assemble_model(prog_model, int(at)); lib_at = int(at)
            prog = list(mn) + [0] * (lib_at - len(mn)) + list(lb)
        else: prog, lib_at = drives2.assemble_packed(prog_model)
        if model.endswith("x"): prog = list(drives2.assemble("jmp 1280\n", 0, {})[0]) + prog[1:]
        prog = np.array(prog, "<u4").tobytes()
        hdr = bytearray(m[o:o + hs])
        struct.pack_into("<5I", hdr, 4, len(code), hs + len(code), len(prog), e0, e1)
        blob = bytes(hdr) + code + prog
        if len(blob) > own:                                       # move the blob into free space of another replaced slot
            fit = sorted((b, a) for a, b in free if b >= len(blob)); assert fit, f"slot {slot}: {len(blob)} bytes, no room"
            fs, fo = fit[0]; free.remove((fo, fs)); used = (len(blob) + 15) & ~15        # best fit
            if own: free.append((o, own)); m[o:o + own] = b"\0" * own
            if fs > used: free.append((fo + used, fs - used))
            m[fo:fo + fs] = blob + b"\0" * (fs - len(blob))
            ptr = struct.unpack_from("<I", m, 0x14 + 4 * 2)[0]; struct.pack_into("<I", m, ptr + 4 + 4 * slot, fo)
            print(f"slot {slot}: blob moved to module offset {fo}"); own = fs
        else:
            m[o:o + own] = blob + b"\0" * (own - len(blob))      # never past the stock blob's own size
            free.append(((o + len(blob) + 15) & ~15, own - ((len(blob) + 15) & ~15)))
        r = 0x10000 + gd[2][slot]; nxt = 0x10000 + min(x for gl in gd for x in gl if x > gd[2][slot])
        for a, b in NAMES.get(slot, []):
            assert len(a) == len(b); j = d.find(a, r, nxt); assert j > 0, (slot, a); d[j:j + len(a)] = b
        print(f"slot {slot} -> {model}: {len(blob)} of {own} bytes (code {len(code)}, program {len(prog)}, "
              f"library at {lib_at}), spare {own - len(blob)}")
    for slot, (src_slot, nm) in NEWREC.items():                       # 3-knob records (copy of a renamed drive record)
        if str(slot) not in [j[0] for j in jobs]: continue
        allr = sorted(x for gl in gd for x in gl); r0 = gd[2][src_slot]; rec = bytearray(d[0x10000 + r0:0x10000 + next(x for x in allr if x > r0)])
        old = NAMES[src_slot][0][1]; j = rec.find(old); assert j > 0; rec[j:j + len(old)] = nm.ljust(len(old) - 1).encode() + b"\0"
        struct.pack_into("<I", rec, 0, struct.unpack_from("<I", d, 0x10000 + gd[2][slot])[0])     # keep the slot's effect id
        z = zero_run(d, 0x10000, len(rec) + 64, 0x20000); assert z > 0; at = (z + 16) & ~3
        d[at:at + len(rec)] = rec; ptr = struct.unpack_from("<I", d, 0x10000 + 0x14 + 4 * 2)[0]
        struct.pack_into("<I", d, 0x10000 + ptr + 4 + 4 * slot, at - 0x10000); print(f"slot {slot}: new 3-knob record '{nm}'")
    assert len(m) == n0m and len(d) == n0d
    gm2, gd2 = groups(m, 0), groups(d, 0x10000)
    assert all(gm2[k] == gm[k] and gd2[k] == gd[k] for k in range(11) if k != 2) and len(gm2[2]) == len(gm[2])
    if drop:
        assert struct.unpack_from("<I", d, 0x10000 + gd[2][6])[0] == RED_FUZZ
        pm, pd = groups(m, 0)[2], groups(d, 0x10000)[2]
        drop_entry(m, 0, 2, 6); drop_entry(d, 0x10000, 2, 6)
        g2m, g2d = groups(m, 0), groups(d, 0x10000)
        assert g2m[2] == pm[:6] + pm[7:] and g2d[2] == pd[:6] + pd[7:]
        assert all(g2m[k] == gm[k] and g2d[k] == gd[k] for k in range(11) if k != 2)
        THREE.update({50331650: "1" in [j[0] for j in jobs], 50331682: "5" in [j[0] for j in jobs]})
        print("Red Fuzz removed from the menu; factory presets updated (* = knob layout):", repoint_factory(d))
    open(mp, "wb").write(m); open(dp, "wb").write(d)
    binf = os.path.join(out, f"PocketMaster_CFW1.0.2+drives-{name}.bin")
    subprocess.run([sys.executable, os.path.join(RE, "pmfw.py"), "pack", src, binf], check=True, stdout=subprocess.DEVNULL)
    print("built", os.path.relpath(binf, RE))


if __name__ == "__main__":
    main()
