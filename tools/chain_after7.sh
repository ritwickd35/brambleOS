#!/bin/sh
cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
L=logs/work.log; PY=tools/.venv/bin/python
s() { echo "$(date +%H:%M:%S) $*" | tee -a $L; }
s "after-7 chain: waiting for cut7"
until grep -q "CUT7 CHAIN DONE" $L; do sleep 15; done
s "USB re-amp check"; $PY -u tools/reamp_check.py 2>&1 | tee -a logs/reamp.log | grep --line-buffered -E "reamp|restored" >> $L
s "DS-1+ debug"; $PY -u tools/ds1debug.py 2>&1 | tee -a logs/ds1debug.log | grep --line-buffered -E "debug" >> $L
s "DS-1+ / gate sound retest (cut7 modules)"; AUDIT_TAG=-cut7 $PY -u tools/test_cut5.py sound 2>&1 | tee -a logs/cut7.log | grep --line-buffered -E "restored" >> $L
cp cut1/cut5-sound.json cut1/cut7-sound.json
timeout 20 $PY tools/pmpreset.py select 50 >> $L 2>&1
s "AFTER7 DONE"
