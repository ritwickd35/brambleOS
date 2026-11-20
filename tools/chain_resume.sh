#!/bin/sh
# resume the CFW CPU tests (run 9..12, then pairs), park on F01, switch boot protection off and verify
cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
L=logs/chain-cut4b.log; PY=tools/.venv/bin/python
s() { echo "$(date +%H:%M:%S) $*" | tee -a $L logs/work.log; }
s "resume: CPU matrix on CFW, runs 9-12"
MATRIX_SKIP=8 MATRIX_JSON=matrix-results-cfw.json $PY -u tools/cut1_matrix.py 2>&1 | tee -a logs/cut1-matrix-cfw.stdout | grep --line-buffered -E "headroom|SUMMARY|restored"
s "3/3 CPU pairs on CFW"; echo "===== CFW PAIRS (cut4b) =====" >> logs/cut1-matrix.log
PAIRS_JSON=matrix-results-pairs-cfw.json $PY -u tools/cut1_matrix.py pairs 2>&1 | tee -a logs/cut1-matrix-pairs-cfw.stdout | grep --line-buffered -E "headroom|restored"
s "parking on F01"; timeout 20 $PY tools/pmpreset.py select 50 >> $L 2>&1
s "boot protection off"; timeout 30 $PY tools/pmsettings.py set 0205 0 2>&1 | tee -a $L logs/work.log
s "CUT4B CHAIN DONE"
