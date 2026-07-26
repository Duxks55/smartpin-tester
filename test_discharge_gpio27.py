import time
import board
import digitalio

discharge = digitalio.DigitalInOut(board.D27)
discharge.direction = digitalio.Direction.OUTPUT

print("Discharge Test using GPIO27")

try:
    while True:
        print("Discharge ON - LED should light")
        discharge.value = True
        time.sleep(3)
        
        print("Discharge OFF")
        discharge.value = False
        time.sleep(3)
except KeyboardInterrupt:
    discharge.value = False
    print("\nTest stopped.")
