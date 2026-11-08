#!/bin/bash

# Prevent screen blanking and power management on the 7-inch display
xset s off
xset -dpms
xset s noblank

# Start lightweight matchbox window manager in the background if not already running
if ! pgrep -x "matchbox-window" > /dev/null; then
    matchbox-window-manager -use_titlebar no &
fi

# Target the physical local display
export DISPLAY=:0

# Load secret environment variables (e.g. GEMINI_API_KEY) from local .env file if present
if [ -f /home/tpj655/smartpin-tester/.env ]; then
    export $(grep -v '^#' /home/tpj655/smartpin-tester/.env | xargs)
fi

# Continuous kiosk loop using the component_tester_env Python binary
while true; do
    /home/tpj655/component_tester_env/bin/python3 /home/tpj655/smartpin-tester/smartpin_master.py
    # If the app exits normally (like after clicking update), wait 3 seconds
    # for update_kiosk.sh to finish, then loop to restart the new version.
    sleep 3
done
