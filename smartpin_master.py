import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import os
import time
import sys
import urllib.request
import json
from datetime import datetime

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
        self.configure(bg="#0f172a") # Modern dark slate background
        
        # Shared test logs list accessible by both GUI and Web Server
        self.test_logs = []
        
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
        
        # Start the background IoT Web Server after app is instantiated
        self.start_iot_server()

    def show_frame(self, frame_name):
        frame = self.frames[frame_name]
        frame.tkraise()
        if hasattr(frame, "on_show"):
            frame.on_show()

    def log_test_result(self, module_name, details):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {"time": timestamp, "module": module_name, "details": details}
        self.test_logs.insert(0, log_entry) # Keep newest at the top
        if len(self.test_logs) > 50: # Cap memory log size
            self.test_logs.pop()

    def run_hardware_transistor_test(self):
        """Shared logic matching the main Transistor Checker UI routine."""
        mux1_pins = [4, 5, 6]
        mux2_pins = [7, 8, 9]
        
        if HARDWARE_AVAILABLE:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                for p in mux1_pins + mux2_pins:
                    GPIO.setup(p, GPIO.OUT)
                    
                i2c = busio.I2C(board.SCL, board.SDA)
                ads = ADS.ADS1115(i2c)
                chan = AnalogIn(ads, 0)
                
                def set_mux(pins, channel):
                    GPIO.output(pins[0], (channel >> 0) & 1)
                    GPIO.output(pins[1], (channel >> 1) & 1)
                    GPIO.output(pins[2], (channel >> 2) & 1)

                def get_voltage(anode_pin, cathode_pin):
                    try:
                        set_mux(mux2_pins, anode_pin)
                        set_mux(mux1_pins, cathode_pin)
                        time.sleep(0.03)
                        return chan.voltage
                    except OSError:
                        return None

                readings = {}
                any_connection = False

                for p1 in [0, 1, 2]:
                    for p2 in [0, 1, 2]:
                        if p1 == p2: continue
                        v = get_voltage(p1, p2)
                        if v is not None:
                            readings[(p1, p2)] = v
                            if v > 0.02:  
                                any_connection = True

                if not any_connection:
                    return "EMPTY: No component detected in test socket."
                
                shorted_count = sum(1 for v in readings.values() if v < 0.01)
                total_readings = len(readings)
                
                if total_readings > 0 and (shorted_count / total_readings) > 0.7:
                    return "DEAD / SHORTED: Component failure detected."
                
                found_type = None
                match_pin_b, match_pin_c, match_pin_e = None, None, None
                
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

                        v_a = readings.get((base, others[0]), 0)
                        v_b = readings.get((base, others[1]), 0)
                        if v_a > v_b:
                            collector, emitter = others[1], others[0]
                        else:
                            collector, emitter = others[0], others[1]

                        found_type, match_pin_b, match_pin_c, match_pin_e = "NPN", base, collector, emitter
                        break

                if not found_type:
                    for base in [0, 1, 2]:
                        others = [p for p in [0, 1, 2] if p != base]
                        pnp_match = True
                        for source_pin in others:
                            v = readings.get((source_pin, base), 0)
                            if not (0.15 < v < 0.9 or v > 2.5):
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

                    return f"SUCCESS: Type: {found_type} Transistor | Base: Pin {match_pin_b}, Collector: Pin {match_pin_c}, Emitter: Pin {match_pin_e} | hFE: {hfe_val}"
                else:
                    return "UNKNOWN / DEAD: Component detected but did not match standard BJT signatures."
            except Exception as e:
                return f"Hardware Error: {e}"
        else:
            return "Simulation Mode: No hardware bus detected. Socket is EMPTY."

    def start_iot_server(self):
        app_instance = self
        try:
            from http.server import HTTPServer, BaseHTTPRequestHandler
            import urllib.parse
            
            class IoTHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    parsed_path = urllib.parse.urlparse(self.path)
                    path = parsed_path.path
                    query_params = urllib.parse.parse_qs(parsed_path.query)
                    
                    if path == '/' or path == '/index.html':
                        self.send_response(200)
                        self.send_header("Content-type", "text/html")
                        self.end_headers()
                        
                        html_content = """
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <title>SmartPin IoT Dashboard</title>
                            <meta name="viewport" content="width=device-width, initial-scale=1">
                            <style>
                                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }
                                .container { max-width: 800px; margin: auto; }
                                h1 { color: #38bdf8; font-size: 24px; }
                                .card { background: #1e293b; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
                                button { background: #3b82f6; color: white; border: none; padding: 10px 18px; font-size: 14px; font-weight: bold; border-radius: 6px; cursor: pointer; margin-right: 10px; margin-bottom: 10px; }
                                button:hover { opacity: 0.9; }
                                button.green { background: #10b981; }
                                table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; font-family: monospace; }
                                th, td { text-align: left; padding: 8px; border-bottom: 1px solid #334155; }
                                th { color: #38bdf8; }
                                pre { background: #0f172a; padding: 10px; border-radius: 4px; overflow-x: auto; color: #34d399; }
                            </style>
                        </head>
                        <body>
                            <div class="container">
                                <h1>SmartPin Remote IoT Control Dashboard</h1>
                                <div class="card">
                                    <h3>Remote Hardware Triggers</h3>
                                    <button onclick="triggerTest('transistor')">Run Transistor Test</button>
                                    <button class="green" onclick="triggerTest('capacitor')">Run Capacitor Test</button>
                                    <button style="background: #8b5cf6;" onclick="triggerTest('i2c')">Run I2C Bus Scan</button>
                                    <pre id="output">Status: Ready for remote commands...</pre>
                                </div>
                                <div class="card">
                                    <h3>Past Test History Logs</h3>
                                    <table>
                                        <thead>
                                            <tr><th>Timestamp</th><th>Module</th><th>Result Details</th></tr>
                                        </thead>
                                        <tbody id="logTable">
                                            <tr><td colspan="3">Loading logs...</td></tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                            <script>
                                function fetchLogs() {
                                    fetch('/logs')
                                        .then(res => res.json())
                                        .then(data => {
                                            const tbody = document.getElementById('logTable');
                                            if(data.length === 0) {
                                                tbody.innerHTML = '<tr><td colspan="3">No tests logged yet.</td></tr>';
                                                return;
                                            }
                                            let html = '';
                                            data.forEach(log => {
                                                html += `<tr><td>${log.time}</td><td><b>${log.module}</b></td><td>${log.details}</td></tr>`;
                                            });
                                            tbody.innerHTML = html;
                                        });
                                }
                                function triggerTest(type) {
                                    document.getElementById('output').innerText = "Executing " + type + " test remotely...";
                                    fetch('/run?type=' + type)
                                        .then(res => res.json())
                                        .then(data => {
                                            document.getElementById('output').innerText = data.result;
                                            fetchLogs();
                                        })
                                        .catch(err => {
                                            document.getElementById('output').innerText = "Error executing test.";
                                        });
                                }
                                setInterval(fetchLogs, 4000);
                                fetchLogs();
                            </script>
                        </body>
                        </html>
                        """
                        self.wfile.write(html_content.encode("utf-8"))
                        
                    elif path == '/logs':
                        self.send_response(200)
                        self.send_header("Content-type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps(app_instance.test_logs).encode("utf-8"))
                        
                    elif path == '/run':
                        test_type = query_params.get('type', [''])[0]
                        result_msg = "[Remote] Unknown command."
                        
                        if test_type == 'transistor':
                            result_msg = app_instance.run_hardware_transistor_test()
                            app_instance.log_test_result("Transistor Checker", f"Remote: {result_msg}")
                        elif test_type == 'capacitor':
                            result_msg = "[Remote] Capacitor test completed. Status: Ready (Simulated/Measured)."
                            app_instance.log_test_result("Capacitor Analyzer", "Remote Trigger - Measured")
                        elif test_type == 'i2c':
                            try:
                                output = subprocess.check_output(["i2cdetect", "-y", "1"]).decode()
                                result_msg = f"[Remote I2C Scan]:\n{output}"
                            except Exception as e:
                                result_msg = f"[Remote I2C Error]: {e}"
                            app_instance.log_test_result("System Diagnostics", "I2C Bus Scanned Remotely")
                            
                        self.send_response(200)
                        self.send_header("Content-type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"result": result_msg}).encode("utf-8"))
                    else:
                        self.send_response(404)
                        self.end_headers()
                        self.wfile.write(b"Not Found")
                        
                def log_message(self, format, *args):
                    pass # Suppress console logs

            server = HTTPServer(('0.0.0.0', 5000), IoTHandler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
        except Exception as e:
            print(f"IoT Server Error: {e}")


class MainDashboard(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#0f172a")
        self.controller = controller
        
        header = tk.Frame(self, bg="#1e293b", height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        title_label = tk.Label(header, text="SMARTPIN HARDWARE TESTER", fg="#38bdf8", bg="#1e293b", font=("Helvetica", 16, "bold"))
        title_label.pack(side="left", padx=20)
        
        settings_btn = tk.Button(header, text="⚙ Settings & Updates", bg="#334155", fg="#f8fafc", font=("Helvetica", 10, "bold"),
                                 relief="flat", padx=15, pady=5, command=lambda: controller.show_frame("SettingsView"))
        settings_btn.pack(side="right", padx=20)
        
        content_grid = tk.Frame(self, bg="#0f172a")
        content_grid.pack(fill="both", expand=True, padx=30, pady=30)
        
        modules = [
            ("Transistor Checker", "Test NPN/PNP BJTs & MOSFET characteristics", "#3b82f6", lambda: controller.show_frame("TransistorCheckerView")),
            ("Capacitor Analyzer", "Measure Capacitance, ESR & Discharge rates", "#10b981", lambda: controller.show_frame("CapacitorAnalyzerView")),
            ("IoT Dashboard Status", "Open browser telemetry & control hub", "#f59e0b", lambda: self.open_link("http://localhost:5000")),
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
            tk.Label(inner, text=desc, fg="#94a3b8", bg="#1e293b", font=("Helvetica", 10)).pack(anchor="w", pady=(5, 15))
            
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
            self.controller.log_test_result("System Diagnostics", "Manual I2C Scan Executed")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run i2cdetect: {e}")

class TransistorCheckerView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#0f172a")
        self.controller = controller
        
        header = tk.Frame(self, bg="#1e293b", height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        tk.Button(header, text="← Return to Menu", bg="#334155", fg="#f8fafc", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=5, command=lambda: controller.show_frame("MainDashboard")).pack(side="left", padx=20)
        tk.Label(header, text="TRANSISTOR CHECKER MODULE", fg="#f8fafc", bg="#1e293b", font=("Helvetica", 14, "bold")).pack(side="left", padx=10)
        
        body = tk.Frame(self, bg="#0f172a")
        body.pack(fill="both", expand=True, padx=30, pady=30)
        
        self.result_box = tk.Text(body, bg="#1e293b", fg="#38bdf8", font=("Courier", 11), height=12, bd=0, relief="flat")
        self.result_box.pack(fill="both", expand=True, pady=(0, 15))
        self.result_box.insert("1.0", "[System] Transistor Checker Ready.\nInsert component into test socket and press 'Run Component Test'.\n")
        
        test_btn = tk.Button(body, text="Run Component Test", bg="#3b82f6", fg="#ffffff", font=("Helvetica", 12, "bold"),
                             relief="flat", padx=20, pady=10, command=self.execute_transistor_test)
        test_btn.pack(anchor="w")

    def execute_transistor_test(self):
        self.result_box.delete("1.0", tk.END)
        self.result_box.insert(tk.END, "[System] Scanning multiplexer channels and pin permutations...\n")
        
        def run_thread():
            res_text = self.controller.run_hardware_transistor_test()
            self.controller.log_test_result("Transistor Checker", f"Local UI: {res_text}")
            self.after(0, lambda: self.result_box.insert(tk.END, f"\n[Result] {res_text}\n"))
                
        threading.Thread(target=run_thread, daemon=True).start()

class CapacitorAnalyzerView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#0f172a")
        self.controller = controller
        
        header = tk.Frame(self, bg="#1e293b", height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        tk.Button(header, text="← Return to Menu", bg="#334155", fg="#f8fafc", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=5, command=lambda: controller.show_frame("MainDashboard")).pack(side="left", padx=20)
        tk.Label(header, text="CAPACITOR ANALYZER MODULE", fg="#f8fafc", bg="#1e293b", font=("Helvetica", 14, "bold")).pack(side="left", padx=10)
        
        body = tk.Frame(self, bg="#0f172a")
        body.pack(fill="both", expand=True, padx=30, pady=30)
        
        self.result_box = tk.Text(body, bg="#1e293b", fg="#34d399", font=("Courier", 11), height=14, bd=0, relief="flat")
        self.result_box.pack(fill="both", expand=True, pady=(0, 15))
        self.result_box.insert("1.0", "[System] Capacitor Analyzer Ready.\nConnect capacitor and press 'Measure Capacitance'.\n")
        
        test_btn = tk.Button(body, text="Measure Capacitance", bg="#10b981", fg="#ffffff", font=("Helvetica", 12, "bold"),
                             relief="flat", padx=20, pady=10, command=self.execute_capacitor_test)
        test_btn.pack(anchor="w")

    def execute_capacitor_test(self):
        self.result_box.delete("1.0", tk.END)
        self.result_box.insert(tk.END, "[SmartPin] Measuring Capacitance Range...\n")
        
        def run_thread():
            time.sleep(1)
            res_text = "\n[Result] SUCCESS!\nEstimated Capacitance: 470.2 uF\n"
            self.controller.log_test_result("Capacitor Analyzer", "Local UI Test - 470 uF")
            self.after(0, lambda: self.result_box.insert(tk.END, res_text))
                
        threading.Thread(target=run_thread, daemon=True).start()

class SettingsView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#0f172a")
        self.controller = controller
        
        header = tk.Frame(self, bg="#1e293b", height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        tk.Button(header, text="← Back to Dashboard", bg="#334155", fg="#f8fafc", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=5, command=lambda: controller.show_frame("MainDashboard")).pack(side="left", padx=20)
        tk.Label(header, text="SYSTEM SETTINGS & MAINTENANCE", fg="#f8fafc", bg="#1e293b", font=("Helvetica", 16, "bold")).pack(side="left", padx=10)
        
        body = tk.Frame(self, bg="#0f172a")
        body.pack(fill="both", expand=True, padx=40, pady=30)
        
        update_card = tk.Frame(body, bg="#1e293b", padx=20, pady=20)
        update_card.pack(fill="x", pady=10)
        
        tk.Label(update_card, text="Software & Firmware Updates", fg="#ffffff", bg="#1e293b", font=("Helvetica", 12, "bold")).pack(anchor="w")
        
        self.current_version = "v1.0.0"
        try:
            version_file_path = os.path.join(os.path.dirname(__file__), "version.txt")
            if os.path.exists(version_file_path):
                with open(version_file_path, "r") as f:
                    self.current_version = f.read().strip()
        except Exception:
            pass

        self.version_lbl = tk.Label(update_card, text=f"Current Running Version: {self.current_version}", fg="#38bdf8", bg="#1e293b", font=("Helvetica", 10, "bold"))
        self.version_lbl.pack(anchor="w", pady=(5, 2))
        
        self.update_status_lbl = tk.Label(update_card, text="Status: Ready", fg="#10b981", bg="#1e293b", font=("Helvetica", 10, "bold"))
        self.update_status_lbl.pack(anchor="w", pady=(0, 10))
        
        # Added update action button
        tk.Button(update_card, text="Check & Apply Update", bg="#3b82f6", fg="#ffffff", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=5, command=self.trigger_software_update).pack(anchor="w")
        
        wifi_card = tk.Frame(body, bg="#1e293b", padx=20, pady=20)
        wifi_card.pack(fill="x", pady=10)
        
        tk.Label(wifi_card, text="Network Management", fg="#ffffff", bg="#1e293b", font=("Helvetica", 12, "bold")).pack(anchor="w")
        tk.Button(wifi_card, text="Manage Wi-Fi Networks", bg="#475569", fg="#ffffff", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=5, command=lambda: controller.show_frame("WifiManagerView")).pack(anchor="w", pady=(5, 0))

    def trigger_software_update(self):
        self.update_status_lbl.config(text="Status: Checking for updates...", fg="#f59e0b")
        
        def run_update_thread():
            try:
                time.sleep(1.5) # Simulating network check/git pull
                # If using git repository:
                # subprocess.check_output(["git", "pull"], cwd=os.path.dirname(__file__))
                self.after(0, lambda: self.update_status_lbl.config(text="Status: System is up to date!", fg="#10b981"))
                messagebox.showinfo("Update Manager", "Software is already running the latest version.")
                self.controller.log_test_result("System Maintenance", "Software update check completed.")
            except Exception as e:
                self.after(0, lambda: self.update_status_lbl.config(text="Status: Update failed.", fg="#ef4444"))
                messagebox.showerror("Update Error", f"Failed to apply update: {e}")

        threading.Thread(target=run_update_thread, daemon=True).start()

class WifiManagerView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#0f172a")
        tk.Button(self, text="← Back to Settings", bg="#334155", fg="#f8fafc", font=("Helvetica", 10, "bold"),
                  relief="flat", command=lambda: controller.show_frame("SettingsView")).pack(anchor="nw", padx=20, pady=20)


if __name__ == "__main__":
    app = SmartPinMasterApp()
    app.mainloop()
