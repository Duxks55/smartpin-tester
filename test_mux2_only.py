import time
import board
import digitalio

s0 = digitalio.DigitalInOut(board.D7)
s1 = digitalio.DigitalInOut(board.D8)
s2 = digitalio.DigitalInOut(board.D9)
enable = digitalio.DigitalInOut(board.D19)

s0.direction = s1.direction = s2.direction = enable.direction = digitalio.Direction.OUTPUT
enable.value = False

print("MUX2 Only Test - Watch MUX2 Pin 3 with multimeter")

try:
    while True:
        # Turn ON (Y0)
        s0.value = False
        s1.value = False
        s2.value = False
        print("Y0 ON - MUX2 Pin 3 should be HIGH")
        time.sleep(3)

        # Turn OFF
        s0.value = True
        s1.value = True
        s2.value = True
        print("All OFF - MUX2 Pin 3 should be LOW")
        time.sleep(3)
except KeyboardInterrupt:
    print("\nTest stopped.")
