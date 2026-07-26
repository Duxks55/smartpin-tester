import time
import board
import digitalio
import busio
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn

i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS1115(i2c, address=0x48)
chan = AnalogIn(ads, 0)

# Only MUX1 for this test
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

print("Minimal MUX1 Test - Connect a wire from +5V to different Y pins")

try:
    while True:
        for ch in range(8):
            set_channel(ch)
            print(f"Y{ch} active - measure on MUX1 Pin 3")
            time.sleep(3)
except KeyboardInterrupt:
    print("\nTest stopped.")
