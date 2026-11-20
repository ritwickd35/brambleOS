cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
tools/.venv/bin/python -u tools/space_bench.py record build/fx2e/src/4_effect_db_presets_00190000.bin stock > logs/bench-stock.log 2>&1
echo "$(date +%T) BENCH REC DONE" >> logs/work.log
