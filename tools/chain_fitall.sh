cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
for a in twin tweed bassman ac30n ac30tb jc120 jtm45 plexi iicplus slo100 friedman recto 5150 vh4 svt; do
  tools/.venv/bin/python -u tools/ampfit.py fit $a 200 > logs/fit-$a.log 2>&1
  tools/.venv/bin/python tools/ampcmp.py $a amps/$a.fit.json > logs/cmp-$a.log 2>&1
  echo "$(date +%T) fit $a: $(awk '{print $9}' logs/cmp-$a.log | tr '\n' ' ') dB tone diff" >> logs/work.log
done
echo "$(date +%T) FIT ALL DONE" >> logs/work.log
