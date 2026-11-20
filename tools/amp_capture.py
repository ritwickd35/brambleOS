#!/usr/bin/env python3
"""Capture the stock amps for fitting (needs the Mac headphone out -> pedal IN cable and the pedal's USB audio).
  amp_capture.py [amp name ...]     default: the 16 stock amps behind our lineup (tools/ampmodel.py LINEUP)
Per amp and knob set: P08 with only the AMP slot on (no cab, no drive), the audit signal in, USB out recorded.
Writes audio/ampcap/<amp>/<knobs>.f32 (mono, aligned to the bypass take) and audio/ampcap/<amp>/spec.json for
tools/ampfit.py fit. P08 is restored byte-identically."""
import json, os, re, struct, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import audit as A
from ampmodel import LINEUP
from build_cut import groups
OUT = os.path.join(RE, "audio", "ampcap" + os.environ.get("AMPCAP_TAG", ""))
KNOBSETS = [[30, 50, 50, 50, 50, 50, 0], [70, 50, 50, 50, 50, 50, 0], [100, 50, 50, 50, 50, 50, 0],
            [70, 0, 100, 0, 100, 50, 1]]
OURS = ["Gain", "Bass", "Middle", "Treble", "PRES", "VOL", "Bright"]
ALIAS = {"Tone": "Treble", "Presence": "PRES"}


def stock_amps():
    """name -> (fx id, knob names in parameter order) from the effect DB of the daily firmware"""
    d = open(os.environ.get("AMPCAP_DB", os.path.join(RE, "build", "daily", "src", "4_effect_db_presets_00190000.bin")), "rb").read()
    g = groups(d, 0x10000); allr = sorted(x for gl in g for x in gl); out = {}
    for r in g[3]:
        nxt = next((x for x in allr if x > r), r + 400)
        s = [m.group().decode() for m in re.finditer(rb"[A-Za-z][ -~]{1,}", d[0x10000 + r:0x10000 + nxt]) if m.group() not in (b"HB", b"pB")]
        out[s[0]] = (struct.unpack_from("<I", d, 0x10000 + r)[0], s[2:])
    return out


def params_for(knob_names, kn):
    p = [50.0] * 8
    for i, nm in enumerate(knob_names[:8]):
        nm = ALIAS.get(nm, nm)
        if nm in OURS: p[i] = float(kn[OURS.index(nm)]) * (1.0 if nm != "Bright" else 1.0)
    return p


def align(ref, y):
    """delay of y against ref (samples), from the sync burst region"""
    a = ref[:A.FS]; b = y[:A.FS + 4000]
    c = np.correlate(b, a[:int(0.3 * A.FS)], "valid"); return int(np.argmax(np.abs(c)))


def main():
    import sounddevice as sd, pmaudio
    from pmflash import Link
    from cut1_variants import read_p
    from cut1_matrix import send, set_mod
    names = sys.argv[1:] or [v[0] for v in LINEUP.values()]
    amps = stock_amps(); link = Link(); orig = read_p(link); link.close()
    base = orig
    for k in range(10): base = set_mod(base, k, on=False)
    x, _ = A.signal(); play = np.stack([x, x], 1).astype(np.float32); dev = pmaudio.out_device("External Headphones")
    def take(rec, path):
        send(rec); time.sleep(2.0)
        p = pmaudio.record(path, A.DUR + 3.5); time.sleep(1.0); sd.play(play, samplerate=A.FS, device=dev); p.wait(); sd.stop()
        import eprobe_decode as D
        return D.load(path).astype(np.float64)
    try:
        os.makedirs(OUT, exist_ok=True)
        ref = take(base, os.path.join(OUT, "bypass.wav")); n = int(A.DUR * A.FS)
        d0 = align(x, ref); ref = ref[d0:d0 + n]; ref.astype("<f4").tofile(os.path.join(OUT, "bypass.f32"))
        for nm in names:
            fx, kn_names = amps[nm]; od = os.path.join(OUT, nm.replace(" ", "_")); os.makedirs(od, exist_ok=True); spec = []
            for kn in KNOBSETS:
                tag = "-".join(str(int(v)) for v in kn)
                y = take(set_mod(base, 3, fx, params_for(kn_names, kn), True), os.path.join(od, tag + ".wav"))
                d = align(ref, y); y = y[d:d + n]; y.astype("<f4").tofile(os.path.join(od, tag + ".f32"))
                spec.append(dict(**{"in": os.path.join(OUT, "bypass.f32"), "out": os.path.join(od, tag + ".f32")}, knobs=kn))
                print(time.strftime("%H:%M:%S"), nm, tag, "level", round(float(20 * np.log10(np.std(y) + 1e-12)), 1), "dB", flush=True)
            json.dump(spec, open(os.path.join(od, "spec.json"), "w"), indent=1)
    finally:
        send(orig); time.sleep(0.5); link = Link(); back = read_p(link); link.close()
        print("P08 restored:", back[4:] == orig[4:], flush=True)


if __name__ == "__main__":
    main()
