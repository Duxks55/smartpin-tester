#!/bin/bash
cd /home/tpj655/smartpin-tester

echo "Stopping existing application instances..."
sudo pkill -f smartpin_master
sudo pkill -f python3

echo "Pulling latest changes from GitHub..."
git pull origin main

echo "Cleaning old build artifacts..."
rm -rf build dist

echo "Activating Python environment..."
source /home/tpj655/component_tester_env/bin/activate

echo "Installing/updating dependencies..."
pip install -r requirements.txt --quiet

echo "Update applied successfully! Launching application..."

export DISPLAY=:0
python3 smartpin_master.py &
