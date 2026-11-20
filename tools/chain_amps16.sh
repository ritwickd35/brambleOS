cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
echo "$(date +%T) amps16 capture: start" >> logs/work.log
AMPCAP_TAG=-amps16 AMPCAP_DB=build/amps16/src/4_effect_db_presets_00190000.bin tools/.venv/bin/python -u tools/amp_capture.py > logs/ampcap-amps16.log 2>&1
echo "$(date +%T) amps16 capture: done ($(grep -c level logs/ampcap-amps16.log) takes)" >> logs/work.log
