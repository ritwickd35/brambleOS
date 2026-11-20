cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
timeout 20 tools/.venv/bin/python tools/pmpreset.py select 50 >/dev/null 2>&1
tools/.venv/bin/python -u tools/pmflash.py flash "$1" --yes > logs/flash-last.log 2>&1
grep -E "DONE in|STOPPED" logs/flash-last.log | tail -1 | cut -c1-40
n=0; until timeout 9 tools/.venv/bin/python -u tools/pmmode.py 2>/dev/null | tail -1 | grep -q "APP mode"; do n=$((n+1)); [ $n -gt 30 ] && { echo "did not boot"; break; }; sleep 10; done
sleep 15; tools/.venv/bin/python tools/audio_ok.py 2>&1 | tail -1
