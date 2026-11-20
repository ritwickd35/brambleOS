cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
until grep -q "FIT ALL DONE" logs/work.log; do sleep 60; done
for a in plexi jtm45; do
  tools/.venv/bin/python -u tools/ampfit.py fit $a 350 > logs/fit-$a.log 2>&1
  tools/.venv/bin/python tools/ampcmp.py $a amps/$a.fit.json > logs/cmp-$a.log 2>&1
  echo "$(date +%T) refit $a done" >> logs/work.log
done
echo "$(date +%T) FIT2 DONE" >> logs/work.log
