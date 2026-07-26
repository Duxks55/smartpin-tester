import time
import board
import busio
from digitalio import DigitalInOut, Direction
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# --- Matrix GPIO Pins ---
MUX1_S = [DigitalInOut(board.D4), DigitalInOut(board.D5), DigitalInOut(board.D6)]
MUX1_EN = DigitalInOut(board.D18)
MUX2_S = [DigitalInOut(board.D7), DigitalInOut(board.D8), DigitalInOut(board.D9)]
MUX2_EN = DigitalInOut(board.D19)

for pin in MUX1_S + MUX2_S:
    pin.direction = Direction.OUTPUT
    pin.value = False

MUX1_EN.direction = Direction.OUTPUT
MUX2_EN.direction = Direction.OUTPUT
MUX1_EN.value = False
MUX2_EN.value = False

# --- ADC Config ---
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
ads.gain = 1  
chan = AnalogIn(ads, 0)

def set_mux_channel(s_pins, channel):
    for i in range(3):
        s_pins[i].value = bool((channel >> i) & 1)
    time.sleep(0.005)

print("\n=== Live SmartPin Matrix I/O Diagnostic Stream ===")
print("Press Ctrl+C to stop scanning.\n")

try:
    while True:
        print("\r" + " " * 60 + "\r", end="") # Clear line
        
        # 1. Scan the 3 Target Test Pins (MUX1 Inputs)
        set_mux_channel(MUX1_S, 0)
        v_pin1 = chan.voltage
        
        set_mux_channel(MUX1_S, 1)
        v_pin2 = chan.voltage
        
        set_mux_channel(MUX1_S, 2)
        v_pin2_3 = chan.voltage
        
        # Print a clean, formatted live string tracking the lines
        print(f"INPUT MATRIX -> Test Pin 1: {v_pin1:.3f}V | Test Pin 2: {v_pin2:.3f}V | Test Pin 3: {v_pin2_3:.3f}V", end="", flush=True)
        time.sleep(0.2)

except KeyboardInterrupt:
    print("\n\nDiagnostic scan complete.")
