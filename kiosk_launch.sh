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

# Continuous kiosk loop: keeps launching the app, handles clean restarts on update
while true; do
    /home/tpj655/smartpin-tester/dist/smartpin_master/smartpin_master
    # If the app exits normally (like when clicking update), wait 3 seconds 
    # for update_kiosk.sh to finish building, then loop to restart the new version.
    sleep 3
done
