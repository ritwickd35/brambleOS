cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
tools/.venv/bin/python -u tools/space_audit.py build/fx2e/src/4_effect_db_presets_00190000.bin max > logs/space-max.log 2>&1
echo "$(date +%T) SPACE AUDIT DONE" >> logs/work.log
