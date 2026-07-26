import board
import digitalio
import time

enable = digitalio.DigitalInOut(board.D19)
enable.direction = digitalio.Direction.OUTPUT

# Force MUX2 disabled (active HIGH)
enable.value = True

print("MUX2 Enable = HIGH (disabled)")
print("Measure voltage on MUX2 Pin 3 now - it should drop low")
time.sleep(15)
