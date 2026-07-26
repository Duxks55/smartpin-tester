import time
import board
import busio
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn

# Initialize I2C
i2c = busio.I2C(board.SCL, board.SDA)

# Create the ADS1115 object
ads = ADS1115(i2c, address=0x48)

# Create analog input channels (newer syntax)
chan0 = AnalogIn(ads, 0)   # A0
chan1 = AnalogIn(ads, 1)   # A1

print("ADS1115 Test Started - Press Ctrl+C to stop\n")

try:
    while True:
        print(f"A0: {chan0.voltage:.4f} V   |   A1: {chan1.voltage:.4f} V")
        time.sleep(0.5)
except KeyboardInterrupt:
    print("\nTest stopped.")
