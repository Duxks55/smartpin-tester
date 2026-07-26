import time
import board
import digitalio
import busio
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn

# I2C + ADC
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS1115(i2c, address=0x48)
chan = AnalogIn(ads, 0)

# MUX1 control
s0_1 = digitalio.DigitalInOut(board.D4)
s1_1 = digitalio.DigitalInOut(board.D5)
s2_1 = digitalio.DigitalInOut(board.D6)
s0_1.direction = s1_1.direction = s2_1.direction = digitalio.Direction.OUTPUT

# MUX2 control
s0_2 = digitalio.DigitalInOut(board.D7)
s1_2 = digitalio.DigitalInOut(board.D8)
s2_2 = digitalio.DigitalInOut(board.D9)
s0_2.direction = s1_2.direction = s2_2.direction = digitalio.Direction.OUTPUT

# Enable pins
enable1 = digitalio.DigitalInOut(board.D18)
enable2 = digitalio.DigitalInOut(board.D19)
enable1.direction = enable2.direction = digitalio.Direction.OUTPUT
enable1.value = False  # Enable MUX1
enable2.value = False  # Enable MUX2

def set_mux1(ch):
    s0_1.value = bool(ch & 1)
    s1_1.value = bool(ch & 2)
    s2_1.value = bool(ch & 4)

def set_mux2(ch):
    s0_2.value = bool(ch & 1)
    s1_2.value = bool(ch & 2)
    s2_2.value = bool(ch & 4)

print("Both MUXes Test - Looking for voltage change\n")

try:
    while True:
        # Path ON
        set_mux2(0)   # MUX2 Y0
        set_mux1(0)   # MUX1 Y0
        time.sleep(0.5)
        print(f"Path ON  → A0: {chan.voltage:.4f} V")

        # Path OFF
        set_mux2(8)   # All channels off
        set_mux1(8)
        time.sleep(0.5)
        print(f"Path OFF → A0: {chan.voltage:.4f} V")
        print("-" * 50)
        time.sleep(1)
except KeyboardInterrupt:
    print("\nTest stopped.")
