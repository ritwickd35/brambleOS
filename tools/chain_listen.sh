#!/bin/sh
# after the v3 batch: record pedal clips (Sonicake, ours v2, ours v3) of 4 captures for the listening test
cd "$(dirname "$0")/.."
true
echo "$(date +%T) === pedal clips for the listening test (Sonicake / v2 / v3)" >> logs/nam2clo.log
M="/Users/ritwickdas/Downloads/MES DRECF RD Gain2 BAL O808 CAB.nam"
TAGS="ours-v2+ours-v3" nice tools/.venv/bin/python -u tools/clone_pedal_ab.py "mes=$M,cloFile.clo,clones/mes.clo+clones3/mes.clo" \
  "19=$(ls nams2/19/*.nam),nams2/19/cloFile.clo,clones/19.clo+clones3/19.clo" \
  "1071=$(ls nams2/1071/*.nam),nams2/1071/cloFile.clo,clones/1071.clo+clones3/1071.clo" \
  "1882=$(ls nams2/1882/*.nam),nams2/1882/cloFile.clo,clones/1882.clo+clones3/1882.clo" 2>&1 | grep --line-buffered -v -i warn >> logs/nam2clo.log
echo "$(date +%T) LISTEN CLIPS DONE" | tee -a logs/nam2clo.log >> logs/work.log
