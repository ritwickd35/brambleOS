cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
tools/.venv/bin/python -u tools/night_test.py run 10 > logs/night/run.log 2>&1
tools/.venv/bin/python tools/night_test.py summary > logs/night/summary.txt 2>&1
echo "$(date +%T) NIGHT TEST DONE" >> logs/work.log
