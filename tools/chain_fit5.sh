cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
cp amps/jtm45.fit.json amps/jtm45.fit.try4.json; cp amps/jtm45.json amps/jtm45.json.orig4; cp amps/jtm45.json.olp amps/jtm45.json
tools/.venv/bin/python -u tools/ampfit.py fit jtm45 250 > logs/fit-jtm45e.log 2>&1
cp amps/jtm45.json.orig4 amps/jtm45.json
tools/.venv/bin/python tools/ampcmp.py jtm45 amps/jtm45.fit.json > logs/cmp-jtm45e.log 2>&1
echo "$(date +%T) FIT6 DONE" >> logs/work.log
