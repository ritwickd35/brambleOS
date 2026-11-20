#!/bin/sh
cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
L=logs/work.log; PY=tools/.venv/bin/python
s() { echo "$(date +%H:%M:%S) $*" | tee -a $L; }
s "engine probe, long recording"; EPROBE_SECONDS=150 $PY -u tools/eprobe_run.py > logs/eprobe-run2.log 2>&1; grep -E "eprobe|restored|Error" logs/eprobe-run2.log >> $L
timeout 20 $PY tools/pmpreset.py select 50 >> $L 2>&1
s "EPROBE2 DONE"
