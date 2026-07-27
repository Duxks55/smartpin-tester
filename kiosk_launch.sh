#!/bin/bash

# Prevent screen blanking
xset s off
xset -dpms
xset s noblank

# Start window manager in background if not already running
if ! pgrep -x "matchbox-window" > /dev/null; then
    matchbox-window-manager -use_titlebar no &
fi

export DISPLAY=:0

# Continuous kiosk loop using the virtual environment python
while true; do
    /home/tpj655/smartpin-env/bin/python /home/tpj655/smartpin-tester/smartpin_master.py
    # If the app exits normally (like when clicking update), wait 3 seconds
    # for update_kiosk.sh to finish, then loop to restart the new version.
    sleep 3
done
