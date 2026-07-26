#!/usr/bin/env python3
"""
SmartPin MUX Diagnostic Tool
Tests MUX1, MUX2, ADS1115, and signal paths.
"""

import time
import RPi.GPIO as GPIO
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# ================== PIN DEFINITIONS ==================
MUX1_S0 = 4
MUX1_S1 = 5
MUX1_S2 = 6
MUX1_EN = 18   # Active LOW

MUX2_S0 = 7
MUX2_S1 = 8
MUX2_S2 = 9
MUX2_EN = 19   # Active LOW

DISCHARGE_PIN = 27

# I2C for ADS1115
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
ads.gain = 1  # ±4.096V - change if needed

chan = AnalogIn(ads, ADS.P0)

# ================== GPIO SETUP ==================
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

for pin in [MUX1_S0, MUX1_S1, MUX1_S2, MUX1_EN,
            MUX2_S0, MUX2_S1, MUX2_S2, MUX2_EN, DISCHARGE_PIN]:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.HIGH)

def set_mux(mux_num, channel):
    """Set MUX channel (0-7). mux_num: 1 or 2"""
    if channel < 0 or channel > 7:
        print("Invalid channel!")
        return False
    
    s0 = (channel >> 0) & 1
    s1 = (channel >> 1) & 1
    s2 = (channel >> 2) & 1
    
    if mux_num == 1:
        GPIO.output(MUX1_S0, s0)
        GPIO.output(MUX1_S1, s1)
        GPIO.output(MUX1_S2, s2)
        GPIO.output(MUX1_EN, GPIO.LOW)   # Enable MUX1
        GPIO.output(MUX2_EN, GPIO.HIGH)
    elif mux_num == 2:
        GPIO.output(MUX2_S0, s0)
        GPIO.output(MUX2_S1, s1)
        GPIO.output(MUX2_S2, s2)
        GPIO.output(MUX2_EN, GPIO.LOW)   # Enable MUX2
        GPIO.output(MUX1_EN, GPIO.HIGH)
    else:
        return False
    time.sleep(0.05)
    return True

def read_voltage():
    return chan.voltage

def discharge_test(duration=0.3):
    print("Activating discharge circuit...")
    GPIO.output(DISCHARGE_PIN, GPIO.HIGH)
    time.sleep(duration)
    GPIO.output(DISCHARGE_PIN, GPIO.LOW)
    time.sleep(0.1)
    v = read_voltage()
    print(f"Post-discharge voltage: {v:.4f}V")
    return v

def test_all_muxes():
    print("=== SmartPin MUX Diagnostic Started ===")
    print(f"ADS1115 reading from A0 (MUX1 Z)")
    print("=" * 60)
    
    discharge_test()
    
    print("\n--- Testing MUX1 (all 8 channels) ---")
    for ch in range(8):
        set_mux(1, ch)
        time.sleep(0.15)
        v = read_voltage()
        print(f"MUX1 Ch {ch:2d} → {v:.4f} V")
    
    print("\n--- Testing MUX2 (all 8 channels) ---")
    for ch in range(8):
        set_mux(2, ch)
        time.sleep(0.15)
        v = read_voltage()
        print(f"MUX2 Ch {ch:2d} → {v:.4f} V")
    
    print("\n--- Testing MUX2 Y0 → MUX1 Y0 signal path ---")
    set_mux(2, 0)
    time.sleep(0.2)
    v_path = read_voltage()
    print(f"Signal path voltage: {v_path:.4f} V")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    try:
        test_all_muxes()
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        GPIO.cleanup()
        print("Cleanup done.")
