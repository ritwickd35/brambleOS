#!/usr/bin/env python3
"""Pocket Master mode checker: READ-ONLY.

Every 0.5 s it sends the app's own handshake request (12 30) and prints what the pedal answers:
  APP mode     (reply 11 30 01 00): normal firmware running
  UPDATE mode  (reply 11 30 01 01): bootloader/updater waiting for firmware
  no reply / not connected
It also prints any notification the pedal sends (preset changes etc.).

It never sends anything except the 12 30 handshake. Close Sonicake Manager while it runs.
usage:  tools/.venv/bin/python -u tools/pmmode.py
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
import mido
import pmsysex as P

HANDSHAKE = P.build_message(b"\x12\x30")[0]          # the only message this tool ever sends
assert HANDSHAKE == bytes.fromhex("f0050900010000000201020300f7")

def find(names):
    return next((n for n in names if "Pocket Master" in n), None)

def main():
    print("Pocket Master mode checker (read-only). Ctrl+C to stop.")
    inp = out = None
    last_state, last_reply = None, 0.0
    while True:
        try:
            if out is None:
                oname, iname = find(mido.get_output_names()), find(mido.get_input_names())
                if oname and iname:
                    out, inp = mido.open_output(oname), mido.open_input(iname)
                    print(f"[{time.strftime('%H:%M:%S')}] connected: {oname}")
                elif last_state != "absent":
                    print(f"[{time.strftime('%H:%M:%S')}] pedal not visible on USB")
                    last_state = "absent"
            if out is not None:
                out.send(mido.Message.from_bytes(list(HANDSHAKE)))
                t_end = time.time() + 0.5
                while time.time() < t_end:
                    msg = inp.poll()
                    if msg is None:
                        time.sleep(0.01); continue
                    if msg.type != "sysex":
                        continue
                    f = P.parse_frame(bytes([0xF0]) + bytes(msg.data) + b"\xf7")
                    p = f["payload"]
                    if p[:2] == b"\x11\x30" and len(p) >= 4:
                        state = {0: "APP mode (normal firmware)", 1: "UPDATE mode (bootloader)"}.get(p[3], f"unknown mode byte {p[3]}")
                        last_reply = time.time()
                        if state != last_state:
                            print(f"[{time.strftime('%H:%M:%S')}] >>> {state}   (reply {p.hex(' ')})")
                            last_state = state
                    elif p[:2] in (b"\x12\x1b", b"\x12\x43"):
                        print(f"[{time.strftime('%H:%M:%S')}]     pedal event {p[:2].hex()} data {p[2:].hex(' ')}")
                if time.time() - last_reply > 2 and last_state != "silent":
                    print(f"[{time.strftime('%H:%M:%S')}] connected but no handshake reply")
                    last_state = "silent"
                if not find(mido.get_output_names()):
                    print(f"[{time.strftime('%H:%M:%S')}] pedal disconnected")
                    out.close(); inp.close(); out = inp = None; last_state = None
            else:
                time.sleep(0.5)
        except KeyboardInterrupt:
            break
        except Exception as e:                       # port vanished mid-call (pedal switched off)
            print(f"[{time.strftime('%H:%M:%S')}] port error: {e}")
            out = inp = None; last_state = None; time.sleep(0.5)

if __name__ == "__main__":
    main()
