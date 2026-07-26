#!/bin/bash
INSTALL_DIR="$HOME/smartpin-tester"
cd "$INSTALL_DIR"

echo "Pulling latest changes from GitHub..."
git pull origin main

echo "Activating environment and rebuilding binary..."
source ~/component_tester_env/bin/activate
pyinstaller --noconfirm --onedir --noconsole --clean --collect-all adafruit_blinka --collect-all adafruit_ads1x15 smartpin_master.py

cp ~/component_tester_env/lib/python*/site-packages/board_imports.json ./dist/smartpin_master/_internal/

echo "Update applied and rebuilt successfully!"	
