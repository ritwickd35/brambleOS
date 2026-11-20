#!/bin/sh
# score Sonicake's own conversions (nams2/<id>/cloFile.clo) the same way as ours
cd "$(dirname "$0")/.."
for d in nams2/*/; do
  id=$(basename $d); nam=$(ls $d*.nam | head -1)
  r=$(OMP_NUM_THREADS=2 nice -n 15 tools/.venv/bin/python tools/clone_score.py ${d}cloFile.clo "$nam" 6.27 2>/dev/null | tail -1)
  echo "$(date +%T) SONICAKE $id: $r" | tee -a logs/nam2clo.log >> logs/work.log
done
echo "$(date +%T) SONICAKE DONE" | tee -a logs/nam2clo.log >> logs/work.log
