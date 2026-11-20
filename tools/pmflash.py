#!/usr/bin/env python3
"""Pocket Master firmware uploader (replicates Sonicake Manager 1.5.2's update sequence exactly).

  pmflash.py check   <fw.bin>   verify file + compare our message stream with the captured official update (offline)
  pmflash.py flash   <fw.bin>   flash the pedal (asks you to type FLASH unless --yes is given)

Sequence (stop-and-wait: every frame must be ACKed with 14 08 xx before the next is sent):
  [APP mode only] 11 6F → pedal reboots into the bootloader → re-open the port
  12 30 ×2 (reply 11 30 01 01 = update mode)
  11 69 "V<maj><min><patch>\0" ×10 (pedal answers 14 08 01), ~3 s pause
  11 60
  per section in file order:  11 61 {u32 type, u32 frames, u32 size+2}
                              stream (count=0xFF, index wraps): 11 <type> + section bytes, 19 bytes per frame
                              11 6E <type>
  11 6E 'n'  → pedal writes, reboots into the app
Safety: refuses bad files (HTFW magic, sizes, file CRC, section CRCs), refuses while Sonicake Manager runs,
aborts on the first missing ACK (the pedal then stays in update mode: re-run this tool or use Sonicake Manager).
"""
import os, struct, subprocess, sys, time
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pmsysex as P
import pmfw

CHUNK = 19


def plan(path):
    """Return (info, list of (label, frame_bytes, timeout_s)) for a firmware file. Raises on any inconsistency."""
    fw = open(path, "rb").read()
    h = pmfw.parse(fw)
    problems = []
    if h["total"] != len(fw):
        problems.append("file size does not match header")
    if not h["file_crc_ok"]:
        problems.append("file CRC wrong")
    if h["name"] != "Pocket Master":
        problems.append(f"device name is {h['name']!r}")
    for s in h["sections"]:
        if pmfw.crc16_modbus(s["data"]) != s["crc"]:
            problems.append(f"section {s['index']} CRC wrong")
    if problems:
        raise ValueError("refusing file: " + "; ".join(problems))
    v = h["version"]
    ver = b"V" + "".join(str(x) for x in v[1:4]).encode()
    out = [("handshake", P.build_message(b"\x12\x30")[0], 2), ("handshake", P.build_message(b"\x12\x30")[0], 2)]
    out += [("version", P.build_message(b"\x11\x69", ver + b"\0")[0], 2)] * 10
    out += [("pause", None, 3.0), ("start", P.build_message(b"\x11\x60")[0], 5)]
    for s in h["sections"]:
        blob = bytes((0x11, s["type"])) + s["data"]
        nfr = (len(blob) + CHUNK - 1) // CHUNK
        out.append((f"section {chr(s['type'])} header", P.build_message(b"\x11\x61", struct.pack("<III", s["type"], nfr, len(blob)))[0], 15))
        for i in range(nfr):
            out.append((f"section {chr(s['type'])} data", P.build_frame(0xFF, i & 0xFF, blob[i * CHUNK:(i + 1) * CHUNK]), 2))
        out.append((f"section {chr(s['type'])} end", P.build_message(b"\x11\x6e", bytes((s["type"], 0)))[0], 15))
    out.append(("finish", P.build_message(b"\x11\x6e", b"n\0")[0], 15))
    return h, out


def check(path, capture=None):
    h, steps = plan(path)
    frames = [f for _, f, _ in steps if f is not None]
    print(f"{os.path.basename(path)}: {h['name']} V{h['version'][1]}.{h['version'][2]}.{h['version'][3]}, file CRC OK, "
          f"{len(h['sections'])} sections OK, {len(frames)} frames to send")
    capture = capture or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "midi logs", "txt", "07-firmware.txt")
    if os.path.exists(capture):
        sent = []
        for line in open(capture):
            p = line.split()
            if len(p) >= 3 and p[1] == ">" and p[2] == "f0":
                sent.append(bytes.fromhex("".join(p[2:])))
        start = next(i for i, f in enumerate(sent) if P.parse_frame(f)["payload"][:2] == b"\x12\x30")
        sent = sent[start:]
        sent = sent[:next(i for i, f in enumerate(sent) if P.parse_frame(f)["payload"][:3] == b"\x11\x6e\x6e") + 1]
        same = sent == frames
        print(f"compared with captured official update ({len(sent)} frames): {'IDENTICAL' if same else 'DIFFERENT'}")
        if not same:
            for i, (a, b) in enumerate(zip(sent, frames)):
                if a != b:
                    print(f"  first difference at frame {i}: capture {a.hex()}  ours {b.hex()}"); break
        return same
    return True


class Link:
    def __init__(self, wait_s=20):
        import mido
        self.mido = mido
        t_end = time.time() + wait_s
        while True:
            o = next((n for n in mido.get_output_names() if "Pocket Master" in n), None)
            i = next((n for n in mido.get_input_names() if "Pocket Master" in n), None)
            if o and i:
                break
            if time.time() > t_end:
                raise RuntimeError("Pocket Master not visible on USB")
            time.sleep(0.5)
        self.out, self.inp = mido.open_output(o), mido.open_input(i)
        time.sleep(0.5)
        while self.inp.poll() is not None:
            pass

    def close(self):
        self.out.close(); self.inp.close()

    def send(self, frame, timeout, ack_only=False):
        """Send one frame, return the first reply payload (ACK 14 08 xx or a handshake reply).
        ack_only: ignore late handshake replies (left over after an interrupted update)."""
        self.out.send(self.mido.Message.from_bytes(list(frame)))
        t_end = time.time() + timeout
        while time.time() < t_end:
            m = self.inp.poll()
            if m is None:
                time.sleep(0.0002); continue
            if m.type != "sysex":
                continue
            f = P.parse_frame(bytes([0xF0]) + bytes(m.data) + b"\xf7")
            if f["ok"] and f["payload"][:2] in ((b"\x14\x08",) if ack_only else (b"\x14\x08", b"\x11\x30")):
                return f["payload"]
        return None


def flash(path, assume_yes=False):
    if subprocess.run(["pgrep", "-f", "Sonicake Manager.app"], capture_output=True).returncode == 0:
        sys.exit("Sonicake Manager is running. Quit it (Cmd+Q) first.")
    h, steps = plan(path)
    print(f"About to flash {os.path.basename(path)} ({h['name']} V{h['version'][1]}.{h['version'][2]}.{h['version'][3]}).")
    print("Do not touch the pedal or the cable until it says DONE (about 4-5 minutes).")
    if not assume_yes and input('Type FLASH to continue: ').strip() != "FLASH":
        sys.exit("cancelled, nothing sent")
    link = Link()
    hs = link.send(P.build_message(b"\x12\x30")[0], 2) or link.send(P.build_message(b"\x12\x30")[0], 2)
    if hs is None:
        sys.exit("pedal does not answer the handshake; nothing sent")
    if hs[:2] == b"\x11\x30" and hs[3:4] == b"\x00":
        print("pedal is in normal mode: asking it to enter update mode")
        link.send(P.build_message(b"\x11\x6f")[0], 2)
        try:
            link.close()
        except Exception:
            pass
        time.sleep(6)                                  # the official app waits ~5.7 s here
        link = Link(wait_s=30)
    t0, total = time.time(), sum(1 for _, f, _ in steps if f is not None)
    done = 0
    for label, frame, timeout in steps:
        if frame is None:
            time.sleep(timeout); continue
        reply = link.send(frame, timeout, ack_only=label not in ("handshake", "version"))
        done += 1
        if label == "handshake":
            for _ in range(15):                        # the bootloader may need a few seconds after re-enumerating
                if reply is not None:
                    break
                time.sleep(1)
                reply = link.send(frame, timeout)
            if reply is None or reply[3:4] != b"\x01":
                sys.exit(f"pedal is not in update mode (reply {reply.hex() if reply else None}); stopped before writing anything")
            continue
        if reply is None:
            sys.exit(f"\nSTOPPED at {label} (frame {done}/{total}): no acknowledgement.\n"
                     "The pedal stays in update mode. Re-run this tool or use Sonicake Manager to flash a firmware.")
        if label == "version":
            continue                                   # the pedal answers 14 08 01 here in the official update too
        tries = 0
        while reply == b"\x14\x08\x01" and label.endswith("data") and tries < 5:   # rejected packet: send it again
            tries += 1; time.sleep(0.05); reply = link.send(frame, timeout, ack_only=True)
        if tries: print(f"\n  {label} frame {done}: resent {tries}x -> {reply.hex() if reply else None}", flush=True)
        if reply != b"\x14\x08\x00":
            sys.exit(f"\nSTOPPED at {label} (frame {done}/{total}): pedal answered {reply.hex()}.\n"
                     "The pedal stays in update mode. Re-run this tool or use Sonicake Manager to flash a firmware.")
        if done % 2000 == 0 or label.endswith("end"):
            el = time.time() - t0
            print(f"\r  {label:22s} {done}/{total} frames  {100 * done / total:5.1f}%  {el:5.0f}s", end="", flush=True)
    print(f"\nDONE in {time.time() - t0:.0f}s. Tap OK on the pedal NOW to reboot it (if you wait, the pedal switches itself off).")
    link.close()


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == "check":
        sys.exit(0 if check(a[1]) else 1)
    if len(a) >= 2 and a[0] == "flash":
        flash(a[1], assume_yes="--yes" in a)
        sys.exit(0)
    sys.exit(__doc__)
