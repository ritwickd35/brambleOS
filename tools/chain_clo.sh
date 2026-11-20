#!/bin/sh
# convert + score every capture (offline), log to logs/nam2clo.log; summary lines in logs/work.log
cd "$(dirname "$0")/.."
L=logs/nam2clo.log; echo "=== batch $(date +%T)" >> $L
for nam in "/Users/ritwickdas/Downloads/MES DRECF RD Gain2 BAL O808 CAB.nam" nams2/*/*.nam; do
  id=$(basename "$(dirname "$nam")"); [ "$id" = "Downloads" ] && id=mes
  if grep -q "CLO $id:" logs/work.log 2>/dev/null; then echo "--- $id already done" >> $L; continue; fi
  echo "--- $id $(date +%T)" >> $L
  LR=5e-4 OMP_NUM_THREADS=4 nice tools/.venv/bin/python -u tools/nam2clo.py "$nam" clones/$id.clo 4001 >> $L 2>&1
  r=$(nice tools/.venv/bin/python tools/clone_score.py clones/$id.clo "$nam" 6.27 2>/dev/null | tail -1)
  echo "$(date +%T) CLO $id: $r $(cat clones/$id.clo.json 2>/dev/null)" | tee -a $L >> logs/work.log
done
grep -q "SONICAKE mes:" logs/work.log || { r=$(nice tools/.venv/bin/python tools/clone_score.py cloFile.clo "/Users/ritwickdas/Downloads/MES DRECF RD Gain2 BAL O808 CAB.nam" 6.27 2>/dev/null | tail -1); echo "$(date +%T) SONICAKE mes: $r" | tee -a $L >> logs/work.log; }
echo "$(date +%T) CLO BATCH DONE" | tee -a $L >> logs/work.log
