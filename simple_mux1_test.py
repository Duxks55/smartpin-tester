import time
import board
import digitalio
import busio
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn

i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS1115(i2c, address=0x48)
chan = AnalogIn(ads, 0)

s0 = digitalio.DigitalInOut(board.D4)
s1 = digitalio.DigitalInOut(board.D5)
s2 = digitalio.DigitalInOut(board.D6)
e = digitalio.DigitalInOut(board.D18)
s0.direction = s1.direction = s2.direction = e.direction = digitalio.Direction.OUTPUT
e.value = False

def set_channel(ch):
    s0.value = bool(ch & 1)
    s1.value = bool(ch & 2)
    s2.value = bool(ch & 4)

print("Simple MUX1 Test - Manually connect +5V to Y pins")

try:
    while True:
        for ch in range(8):
            set_channel(ch)
            print(f"Y{ch} active - connect +5V to MUX1 Y{ch} to see change")
            time.sleep(4)
except KeyboardInterrupt:
    print("\nTest stopped.")
