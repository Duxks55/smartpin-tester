#!/usr/bin/env python3
"""
SmartPin Full System Test
Tests MUXes, Discharge, ADC, and prepares for BJT / Capacitor testing.
"""

import time
import RPi.GPIO as GPIO
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# ================== PIN DEFINITIONS ==================
MUX1_S0 = 4; MUX1_S1 = 5; MUX1_S2 = 6; MUX1_EN = 18
MUX2_S0 = 7; MUX2_S1 = 8; MUX2_S2 = 9; MUX2_EN = 19
DISCHARGE_PIN = 27

# ADS1115 Setup
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
ads.gain = 1
chan = AnalogIn(ads, ADS.P0)

# GPIO Setup
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
pins = [MUX1_S0, MUX1_S1, MUX1_S2, MUX1_EN, MUX2_S0, MUX2_S1, MUX2_S2, MUX2_EN, DISCHARGE_PIN]
for p in pins:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, GPIO.HIGH)

def set_mux(mux_num, channel):
    if channel < 0 or channel > 7:
        return False
    s0 = (channel >> 0) & 1
    s1 = (channel >> 1) & 1
    s2 = (channel >> 2) & 1
    if mux_num == 1:
        GPIO.output([MUX1_S0, MUX1_S1, MUX1_S2], [s0, s1, s2])
        GPIO.output(MUX1_EN, GPIO.LOW)
        GPIO.output(MUX2_EN, GPIO.HIGH)
    else:
        GPIO.output([MUX2_S0, MUX2_S1, MUX2_S2], [s0, s1, s2])
        GPIO.output(MUX2_EN, GPIO.LOW)
        GPIO.output(MUX1_EN, GPIO.HIGH)
    time.sleep(0.05)
    return True

def read_voltage():
    return chan.voltage

def discharge(duration=0.5):
    print(f"Discharging for {duration}s...")
    GPIO.output(DISCHARGE_PIN, GPIO.HIGH)
    time.sleep(duration)
    GPIO.output(DISCHARGE_PIN, GPIO.LOW)
    time.sleep(0.2)
    return read_voltage()

def test_mux(mux_num, name):
    print(f"\n--- Testing {name} ---")
    for ch in range(8):
        set_mux(mux_num, ch)
        time.sleep(0.12)
        v = read_voltage()
        print(f"  Ch {ch:2d} → {v:.4f} V")

# ================== MAIN FULL TEST ==================
def run_full_test():
    print("=== SmartPin Full System Test Started ===")
    print("External 5V power should be ON.")
    print("=" * 70)
    
    # Initial discharge
    post_discharge = discharge()
    print(f"Voltage after initial discharge: {post_discharge:.4f}V\n")
    
    # Test both MUXes
    test_mux(1, "MUX1")
    test_mux(2, "MUX2")
    
    # Signal path test
    print("\n--- MUX2 Y0 → MUX1 Y0 Path Test ---")
    set_mux(2, 0)
    time.sleep(0.2)
    print(f"Path voltage: {read_voltage():.4f}V")
    
    # Discharge + re-test
    print("\n--- Discharge + MUX2 Y3 Test (as per wiring) ---")
    discharge(0.4)
    set_mux(2, 3)
    time.sleep(0.2)
    print(f"After discharge on Y3 path: {read_voltage():.4f}V")
    
    print("\n=== Full System Test Complete ===")
    print("Use this output to identify bad MUX2 channels.")
    print("Good channels can be used immediately for BJT/Cap testing.")

if __name__ == "__main__":
    try:
        run_full_test()
    except KeyboardInterrupt:
        print("\nTest stopped.")
    finally:
        GPIO.cleanup()
        print("GPIO cleaned up.")
