cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
while true; do
  clear; echo "Background work  $(date +%T)   (Ctrl-C closes this window, the work keeps running)"; echo
  echo "Running:"; pgrep -fl "ampfit.py|amp_capture.py|pmflash.py|drv_audit.py" | sed 's/^[0-9]* /  /' | cut -c1-110 || true
  pgrep -f "ampfit.py|amp_capture.py|pmflash.py|drv_audit.py" >/dev/null || echo "  nothing"
  echo; echo "Amp fits done: $(ls amps/*.fit.json 2>/dev/null | wc -l | tr -d ' ') of 16"
  cur=$(ls -t logs/fit-*.log 2>/dev/null | head -1); [ -n "$cur" ] && { echo "Current: $cur"; tail -2 "$cur" | cut -c1-110; }
  echo; echo "Recent log:"; tail -8 logs/work.log | cut -c1-110
  sleep 10
done
