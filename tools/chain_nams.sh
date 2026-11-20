cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
for d in nams/*/; do
  n=$(basename $d); f=$(ls $d*.nam | head -1)
  NAM_THREADS=3 nice -n 19 tools/.venv/bin/python -u tools/nam2pedal.py fit "$f" $n 1500 --amp-only > logs/nam2pedal-$n.log 2>&1
  nice -n 19 tools/.venv/bin/python tools/nam2pedal.py eval "$f" $n >> logs/nam2pedal-$n.log 2>&1
  echo "$(date +%T) NAM $n: $(tail -1 logs/nam2pedal-$n.log | cut -c1-140)" >> logs/work.log
done
echo "$(date +%T) NAM BATCH DONE" >> logs/work.log
