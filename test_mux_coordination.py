import time
import board
import busio
from digitalio import DigitalInOut, Direction
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# --- GPIO Configuration ---
# MUX1 (Measurement)
MUX1_S = [DigitalInOut(board.D4), DigitalInOut(board.D5), DigitalInOut(board.D6)]
MUX1_EN = DigitalInOut(board.D18)

# MUX2 (Drive)
MUX2_S = [DigitalInOut(board.D7), DigitalInOut(board.D8), DigitalInOut(board.D9)]
MUX2_EN = DigitalInOut(board.D19)

# Discharge
DISCHARGE = DigitalInOut(board.D27)

# Initialize GPIO Directions
for pin in MUX1_S + MUX2_S:
    pin.direction = Direction.OUTPUT
    pin.value = False

MUX1_EN.direction = Direction.OUTPUT
MUX2_EN.direction = Direction.OUTPUT
DISCHARGE.direction = Direction.OUTPUT

# Active-Low or Active-High Enable? 
# (Standard 74HC4051 is Active-LOW Enable. Adjust if you use an inverter)
MUX_ENABLE = False 
MUX_DISABLE = True

MUX1_EN.value = MUX_DISABLE
MUX2_EN.value = MUX_DISABLE
DISCHARGE.value = False # Keep discharge off during matrix test

# --- ADS1115 Configuration ---
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
ads.gain = 1  # Range: +/-4.096V
chan = AnalogIn(ads, 0)

def set_mux_channel(s_pins, channel):
    """Sets the select pins for a given channel (0-7)"""
    for i in range(3):
        s_pins[i].value = bool((channel >> i) & 1)
    time.sleep(0.002) # Small propagation/settling delay

def run_matrix_test():
    print("Starting MUX Coordinated Verification Matrix...")
    print("------------------------------------------------")
    
    # Enable both MUXes
    MUX1_EN.value = MUX_ENABLE
    MUX2_EN.value = MUX_ENABLE
    
    # Testing the channels tied to your 3-pin test header (Channels 0, 1, and 2)
    test_channels = [0, 1, 2]
    
    for drive_ch in test_channels:
        print(f"\n[Driving MUX2 Channel Y{drive_ch}] (Should output ~5V via 680Ω)")
        set_mux_channel(MUX2_S, drive_ch)
        
        for meas_ch in test_channels:
            set_mux_channel(MUX1_S, meas_ch)
            time.sleep(0.01) # Allow ADS1115 input capacitor to settle
            
            voltage = chan.voltage
            
            # Determine status
            if drive_ch == meas_ch:
                # Expecting a high voltage reading here
                status = "PASS" if voltage > 3.0 else "FAIL (Low Voltage)"
            else:
                # Expecting near 0V because channels should be isolated
                status = "PASS" if voltage < 0.3 else "FAIL (Cross-talk/Leakage)"
                
            print(f"  -> Measuring MUX1 Y{meas_ch}: {voltage:.3f}V | {status}")
            
    # Clean up / Disable
    MUX1_EN.value = MUX_DISABLE
    MUX2_EN.value = MUX_DISABLE
    print("\nMatrix test complete. MUXes disabled.")

if __name__ == "__main__":
    try:
        run_matrix_test()
    except KeyboardInterrupt:
        MUX1_EN.value = MUX_DISABLE
        MUX2_EN.value = MUX_DISABLE
        print("\nTesting aborted cleanly.")
