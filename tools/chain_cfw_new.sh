#!/bin/sh
cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
L=logs/chain-cfw.log
until grep -q "CFW SOUND BASELINE DONE" $L; do sleep 20; done
echo "$(date +%H:%M:%S) CFW sound baseline, part 3: the CFW's own new effects and amps" >> $L
AUDIT_TAG=-cfwnew AUDIT_SET=cfw-new tools/.venv/bin/python -u tools/audit_fx.py run > logs/audit-fx-cfwnew.stdout 2>&1
echo "$(date +%H:%M:%S) CFW NEW-EFFECTS BASELINE DONE" >> $L
osascript -e 'display notification "CFW new-effects baseline finished" with title "Pocket Master"'
