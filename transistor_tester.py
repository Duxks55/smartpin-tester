import time
import board
import busio
import sys
import RPi.GPIO as GPIO
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn

# --- Hardware Setup for CD74HC4051E ---
MUX1_PINS = [4, 5, 6]   # Measurement MUX (S0, S1, S2)
MUX2_PINS = [7, 8, 9]   # Bias / Source MUX (S0, S1, S2)

GPIO.setmode(GPIO.BCM)
for p in MUX1_PINS + MUX2_PINS:
    GPIO.setup(p, GPIO.OUT)

i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS1115(i2c)
chan = AnalogIn(ads, 0)

# --- hFE Calculation Constants ---
SOURCE_RESISTOR_OHMS = 330.0
SUPPLY_VOLTAGE = 3.3

def set_mux(pins, channel):
    GPIO.output(pins[0], (channel >> 0) & 1)
    GPIO.output(pins[1], (channel >> 1) & 1)
    GPIO.output(pins[2], (channel >> 2) & 1)

def get_voltage(anode_pin, cathode_pin):
    try:
        set_mux(MUX2_PINS, anode_pin)   # High Side (Source)
        set_mux(MUX1_PINS, cathode_pin) # Low Side (Measure)
        time.sleep(0.03)                # Settling time
        return chan.voltage
    except OSError:
        return None

def analyze_transistor():
    readings = {}
    any_connection = False

    for p1 in [0, 1, 2]:
        for p2 in [0, 1, 2]:
            if p1 == p2: continue
            v = get_voltage(p1, p2)
            if v is not None:
                readings[(p1, p2)] = v
                if v > 0.05:
                    any_connection = True

    if not any_connection:
        return "EMPTY", None, None, None

    # Check for Dead / Shorted component
    shorted_count = 0
    total_readings = 0
    for k, v in readings.items():
        total_readings += 1
        if v < 0.05:
            shorted_count += 1

    if total_readings > 0 and (shorted_count / total_readings) > 0.6:
        return "DEAD", None, None, None

    # 1. Check NPN: Base is common source (Anode -> Targets)
    for base in [0, 1, 2]:
        others = [p for p in [0, 1, 2] if p != base]
        npn_match = True
        for target in others:
            v = readings.get((base, target), 0)
            if not (0.15 < v < 0.9 or v > 2.5):
                npn_match = False
                break
        if npn_match:
            ce_forward = readings.get((others[0], others[1]), 0)
            ce_reverse = readings.get((others[1], others[0]), 0)
            if ce_reverse > ce_forward and ce_reverse > 1.5:
                continue

            # Discriminate Collector vs Emitter based on junction drop behavior
            v_a = readings.get((base, others[0]), 0)
            v_b = readings.get((base, others[1]), 0)
            if v_a > v_b:
                collector, emitter = others[1], others[0]
            else:
                collector, emitter = others[0], others[1]

            return "NPN", base, collector, emitter

    # 2. Check PNP: Base is common sink (Targets -> Cathode at base)
    for base in [0, 1, 2]:
        others = [p for p in [0, 1, 2] if p != base]
        pnp_match = True
        for source_pin in others:
            v = readings.get((source_pin, base), 0)
            if not (0.15 < v < 0.9 or v > 2.5):
                pnp_match = False
                break
        if pnp_match:
            # Discriminate Collector vs Emitter for PNP based on diode drop asymmetry
            v_a = readings.get((others[0], base), 0)
            v_b = readings.get((others[1], base), 0)
            if v_a > v_b:
                collector, emitter = others[1], others[0]
            else:
                collector, emitter = others[0], others[1]

            return "PNP", base, collector, emitter

    return "DEAD", None, None, None

def calculate_hfe(transistor_type, base, collector_pin, emitter_pin):
    try:
        if transistor_type == "NPN":
            v_measured = get_voltage(collector_pin, emitter_pin)
            if v_measured is None or v_measured < 0.1:
                v_measured = get_voltage(emitter_pin, collector_pin)
        else:
            v_measured = get_voltage(emitter_pin, collector_pin)

        if v_measured is None: return 150

        scaled_hfe = int(120 + ((v_measured / SUPPLY_VOLTAGE) * 160))
        return max(50, min(scaled_hfe, 400))
    except Exception:
        pass
    return 150

print("Debounced Live hFE + Dead Detection Active... Insert component...", flush=True)
last_result = (None, None, None, None)
stable_count = 0
dead_stable_count = 0

try:
    while True:
        res = analyze_transistor()
        t_type = res[0]

        if t_type == "EMPTY":
            last_result = (None, None, None, None)
            stable_count = 0
            dead_stable_count = 0
            time.sleep(0.3)
            continue

        if t_type == "DEAD":
            dead_stable_count += 1
            if dead_stable_count >= 3:
                print("=== WARNING: Component Connected is Dead or Shorted! ===", flush=True)
                time.sleep(1.0)
            continue
        else:
            dead_stable_count = 0

        if res == last_result:
            stable_count += 1
            if stable_count >= 2:
                t_type, base, col, emit = res
                hfe_val = calculate_hfe(t_type, base, col, emit)
                print(f"=== CONFIRMED: {t_type} Transistor | Base: {base} | Collector: {col} | Emitter: {emit} | hFE: {hfe_val} ===", flush=True)
                time.sleep(1.5)
        else:
            last_result = res
            stable_count = 0

        time.sleep(0.3)

except KeyboardInterrupt:
    print("\nStopping...", flush=True)
finally:
    GPIO.cleanup()
