#!/usr/bin/env python3
"""Name LVGL functions in the MCU app by comparing instruction shapes with LVGL v8.3 compiled for NDS32.
Writes ui/lvgl_names.json {fw address: [lvgl name, score]} for matches with a clear margin.
Normalised instruction = mnemonic + register operands (immediates, addresses and branch targets dropped)."""
import collections, json, os, re
RE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INS = re.compile(r"^\s+([0-9a-f]+):\t(?:[0-9a-f]{2} ){2,4}\s*\t(\S+)\s*([^!]*)")


def norm(mn, ops):
    ops = re.sub(r"#?-?0x[0-9a-f]+|#-?\d+|<[^>]*>|\+ ?", "", ops)
    mn = re.sub(r"\d+$", "", mn.split(".")[0])                    # 16-bit forms (movi55, beqz38, ...) = base op
    return mn


def lib_funcs(path):
    f, cur, name = {}, None, None
    for l in open(path):
        m = re.match(r"^[0-9a-f]+ <([\w.]+)>:", l)
        if m: name = m.group(1).replace(".text.", ""); cur = f.setdefault(name, []); continue
        m = INS.match(l)
        if m and cur is not None: cur.append(norm(m.group(2), m.group(3)))
    return {k: v for k, v in f.items() if len(v) >= 8}


def fw_funcs(path):
    lines = [(int(m.group(1), 16), norm(m.group(2), m.group(3))) for m in map(INS.match, open(path)) if m]
    starts = sorted({int(t, 16) for l in open(path) for t in re.findall(r"\tjal\t0x([0-9a-f]+)", l)})
    out, si, cur = {}, 0, None
    for a, ins in lines:
        while si < len(starts) and starts[si] <= a:
            cur = out.setdefault(starts[si], []); si += 1
        if cur is not None:
            cur.append(ins)
            if ins.startswith(("ret", "lmw.bim")) and False: pass
    return {k: v[:400] for k, v in out.items() if len(v) >= 8}


def grams(seq, n=4): return {tuple(seq[i:i + n]) for i in range(len(seq) - n + 1)}


def main():
    lib = lib_funcs(os.path.join(RE, "ui", "lvgl", "lvgl_v8.dis")); fw = fw_funcs(os.path.join(RE, "cfw", "mcu_cfw.dis"))
    lg = {k: grams(v) for k, v in lib.items()}; idx = collections.defaultdict(set)
    for k, g in lg.items():
        for x in g: idx[x].add(k)
    res = {}
    for a, seq in fw.items():
        g = grams(seq); cnt = collections.Counter()
        for x in g:
            if len(idx.get(x, ())) <= 40:
                for k in idx[x]: cnt[k] += 1
        sc = sorted(((c / len(g | lg[k]), k) for k, c in cnt.most_common(8)), reverse=True)
        if sc and sc[0][0] > 0.45 and (len(sc) == 1 or sc[0][0] - sc[1][0] > 0.1):
            res[hex(a)] = [sc[0][1], round(sc[0][0], 2)]
    json.dump(res, open(os.path.join(RE, "ui", "lvgl_names.json"), "w"), indent=0)
    print(len(lib), "LVGL functions,", len(fw), "firmware functions,", len(res), "named")
    for a in ("0x479b8", "0x48cd0", "0x2c1d0", "0x335cc", "0x335e8", "0x33658", "0x427b8", "0x2e3f4", "0x2f2bc", "0x47998", "0x328f8"):
        print(" ", a, res.get(a))


if __name__ == "__main__":
    main()
