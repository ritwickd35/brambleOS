#!/bin/sh
cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
L=logs/work.log; PY=tools/.venv/bin/python
s() { echo "$(date +%H:%M:%S) $*" | tee -a $L; }
s "drive audit (rerun)"; $PY -u tools/drv_audit.py > logs/drv-audit.log 2>&1; grep -E "stock|new|bypass|restored|Error" logs/drv-audit.log >> $L
timeout 20 $PY tools/pmpreset.py select 50 >> $L 2>&1
s "DRVAUDIT DONE"
