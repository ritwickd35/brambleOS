#!/bin/sh
# listening set (Sonicake / v2 / v3 = clones4) for 4 captures, ONE pedal session, test DI = R takes of all songs
cd "$(dirname "$0")/.."; L=logs/nam2clo.log
echo "$(date +%T) === listening set re-recorded (previous run collided with a UI flash, then the pedal was switched off)" >> $L
M="/Users/ritwickdas/Downloads/MES DRECF RD Gain2 BAL O808 CAB.nam"
TAGS="ours-v2+ours-v3" nice tools/.venv/bin/python -u tools/clone_pedal_ab.py "mes=$M,cloFile.clo,clones/mes.clo+clones4/mes.clo" \
  "19=$(ls nams2/19/*.nam),nams2/19/cloFile.clo,clones/19.clo+clones4/19.clo" "1071=$(ls nams2/1071/*.nam),nams2/1071/cloFile.clo,clones/1071.clo+clones4/1071.clo" \
  "1882=$(ls nams2/1882/*.nam),nams2/1882/cloFile.clo,clones/1882.clo+clones4/1882.clo" 2>&1 | grep --line-buffered -v -i warn >> $L
echo "$(date +%T) LISTEN4 DONE" | tee -a $L >> logs/work.log
