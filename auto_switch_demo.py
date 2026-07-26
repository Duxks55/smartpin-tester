import time
import board
import busio
from digitalio import DigitalInOut, Direction
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# --- Matrix Setup ---
MUX1_S = [DigitalInOut(board.D4), DigitalInOut(board.D5), DigitalInOut(board.D6)]
MUX1_EN = DigitalInOut(board.D18)
MUX2_S = [DigitalInOut(board.D7), DigitalInOut(board.D8), DigitalInOut(board.D9)]
MUX2_EN = DigitalInOut(board.D19)

# We will temporarily use a free GPIO to simulate an output source 
# We feed this into MUX2's Common (COM) pin so MUX2 can route it!
MATRIX_SOURCE = DigitalInOut(board.D22) 

for pin in MUX1_S + MUX2_S:
    pin.direction = Direction.OUTPUT
    pin.value = False

MUX1_EN.direction = Direction.OUTPUT
MUX2_EN.direction = Direction.OUTPUT
MATRIX_SOURCE.direction = Direction.OUTPUT

# Enable both multiplexer chips
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
    time.sleep(0.005) # Crucial settling time for hardware switching

print("====================================================")
print("   AUTOMATED INPUT/OUTPUT MATRIX SWITCHING DEMO")
print("====================================================\n")
print("Watch how the MCU changes roles per pin in real-time...\n")

try:
    while True:
        # Cycle through Test Pins 1, 2, and 3 (Channels 0, 1, 2)
        for pin_idx in range(3):
            print(f"--- Isolating Test Pin {pin_idx + 1} ---")
            
            # PHASE 1: Set as an inactive Input (Read baseline/floating)
            MATRIX_SOURCE.value = False
            set_mux_channel(MUX2_S, 7) # Send MUX2 to an empty channel (turns output off)
            set_mux_channel(MUX1_S, pin_idx) # Point the ADC input to this pin
            time.sleep(0.1)
            v_input = chan.voltage
            print(f"  [ROLE: INPUT]  Reading natural line voltage: {v_input:.3f}V")
            
            # PHASE 2: Automatically switch role to an active Output (Source Voltage)
            print(f"  [AUTO-SWITCHING] Driving power out of Pin {pin_idx + 1}...")
            MATRIX_SOURCE.value = True       # Turn on our test voltage supply
            set_mux_channel(MUX2_S, pin_idx) # Switch MUX2 output directly onto this test pin row
            
            # PHASE 3: Instantly sample with MUX1 to verify the output arrived
            set_mux_channel(MUX1_S, pin_idx) # Keep watching with the input matrix
            time.sleep(0.2)
            v_output = chan.voltage
            print(f"  [ROLE: OUTPUT] Verification read back:        {v_output:.3f}V")
            
            print("-" * 45)
            time.sleep(1.5) # Pause so your audience can read the transition

except KeyboardInterrupt:
    print("\nDemo stopped cleanly.")
finally:
    MATRIX_SOURCE.value = False
    MUX1_EN.value = True
    MUX2_EN.value = True
