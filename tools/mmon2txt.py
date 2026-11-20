#!/usr/bin/env python3
"""Convert MIDI Monitor (.mmon) sessions to plain text: one message per line.
   usage: mmon2txt.py file.mmon [> out.txt]
   line format: <seconds since first msg> <dir> <hex bytes>   dir: '>' = Mac->pedal, '<' = pedal->Mac
"""
import plistlib, sys

def load(path):
    outer = plistlib.load(open(path, "rb"))
    ar = plistlib.loads(outer["messageData"])
    objs = ar["$objects"]
    def R(x):
        return objs[x.data] if isinstance(x, plistlib.UID) else x
    root = R(ar["$top"]["root"])
    msgs = [R(u) for u in R(root)["NS.objects"]] if "NS.objects" in R(root) else []
    out = []
    for m in msgs:
        cls = R(m["$class"])["$classname"]
        ts = m.get("timeStampInNanos") or 0
        ep = R(m.get("originatingEndpoint"))
        epname = ""
        if isinstance(ep, dict):
            epname = R(ep.get("name", "")) if "name" in ep else ""
            if not epname:
                for k, v in ep.items():
                    v = R(v)
                    if isinstance(v, str) and "Pocket" in v:
                        epname = v
        elif isinstance(ep, str):
            epname = ep
        status = m.get("statusByte", 0)
        if cls == "SMSystemExclusiveMessage":
            data = R(m.get("data"))
            if isinstance(data, dict):
                data = data.get("NS.data", b"")
            body = bytes([0xF0]) + bytes(data) + (b"" if bytes(data)[-1:] == b"\xf7" else bytes([0xF7]))
        else:
            body = bytes([status]) + bytes([b for b in (m.get("dataByte1"), m.get("dataByte2")) if isinstance(b, int)])
        d = ">" if epname.startswith("To") else "<"
        out.append((ts, d, cls, epname, body))
    return out

if __name__ == "__main__":
    msgs = load(sys.argv[1])
    t0 = msgs[0][0] if msgs else 0
    for ts, d, cls, ep, body in msgs:
        print(f"{(ts - t0) / 1e9:10.4f} {d} {body.hex(' ')}")
