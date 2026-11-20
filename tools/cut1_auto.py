#!/usr/bin/env python3
"""Cut 1 unattended runner.

Waits for the pedal on USB, then:
  APP mode    -> automated CPU test:
                 remember current preset, start tone+recording (pmloadtest), write the test preset into slot P100
                 (index 99, a duplicate factory preset; backed up), make sure it is active, wait, analyse,
                 then restore P100 from the backup and re-select the original preset, and verify.
  UPDATE mode -> the cut1 firmware is not booting: re-flash the known-good cut2 (English) firmware.
Everything is logged to re/logs/cut1-auto.log.
"""
import os, subprocess, sys, time, struct
HERE = os.path.dirname(os.path.abspath(__file__))
RE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pmsysex as P
import pmpreset
from pmflash import Link, flash

LOG = os.path.join(RE, "logs", "cut1-auto.log")
BACKUP_P100 = os.path.join(RE, "backups", "20261117-163745", "presets", "100 Bass Q.bin")
TEST_PRESET = os.path.join(RE, "cut1", "preset-cputest.bin")
GOOD_FW = os.path.join(RE, "build", "cut2", "Pocket Master Firmware V1.3.3-cut2-english.bin")
PY = os.path.join(HERE, ".venv", "bin", "python")


def log(*a):
    s = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
    print(s, flush=True)
    open(LOG, "a").write(s + "\n")


def mode():
    try:
        link = Link(wait_s=1)
    except Exception:
        return None, None
    hs = None
    for _ in range(3):
        hs = link.send(P.build_message(b"\x12\x30")[0], 1.0)
        if hs:
            break
    if not hs:
        link.close(); return "silent", None
    m = "app" if hs[3:4] == b"\x00" else "update"
    if m == "update":
        link.close(); return m, None
    return m, link


def wait_for_pedal(max_s=3600):
    t0 = time.time(); last = None
    while time.time() - t0 < max_s:
        m, link = mode()
        if m != last:
            log("pedal state:", m or "not on USB"); last = m
        if m == "app":
            time.sleep(5)                                      # let it settle, then confirm
            link.close()
            m2, link = mode()
            if m2 == "app":
                return "app", link
        elif m == "update":
            return "update", None
        time.sleep(2)
    return None, None


def autotest(link):
    orig = pmpreset.current(link)
    log("current preset index:", orig)
    if orig is None:
        log("cannot read current preset; abort test"); return
    link.close()
    rec = subprocess.Popen([PY, "-u", os.path.join(HERE, "pmloadtest.py"), "run", "110"],
                           stdout=open(os.path.join(RE, "logs", "cut1-loadtest.log"), "w"), stderr=subprocess.STDOUT)
    time.sleep(4)
    link = Link()
    rec_bytes = open(TEST_PRESET, "rb").read()
    pmpreset.write_message(link, b"\x11\x4f", struct.pack("<I", 99) + rec_bytes[4:])
    time.sleep(0.5)
    cur = pmpreset.current(link)
    log("test preset written to P100; current preset now", cur)
    if cur != 99:
        pmpreset.write_message(link, b"\x11\x43", struct.pack("<I", 99))
        time.sleep(0.5); cur = pmpreset.current(link); log("selected P100; current preset now", cur)
    link.close()
    log("CPU test running (about 110 s) ...")
    rec.wait()
    log("recording finished; analysis:")
    for line in open(os.path.join(RE, "logs", "cut1-loadtest.log")):
        if "cycle" in line or "glitch events" in line or "no marker" in line:
            log("   " + line.rstrip())
    # restore
    link = Link()
    pmpreset.write_message(link, b"\x11\x4f", struct.pack("<I", 99) + open(BACKUP_P100, "rb").read()[4:])
    time.sleep(0.5)
    pmpreset.write_message(link, b"\x11\x43", struct.pack("<I", orig))
    time.sleep(0.5)
    back = pmpreset.ask(link, 0x4F, struct.pack("<I", 99))
    ok = back is not None and back[4:] == open(BACKUP_P100, "rb").read()[4:]
    log("P100 restored from backup:", "OK (byte-identical)" if ok else "MISMATCH")
    log("current preset back to", pmpreset.current(link), "(was", orig, ")")
    link.close()


def record_only(link):
    link.close()
    log("recording only (the test effect is already in the current preset); about 140 s ...")
    r = subprocess.run([PY, "-u", os.path.join(HERE, "pmloadtest.py"), "run", "140"],
                       stdout=open(os.path.join(RE, "logs", "cut1-loadtest.log"), "w"), stderr=subprocess.STDOUT)
    for line in open(os.path.join(RE, "logs", "cut1-loadtest.log")):
        if "cycle" in line or "glitch events" in line or "no marker" in line:
            log("   " + line.rstrip())


def main():
    log("watcher started", " ".join(sys.argv[1:]))
    if len(sys.argv) > 2 and sys.argv[1] == "--flash":
        fw = sys.argv[2]
        log("flashing", os.path.basename(fw))
        flash(fw, assume_yes=True)
        log("flash done; waiting for the pedal to come back (switch it on if it turned off)")
        time.sleep(10)
    m, link = wait_for_pedal()
    if m == "app" and "--record-only" in sys.argv:
        record_only(link)
    elif m == "app":
        autotest(link)
    elif m == "update":
        log("pedal is in UPDATE mode -> cut1 does not boot; re-flashing known-good cut2 (English)")
        flash(GOOD_FW, assume_yes=True)
        log("re-flash done; waiting for app mode")
        m2, link = wait_for_pedal(300)
        log("after re-flash:", m2)
        if link:
            link.close()
    else:
        log("pedal did not appear within an hour")
    log("watcher finished")


if __name__ == "__main__":
    main()
