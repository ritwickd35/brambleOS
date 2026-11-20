#!/usr/bin/env python3
"""Pocket Master backup: READ-ONLY.

Saves everything the pedal reports over USB into a timestamped folder next to this script's parent:
  device info, preset name list, all presets (494-byte records), user IR list, clone list,
  current preset, and two status reports (12 41 / 12 45, raw).

Only "read" commands (class 0x12) are ever sent. Close Sonicake Manager first.
Safety: refuses to run while Sonicake Manager is open, retries a request once after a pause, and stops
if the pedal still does not answer. Do not operate the pedal while it runs (~10 s).
usage:  tools/.venv/bin/python -u tools/pmbackup.py
"""
import json, os, struct, subprocess, sys, time
sys.path.insert(0, os.path.dirname(__file__))
import mido
import pmsysex as P

READ_ONLY = {0x10, 0x20, 0x24, 0x30, 0x40, 0x41, 0x43, 0x45, 0x4F}   # the only objects we may ask for


def find(names):
    return next((n for n in names if "Pocket Master" in n), None)


class Pedal:
    def __init__(self):
        o, i = find(mido.get_output_names()), find(mido.get_input_names())
        if not (o and i):
            sys.exit("Pocket Master not found on USB. Is it switched on and connected?")
        self.out, self.inp = mido.open_output(o), mido.open_input(i)
        time.sleep(0.5)                               # the first message after opening the port gets lost otherwise
        while self.inp.poll() is not None:            # drop anything queued
            pass

    def ask(self, obj, data=b"", timeout=1.5, tries=2):
        assert obj in READ_ONLY, "refusing to send a non-read command"
        cmd = bytes((0x12, obj))
        for _ in range(tries):
            for fr in P.build_message(cmd, data):
                self.out.send(mido.Message.from_bytes(list(fr)))
            buf, expect, t_end = bytearray(), None, time.time() + timeout
            while time.time() < t_end:
                msg = self.inp.poll()
                if msg is None:
                    time.sleep(0.002); continue
                if msg.type != "sysex":
                    continue
                f = P.parse_frame(bytes([0xF0]) + bytes(msg.data) + b"\xf7")
                if not f["ok"]:
                    continue
                p = f["payload"]
                if f["index"] == 0:
                    if p[:2] not in (cmd, bytes((0x11, obj))):
                        continue                        # ACKs, events, other replies
                    buf, expect = bytearray(p), f["count"]
                elif expect is not None:
                    buf += p
                if expect is not None and f["index"] == expect - 1:
                    return bytes(buf[2:])
            time.sleep(0.3)                             # one calm retry, then give up
        raise TimeoutError(f"no reply to 12 {obj:02x}; stopping (pedal busy or stuck?)")


def tlv(b):
    out, i = [], 0
    while i + 4 <= len(b):
        tag, ln = struct.unpack_from("<HH", b, i)
        out.append((tag, b[i + 4:i + 4 + ln])); i += 4 + ln
    return out


def slots(b):
    return [{"slot": k + 1, "empty": bool(b[k]), "name": b[5 + 16 * k:21 + 16 * k].split(b"\0")[0].decode(errors="replace")}
            for k in range(5)]


def main():
    if subprocess.run(["pgrep", "-f", "Sonicake Manager.app"], capture_output=True).returncode == 0:
        sys.exit("Sonicake Manager is running. Quit it (Cmd+Q) first, so only one program talks to the pedal.")
    print("Reading from the pedal (~10 s). Please do not touch the pedal until it says 'Backup complete'.")
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backups",
                        time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(os.path.join(root, "presets"))
    pd = Pedal()
    save = lambda name, b: open(os.path.join(root, name), "wb").write(b)

    hs = pd.ask(0x30, tries=2); save("handshake.bin", hs)   # handshake only: one retry allowed
    if hs[1:2] != b"\x00":
        sys.exit(f"pedal is not in normal (app) mode: {hs.hex()}")
    info = pd.ask(0x10); save("device_info.bin", info)
    info_t = {f"{t:#06x}": v.hex() for t, v in tlv(info)}
    count = next((v[0] for t, v in tlv(info) if t == 0x0203), 100)
    names = pd.ask(0x40); save("preset_names.bin", names)
    ir = pd.ask(0x20); save("ir_list.bin", ir)
    cl = pd.ask(0x24); save("clone_list.bin", cl)
    cur = pd.ask(0x43); save("current_preset.bin", cur)
    for obj in (0x41, 0x45):
        save(f"report_12{obj:02x}.bin", pd.ask(obj))

    plist = []
    for i in range(count):
        rec = pd.ask(0x4F, struct.pack("<I", i))
        nm = rec[4:20].split(b"\0")[0].decode(errors="replace")
        safe = "".join(c if c.isalnum() or c in " -_." else "_" for c in nm).strip() or "unnamed"
        save(os.path.join("presets", f"{i + 1:03d} {safe}.bin"), rec)
        plist.append({"index": i, "slot": i + 1, "name": nm, "bytes": len(rec)})
        print(f"\r  preset {i + 1}/{count}  {nm:16s}", end="")
        time.sleep(0.02)
    print()

    summary = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "device_info_tlv": info_t, "preset_count": count,
               "current_preset_index": struct.unpack("<I", cur[:4])[0] if len(cur) >= 4 else None,
               "presets": plist, "user_irs": slots(ir), "clones": slots(cl)}
    json.dump(summary, open(os.path.join(root, "summary.json"), "w"), indent=2, ensure_ascii=False)
    print(f"Backup complete: {root}")
    print(f"  {count} presets, IR slots {[s['name'] for s in slots(ir)]}, clone slots {[s['name'] for s in slots(cl)]}")


if __name__ == "__main__":
    try:
        main()
    except TimeoutError as e:
        sys.exit(f"STOPPED: {e}. Nothing was changed on the pedal.")
