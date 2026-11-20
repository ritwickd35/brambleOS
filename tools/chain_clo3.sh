#!/bin/sh
# v3 conversion (level-balanced loss, stronger spectral term) for all captures; offline only
cd "$(dirname "$0")/.."; L=logs/nam2clo.log; mkdir -p clones3
echo "=== v3 batch $(date +%T)" >> $L
for nam in "/Users/ritwickdas/Downloads/MES DRECF RD Gain2 BAL O808 CAB.nam" nams2/*/*.nam; do
  id=$(basename "$(dirname "$nam")"); [ "$id" = "Downloads" ] && id=mes
  echo "--- v3 $id $(date +%T)" >> $L
  LR=5e-4 OMP_NUM_THREADS=4 nice tools/.venv/bin/python -u tools/nam2clo.py "$nam" clones3/$id.clo 4001 2>&1 | grep --line-buffered -v -i warn >> $L
  r=$(nice tools/.venv/bin/python tools/clone_score.py clones3/$id.clo "$nam" 6.27 2>/dev/null | tail -1)
  echo "$(date +%T) CLO3 $id: $r" | tee -a $L >> logs/work.log
done
echo "$(date +%T) CLO3 BATCH DONE" | tee -a $L >> logs/work.log
