#!/bin/sh
# new split (train on the L takes, test on the R takes of every song): retrain v3 for all captures, re-score
# Sonicake + v2 + v3 on the new test set, then record the short listening set on the pedal in one session
cd "$(dirname "$0")/.."; L=logs/nam2clo.log; mkdir -p clones4
echo "$(date +%T) === new split: retrain (v3 loss) on L takes, test on R takes of all 4 songs" >> $L
NAMS="mes|/Users/ritwickdas/Downloads/MES DRECF RD Gain2 BAL O808 CAB.nam"
for d in nams2/*/; do NAMS="$NAMS
$(basename $d)|$(ls $d*.nam)"; done
echo "$NAMS" | while IFS='|' read id nam; do
  echo "$(date +%T) --- train $id" >> $L
  LR=5e-4 nice tools/.venv/bin/python -u tools/nam2clo.py "$nam" clones4/$id.clo 4001 2>&1 | grep --line-buffered -v -i warn >> $L
  sc=$( [ $id = mes ] && echo cloFile.clo || echo nams2/$id/cloFile.clo )
  for who in sonicake:$sc v2:clones/$id.clo v3:clones4/$id.clo; do
    r=$(nice tools/.venv/bin/python tools/clone_score.py ${who#*:} "$nam" 6.27 2>/dev/null | tail -1)
    echo "$(date +%T) SCORE4 $id ${who%%:*}: $r" | tee -a $L >> logs/work.log
  done
done
echo "$(date +%T) === listening set, one pedal session" >> $L
M="/Users/ritwickdas/Downloads/MES DRECF RD Gain2 BAL O808 CAB.nam"
TAGS="ours-v2+ours-v3" nice tools/.venv/bin/python -u tools/clone_pedal_ab.py "mes=$M,cloFile.clo,clones/mes.clo+clones4/mes.clo" \
  "19=$(ls nams2/19/*.nam),nams2/19/cloFile.clo,clones/19.clo+clones4/19.clo" "1071=$(ls nams2/1071/*.nam),nams2/1071/cloFile.clo,clones/1071.clo+clones4/1071.clo" \
  "1882=$(ls nams2/1882/*.nam),nams2/1882/cloFile.clo,clones/1882.clo+clones4/1882.clo" 2>&1 | grep --line-buffered -v -i warn >> $L
echo "$(date +%T) V4 ALL DONE" | tee -a $L >> logs/work.log
