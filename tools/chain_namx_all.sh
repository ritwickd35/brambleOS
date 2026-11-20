#!/bin/sh
# own engine: convert the remaining 7 captures (best of several starts, cab first for full rigs), 4 at a time
cd "$(dirname "$0")/.."; L=logs/nam2clo.log
echo "$(date +%T) === own engine: remaining 7 captures (dry run of the method passed on MES)" >> $L
run() { id=$1; nam=$(ls nams2/$id/*.nam)
  INITS=recto,5150,jcm800,vh4,friedman,plexi,twin TRIAL=200 CABFIRST=1 THREADS=3 nice tools/.venv/bin/python -u tools/nam2amp.py fit "$nam" $id 1500 2>&1 | grep --line-buffered -v -i warn >> $L
  r=$(nice tools/.venv/bin/python tools/nam2amp.py score "$nam" $id 2>/dev/null | tail -1); echo "$(date +%T) NAMX $id ours-engine: $r" | tee -a $L >> logs/work.log; }
for id in 1686 29891 30435 32868; do run $id & done; wait
for id in 33505 41359 51649; do run $id & done; wait
echo "$(date +%T) NAMX ALL DONE" | tee -a $L >> logs/work.log
