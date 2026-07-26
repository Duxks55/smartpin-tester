import time
import board
import digitalio
import busio
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn

# ADC
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS1115(i2c, address=0x48)
chan = AnalogIn(ads, 0)

# MUX1 (now in old MUX2 position)
s0_1 = digitalio.DigitalInOut(board.D7)
s1_1 = digitalio.DigitalInOut(board.D8)
s2_1 = digitalio.DigitalInOut(board.D9)
e1 = digitalio.DigitalInOut(board.D19)
s0_1.direction = s1_1.direction = s2_1.direction = e1.direction = digitalio.Direction.OUTPUT
e1.value = False

# MUX2 (now in old MUX1 position)
s0_2 = digitalio.DigitalInOut(board.D4)
s1_2 = digitalio.DigitalInOut(board.D5)
s2_2 = digitalio.DigitalInOut(board.D6)
e2 = digitalio.DigitalInOut(board.D18)
s0_2.direction = s1_2.direction = s2_2.direction = e2.direction = digitalio.Direction.OUTPUT
e2.value = False

def mux1(ch):
    s0_1.value = bool(ch & 1)
    s1_1.value = bool(ch & 2)
    s2_1.value = bool(ch & 4)

def mux2(ch):
    s0_2.value = bool(ch & 1)
    s1_2.value = bool(ch & 2)
    s2_2.value = bool(ch & 4)

print("After Swap Test - MUX2 Y0 -> MUX1 Y0")
print("Watch for clear voltage change on A0\n")

try:
    while True:
        # Path ON
        mux2(0)
        mux1(0)
        time.sleep(1)
        print(f"Path ON  → {chan.voltage:.4f} V")

        # Path OFF
        mux2(8)
        mux1(8)
        time.sleep(1)
        print(f"Path OFF → {chan.voltage:.4f} V")
        print("-" * 50)
except KeyboardInterrupt:
    print("\nTest stopped.")
