#!/bin/sh
cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
L=logs/chain-cfw.log; PY=tools/.venv/bin/python
echo "$(date +%H:%M:%S) CFW sound baseline: 1/2 drives + amps" >> $L
AUDIT_TAG=-cfw $PY -u tools/audit.py run > logs/audit-cfw.stdout 2>&1
echo "$(date +%H:%M:%S) CFW sound baseline: 2/2 effects + remaining amps" >> $L
AUDIT_TAG=-cfw $PY -u tools/audit_fx.py run > logs/audit-fx-cfw.stdout 2>&1
echo "$(date +%H:%M:%S) CFW SOUND BASELINE DONE" >> $L
osascript -e 'display notification "CFW sound baseline finished" with title "Pocket Master"'
