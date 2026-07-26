import time
import board
import busio
import digitalio
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn

# I2C & ADC
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS1115(i2c, address=0x48)
chan = AnalogIn(ads, 0)

# MUX control pins
s0 = digitalio.DigitalInOut(board.D4)
s1 = digitalio.DigitalInOut(board.D5)
s2 = digitalio.DigitalInOut(board.D6)
s0.direction = s1.direction = s2.direction = digitalio.Direction.OUTPUT

def set_mux_channel(ch):
    s0.value = bool(ch & 1)
    s1.value = bool(ch & 2)
    s2.value = bool(ch & 4)

print("MUX1 + ADS1115 Test - Cycling through channels")

try:
    while True:
        for ch in range(8):
            set_mux_channel(ch)
            time.sleep(0.1)
            print(f"Channel Y{ch}: {chan.voltage:.4f} V")
        print("-" * 40)
        time.sleep(1)
except KeyboardInterrupt:
    print("\nTest stopped.")
