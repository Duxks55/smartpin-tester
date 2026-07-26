import board
import digitalio
import time

s0 = digitalio.DigitalInOut(board.D7)
s1 = digitalio.DigitalInOut(board.D8)
s2 = digitalio.DigitalInOut(board.D9)
enable = digitalio.DigitalInOut(board.D19)

s0.direction = s1.direction = s2.direction = enable.direction = digitalio.Direction.OUTPUT

# Turn everything off
s0.value = s1.value = s2.value = True
enable.value = False   # Enable the MUX

print("MUX2 forced OFF - check voltage on Z pin")
time.sleep(10)
