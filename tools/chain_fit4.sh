cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
cp amps/jtm45.fit.json amps/jtm45.fit.try2.json; cp amps/jtm45.json amps/jtm45.json.orig2; cp amps/jtm45.json.fromplexi2 amps/jtm45.json
tools/.venv/bin/python -u tools/ampfit.py fit jtm45 300 > logs/fit-jtm45c.log 2>&1
cp amps/jtm45.json.orig2 amps/jtm45.json
tools/.venv/bin/python tools/ampcmp.py jtm45 amps/jtm45.fit.json > logs/cmp-jtm45c.log 2>&1
echo "$(date +%T) FIT4 DONE" >> logs/work.log
