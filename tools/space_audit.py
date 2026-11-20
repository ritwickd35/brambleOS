#!/usr/bin/env python3
"""space_audit.py <db.bin> <tag>: every delay and reverb with Decay at max, F.Back at 70 %, Mix 40, rest default.
Records the fx-audit signal, then reports tail length, stereo width of the tail, smoothness and junk.
Results logs/space_audit-<tag>.json, recordings audio/space-<tag>/. P08 restored byte-identically."""
import json, os, sys, time, wave
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import audit_fx as F, dbrec


def analyse(path):
    w = wave.open(path); x = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2).astype(float) / 32768
    t0, tc = F.anchors(x[:, 0]); s = x[int((tc + 0.05) * 44100):int((tc + 3.9) * 44100)]
    e = np.sum(s ** 2, 1); env = np.convolve(e, np.ones(441) / 441, "same"); db = 10 * np.log10(env / (env.max() + 1e-20) + 1e-12)
    tail = float(np.argmax(db < -40) / 44100) if np.any(db < -40) else 3.85
    a = s[:int(1.0 * 44100)]; corr = np.corrcoef(a[:, 0], a[:, 1])[0, 1] if np.std(a[:, 1]) > 1e-6 else 1.0
    m = a[:, 0]; X = np.abs(np.fft.rfft(m * np.hanning(len(m)))) ** 2; fr = np.fft.rfftfreq(len(m), 1 / 44100); b = X[(fr > 200) & (fr < 6000)]
    flat = float(np.exp(np.mean(np.log(b + 1e-20))) / np.mean(b))
    r = F.analyse_fx(path)
    return dict(tail_to_minus40dB_s=round(tail, 2), width=round(1 - float(corr), 2), smooth=round(flat, 2), junk_db=r["spurious_db"])


def main():
    import sounddevice as sd, pmaudio
    from pmflash import Link
    from cut1_variants import read_p
    from cut1_matrix import send, set_mod
    db, tag = sys.argv[1], sys.argv[2]; out = os.path.join(RE, "audio", f"space-{tag}"); os.makedirs(out, exist_ok=True)
    jobs = [r for r in dbrec.records(db) if r[0] in (7, 8)]
    x = F.signal()[0]; play = np.stack([x, x], 1).astype(np.float32); dev = pmaudio.out_device("External Headphones")
    l = Link(); orig = read_p(l); l.close(); base = orig; res = {}
    for k in range(10): base = set_mod(base, k, on=False)
    try:
        for g, i, fx, title, kn in jobs:
            p = [0.0] * 8
            for j, (nm, df, mx) in enumerate(kn[:8]):
                p[j] = mx if nm == "Decay" else 0.7 * mx if nm == "F.Back" else 40.0 if nm == "Mix" else df
            send(set_mod(base, g, fx, p, True)); time.sleep(2.0)
            path = os.path.join(out, f"{'DLY' if g == 7 else 'RVB'} {title}.wav")
            pr = pmaudio.record(path, F.DUR + 2.5); time.sleep(0.8); sd.play(play, samplerate=44100, device=dev); pr.wait(); sd.stop()
            try: res[f"{'DLY' if g == 7 else 'RVB'} {title}"] = analyse(path)
            except Exception as e: res[title] = dict(error=str(e)[:80])
            json.dump(res, open(os.path.join(RE, "logs", f"space_audit-{tag}.json"), "w"), indent=1)
            print(time.strftime("%H:%M:%S"), title, res.get(f"{'DLY' if g == 7 else 'RVB'} {title}"), flush=True)
    finally:
        send(orig); time.sleep(0.5); l = Link(); back = read_p(l); l.close(); print("P08 restored:", back[4:] == orig[4:], flush=True)


if __name__ == "__main__":
    main()
