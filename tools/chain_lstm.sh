#!/bin/sh
cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
L=logs/work.log; PY=tools/.venv/bin/python
s() { echo "$(date +%H:%M:%S) $*" | tee -a $L; }
[ -f audio/nam_target_44100.f32 ] || { s "lstm: computing NAM target"; $PY -u tools/lstmamp.py target > logs/lstm-target.log 2>&1; }
for cfg in "8 128" "8 192" "6 128" "10 128"; do
  s "lstm: training H/L $cfg"; $PY -u tools/lstmamp.py train $cfg 3000 > "logs/lstm-train-$(echo $cfg | tr ' ' _).log" 2>&1
  grep RESULT "logs/lstm-train-$(echo $cfg | tr ' ' _).log" >> $L
done
s "LSTM CHAIN DONE"
