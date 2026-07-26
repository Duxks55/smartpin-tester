import time
import math
import board
import busio
import RPi.GPIO as GPIO
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn

# ========================== HARDWARE SETUP ==========================
MUX1_PINS = [4, 5, 6]      # Measurement MUX (to ADS1115)
MUX2_PINS = [7, 8, 9]      # Bias / Drive MUX
DISCHARGE_PIN = 27         # Base of 2N3904 (transistor ON/OFF)

DISCHARGE_CHANNEL = 3      # MUX2 channel for draining through transistor
CHARGE_CHANNEL = 0         # MUX2 channel for charging through 680 ohm resistor

GPIO.setmode(GPIO.BCM)
for p in MUX1_PINS + MUX2_PINS:
    GPIO.setup(p, GPIO.OUT)

GPIO.setup(DISCHARGE_PIN, GPIO.OUT)
GPIO.output(DISCHARGE_PIN, LOW := GPIO.LOW)

i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS1115(i2c)
ads.gain = 1 
chan = AnalogIn(ads, 0)

SUPPLY_VOLTAGE = 5.0       
REF_RESISTOR_OHMS = 680.0  

def set_mux(pins, channel):
    channel = channel & 0x07  
    GPIO.output(pins[0], (channel >> 0) & 1)
    GPIO.output(pins[1], (channel >> 1) & 1)
    GPIO.output(pins[2], (channel >> 2) & 1)

def verify_and_drain(ground_pin, measure_pin):
    print(f"\nDraining capacitor on pins {measure_pin} and {ground_pin}...")
    
    # Route MUX2 to transistor drain channel, MUX1 to ground pin
    set_mux(MUX2_PINS, DISCHARGE_CHANNEL)
    set_mux(MUX1_PINS, ground_pin)
    
    # Turn transistor ON
    GPIO.output(DISCHARGE_PIN, GPIO.HIGH)
    
    # Wait and check until voltage drops below 0.1V (up to 3 seconds max)
    drain_start = time.time()
    while (time.time() - drain_start) < 3.0:
        set_mux(MUX1_PINS, measure_pin)
        v = chan.voltage
        if v is not None and v < 0.10:
            break
        time.sleep(0.05)
        
    # Turn transistor OFF
    GPIO.output(DISCHARGE_PIN, GPIO.LOW)
    time.sleep(0.1)
    
    # Final check
    set_mux(MUX1_PINS, measure_pin)
    final_drain_v = chan.voltage
    print(f"[Debug] Post-drain voltage verification: {final_drain_v:.4f}V" if final_drain_v else "[Debug] Drain check failed")
    
    if final_drain_v is None or final_drain_v > 0.15:
        return False
    return True

def try_measurement(measure_pin, ground_pin):
    try:
        if not verify_and_drain(ground_pin, measure_pin):
            print("    → Drain failed or capacitor still charged.")
            return None

        # === CHARGING PHASE ===
        GPIO.output(DISCHARGE_PIN, GPIO.LOW) 
        
        # Switch MUX2 to CHARGE_CHANNEL (connected to 680 ohm resistor / 5V)
        set_mux(MUX2_PINS, CHARGE_CHANNEL)
        set_mux(MUX1_PINS, measure_pin)
        
        # Brief settling time for MUX transition
        time.sleep(0.02) 

        start_time = time.time()
        target_voltage = 1.5 
        timeout = 15.0
        samples = 0

        while True:
            measured_v = chan.voltage
            samples += 1
            if measured_v is None:
                return None
            
            if samples <= 5 or samples % 25 == 0:
                print(f"  [Sample {samples}] Voltage: {measured_v:.4f}V (t={time.time()-start_time:.4f}s)")

            # If it jumps straight to target on sample 1, something is wrong with the resistor path
            if samples == 1 and measured_v >= target_voltage:
                print("    → [WARNING] Instant voltage spike detected. Resistor path may be bypassed.")
                return -1 

            if measured_v >= target_voltage:
                break
                
            if (time.time() - start_time) > timeout:
                print(f"    → Timeout. Final voltage: {measured_v:.4f}V")
                return None
            
            time.sleep(0.005)

        elapsed = time.time() - start_time
        print(f"[Success] Took {elapsed:.4f}s across {samples} samples to reach {target_voltage}V")
        return elapsed

    except Exception as e:
        print(f"[Debug Error] {e}")
        return None
    finally:
        GPIO.output(DISCHARGE_PIN, GPIO.LOW)
        set_mux(MUX2_PINS, 0)
        set_mux(MUX1_PINS, 0)

def calculate_capacitance(elapsed_time):
    if elapsed_time is None or elapsed_time < 0.02:
        return None
    V_s = SUPPLY_VOLTAGE
    V_c = 1.5  
    R = REF_RESISTOR_OHMS
    try:
        capacitance_farads = -elapsed_time / (R * math.log(1.0 - (V_c / V_s)))
        return capacitance_farads * 1_000_000.0
    except ZeroDivisionError:
        return None

print("Forced-Drain Tester Ready. Insert capacitor into Pins 0 and 1...")

try:
    scan_p1, scan_p2 = 0, 1
    while True:
        set_mux(MUX2_PINS, 0)
        set_mux(MUX1_PINS, scan_p2)
        time.sleep(0.15)
        
        v = chan.voltage
        if v is not None and v > 0.18:
            print(f"\n[+] Capacitor detected! (Initial voltage: {v:.2f}V)")
            
            elapsed = try_measurement(measure_pin=scan_p1, ground_pin=scan_p2)
            if elapsed is None or elapsed < 0 or elapsed < 0.02:
                print("Direction 1 failed or spiked. Trying direction 2...")
                elapsed = try_measurement(measure_pin=scan_p2, ground_pin=scan_p1)
                
            if elapsed is not None and elapsed > 0:
                cap_val = calculate_capacitance(elapsed)
                if cap_val is not None:
                    print(f"=== RESULT: Measured Capacitance = {cap_val:.2f} µF ===")
                else:
                    print("Measurement failed (too fast or invalid curve).")
            else:
                print("Measurement failed (Spike detected).")
                
            print("Waiting for capacitor to be removed...")
            while True:
                set_mux(MUX1_PINS, scan_p2)
                time.sleep(0.4)
                if chan.voltage is not None and chan.voltage < 0.08:
                    print("Capacitor removed.\n")
                    break
        else:
            time.sleep(0.25)
                        
except KeyboardInterrupt:
    print("\nStopping...")
finally:
    GPIO.output(DISCHARGE_PIN, GPIO.LOW)
    GPIO.cleanup()
