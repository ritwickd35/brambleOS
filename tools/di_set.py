#!/usr/bin/env python3
"""Guitar DI collection in re/guitar_di/<song>/*.wav -> training / held-out sets for capture conversion.
Split by song (a song is never in both sets); with a single song, the first file trains and the others are
held out. Only active passages are used (silence removed); each set is peak-normalised to 0.9 (DSP scale).
  di_set.py           list songs and the split"""
import glob, hashlib, os, re, sys
import numpy as np
RE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.path.join(RE, "guitar_di"); FS = 44100


def songs():
    return sorted(d for d in glob.glob(os.path.join(ROOT, "*")) if os.path.isdir(d) and glob.glob(os.path.join(d, "*.wav")))


def split():
    """test = the right-hand take ("... R.wav") of every song, train = all other takes (separate performances, so
    no recording is in both sets and the test covers every style). Songs with one take: split by song hash."""
    files = sorted(f for d in songs() for f in glob.glob(os.path.join(d, "*.wav")))
    te = [f for f in files if re.search(r"\bR\.wav$|[ _-]R\.wav$", f, re.I)]
    if te: return [f for f in files if f not in te], te
    s = songs()
    if len(s) == 1:
        f = sorted(glob.glob(os.path.join(s[0], "*.wav"))); return f[:1], f[1:]
    test = [d for d in s if int(hashlib.md5(os.path.basename(d).encode()).hexdigest(), 16) % 4 == 0] or s[-1:]
    files = lambda ds: sorted(f for d in ds for f in glob.glob(os.path.join(d, "*.wav")))
    return files([d for d in s if d not in test]), files(test)


def active(x, secs=None):
    """only passages where the guitar actually plays: 50 ms windows above -50 dBFS and above the loudest - 40 dB; gaps < 0.3 s are bridged (note decays stay whole), passages < 1 s dropped, 10 ms fades."""
    w = FS // 20; n = len(x) // w; r = np.sqrt(np.mean(x[:n * w].reshape(n, w) ** 2, 1)) + 1e-12
    keep = r > max(10 ** (-50 / 20), r.max() * 10 ** (-40 / 20))   # DI noise floors sit near -60 dBFS, silence = 0
    k = keep.copy()                                              # bridge short gaps
    i = 0
    while i < n:
        if not keep[i]:
            j = i
            while j < n and not keep[j]: j += 1
            if 0 < i and j < n and j - i <= 6: k[i:j] = True
            i = j
        else: i += 1
    out, i, fade = [], 0, np.hanning(2 * 441)
    while i < n:
        if k[i]:
            j = i
            while j < n and k[j]: j += 1
            if j - i >= 20:
                seg = x[i * w:j * w].copy(); seg[:441] *= fade[:441]; seg[-441:] *= fade[441:]; out.append(seg)
            i = j
        else: i += 1
    y = np.concatenate(out) if out else x[:0]; return y if secs is None else y[:int(secs * FS)]


def load(which, secs):
    import soundfile as sf
    files = split()[0 if which == "train" else 1]; per = secs / max(len(files), 1); parts = []
    for f in files:
        x, sr = sf.read(f, dtype="float64"); x = x.mean(1) if x.ndim > 1 else x
        assert sr == FS, f"{f}: {sr} Hz (resample first)"
        a = active(x); a = a[len(a) // 2 - int(per * FS) // 2:][:int(per * FS)] if len(a) > per * FS else a   # middle of the song
        parts.append(a * (0.9 / (np.percentile(np.abs(a), 99.95) + 1e-12)))                                      # per file
    return np.clip(np.concatenate(parts), -1, 1)


if __name__ == "__main__":
    tr, te = split(); print(len(songs()), "songs;", len(tr), "train files,", len(te), "held-out files")
    import soundfile as sf
    for f in tr + te:
        x, _ = sf.read(f, dtype="float64"); x = x.mean(1) if x.ndim > 1 else x; a = active(x)
        print(f"  {'TEST ' if f in te else 'train'} {os.path.relpath(f, ROOT)[:60]:60s} {len(x) / FS / 60:5.1f} min, playing {len(a) / FS / 60:4.1f} min")
