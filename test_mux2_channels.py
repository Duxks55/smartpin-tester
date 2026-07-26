import time
import board
import digitalio

s0 = digitalio.DigitalInOut(board.D7)
s1 = digitalio.DigitalInOut(board.D8)
s2 = digitalio.DigitalInOut(board.D9)
enable = digitalio.DigitalInOut(board.D19)

s0.direction = s1.direction = s2.direction = enable.direction = digitalio.Direction.OUTPUT
enable.value = False   # Enable MUX2

def set_channel(ch):
    s0.value = bool(ch & 1)
    s1.value = bool(ch & 2)
    s2.value = bool(ch & 4)

print("MUX2 Channel Test - Connect LED + 330Ω to different Y pins to see switching")

try:
    while True:
        for ch in range(8):
            set_channel(ch)
            print(f"Activating Y{ch} (Pin { [13,14,15,12,1,5,2,4][ch] })")
            time.sleep(2)
        print("Cycle complete\n")
except KeyboardInterrupt:
    print("\nTest stopped.")
