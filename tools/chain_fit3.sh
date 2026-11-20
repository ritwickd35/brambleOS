cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
cp amps/jtm45.json amps/jtm45.json.orig; cp amps/jtm45.json.fromplexi amps/jtm45.json
tools/.venv/bin/python -u tools/ampfit.py fit jtm45 250 > logs/fit-jtm45b.log 2>&1
cp amps/jtm45.json.orig amps/jtm45.json
tools/.venv/bin/python tools/ampcmp.py jtm45 amps/jtm45.fit.json > logs/cmp-jtm45b.log 2>&1
echo "$(date +%T) FIT3 DONE" >> logs/work.log
