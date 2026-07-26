import time
import board
import digitalio

# MUX2 control pins
s0 = digitalio.DigitalInOut(board.D7)
s1 = digitalio.DigitalInOut(board.D8)
s2 = digitalio.DigitalInOut(board.D9)
s0.direction = s1.direction = s2.direction = digitalio.Direction.OUTPUT

discharge = digitalio.DigitalInOut(board.D17)
discharge.direction = digitalio.Direction.OUTPUT
discharge.value = False  # Off by default

def set_mux2_channel(ch):
    s0.value = bool(ch & 1)
    s1.value = bool(ch & 2)
    s2.value = bool(ch & 4)

print("MUX2 + Discharge Test")
print("Press Ctrl+C to stop\n")

try:
    while True:
        print("Testing MUX2 channels...")
        for ch in range(8):
            set_mux2_channel(ch)
            print(f"  MUX2 Channel Y{ch} activated")
            time.sleep(0.3)

        # Test discharge
        print("Activating discharge for 2 seconds...")
        discharge.value = True
        time.sleep(2)
        discharge.value = False
        print("Discharge OFF\n")
        time.sleep(1)
except KeyboardInterrupt:
    discharge.value = False
    print("\nTest stopped.")
