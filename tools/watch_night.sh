cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
while true; do
  clear; echo "Overnight test  $(date +%T)   (Ctrl-C closes this window only)"; echo
  n=$(wc -l < logs/night/results.jsonl 2>/dev/null); echo "takes so far: $n   (about 531 per round, 10 rounds)"
  tail -3 logs/night/events.log 2>/dev/null; echo
  tools/.venv/bin/python tools/night_test.py summary 2>/dev/null | head -14
  echo; echo "last take:"; tail -1 logs/night/results.jsonl 2>/dev/null | cut -c1-150
  echo; echo "NAM fit: $(tail -1 logs/nam2pedal-recto808.log 2>/dev/null | cut -c1-90)"
  sleep 30
done
