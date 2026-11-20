cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
NAM_THREADS=3 nice -n 19 tools/.venv/bin/python -u tools/nam2pedal.py fit "/Users/ritwickdas/Downloads/MES DRECF RD Gain2 BAL O808 CAB.nam" recto808 1500 > logs/nam2pedal-recto808.log 2>&1
nice -n 19 tools/.venv/bin/python tools/nam2pedal.py eval "/Users/ritwickdas/Downloads/MES DRECF RD Gain2 BAL O808 CAB.nam" recto808 >> logs/nam2pedal-recto808.log 2>&1
echo "$(date +%T) NAM FIT DONE" >> logs/work.log
