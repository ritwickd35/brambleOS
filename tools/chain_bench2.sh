cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
rm -rf audio/bench-stock2
BENCH_ONLY="8:0,8:1,8:2,8:3,8:4,8:5,8:6,8:7,8:8,8:9,8:10,8:11,8:12,8:13,8:14" tools/.venv/bin/python -u tools/space_bench.py record build/safe1/src/4_effect_db_presets_00190000.bin stock2 > logs/bench-stock2.log 2>&1
tools/.venv/bin/python tools/space_bench.py report stock2 > logs/bench-stock2-report.txt 2>&1
echo "$(date +%T) BENCH2 DONE" >> logs/work.log
