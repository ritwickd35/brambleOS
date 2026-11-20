#!/bin/sh
# own-engine converter: fit the 4 listening captures in parallel, then score them and the stock-format clones
# (Sonicake, our v3) with the same measures (accuracy, tone, dynamics, fizz, crest, level)
cd "$(dirname "$0")/.."; L=logs/nam2clo.log
echo "$(date +%T) === own-engine model (nam2amp): fit mes, 19, 1071, 1882 in parallel" >> $L
M="/Users/ritwickdas/Downloads/MES DRECF RD Gain2 BAL O808 CAB.nam"
for id in mes 19 1071 1882; do
  nam=$([ $id = mes ] && echo "$M" || ls nams2/$id/*.nam)
  (THREADS=2 nice tools/.venv/bin/python -u tools/nam2amp.py fit "$nam" $id 1500 2>&1 | grep --line-buffered -v -i warn >> $L
   r=$(nice tools/.venv/bin/python tools/nam2amp.py score "$nam" $id 2>/dev/null | tail -1); echo "$(date +%T) NAMX $id ours-engine: $r" | tee -a $L >> logs/work.log) &
done
wait
for id in mes 19 1071 1882; do
  nam=$([ $id = mes ] && echo "$M" || ls nams2/$id/*.nam); sc=$([ $id = mes ] && echo cloFile.clo || echo nams2/$id/cloFile.clo)
  for who in sonicake:$sc v3:clones4/$id.clo; do
    r=$(nice tools/.venv/bin/python tools/nam2amp.py score_clone ${who#*:} "$nam" 2>/dev/null | tail -1); echo "$(date +%T) NAMX $id ${who%%:*}: $r" | tee -a $L >> logs/work.log
  done
done
echo "$(date +%T) NAMX DONE" | tee -a $L >> logs/work.log
