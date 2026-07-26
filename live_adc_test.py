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

# Force Y2
s0.value = False
s1.value = True
s2.value = False

print("Forced Y2 active - connect +5V to MUX1 Y2 (Pin 15)")

try:
    while True:
        print(f"A0: {chan.voltage:.4f} V")
        time.sleep(0.3)
except KeyboardInterrupt:
    print("\nTest stopped.")
