#!/bin/sh
# pedal A/B of all captures (Sonicake vs ours), recordings checked for USB sample drops
cd "$(dirname "$0")/.."
echo "=== pedal A/B (all) $(date +%T)" >> logs/nam2clo.log
M="/Users/ritwickdas/Downloads/MES DRECF RD Gain2 BAL O808 CAB.nam"; J="mes=$M,cloFile.clo,clones/mes.clo"
for d in nams2/*/; do id=$(basename $d); J="$J|$id=$(ls $d*.nam),${d}cloFile.clo,clones/$id.clo"; done
IFS='|'; set -- $J; unset IFS
SKIP_DONE=1 nice tools/.venv/bin/python -u tools/clone_pedal_ab.py "$@" 2>&1 | grep --line-buffered -v -i warn | tee -a logs/nam2clo.log | grep "PEDAL AB" >> logs/work.log
echo "$(date +%T) PEDAL AB DONE" | tee -a logs/nam2clo.log >> logs/work.log
