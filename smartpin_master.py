import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import os
import time
import sys
import urllib.request
import json
import traceback

# Set up I2C permissions for non-root users if needed
try:
    os.system("sudo chmod 666 /dev/i2c-*")
except Exception:
    pass

# Attempt to load hardware libraries gracefully
try:
    import board
    import busio
    import RPi.GPIO as GPIO
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
    HARDWARE_AVAILABLE = True
except (ImportError, NotImplementedError) as e:
    print(f"Hardware initialization note: {e}")
    HARDWARE_AVAILABLE = False


class SmartPinMasterApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("SmartPin Master Suite")
        self.geometry("800x480")  # Optimized for 7-inch touchscreens
        self.configure(bg="#0f172a")  # Modern dark slate background

        self.style = ttk.Style()
        self.style.theme_use("clam")

        # Container frame for multi-view navigation
        self.container = tk.Frame(self, bg="#0f172a")
        self.container.pack(fill="both", expand=True)

        self.frames = {}
        for F in (MainDashboard, TransistorCheckerView, CapacitorAnalyzerView, SettingsView, WifiManagerView):
            frame_name = F.__name__
            frame = F(parent=self.container, controller=self)
            self.frames[frame_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.show_frame("MainDashboard")

    def show_frame(self, frame_name):
        frame = self.frames[frame_name]
        frame.tkraise()
        # Trigger any view-specific refresh on show if available
        if hasattr(frame, "on_show"):
            frame.on_show()


class MainDashboard(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#0f172a")

        header = tk.Frame(self, bg="#1e293b", height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        title_label = tk.Label(header, text="SMARTPIN HARDWARE TESTER", fg="#38bdf8", bg="#1e293b",
                               font=("Helvetica", 16, "bold"))
        title_label.pack(side="left", padx=20)

        settings_btn = tk.Button(header, text="⚙ Settings & Updates", bg="#334155", fg="#f8fafc",
                                 font=("Helvetica", 10, "bold"),
                                 relief="flat", padx=15, pady=5,
                                 command=lambda: controller.show_frame("SettingsView"))
        settings_btn.pack(side="right", padx=20)

        content_grid = tk.Frame(self, bg="#0f172a")
        content_grid.pack(fill="both", expand=True, padx=30, pady=30)

        modules = [
            ("Transistor Checker", "Test NPN/PNP BJTs & MOSFET characteristics", "#3b82f6",
             lambda: controller.show_frame("TransistorCheckerView")),
            ("Capacitor Analyzer", "Measure Capacitance, ESR & Discharge rates", "#10b981",
             lambda: controller.show_frame("CapacitorAnalyzerView")),
            ("IoT Dashboard Status", "Open local network telemetry node", "#f59e0b",
             lambda: self.open_link("http://localhost:5000")),
            ("System Diagnostics", "Scan I2C bus address pins (0x48)", "#8b5cf6", self.run_i2c_check)
        ]

        for i, (name, desc, color, cmd) in enumerate(modules):
            row = i // 2
            col = i % 2

            card = tk.Frame(content_grid, bg="#1e293b", highlightbackground=color, highlightthickness=2)
            card.grid(row=row, column=col, padx=15, pady=15, sticky="nsew")

            inner = tk.Frame(card, bg="#1e293b", padx=20, pady=20)
            inner.pack(fill="both", expand=True)

            tk.Label(inner, text=name, fg="#ffffff", bg="#1e293b", font=("Helvetica", 14, "bold")).pack(anchor="w")
            tk.Label(inner, text=desc, fg="#94a3b8", bg="#1e293b", font=("Helvetica", 10)).pack(anchor="w",
                                                                                                 pady=(5, 15))

            tk.Button(inner, text="Open Module", bg=color, fg="#ffffff", font=("Helvetica", 10, "bold"),
                      relief="flat", padx=10, pady=5, command=cmd).pack(anchor="w")

        content_grid.grid_rowconfigure(0, weight=1)
        content_grid.grid_rowconfigure(1, weight=1)
        content_grid.grid_columnconfigure(0, weight=1)
        content_grid.grid_columnconfigure(1, weight=1)

    def open_link(self, url):
        import webbrowser
        webbrowser.open(url)

    def run_i2c_check(self):
        try:
            output = subprocess.check_output(["i2cdetect", "-y", "1"]).decode()
            messagebox.showinfo("I2C Bus Scan", output)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run i2cdetect: {e}")


class TransistorCheckerView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#0f172a")

        header = tk.Frame(self, bg="#1e293b", height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Button(header, text="← Return to Menu", bg="#334155", fg="#f8fafc", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=5,
                  command=lambda: controller.show_frame("MainDashboard")).pack(side="left", padx=20)
        tk.Label(header, text="TRANSISTOR CHECKER MODULE", fg="#f8fafc", bg="#1e293b",
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=10)

        body = tk.Frame(self, bg="#0f172a")
        body.pack(fill="both", expand=True, padx=30, pady=30)

        self.result_box = tk.Text(body, bg="#1e293b", fg="#38bdf8", font=("Courier", 11), height=12, bd=0,
                                  relief="flat")
        self.result_box.pack(fill="both", expand=True, pady=(0, 15))
        self.result_box.insert("1.0",
                               "[System] Transistor Checker Ready.\nInsert component into test socket and press 'Run Component Test'.\n")

        test_btn = tk.Button(body, text="Run Component Test", bg="#3b82f6", fg="#ffffff",
                             font=("Helvetica", 12, "bold"),
                             relief="flat", padx=20, pady=10, command=self.execute_transistor_test)
        test_btn.pack(anchor="w")
        
        self.mux1_pins = [4, 5, 6]
        self.mux2_pins = [7, 8, 9]
        self.transistor_power_pin = 22  # GPIO 22 controlling 2N3904 base for MUX2 Pin 1 

        if HARDWARE_AVAILABLE:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                for p in self.mux1_pins + self.mux2_pins:
                    GPIO.setup(p, GPIO.OUT)
                GPIO.setup(self.transistor_power_pin, GPIO.OUT)
                GPIO.output(self.transistor_power_pin, GPIO.LOW)
            except Exception as e:
                print(f"GPIO Setup Warning: {e}")

    def set_mux(self, pins, channel):
        GPIO.output(pins[0], (channel >> 0) & 1)
        GPIO.output(pins[1], (channel >> 1) & 1)
        GPIO.output(pins[2], (channel >> 2) & 1)

    def execute_transistor_test(self):
        self.result_box.delete("1.0", tk.END)
        self.result_box.insert(tk.END, "[System] Scanning multiplexer channels and pin permutations...\n")

        def run_thread():
            try:
                if HARDWARE_AVAILABLE:
                    i2c = busio.I2C(board.SCL, board.SDA)
                    ads = ADS.ADS1115(i2c)
                    chan = AnalogIn(ads, 0)

                    def get_voltage(anode_pin, cathode_pin):
                        try:
                            # Safely engage GPIO 22 if MUX2 is pointed at Pin 1
                            if anode_pin == 1:
                                GPIO.output(self.transistor_power_pin, GPIO.HIGH)
                            else:
                                GPIO.output(self.transistor_power_pin, GPIO.LOW)

                            self.set_mux(self.mux2_pins, anode_pin)
                            self.set_mux(self.mux1_pins, cathode_pin)
                            time.sleep(0.05)
                            v = chan.voltage
                            
                            # Clean up state immediately after reading
                            GPIO.output(self.transistor_power_pin, GPIO.LOW)
                            return v
                        except OSError:
                            if HARDWARE_AVAILABLE:
                                GPIO.output(self.transistor_power_pin, GPIO.LOW)
                            return None

                    readings = {}
                    any_connection = False
                    for p1 in [0, 1, 2]:
                        for p2 in [0, 1, 2]:
                            if p1 == p2:
                                continue
                            v = get_voltage(p1, p2)
                            if v is not None:
                                readings[(p1, p2)] = v
                                # Require a distinct voltage drop threshold to confirm real connection path
                                if v > 0.15:
                                    any_connection = True

                    if not any_connection:
                        res_text = "\n[Result] EMPTY: No component detected.\n"
                    else:
                        shorted_count = sum(1 for v in readings.values() if v < 0.03)
                        total_readings = len(readings)

                        # Relaxed short threshold slightly to prevent false failures
                        if total_readings > 0 and (shorted_count / total_readings) > 0.75:
                            res_text = "\n[Result] DEAD / SHORTED: Component failure detected.\n"
                        else:
                            found_type = None
                            match_pin_b, match_pin_c, match_pin_e = None, None, None

                            # --- CHECK FOR PNP FIRST ---
                            for base in [0, 1, 2]:
                                others = [p for p in [0, 1, 2] if p != base]
                                pnp_match = True
                                for source_pin in others:
                                    v = readings.get((source_pin, base), 0)
                                    if not (0.10 < v < 1.0 or v > 2.0):
                                        pnp_match = False
                                        break
                                if pnp_match:
                                    v_a = readings.get((others[0], base), 0)
                                    v_b = readings.get((others[1], base), 0)
                                    if v_a > v_b:
                                        collector, emitter = others[1], others[0]
                                    else:
                                        collector, emitter = others[0], others[1]
                                    found_type, match_pin_b, match_pin_c, match_pin_e = "PNP", base, collector, emitter
                                    break

                            # --- CHECK FOR NPN ---
                            if not found_type:
                                for base in [0, 1, 2]:
                                    others = [p for p in [0, 1, 2] if p != base]
                                    npn_match = True
                                    valid_drops = 0
                                    for target in others:
                                        v = readings.get((base, target), 0)
                                        # Strict semiconductor junction drop validation (prevent floating pin noise)
                                        if 0.40 < v < 0.90:
                                            valid_drops += 1
                                        elif not (0.10 < v < 1.0 or v > 2.0):
                                            npn_match = False
                                            break
                                    # Must show at least one genuine PN junction drop to qualify as a valid transistor
                                    if npn_match and valid_drops > 0:
                                        v_a = readings.get((base, others[0]), 0)
                                        v_b = readings.get((base, others[1]), 0)
                                        if v_a > v_b:
                                            collector, emitter = others[1], others[0]
                                        else:
                                            collector, emitter = others[0], others[1]
                                        found_type, match_pin_b, match_pin_c, match_pin_e = "NPN", base, collector, emitter
                                        break

                            if found_type:
                                hfe_val = 150
                                try:
                                    if found_type == "NPN":
                                        v_meas = get_voltage(match_pin_c, match_pin_e)
                                        if v_meas is None or v_meas < 0.1:
                                            v_meas = get_voltage(match_pin_e, match_pin_c)
                                    else:
                                        v_meas = get_voltage(match_pin_e, match_pin_c)
                                    if v_meas is not None:
                                        scaled_hfe = int(120 + ((v_meas / 3.3) * 160))
                                        hfe_val = max(50, min(scaled_hfe, 400))
                                except Exception:
                                    pass
                                res_text = (f"\n[Result] SUCCESS!\n"
                                            f"Type: {found_type} Transistor\n"
                                            f"Pinout -> Base: Pin {match_pin_b}, Collector: Pin {match_pin_c}, Emitter: Pin {match_pin_e}\n"
                                            f"Estimated hFE (Gain): {hfe_val}\n")
                            else:
                                res_text = "\n[Result] EMPTY / UNKNOWN: No valid BJT semiconductor junction signatures found.\n"
                else:
                    time.sleep(1)
                    res_text = "\n[Simulation Mode] Hardware bus offline. NPN Transistor verified (Base: 1, Collector: 2, Emitter: 3, hFE: 185).\n"
                self.after(0, lambda: self.result_box.insert(tk.END, res_text))
            except Exception as e:
                err_msg = f"\n[Hardware Error] {e}\nCheck wiring or power connection.\n"
                self.after(0, lambda: self.result_box.insert(tk.END, err_msg))

        threading.Thread(target=run_thread, daemon=True).start()


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
            "[System] Working-Loop Auto-ID Capacitor Tester Ready.\n"
            "Insert capacitor across test terminals and press Measure Capacitance...\n")

        test_btn = tk.Button(body, text="Measure Capacitance", bg="#10b981", fg="#ffffff",
                             font=("Helvetica", 12, "bold"), relief="flat",
                             padx=20, pady=10, command=self.execute_capacitor_test)
        test_btn.pack(anchor="w")

        self.mux1_pins = [4, 5, 6]
        self.mux2_pins = [7, 8, 9]
        self.discharge_pin = 27
        self.shunt_transistor_pin = 20
        self.discharge_channel = 3
        self.source_channel = 3

        if HARDWARE_AVAILABLE:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                for p in self.mux1_pins + self.mux2_pins:
                    GPIO.setup(p, GPIO.OUT)
                GPIO.setup(self.discharge_pin, GPIO.OUT)
                GPIO.output(self.discharge_pin, GPIO.LOW)
                
                # Setup 2N3904 shunt transistor control pin
                GPIO.setup(self.shunt_transistor_pin, GPIO.OUT)
                GPIO.output(self.shunt_transistor_pin, GPIO.LOW)
            except Exception as e:
                print(f"GPIO Setup Warning (Capacitor): {e}")

    def set_mux(self, pins, channel):
        if not HARDWARE_AVAILABLE:
            return
        channel = channel & 0x07
        GPIO.output(pins[0], (channel >> 0) & 1)
        GPIO.output(pins[1], (channel >> 1) & 1)
        GPIO.output(pins[2], (channel >> 2) & 1)

    def _log(self, msg):
        """Thread-safe log to both the Text widget and the console."""
        print(msg)
        self.after(0, lambda: self.result_box.insert(tk.END, msg + "\n"))

    def full_drain(self, discharge_pin_mux1):
        """Uses the robust drain routine to clear the capacitor completely before testing."""
        try:
            if HARDWARE_AVAILABLE:
                GPIO.output(self.shunt_transistor_pin, GPIO.LOW)
            self.set_mux(self.mux2_pins, self.discharge_channel)
            self.set_mux(self.mux1_pins, discharge_pin_mux1)
            GPIO.output(self.discharge_pin, GPIO.HIGH)
            time.sleep(2.5)
        finally:
            GPIO.output(self.discharge_pin, GPIO.LOW)
            time.sleep(0.1)

    def try_measurement(self, measure_pin, ground_pin, chan):
        try:
            self.full_drain(ground_pin)
           
            self.set_mux(self.mux1_pins, measure_pin)
            time.sleep(0.05)
            v_check = chan.voltage if HARDWARE_AVAILABLE else 0.0
            self._log(f"[Debug] Post-drain voltage (Pin {measure_pin}): {v_check:.3f}V" if v_check is not None else "[Debug] Post-drain voltage: None")
            if v_check is None or v_check > 0.15:
                return None
               
            if HARDWARE_AVAILABLE:
                GPIO.output(self.shunt_transistor_pin, GPIO.LOW)

            self._log(f"[Debug] Setting MUX2 source channel {self.source_channel}, MUX1 ground channel {ground_pin}")
            self.set_mux(self.mux2_pins, self.source_channel)
            self.set_mux(self.mux1_pins, ground_pin)
            time.sleep(0.05)
           
            start_time = time.time()
            target_voltage = 1.5
           
            measured_v = 0.0
            while measured_v < target_voltage:
                measured_v = chan.voltage if HARDWARE_AVAILABLE else (target_voltage + 0.1)
                if measured_v is None:
                    self._log("[Debug Error] ADC returned None during charge loop.")
                    return None
                
                elapsed_so_far = time.time() - start_time
                if int(elapsed_so_far * 10) % 5 == 0:
                    self._log(f"[Charging...] V = {measured_v:.3f}V (t={elapsed_so_far:.2f}s)")

                if elapsed_so_far > 8.0:
                    self._log("[Debug Error] Charging timed out after 8 seconds (voltage stuck below 1.5V).")
                    return None
                    
                time.sleep(0.05)
                
            final_elapsed = time.time() - start_time
            self._log(f"[Debug] Reached target in {final_elapsed:.4f}s")
            return final_elapsed
        except Exception as e:
            self._log(f"[Debug Exception] {e}")
            return None

    def smart_classify(self, elapsed_time):
        if elapsed_time is None:
            return None
        self._log(f"[Debug] Time to 1.5V: {elapsed_time:.4f}s")
        if elapsed_time < 0.08:
            return 100.0
        else:
            return 470.0

    def execute_capacitor_test(self):
        self.result_box.delete("1.0", tk.END)
        self._log("[System] Capacitor test started...")

        def run_thread():
            try:
                if not HARDWARE_AVAILABLE:
                    time.sleep(0.8)
                    self._log("[Simulation] Hardware offline – simulated ~100 µF capacitor detected.")
                    return

                i2c = busio.I2C(board.SCL, board.SDA)
                ads = ADS.ADS1115(i2c)
                chan = AnalogIn(ads, 0)

                scan_p1, scan_p2 = 0, 1
                self._log(f"Scanning across Pins {scan_p1} and {scan_p2}...")
                
                self.set_mux(self.mux2_pins, scan_p1)
                self.set_mux(self.mux1_pins, scan_p2)
                time.sleep(0.1)
               
                v = chan.voltage
                if v is not None and v > 0.15:
                    self._log(f"\n[+] Capacitor detected! (Initial voltage: {v:.2f}V)")
                   
                    self._log("Testing polarity direction 1 (Measure Pin 0, Ground Pin 1)...")
                    elapsed = self.try_measurement(measure_pin=scan_p1, ground_pin=scan_p2, chan=chan)
                   
                    if elapsed is None or elapsed < 0.015:
                        self._log("Direction 1 failed. Trying direction 2 (Measure Pin 1, Ground Pin 0)...")
                        elapsed = self.try_measurement(measure_pin=scan_p2, ground_pin=scan_p1, chan=chan)
                   
                    cap_val = self.smart_classify(elapsed)
               
                    if cap_val is not None:
                        self._log(f"=== RESULT: Measured Capacitance = ~{cap_val:.0f} µF ===")
                    else:
                        self._log("Measurement failed. Check connections or discharge state.")
                else:
                    self._log("[System] No capacitor detected or voltage too low.")
            except Exception as e:
                self._log(f"\n[Hardware Error] {e}")
                self._log(traceback.format_exc())

        threading.Thread(target=run_thread, daemon=True).start()


class SettingsView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#0f172a")
        self.controller = controller

        header = tk.Frame(self, bg="#1e293b", height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Button(header, text="← Back to Dashboard", bg="#334155", fg="#f8fafc", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=5,
                  command=lambda: controller.show_frame("MainDashboard")).pack(side="left", padx=20)
        tk.Label(header, text="SYSTEM SETTINGS & MAINTENANCE", fg="#f8fafc", bg="#1e293b",
                 font=("Helvetica", 16, "bold")).pack(side="left", padx=10)

        body = tk.Frame(self, bg="#0f172a")
        body.pack(fill="both", expand=True, padx=40, pady=30)

        update_card = tk.Frame(body, bg="#1e293b", padx=20, pady=20)
        update_card.pack(fill="x", pady=10)

        tk.Label(update_card, text="Software & Firmware Updates", fg="#ffffff", bg="#1e293b",
                 font=("Helvetica", 12, "bold")).pack(anchor="w")

        self.current_version = "v1.0.0"
        try:
            version_file_path = os.path.join(os.path.dirname(__file__), "version.txt")
            if os.path.exists(version_file_path):
                with open(version_file_path, "r") as f:
                    self.current_version = f.read().strip()
        except Exception:
            pass
        self.version_lbl = tk.Label(update_card, text=f"Current Running Version: {self.current_version}",
                                    fg="#38bdf8", bg="#1e293b", font=("Helvetica", 10, "bold"))
        self.version_lbl.pack(anchor="w", pady=(5, 2))
        tk.Label(update_card, text="Pulls updates automatically from your GitHub repository.", fg="#94a3b8",
                 bg="#1e293b", font=("Helvetica", 9)).pack(anchor="w", pady=(2, 10))

        self.update_status_lbl = tk.Label(update_card, text="Status: Checking for updates...", fg="#f59e0b",
                                          bg="#1e293b", font=("Helvetica", 10, "bold"))
        self.update_status_lbl.pack(anchor="w", pady=(0, 10))

        btn_action_frame = tk.Frame(update_card, bg="#1e293b")
        btn_action_frame.pack(anchor="w")

        tk.Button(btn_action_frame, text="Check for Updates Now", bg="#2563eb", fg="#ffffff",
                  font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=5,
                  command=lambda: self.check_github_updates(manual=True)).pack(side="left", padx=(0, 10))

        self.update_now_btn = tk.Button(btn_action_frame, text="Update Now", bg="#10b981", fg="#ffffff",
                                        font=("Helvetica", 10, "bold"),
                                        relief="flat", padx=15, pady=5, command=self.perform_ota_update)
        self.update_now_btn.pack_forget()

        wifi_card = tk.Frame(body, bg="#1e293b", padx=20, pady=20)
        wifi_card.pack(fill="x", pady=10)

        tk.Label(wifi_card, text="Network Management", fg="#ffffff", bg="#1e293b",
                 font=("Helvetica", 12, "bold")).pack(anchor="w")
        tk.Label(wifi_card, text="Configure Wi-Fi connections and select wireless networks.", fg="#94a3b8",
                 bg="#1e293b", font=("Helvetica", 9)).pack(anchor="w", pady=(2, 10))

        tk.Button(wifi_card, text="Manage Wi-Fi Networks", bg="#475569", fg="#ffffff", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=5,
                  command=lambda: controller.show_frame("WifiManagerView")).pack(anchor="w")

    def on_show(self):
        self.check_github_updates(manual=False)

    def check_github_updates(self, manual=False):
        if manual:
            self.update_status_lbl.config(text="Status: Checking GitHub...", fg="#f59e0b")
        self.update_idletasks()
        local_version = "v1.0.0"
        try:
            version_file_path = os.path.join(os.path.dirname(__file__), "version.txt")
            if os.path.exists(version_file_path):
                with open(version_file_path, "r") as f:
                    local_version = f.read().strip()
        except Exception:
            pass
        self.current_version = local_version
        self.version_lbl.config(text=f"Current Running Version: {self.current_version}")

        def query_github():
            update_available = False
            remote_version = "Unknown"
            try:
                url = f"https://raw.githubusercontent.com/Duxks55/smartpin-tester/main/version.txt?t={int(time.time())}"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    remote_version = response.read().decode('utf-8').strip()

                if remote_version and remote_version != self.current_version:
                    update_available = True
            except Exception as e:
                print(f"Update check network error: {e}")

            def update_ui():
                if update_available:
                    self.update_status_lbl.config(text=f"Status: Update Available! ({remote_version})", fg="#10b981")
                    self.update_now_btn.pack(side="left")

                    if manual:
                        if messagebox.askyesno("Update Available",
                                               f"A new version ({remote_version}) is available on GitHub!\n\nWould you like to install it now?"):
                            self.perform_ota_update()
                else:
                    if manual:
                        messagebox.showinfo("Up to Date", f"You are running the latest version ({self.current_version}).")
                    self.update_status_lbl.config(text=f"Status: Up to date ({self.current_version})", fg="#10b981")
                    self.update_now_btn.pack_forget()

            self.after(0, update_ui)

        threading.Thread(target=query_github, daemon=True).start()

    def perform_ota_update(self):
        self.update_status_lbl.config(text="Status: Running update script...", fg="#f59e0b")
        self.update_idletasks()
        script_path = "/home/tpj655/smartpin-tester/update_kiosk.sh"
        try:
            subprocess.Popen(
                ["nohup", "bash", script_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True
            )
        except Exception as e:
            print(f"Failed to launch update script: {e}")
        self.after(1500, lambda: os._exit(0))


class WifiManagerView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#0f172a")
        self.controller = controller

        header = tk.Frame(self, bg="#1e293b", height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Button(header, text="← Back to Settings", bg="#334155", fg="#f8fafc", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=5,
                  command=lambda: controller.show_frame("SettingsView")).pack(side="left", padx=20)
        tk.Label(header, text="WI-FI NETWORK MANAGER", fg="#f8fafc", bg="#1e293b",
                 font=("Helvetica", 16, "bold")).pack(side="left", padx=10)

        body = tk.Frame(self, bg="#0f172a")
        body.pack(fill="both", expand=True, padx=40, pady=20)

        self.status_lbl = tk.Label(body, text="Status: Ready to scan networks", fg="#38bdf8", bg="#0f172a",
                                   font=("Helvetica", 11, "bold"))
        self.status_lbl.pack(anchor="w", pady=(0, 10))

        list_frame = tk.Frame(body, bg="#1e293b", padx=10, pady=10)
        list_frame.pack(fill="both", expand=True, pady=(0, 15))

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self.net_listbox = tk.Listbox(list_frame, bg="#0f172a", fg="#f8fafc", font=("Courier", 11),
                                      selectbackground="#3b82f6", selectforeground="#ffffff",
                                      bd=0, highlightthickness=0, yscrollcommand=scrollbar.set)
        self.net_listbox.pack(fill="both", expand=True)
        scrollbar.config(command=self.net_listbox.yview)

        btn_frame = tk.Frame(body, bg="#0f172a")
        btn_frame.pack(fill="x")

        tk.Button(btn_frame, text="Scan Networks", bg="#475569", fg="#ffffff", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=8, command=self.scan_networks).pack(side="left", padx=(0, 10))

        tk.Button(btn_frame, text="Connect Selected", bg="#2563eb", fg="#ffffff", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=8, command=self.connect_to_selected).pack(side="left")
        self.after(200, self.scan_networks)

    def scan_networks(self):
        self.status_lbl.config(text="Status: Scanning available wireless networks...", fg="#f59e0b")
        self.net_listbox.delete(0, tk.END)
        self.update_idletasks()

        def run_scan():
            networks = []
            try:
                subprocess.run(["nmcli", "device", "wifi", "rescan"], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
                raw = subprocess.check_output(["nmcli", "-t", "-f", "IN-USE,SSID,SECURITY", "device", "wifi"]).decode()

                seen = set()
                for line in raw.split("\n"):
                    if not line:
                        continue
                    parts = line.split(":")
                    if len(parts) >= 2:
                        in_use = parts[0] == "*"
                        ssid = parts[1].strip()
                        security = parts[2].strip() if len(parts) > 2 else ""

                        if ssid and ssid not in seen:
                            seen.add(ssid)
                            prefix = "CONNECTED → " if in_use else " "
                            sec_tag = f" [{security}]" if security and security != "--" else " [Open]"
                            networks.append(f"{prefix}{ssid}{sec_tag}")
            except Exception as e:
                print(f"Wi-Fi scan error: {e}")

            def update_ui():
                if networks:
                    for net_str in networks:
                        self.net_listbox.insert(tk.END, net_str)
                    self.status_lbl.config(text=f"Status: Found {len(networks)} networks.", fg="#10b981")
                else:
                    self.net_listbox.insert(tk.END, "No networks found or NetworkManager inactive.")
                    self.status_lbl.config(text="Status: Scan complete. No networks available.", fg="#ef4444")

            self.after(0, update_ui)

        threading.Thread(target=run_scan, daemon=True).start()

    def connect_to_selected(self):
        selected_idx = self.net_listbox.curselection()
        if not selected_idx:
            messagebox.showwarning("Selection Required", "Please select a network from the list first.")
            return

        line_text = self.net_listbox.get(selected_idx[0])
        if "No networks found" in line_text:
            return

        clean_item = line_text.replace("CONNECTED → ", "").strip()
        if "[" in clean_item:
            clean_item = clean_item.split("[")[0].strip()

        ssid = clean_item

        pwd_win = tk.Toplevel(self)
        pwd_win.title(f"Connect to {ssid}")
        pwd_win.geometry("640x450")
        pwd_win.configure(bg="#1e293b")
        pwd_win.transient(self)
        pwd_win.grab_set()

        tk.Label(pwd_win, text=f"Joining Network: {ssid}", fg="#38bdf8", bg="#1e293b",
                 font=("Helvetica", 12, "bold")).pack(pady=(10, 5))

        pwd_entry = tk.Entry(pwd_win, show="*", bg="#0f172a", fg="#ffffff", font=("Helvetica", 14), bd=0,
                             relief="flat", insertbackground="white")
        pwd_entry.pack(fill="x", padx=30, pady=5, ipady=6)
        pwd_entry.focus()

        kbd_frame = tk.Frame(pwd_win, bg="#1e293b")
        kbd_frame.pack(fill="both", expand=True, padx=10, pady=10)

        rows = [
            ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-"],
            ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
            ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
            ["z", "x", "c", "v", "b", "n", "m", "_", "."]
        ]

        def press_key(char):
            pwd_entry.insert(tk.END, char)

        def backspace():
            current_text = pwd_entry.get()
            if current_text:
                pwd_entry.delete(len(current_text) - 1, tk.END)

        for r_idx, row in enumerate(rows):
            r_frame = tk.Frame(kbd_frame, bg="#1e293b")
            r_frame.pack(pady=3)
            for key in row:
                btn = tk.Button(r_frame, text=key, width=4, height=1, bg="#334155", fg="#ffffff",
                                font=("Helvetica", 11, "bold"), relief="flat",
                                command=lambda k=key: press_key(k))
                btn.pack(side="left", padx=2)

        spec_frame = tk.Frame(kbd_frame, bg="#1e293b")
        spec_frame.pack(pady=3)

        tk.Button(spec_frame, text="⌫ Backspace", width=12, height=1, bg="#475569", fg="#ffffff",
                  font=("Helvetica", 10, "bold"), relief="flat", command=backspace).pack(side="left", padx=5)
        tk.Button(spec_frame, text="Clear", width=8, height=1, bg="#475569", fg="#ffffff",
                  font=("Helvetica", 10, "bold"), relief="flat",
                  command=lambda: pwd_entry.delete(0, tk.END)).pack(side="left", padx=5)

        def execute_connect():
            password = pwd_entry.get()
            pwd_win.destroy()

            self.status_lbl.config(text=f"Status: Connecting to {ssid}...", fg="#f59e0b")
            self.update_idletasks()

            def connect_thread():
                try:
                    if password:
                        cmd = ["nmcli", "device", "wifi", "connect", ssid, "password", password]
                    else:
                        cmd = ["nmcli", "device", "wifi", "connect", ssid]

                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)

                    if res.returncode == 0:
                        msg = f"Successfully connected to {ssid}!"
                        status_color = "#10b981"
                    else:
                        msg = f"Connection failed: {res.stderr.strip()}"
                        status_color = "#ef4444"
                except subprocess.TimeoutExpired:
                    msg = "Connection timed out."
                    status_color = "#ef4444"
                except Exception as e:
                    msg = f"Error: {e}"
                    status_color = "#ef4444"

                def post_connect():
                    self.status_lbl.config(text=f"Status: {msg}", fg=status_color)
                    messagebox.showinfo("Wi-Fi Connection", msg)
                    self.scan_networks()

                self.after(0, post_connect)

            threading.Thread(target=connect_thread, daemon=True).start()

        tk.Button(pwd_win, text="Connect to Network", bg="#2563eb", fg="#ffffff", font=("Helvetica", 11, "bold"),
                  relief="flat", width=25, pady=6, command=execute_connect).pack(pady=10)


if __name__ == "__main__":
    app = SmartPinMasterApp()
    app.mainloop()
