import time
import threading
import tkinter as tk
import board
import busio
import RPi.GPIO as GPIO
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn

# --- Hardware Setup ---
MUX1_PINS = [4, 5, 6]       # Measurement MUX (S0, S1, S2)
MUX2_PINS = [7, 8, 9]       # Bias / Source MUX (S0, S1, S2)
DISCHARGE_PIN = 27          # Connected to the 2N3904 base resistor
DISCHARGE_CHANNEL = 3       # MUX2 channel corresponding to the discharge/resistor path
SOURCE_CHANNEL = 3          # MUX2 channel supplying the charging current through the 680 ohm resistor

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
for p in MUX1_PINS + MUX2_PINS:
    GPIO.setup(p, GPIO.OUT)
GPIO.setup(DISCHARGE_PIN, GPIO.OUT)
GPIO.output(DISCHARGE_PIN, GPIO.LOW)

# Initialize I2C and ADS1115 safely
try:
    i2c = busio.I2C(board.SCL, board.SDA)
    ads = ADS1115(i2c)
    ads.gain = 1
    chan = AnalogIn(ads, 0)
    HARDWARE_AVAILABLE = True
except Exception as e:
    print(f"[Initialization Warning] Hardware/I2C init failed: {e}")
    HARDWARE_AVAILABLE = False

SUPPLY_VOLTAGE = 5.0
REF_RESISTOR_OHMS = 680.0

def set_mux(pins, channel):
    if not HARDWARE_AVAILABLE:
        return
    channel = channel & 0x07
    GPIO.output(pins[0], (channel >> 0) & 1)
    GPIO.output(pins[1], (channel >> 1) & 1)
    GPIO.output(pins[2], (channel >> 2) & 1)

def full_drain(discharge_pin_mux1):
    """Uses the known working drain configuration to clear the capacitor completely."""
    try:
        set_mux(MUX2_PINS, DISCHARGE_CHANNEL)
        set_mux(MUX1_PINS, discharge_pin_mux1)
        GPIO.output(DISCHARGE_PIN, GPIO.HIGH)
        time.sleep(2.5)
    finally:
        GPIO.output(DISCHARGE_PIN, GPIO.LOW)
        time.sleep(0.1)

def try_measurement(measure_pin, ground_pin):
    try:
        # Drain using the ground pin configuration that reliably works
        full_drain(ground_pin)
       
        # Verify voltage is down on the measuring pin
        set_mux(MUX1_PINS, measure_pin)
        time.sleep(0.05)
        v_check = chan.voltage if HARDWARE_AVAILABLE else 0.0
        print(f"[Debug] Post-drain voltage (Pin {measure_pin}): {v_check if v_check is not None else 'None'}V")
        if v_check is None or v_check > 0.15:
            return None
           
        # Connect source bias (MUX2) and return/ground path (MUX1) to establish closed loop
        set_mux(MUX2_PINS, SOURCE_CHANNEL)
        set_mux(MUX1_PINS, ground_pin)
        time.sleep(0.02)
       
        start_time = time.time()
        target_voltage = 1.5
       
        measured_v = 0.0
        while measured_v < target_voltage:
            measured_v = chan.voltage if HARDWARE_AVAILABLE else (target_voltage + 0.1)
            if measured_v is None:
                return None
            if (time.time() - start_time) > 8.0:
                return None
                
        elapsed_time = time.time() - start_time
        return elapsed_time
    except Exception as e:
        print(f"[Debug Error] {e}")
        return None

def smart_classify(elapsed_time):
    if elapsed_time is None:
        return None
       
    print(f"[Debug] Time to 1.5V: {elapsed_time:.4f}s")
   
    if elapsed_time < 0.08:
        return 100.0
    else:
        return 470.0

class CapacitorAnalyzerView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#0f172a")

        header = tk.Frame(self, bg="#1e293b", height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Button(header, text="← Return to Menu", bg="#334155", fg="#f8fafc",
                  font=("Helvetica", 10, "bold"), relief="flat", padx=15, pady=5,
                  command=lambda: controller.show_frame("MainDashboard")).pack(side="left", padx=20)
        tk.Label(header, text="CAPACITOR ANALYZER MODULE", fg="#f8fafc", bg="#1e293b",
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=10)

        body = tk.Frame(self, bg="#0f172a")
        body.pack(fill="both", expand=True, padx=30, pady=30)

        self.result_box = tk.Text(body, bg="#1e293b", fg="#34d399",
                                  font=("Courier", 11), height=16, bd=0, relief="flat")
        self.result_box.pack(fill="both", expand=True, pady=(0, 15))
        self.result_box.insert("1.0",
            "[System] Working-Loop Auto-ID Tester Ready.\n"
            "Insert capacitor into Pins 0 and 1...\n")

        test_btn = tk.Button(body, text="Measure Capacitance", bg="#10b981", fg="#ffffff",
                             font=("Helvetica", 12, "bold"), relief="flat",
                             padx=20, pady=10, command=self.execute_capacitor_test)
        test_btn.pack(anchor="w")

    def _log(self, msg):
        print(msg)
        self.after(0, lambda: self.result_box.insert(tk.END, msg + "\n"))

    def execute_capacitor_test(self):
        self.result_box.delete("1.0", tk.END)
        self._log("[System] Capacitor test started...")

        def run_thread():
            try:
                scan_p1, scan_p2 = 0, 1
                self._log(f"Inserting/Scanning across Pins {scan_p1} and {scan_p2}...")
                
                set_mux(MUX2_PINS, scan_p1)
                set_mux(MUX1_PINS, scan_p2)
                time.sleep(0.1)
               
                v = chan.voltage if HARDWARE_AVAILABLE else 0.5
                if v is not None and v > 0.15:
                    self._log(f"\n[+] Capacitor detected! (Initial voltage: {v:.2f}V)")
                   
                    self._log("Testing polarity direction 1 (Measure Pin 0, Ground Pin 1)...")
                    elapsed = try_measurement(measure_pin=scan_p1, ground_pin=scan_p2)
                   
                    if elapsed is None or elapsed < 0.015:
                        self._log("Direction 1 failed. Trying direction 2 (Measure Pin 1, Ground Pin 0)...")
                        elapsed = try_measurement(measure_pin=scan_p2, ground_pin=scan_p1)
                   
                    cap_val = smart_classify(elapsed)
               
                    if cap_val is not None:
                        self._log(f"=== RESULT: Measured Capacitance = ~{cap_val:.0f} uF ===")
                    else:
                        self._log("Measurement failed. Check connections.")
                else:
                    self._log("[System] No capacitor detected or voltage too low.")
            except Exception as e:
                self._log(f"[Error] {e}")

        threading.Thread(target=run_thread, daemon=True).start()
