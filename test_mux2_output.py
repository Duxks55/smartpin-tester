import time
import board
import digitalio

s0 = digitalio.DigitalInOut(board.D7)
s1 = digitalio.DigitalInOut(board.D8)
s2 = digitalio.DigitalInOut(board.D9)
e = digitalio.DigitalInOut(board.D19)

s0.direction = s1.direction = s2.direction = e.direction = digitalio.Direction.OUTPUT
e.value = False

print("MUX2 Output Test - Measure MUX2 Pin 3")

try:
    while True:
        # Y0 ON
        s0.value = False
        s1.value = False
        s2.value = False
        print("Y0 ON - MUX2 Pin 3 should be HIGH (~4V)")
        time.sleep(3)

        # OFF
        s0.value = True
        s1.value = True
        s2.value = True
        print("OFF - MUX2 Pin 3 should be LOW")
        time.sleep(3)
except KeyboardInterrupt:
    print("\nTest stopped.")
