cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
echo "$(date +%T) amp capture: start" >> logs/work.log
tools/.venv/bin/python -u tools/amp_capture.py "Dark Twin" "TWD Deluxe" "B-Man B" "Voks 30N" "Voks 30TB" "Jazz 120" "Brit 45" "Brit 50" "Calif IIC+" "Sol 100 LD" "Flyman B1+" "Calif DualM" "Halen 51" "Dizzy VH+" "A BassVT" > logs/ampcap.log 2>&1
echo "$(date +%T) amp capture: done ($(grep -c level logs/ampcap.log) takes)" >> logs/work.log
