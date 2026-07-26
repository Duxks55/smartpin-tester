#!/bin/bash

# Prevent the ribbon cable screen from blanking or turning off due to power-saving
xset s off
xset -dpms
xset s noblank

# Start the Matchbox window manager in the background to lock the app into full-screen
matchbox-window-manager -use_titlebar no &

# Launch your compiled standalone SmartPin binary package
/home/tpj655/smartpin-tester/dist/smartpin_master/smartpin_master
