import time
import board
import digitalio

# MUX2 control (for Y3 discharge channel)
s0 = digitalio.DigitalInOut(board.D7)
s1 = digitalio.DigitalInOut(board.D8)
s2 = digitalio.DigitalInOut(board.D9)
s0.direction = s1.direction = s2.direction = digitalio.Direction.OUTPUT

discharge = digitalio.DigitalInOut(board.D17)
discharge.direction = digitalio.Direction.OUTPUT

print("Discharge Test - Connect LED or multimeter to discharge node")

try:
    while True:
        # Activate discharge channel
        s0.value = False
        s1.value = False
        s2.value = True   # Y3 = binary 011 = 3
        print("Discharge channel active - turning ON discharge")
        discharge.value = True
        time.sleep(3)

        # Turn off
        s0.value = True
        s1.value = True
        s2.value = True
        discharge.value = False
        print("Discharge OFF")
        time.sleep(3)
except KeyboardInterrupt:
    discharge.value = False
    print("\nTest stopped.")
