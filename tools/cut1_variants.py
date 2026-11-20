#!/usr/bin/env python3
"""Cut 1: CPU headroom for preset variants (all automatic, P08 = index 7 holds the test effect in DRV).

For each variant: start tone+recording, write the variant into P08, select P08 (restarts the test effect),
record 120 s, find the three degradation episodes, compute load % at onset and at overrun.
Finally P08 is written back exactly as read at the start, and verified.
"""
import os, struct, subprocess, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pmpreset, pmloadtest as L
from pmflash import Link
PY = os.path.join(HERE, ".venv", "bin", "python")
IDX = 7
LOG = os.path.join(RE, "logs", "cut1-variants.log")
FS = 44100


def log(*a):
    s = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
    print(s, flush=True); open(LOG, "a").write(s + "\n")


def tlv(b):
    i, out = 0, []
    while i + 4 <= len(b):
        t, l = struct.unpack_from("<HH", b, i); out.append((t, i + 4, l)); i += 4 + l
    return out


def offsets(rec):
    top = tlv(rec[20:]); mod = [x for x in top if x[0] == 2][0]; base = 20 + mod[1]
    return {t: base + o for t, o, l in tlv(rec[base:base + mod[2]])}


def variant(rec, on=(), off=()):
    r = bytearray(rec); o = offsets(rec)
    en = struct.unpack_from("<I", r, o[0x3001])[0]
    for m in on: en |= 1 << m
    for m in off: en &= ~(1 << m)
    struct.pack_into("<I", r, o[0x3001], en)
    return bytes(r)


def describe(rec):
    o = offsets(rec); en = struct.unpack_from("<I", rec, o[0x3001])[0]
    names = ["NR", "FX1", "DRV", "AMP", "IR", "EQ", "FX2", "DLY", "RVB", "CLONE"]
    return " ".join(n for i, n in enumerate(names) if en >> i & 1)


def read_p(link):
    for _ in range(3):
        r = pmpreset.ask(link, 0x4F, struct.pack("<I", IDX))
        if r: return r
        time.sleep(0.5)
    raise RuntimeError("cannot read P08")


def episodes(path):
    y = L.load(path); w = 32; n = len(y) // w
    env = np.sqrt(np.mean(y[:n * w].reshape(n, w) ** 2, 1)); med = np.median(env)
    q = int(0.25 * FS / w); m = n // q
    mins = np.array([env[i * q:(i + 1) * q].min() / med for i in range(m)]); t = np.arange(m) * 0.25
    ev = []
    for i in np.where(mins < 0.8)[0]:
        if ev and t[i] - ev[-1][1] <= 1.0: ev[-1][1] = t[i]
        else: ev.append([t[i], t[i]])
    return ev


def run(rec, label):
    log(f"--- {label}: blocks on = {describe(rec)}")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    p = subprocess.Popen([PY, "-u", os.path.join(HERE, "pmloadtest.py"), "run", "120"],
                         stdout=open(os.path.join(RE, "logs", f"cut1-{stamp}.log"), "w"), stderr=subprocess.STDOUT)
    time.sleep(5)
    link = Link()
    pmpreset.write_message(link, b"\x11\x4f", struct.pack("<I", IDX) + rec[4:])
    time.sleep(0.5)
    pmpreset.write_message(link, b"\x11\x43", struct.pack("<I", IDX))
    t_sel = time.time()
    link.close()
    p.wait()
    wav = sorted(f for f in os.listdir(L.OUT) if f.endswith("-cputest.wav"))[-1]
    ev = episodes(os.path.join(L.OUT, wav))
    log("episodes (s):", [(float(a), float(b)) for a, b in ev], "file", wav)
    res = []
    # first episode = preset switch; cycles follow. ramp0 = start of cycle + 0.14 + 2 s
    if len(ev) >= 2:
        cyc_start = ev[0][1] + 0.25
        for e in ev[1:4]:
            ramp0 = cyc_start + 0.14 + 2.0
            res.append((round((e[0] - ramp0) / 0.25), round((e[1] + 0.25 - ramp0) / 0.25)))
            cyc_start = e[1] + 0.25 + 4.0
    for i, (a, b) in enumerate(res, 1):
        log(f"   cycle {i}: dips from ~{a} % extra load, overrun at ~{b} %")
    return res


def main():
    open(LOG, "a").write("\n")
    log("variant test started")
    link = Link(); orig = read_p(link); link.close()
    open(os.path.join(RE, "cut1", "p08-before-variants.bin"), "wb").write(orig)
    log("P08 saved to cut1/p08-before-variants.bin; current blocks on =", describe(orig))
    results = {}
    results["amp off"] = run(variant(orig, off=(3,)), "AMP off (IR stays on)")
    results["all on"] = run(variant(orig, on=(1, 5, 7)), "worst case: FX1, EQ, DLY also on")
    link = Link()
    pmpreset.write_message(link, b"\x11\x4f", struct.pack("<I", IDX) + orig[4:]); time.sleep(0.5)
    pmpreset.write_message(link, b"\x11\x43", struct.pack("<I", IDX)); time.sleep(0.5)
    back = read_p(link); link.close()
    log("P08 restored:", "OK (byte-identical)" if back[4:] == orig[4:] else "MISMATCH")
    log("summary:", results)


if __name__ == "__main__":
    main()
