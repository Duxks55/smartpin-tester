import time
import board
import digitalio

discharge = digitalio.DigitalInOut(board.D17)
discharge.direction = digitalio.Direction.OUTPUT

print("Simple Discharge Test")

try:
    while True:
        print("Discharge ON")
        discharge.value = True
        time.sleep(3)
        
        print("Discharge OFF")
        discharge.value = False
        time.sleep(3)
except KeyboardInterrupt:
    discharge.value = False
    print("\nTest stopped.")
