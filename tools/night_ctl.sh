# night_ctl.sh pause   -> waits until the overnight test has parked (P08 restored), then returns
# night_ctl.sh resume  -> lets it continue (flash the normal build back first: sh tools/reflash.sh build/dl14/...)
cd "/Users/ritwickdas/Downloads/Pocket Master Firmware V1.3.0/re"
case "$1" in
  pause) touch logs/night/PAUSE; n=0; until [ -f logs/night/PAUSED ]; do sleep 3; n=$((n+1)); [ $n -gt 200 ] && { echo "test not responding"; exit 1; }; done; echo "test paused";;
  resume) rm -f logs/night/PAUSE; echo "resumed";;
esac
