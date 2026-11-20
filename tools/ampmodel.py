#!/usr/bin/env python3
"""Settings files for our amp model (dsp/amp.c) + offline checks with the same test signal as the pedal audit.
  ampmodel.py init                     write amps/<name>.json starting points for the lineup
  ampmodel.py eval <name> [gain bass mid treble pres vol bright]   fizz, gain ramp, tone (via dsp/host)
Settings are kept as JSON (named) and passed to dsp/host as a plain text file in enum order."""
import json, os, subprocess, sys, tempfile
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
AMPS = os.path.join(RE, "amps"); HOST = os.path.join(RE, "dsp", "host"); FS = 44100

NAMES = (["nst", "gmin", "gmax", "brt_hz", "brt_db"]
         + [f"s{k}_{f}" for k in range(3) for f in ("hp", "lp", "gain", "bias", "out")]
         + ["R1", "R2", "R3", "R4", "C1", "C2", "C3", "pdrv", "pout", "pres_hz", "pres_db", "res_hz", "res_db", "out", "os", "olp"])
assert len(NAMES) == 36

# tone stacks (D. T. Yeh / CAPS component values): R1 R2 R3 R4 C1 C2 C3
K, M_, n, p = 1e3, 1e6, 1e-9, 1e-12
TS = {"bassman": (250*K, 1*M_, 25*K, 56*K, 250*p, 20*n, 20*n), "twin": (250*K, 250*K, 10*K, 100*K, 120*p, 100*n, 47*n),
      "mesa": (250*K, 250*K, 25*K, 100*K, 250*p, 100*n, 47*n), "jcm800": (220*K, 1*M_, 22*K, 33*K, 470*p, 22*n, 22*n),
      "jtm45": (250*K, 1*M_, 25*K, 33*K, 270*p, 22*n, 22*n), "mlead": (250*K, 1*M_, 25*K, 33*K, 500*p, 22*n, 22*n),
      "ac30": (1*M_, 1*M_, 10*K, 100*K, 50*p, 22*n, 22*n), "soldano": (250*K, 1*M_, 25*K, 47*K, 470*p, 20*n, 20*n),
      "engl": (250*K, 1*M_, 20*K, 100*K, 600*p, 47*n, 47*n), "peavey": (250*K, 250*K, 20*K, 68*K, 270*p, 22*n, 22*n),
      "roland": (250*K, 250*K, 10*K, 41*K, 240*p, 33*n, 82*n), "ampeg": (250*K, 1*M_, 25*K, 32*K, 470*p, 22*n, 22*n),
      "fender": (250*K, 250*K, 10*K, 100*K, 250*p, 100*n, 47*n)}

# lineup: name -> (stock slot it replaces, tone stack family, gain class). Starting points only; fitted later.
LINEUP = {"twin": ("Dark Twin", "twin", "clean"), "tweed": ("TWD Deluxe", "fender", "edge"),
          "bassman": ("B-Man B", "bassman", "edge"), "ac30n": ("Voks 30N", "ac30", "edge"),
          "ac30tb": ("Voks 30TB", "ac30", "crunch"), "jc120": ("Jazz 120", "roland", "clean"),
          "jtm45": ("Brit 45", "jtm45", "crunch"), "plexi": ("Brit 50", "mlead", "crunch"),
          "jcm800": ("Brit 800", "jcm800", "drive"), "iicplus": ("Calif IIC+", "mesa", "high"),
          "slo100": ("Sol 100 LD", "soldano", "high"), "friedman": ("Flyman B1+", "jcm800", "high"),
          "recto": ("Calif DualM", "mesa", "high"), "5150": ("Halen 51", "peavey", "high"),
          "vh4": ("Dizzy VH+", "engl", "high"), "svt": ("A BassVT", "ampeg", "edge")}
CLASS = {  # nst, gmin, gmax, stage gains, power drive
    "clean": (1, 0.3, 3.0, (1.5, 1, 1), 0.6), "edge": (2, 0.4, 6.0, (1.5, 2.0, 1), 0.9),
    "crunch": (2, 0.5, 12.0, (2.0, 4.0, 1), 1.2), "drive": (3, 0.5, 20.0, (2.0, 5.0, 3.0), 1.4),
    "high": (3, 1.0, 40.0, (3.0, 6.0, 4.0), 1.6)}


def start(name):
    slot, ts, cl = LINEUP[name]; nst, gmin, gmax, g, pd = CLASS[cl]
    s = dict(nst=nst, gmin=gmin, gmax=gmax, brt_hz=1500.0, brt_db=6.0)
    for k, (hp, lp, b) in enumerate(((30.0, 12000.0, 0.15), (120.0, 8000.0, 0.25), (60.0, 6000.0, 0.10))):
        s.update({f"s{k}_hp": hp, f"s{k}_lp": lp, f"s{k}_gain": g[k], f"s{k}_bias": b, f"s{k}_out": 0.8})
    s.update(dict(zip(["R1", "R2", "R3", "R4", "C1", "C2", "C3"], TS[ts])))
    s.update(pdrv=pd, pout=1.2, pres_hz=3500.0, pres_db=6.0, res_hz=100.0, res_db=3.0, out=0.5, _replaces=slot, _stack=ts)
    return s


def load(name): return json.load(open(os.path.join(AMPS, f"{name}.json")))


def run(settings, knobs, x):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("\n".join(repr(float(settings.get(k, {"os": 4.0, "olp": 19000.0}.get(k, 0.0)))) for k in NAMES) + "\n"); path = f.name
    try:
        p = subprocess.run([HOST, "amp", path] + [str(float(k)) for k in knobs[:6]] + [str(int(knobs[6]) if len(knobs) > 6 else 0)],
                           input=np.asarray(x, "<f4").tobytes(), capture_output=True, check=True)
    finally: os.unlink(path)
    return np.frombuffer(p.stdout, "<f4").astype(np.float64)


def evaluate(settings, knobs):
    import audit as A
    x, nz = A.signal(); y = run(settings, knobs, x * 2.87)
    harsh = {f: round(A.harshness(A.piece(y, 0.0, A.T_TONE + i + 0.15, A.T_TONE + i + 0.85), f), 1) for i, f in enumerate(A.TONES)}
    ramp = [(L, round(float(20 * np.log10(np.std(A.piece(y, 0.0, A.T_RAMP + i * 0.75 + 0.15, A.T_RAMP + i * 0.75 + 0.65)) * 1.4142 + 1e-12)), 1))
            for i, L in enumerate(A.LEVELS)]
    return dict(harsh=harsh, ramp=ramp)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "init":
        os.makedirs(AMPS, exist_ok=True)
        for nm in LINEUP:
            pth = os.path.join(AMPS, f"{nm}.json")
            if not os.path.exists(pth): json.dump(start(nm), open(pth, "w"), indent=1)
        print("wrote", len(LINEUP), "starting points to amps/")
    elif a[0] == "eval":
        kn = [float(v) for v in a[2:]] or [50, 50, 50, 50, 50, 50, 0]
        for k, v in evaluate(load(a[1]), kn).items(): print(k, v)
