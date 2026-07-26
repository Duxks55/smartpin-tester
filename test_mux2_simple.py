import board
import digitalio
import time

enable = digitalio.DigitalInOut(board.D19)
enable.direction = digitalio.Direction.OUTPUT
enable.value = False   # Enable MUX2

print("MUX2 Enable = LOW (should be active)")

time.sleep(10)
print("Test finished.")
