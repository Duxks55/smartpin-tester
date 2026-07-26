import board
import digitalio
import time

enable = digitalio.DigitalInOut(board.D19)
enable.direction = digitalio.Direction.OUTPUT

print("Testing MUX2 Enable pin")

try:
    while True:
        enable.value = False   # Should enable MUX2
        print("Enable = LOW (MUX2 should be active)")
        time.sleep(3)
        
        enable.value = True    # Should disable MUX2
        print("Enable = HIGH (MUX2 should be disabled)")
        time.sleep(3)
except KeyboardInterrupt:
    print("\nTest stopped.")

