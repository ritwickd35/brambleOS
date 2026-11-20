#!/usr/bin/env python3
"""Pocket Master SysEx protocol codec (reverse engineered from Sonicake Manager 1.5.2 captures).

Frame (on the wire): F0 <nibbles...> F7. Every logical byte is sent as two 7-bit-safe bytes: high nibble, low nibble.
Logical frame: crc8 | count | index | length | payload[length]
  crc8   = CRC-8 (poly 0x07, init 0x00, no reflection, no xorout) over count|index|length|payload
  count  = number of frames in this message (1..254), index = 0..count-1; count=0xFF marks a bulk stream
  payload of frame 0 starts with the 2-byte command; later frames continue the data.
"""
import sys

def crc8(data, poly=0x07):
    c = 0
    for b in data:
        c ^= b
        for _ in range(8):
            c = ((c << 1) ^ poly) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    return c

def unnibble(raw):           # raw = bytes between F0 and F7
    return bytes((raw[i] << 4) | raw[i + 1] for i in range(0, len(raw) - 1, 2))

def nibble(data):
    out = bytearray()
    for b in data:
        out += bytes((b >> 4, b & 0xF))
    return bytes(out)

def parse_frame(sysex):      # sysex includes F0..F7
    by = unnibble(sysex[1:-1])
    ck, cnt, idx, ln = by[0], by[1], by[2], by[3]
    payload = by[4:4 + ln]
    return dict(ok=crc8(by[1:]) == ck, count=cnt, index=idx, length=ln, payload=payload)

def build_frame(count, index, payload):
    body = bytes((count, index, len(payload))) + payload
    return b"\xf0" + nibble(bytes((crc8(body),)) + body) + b"\xf7"

def build_message(cmd, data=b"", chunk=19):
    """Split cmd+data into frames of up to `chunk` payload bytes (19 is what the app uses)."""
    blob = bytes(cmd) + bytes(data)
    parts = [blob[i:i + chunk] for i in range(0, len(blob), chunk)] or [b""]
    return [build_frame(len(parts), i, p) for i, p in enumerate(parts)]

def read_txt(path):
    """Yield (t, dir, frame-dict) from tools/mmon2txt.py output."""
    for line in open(path):
        p = line.split()
        if len(p) < 3:
            continue
        b = bytes.fromhex("".join(p[2:]))
        if b[:1] == b"\xf0":
            yield float(p[0]), p[1], parse_frame(b)

def messages(path):
    """Reassemble messages per direction. Yields (t, dir, cmd(hex), data, nframes, all_crc_ok).
    Normal messages: count = number of frames (1..254), index 0..count-1, frame 0 starts with the 2-byte command.
    Bulk stream (firmware sections): count = 0xFF and index wraps 0..255; the stream's first 2 bytes are the
    command (0x11 <section type>). Stream frames are yielded per 255-frame group as cmd='stream'."""
    pend = {}
    for t, d, f in read_txt(path):
        if f["count"] == 0xFF:
            m = pend.get(("s", d))
            if m is None:
                m = pend[("s", d)] = [t, bytearray(), 0, True]
            m[1] += f["payload"]; m[2] += 1; m[3] &= f["ok"]
            if f["index"] == 0xFE:
                yield m[0], d, "stream", bytes(m[1]), m[2], m[3]
                del pend[("s", d)]
            continue
        if ("s", d) in pend:
            m = pend.pop(("s", d))
            yield m[0], d, "stream", bytes(m[1]), m[2], m[3]
        if f["index"] == 0:
            pend[d] = [t, f["count"], bytearray(), 0, True]
        if d not in pend:
            continue
        m = pend[d]
        m[2] += f["payload"]; m[3] += 1; m[4] &= f["ok"]
        if f["index"] == m[1] - 1:
            blob = bytes(m[2])
            yield m[0], d, blob[:2].hex(), blob[2:], m[3], m[4]
            del pend[d]

if __name__ == "__main__":
    for t, d, cmd, data, n, ok in messages(sys.argv[1]):
        shown = data[:48].hex(" ")
        txt = "".join(chr(c) if 32 <= c < 127 else "." for c in data[:48])
        print(f"{t:9.3f} {d} cmd={cmd} len={len(data):6d} frames={n:4d}{'' if ok else ' CRC!'}  {shown}{' …' if len(data) > 48 else ''}  |{txt}|")
