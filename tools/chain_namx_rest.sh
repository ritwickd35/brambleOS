#!/bin/sh
# resume: own engine for the 3 captures that never ran + Bassman with a broader start search (skip finished ones)
cd "$(dirname "$0")/.."; L=logs/nam2clo.log
echo "$(date +%T) === resume: 33505 41359 51649 + Bassman broad search" >> $L
run() { id=$1; inits=$2; nam=$(ls nams2/$id/*.nam)
  INITS=$inits TRIAL=200 CABFIRST=1 THREADS=3 nice tools/.venv/bin/python -u tools/nam2amp.py fit "$nam" $id 1500 2>&1 | grep --line-buffered -v -i warn >> $L
  r=$(nice tools/.venv/bin/python tools/nam2amp.py score "$nam" $id 2>/dev/null | tail -1); echo "$(date +%T) NAMX $id ours-engine: $r" | tee -a $L >> logs/work.log; }
run 33505 recto,5150,jcm800,vh4,friedman,plexi,twin &
run 41359 recto,5150,jcm800,vh4,friedman,plexi,twin &
run 51649 recto,5150,jcm800,vh4,friedman,plexi,twin &
cp amps/namx_1882.json amps/namx_1882_prev.json
run 1882 bassman,tweed,jcm800,plexi,twin,jtm45,ac30n,svt,recto,5150 &
wait; echo "$(date +%T) NAMX REST DONE" | tee -a $L >> logs/work.log
