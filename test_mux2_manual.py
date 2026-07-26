import time
import board
import digitalio

s0 = digitalio.DigitalInOut(board.D7)
s1 = digitalio.DigitalInOut(board.D8)
s2 = digitalio.DigitalInOut(board.D9)
enable = digitalio.DigitalInOut(board.D19)

s0.direction = s1.direction = s2.direction = enable.direction = digitalio.Direction.OUTPUT
enable.value = False   # Enable MUX2

print("MUX2 Manual Test")
print("Connect +5V to different Y pins and watch MUX2 Pin 3")

try:
    while True:
        for ch in range(8):
            s0.value = bool(ch & 1)
            s1.value = bool(ch & 2)
            s2.value = bool(ch & 4)
            print(f"Activating Y{ch} (Pin {[13,14,15,12,1,5,2,4][ch]}) - Check MUX2 Pin 3")
            time.sleep(4)
except KeyboardInterrupt:
    print("\nTest stopped.")
