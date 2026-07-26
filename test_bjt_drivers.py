import time
import board
import busio
from digitalio import DigitalInOut, Direction
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# --- GPIO Setup ---
MUX1_S = [DigitalInOut(board.D4), DigitalInOut(board.D5), DigitalInOut(board.D6)]
MUX1_EN = DigitalInOut(board.D18)
MUX2_S = [DigitalInOut(board.D7), DigitalInOut(board.D8), DigitalInOut(board.D9)]
MUX2_EN = DigitalInOut(board.D19)

NPN_DRIVE = DigitalInOut(board.D22)
PNP_DRIVE = DigitalInOut(board.D23)
DISCHARGE = DigitalInOut(board.D27) # Your discharge control line

for pin in MUX1_S + MUX2_S:
    pin.direction = Direction.OUTPUT
    pin.value = False

MUX1_EN.direction = Direction.OUTPUT
MUX2_EN.direction = Direction.OUTPUT
NPN_DRIVE.direction = Direction.OUTPUT
PNP_DRIVE.direction = Direction.OUTPUT
DISCHARGE.direction = Direction.OUTPUT

# Enable chips (Active-LOW) & Set safe initial states
MUX1_EN.value = False
MUX2_EN.value = False
NPN_DRIVE.value = False
PNP_DRIVE.value = True   # PNP Off initially
DISCHARGE.value = False  # Discharge Off initially

# --- ADS1115 Setup ---
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
ads.gain = 1  
chan = AnalogIn(ads, 0)

def set_mux_channel(s_pins, channel):
    for i in range(3):
        s_pins[i].value = bool((channel >> i) & 1)
    time.sleep(0.002)

def run_discharge_sequence(target_pin_mux1):
    """Switches system resources to drain trapped line charge to GND"""
    print(f"  [Discharge] Blasting residual charge on Test Pin {target_pin_mux1 + 1}...")
    set_mux_channel(MUX2_S, 3) # Map MUX2 to Y3 (Discharge Transistor Path)
    set_mux_channel(MUX1_S, target_pin_mux1) # Keep ADS1115 watching the pin
    DISCHARGE.value = True     # Turn on discharge transistor
    time.sleep(0.1)            # Let it bleed to ground
    DISCHARGE.value = False    # Turn off discharge
    print(f"  [Discharge] Voltage after bleed: {chan.voltage:.3f}V")

print("--- SmartPin Driver & Discharge Integration Verification ---")

try:
    # TEST 1: Verify NPN Drive & Discharge Success
    print("\n[TEST 1] Testing NPN Drive (MUX2 Y4 -> Test Pin 1)...")
    set_mux_channel(MUX2_S, 4) # Select NPN Drive source
    set_mux_channel(MUX1_S, 0) # Read Test Pin 1 (Y0)
    
    print("  -> Turning GPIO 22 (NPN Base) HIGH...")
    NPN_DRIVE.value = True
    time.sleep(0.1)
    print(f"  Voltage read on Test Pin 1 (Active): {chan.voltage:.3f}V")
    
    print("  -> Turning GPIO 22 LOW (Transistor Cutoff)...")
    NPN_DRIVE.value = False
    time.sleep(0.1)
    print(f"  Voltage read before discharge (Trapped): {chan.voltage:.3f}V")
    
    # Trigger your hardware discharge path
    run_discharge_sequence(target_pin_mux1=0)

    # TEST 2: Verify PNP Drive (Sinking Voltage from Test Pin 2 / Y1)
    print("\n[TEST 2] Testing PNP Drive (MUX2 Y5 -> Test Pin 2)...")
    set_mux_channel(MUX2_S, 5) # Select PNP sink pathway
    set_mux_channel(MUX1_S, 1) # Read Test Pin 2 (Y1)
    
    print("  -> Turning GPIO 23 (PNP Base) LOW to ACTIVATE...")
    PNP_DRIVE.value = False
    time.sleep(0.1)
    print(f"  Voltage read on Test Pin 2 (Pulled Low): {chan.voltage:.3f}V")
    
    print("  -> Turning GPIO 23 HIGH to CUTOFF...")
    PNP_DRIVE.value = True
    time.sleep(0.1)
    
    # Discharge Test Pin 2 just in case
    run_discharge_sequence(target_pin_mux1=1)

finally:
    MUX1_EN.value = True
    MUX2_EN.value = True
    NPN_DRIVE.value = False
    PNP_DRIVE.value = True
    DISCHARGE.value = False
    print("\nSystem safe state applied.")
