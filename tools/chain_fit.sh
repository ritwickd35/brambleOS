cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
tools/.venv/bin/python -u tools/ampfit.py fit jcm800 200 > logs/fit-jcm800.log 2>&1
echo "$(date +%T) fit jcm800 done: $(grep fitted logs/fit-jcm800.log)" >> logs/work.log
