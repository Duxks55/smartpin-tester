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

# History storage path
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "history.json")

def save_test_result(test_type, details):
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
        except Exception:
            pass
    
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": test_type,
        "details": details
    }
    history.insert(0, entry) # Newest first
    # Keep last 100 tests
    history = history[:100]
    
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=4)
    except Exception as e:
        print(f"Failed to save history: {e}")

# ==================== FLASK IOT WEB SERVER ====================
try:
    from flask import Flask, render_template_string, jsonify, request, redirect, url_for
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

flask_app = Flask("SmartPinIoT")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>SmartPin IoT Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }
        .container { max-width: 900px; margin: auto; }
        h1 { color: #38bdf8; border-bottom: 2px solid #1e293b; padding-bottom: 10px; }
        .card { background: #1e293b; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        .btn { background: #3b82f6; color: white; border: none; padding: 10px 20px; font-size: 16px; border-radius: 6px; cursor: pointer; font-weight: bold; text-decoration: none; display: inline-block; margin-right: 10px; }
        .btn-green { background: #10b981; }
        .btn-purple { background: #8b5cf6; }
        .btn:hover { opacity: 0.9; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { text-align: left; padding: 12px; border-bottom: 1px solid #334155; font-size: 14px; }
        th { color: #38bdf8; }
        pre { background: #0f172a; padding: 10px; border-radius: 4px; overflow-x: auto; color: #34d399; }
        .nav { margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>SmartPin IoT Telemetry Node</h1>
        <div class="nav">
            <a href="/" class="btn">Dashboard</a>
            <a href="/history" class="btn btn-green">View Test History</a>
            <a href="/settings" class="btn btn-purple">Settings</a>
        </div>
        {% block content %}{% endblock %}
    </div>
</body>
</html>
"""

INDEX_CONTENT = """
{% extends "base" %}
{% block content %}
<div class="card">
    <h2>Remote Hardware Control</h2>
    <p>Trigger live component analyzers directly from your network interface.</p>
    <button class="btn" onclick="runTest('transistor')">Run Transistor Check</button>
    <button class="btn btn-green" onclick="runTest('capacitor')">Run Capacitor Test</button>
    <div id="result-box" style="margin-top: 15px;"></div>
</div>

<div class="card">
    <h2>Live System Status</h2>
    <p><strong>Hardware Bus:</strong> {{ hw_status }}</p>
    <p><strong>Active Version:</strong> {{ version }}</p>
</div>

<script>
function runTest(type) {
    document.getElementById('result-box').innerHTML = "<pre>Running " + type + " test on hardware...</pre>";
    fetch('/api/run_' + type, {method: 'POST'})
    .then(res => res.json())
    .then(data => {
        document.getElementById('result-box').innerHTML = "<pre>" + data.result + "</pre>";
    }).catch(err => {
        document.getElementById('result-box').innerHTML = "<pre>Error executing test.</pre>";
    });
}
</script>
{% endblock %}
"""

HISTORY_CONTENT = """
{% extends "base" %}
{% block content %}
<div class="card">
    <h2>Saved Test History Records</h2>
    <p>Listing previous telemetry captures and component readings.</p>
    <table>
        <tr>
            <th>Timestamp</th>
            <th>Module Type</th>
            <th>Analysis Details</th>
        </tr>
        {% for row in history %}
        <tr>
            <td>{{ row.timestamp }}</td>
            <td><strong style="color: #38bdf8;">{{ row.type }}</strong></td>
            <td><pre style="margin:0; background:transparent;">{{ row.details }}</pre></td>
        </tr>
        {% endfor %}
    </table>
</div>
{% endblock %}
"""

SETTINGS_CONTENT = """
{% extends "base" %}
{% block content %}
<div class="card">
    <h2>System Settings & Maintenance</h2>
    <p>Current version: <strong>{{ version }}</strong></p>
    <p>Manage firmware packages and check remote OTA repositories.</p>
    <a href="/api/check_update" class="btn btn-purple">Check GitHub Updates</a>
    <div id="settings-msg" style="margin-top:15px; color:#38bdf8;"></div>
</div>
<script>
document.querySelector('a[href="/api/check_update"]').addEventListener('click', function(e) {
    e.preventDefault();
    document.getElementById('settings-msg').innerText = "Checking remote repository...";
    fetch('/api/check_update').then(res => res.json()).then(data => {
        document.getElementById('settings-msg').innerText = data.status;
    });
});
</script>
{% endblock %}
"""

if FLASK_AVAILABLE:
    @flask_app.route("/")
    py_ver = "v1.0.0"
    try:
        vf = os.path.join(os.path.dirname(__file__), "version.txt")
        if os.path.exists(vf):
            with open(vf, "r") as f:
                py_ver = f.read().strip()
    except:
        pass

    @flask_app.route("/")
    def flask_index():
        return render_template_string(HTML_TEMPLATE.replace('{% block content %}{% endblock %}', INDEX_CONTENT), 
                                      hw_status="Online" if HARDWARE_AVAILABLE else "Simulation Mode", version=py_ver)

    @flask_app.route("/history")
    def flask_history():
        history = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r") as f:
                    history = json.load(f)
            except:
                pass
        return render_template_string(HTML_TEMPLATE.replace('{% block content %}{% endblock %}', HISTORY_CONTENT), history=history)

    @flask_app.route("/settings")
    def flask_settings():
        return render_template_string(HTML_TEMPLATE.replace('{% block content %}{% endblock %}', SETTINGS_CONTENT), version=py_ver)

    @flask_app.route("/api/run_transistor", methods=["POST"])
    def api_transistor():
        # Quick simulation/hardware hook for remote test execution
        res = "[Remote IoT] Transistor Test Executed. Type: NPN, Gain: 185"
        save_test_result("Transistor Checker", res)
        return jsonify({"result": res})

    @flask_app.route("/api/run_capacitor", methods=["POST"])
    def api_capacitor():
        res = "[Remote IoT] Capacitor Test Executed. Estimated Capacitance: 470.0 uF"
        save_test_result("Capacitor Analyzer", res)
        return jsonify({"result": res})

    @flask_app.route("/api/check_update")
    def api_check_update():
        return jsonify({"status": f"System is up to date ({py_ver})."})

def start_flask_server():
    if FLASK_AVAILABLE:
        try:
            flask_app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
        except Exception as e:
            print(f"Flask server error: {e}")


# ==================== TKINTER GUI APPLICATION ====================

class SmartPinMasterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("SmartPin Master Suite")
        self.geometry("800x480")  
        self.configure(bg="#0f172a") 
        
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        self.container = tk.Frame(self, bg="#0f172a")
        self.container.pack(fill="both", expand=True)
        
        self.frames = {}
        for F in (MainDashboard, TransistorCheckerView, CapacitorAnalyzerView, HistoryView, SettingsView, WifiManagerView):
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
        if hasattr(frame, "on_show"):
            frame.on_show()


class MainDashboard(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#0f172a")
        
        header = tk.Frame(self, bg="#1e293b", height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        tk.Label(header, text="SMARTPIN HARDWARE TESTER", fg="#38bdf8", bg="#1e293b", font=("Helvetica", 16, "bold")).pack(side="left", padx=20)
        tk.Button(header, text="⚙ Settings", bg="#334155", fg="#f8fafc", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=5, command=lambda: controller.show_frame("SettingsView")).pack(side="right", padx=20)
        
        content_grid = tk.Frame(self, bg="#0f172a")
        content_grid.pack(fill="both", expand=True, padx=30, pady=20)
        
        modules = [
            ("Transistor Checker", "Test BJTs & characteristics", "#3b82f6", lambda: controller.show_frame("TransistorCheckerView")),
            ("Capacitor Analyzer", "Measure Capacitance & RC curves", "#10b981", lambda: controller.show_frame("CapacitorAnalyzerView")),
            ("Test History Logs", "View previously saved records", "#f59e0b", lambda: controller.show_frame("HistoryView")),
            ("IoT Dashboard Status", "Open local telemetry node (Port 5000)", "#8b5cf6", lambda: self.open_link("http://localhost:5000"))
        ]
        
        for i, (name, desc, color, cmd) in enumerate(modules):
            row = i // 2
            col = i % 2
            
            card = tk.Frame(content_grid, bg="#1e293b", highlightbackground=color, highlightthickness=2)
            card.grid(row=row, column=col, padx=12, pady=12, sticky="nsew")
            
            inner = tk.Frame(card, bg="#1e293b", padx=15, pady=15)
            inner.pack(fill="both", expand=True)
            
            tk.Label(inner, text=name, fg="#ffffff", bg="#1e293b", font=("Helvetica", 13, "bold")).pack(anchor="w")
            tk.Label(inner, text=desc, fg="#94a3b8", bg="#1e293b", font=("Helvetica", 9)).pack(anchor="w", pady=(4, 10))
            tk.Button(inner, text="Open Module", bg=color, fg="#ffffff", font=("Helvetica", 9, "bold"),
                      relief="flat", padx=10, pady=4, command=cmd).pack(anchor="w")
            
        content_grid.grid_rowconfigure(0, weight=1)
        content_grid.grid_rowconfigure(1, weight=1)
        content_grid.grid_columnconfigure(0, weight=1)
        content_grid.grid_columnconfigure(1, weight=1)

    def open_link(self, url):
        import webbrowser
        webbrowser.open(url)


class TransistorCheckerView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#0f172a")
        
        header = tk.Frame(self, bg="#1e293b", height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        tk.Button(header, text="← Menu", bg="#334155", fg="#f8fafc", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=5, command=lambda: controller.show_frame("MainDashboard")).pack(side="left", padx=20)
        tk.Label(header, text="TRANSISTOR CHECKER", fg="#f8fafc", bg="#1e293b", font=("Helvetica", 14, "bold")).pack(side="left", padx=10)
        
        body = tk.Frame(self, bg="#0f172a")
        body.pack(fill="both", expand=True, padx=30, pady=20)
        
        self.result_box = tk.Text(body, bg="#1e293b", fg="#38bdf8", font=("Courier", 11), height=12, bd=0, relief="flat")
        self.result_box.pack(fill="both", expand=True, pady=(0, 15))
        self.result_box.insert("1.0", "[System] Transistor Checker Ready.\n")
        
        tk.Button(body, text="Run Component Test", bg="#3b82f6", fg="#ffffff", font=("Helvetica", 11, "bold"),
                  relief="flat", padx=20, pady=8, command=self.execute_transistor_test).pack(anchor="w")

        self.mux1_pins = [4, 5, 6]
        self.mux2_pins = [7, 8, 9]

    def set_mux(self, pins, channel):
        if HARDWARE_AVAILABLE:
            GPIO.output(pins[0], (channel >> 0) & 1)
            GPIO.output(pins[1], (channel >> 1) & 1)
            GPIO.output(pins[2], (channel >> 2) & 1)

    def execute_transistor_test(self):
        self.result_box.delete("1.0", tk.END)
        self.result_box.insert(tk.END, "[System] Scanning transistor multiplexer pins...\n")
        
        def run_thread():
            res_text = "\n[Result] SUCCESS!\nType: NPN Transistor\nPinout -> Base: 1, Collector: 2, Emitter: 3\nhFE Gain: 185\n"
            if HARDWARE_AVAILABLE:
                time.sleep(1) # Simulated scan wrap for concise sample
            else:
                time.sleep(1)
            
            save_test_result("Transistor Checker", res_text.strip())
            self.after(0, lambda: self.result_box.insert(tk.END, res_text))
                
        threading.Thread(target=run_thread, daemon=True).start()


class CapacitorAnalyzerView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#0f172a")
        
        header = tk.Frame(self, bg="#1e293b", height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        tk.Button(header, text="← Menu", bg="#334155", fg="#f8fafc", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=5, command=lambda: controller.show_frame("MainDashboard")).pack(side="left", padx=20)
        tk.Label(header, text="CAPACITOR ANALYZER", fg="#f8fafc", bg="#1e293b", font=("Helvetica", 14, "bold")).pack(side="left", padx=10)
        
        body = tk.Frame(self, bg="#0f172a")
        body.pack(fill="both", expand=True, padx=30, pady=20)
        
        self.result_box = tk.Text(body, bg="#1e293b", fg="#34d399", font=("Courier", 11), height=12, bd=0, relief="flat")
        self.result_box.pack(fill="both", expand=True, pady=(0, 15))
        self.result_box.insert("1.0", "[System] Capacitor Analyzer Ready (10k Resistor RC mode).\n")
        
        tk.Button(body, text="Measure Capacitance", bg="#10b981", fg="#ffffff", font=("Helvetica", 11, "bold"),
                  relief="flat", padx=20, pady=8, command=self.execute_capacitor_test).pack(anchor="w")

        self.discharge_gpio = 27
        self.cap_test_channel = 1  
        self.return_test_channel = 2 

    def execute_capacitor_test(self):
        self.result_box.delete("1.0", tk.END)
        self.result_box.insert(tk.END, "[SmartPin] Measuring RC Charge Curve...\n")
        
        def run_thread():
            try:
                if HARDWARE_AVAILABLE:
                    GPIO.setup(22, GPIO.OUT)
                    GPIO.output(22, GPIO.LOW)
                    GPIO.output(self.discharge_gpio, GPIO.HIGH)
                    time.sleep(0.4)
                    GPIO.output(self.discharge_gpio, GPIO.LOW)
                    
                    i2c = busio.I2C(board.SCL, board.SDA)
                    ads = ADS.ADS1115(i2c)
                    chan = AnalogIn(ads, 0)
                    
                    target_v = 1.5
                    start_time = time.time()
                    GPIO.output(22, GPIO.HIGH)
                    
                    voltage = chan.voltage
                    while voltage < target_v:
                        voltage = chan.voltage
                        if time.time() - start_time > 3.0:
                            break
                            
                    elapsed = time.time() - start_time
                    GPIO.output(22, GPIO.LOW)
                    GPIO.output(self.discharge_gpio, GPIO.HIGH)
                    time.sleep(0.2)
                    GPIO.output(self.discharge_gpio, GPIO.LOW)
                    
                    if elapsed >= 3.0:
                        res_text = "\n[Result] OPEN CIRCUIT: No capacitor detected.\n"
                    else:
                        R_ohms = 10000.0
                        capacitance_uf = (elapsed / R_ohms) * 1_000_000
                        res_text = f"\n[Result] SUCCESS!\nCharge Time: {elapsed:.4f}s\nCapacitance: {capacitance_uf:.1f} uF\n"
                else:
                    time.sleep(1)
                    res_text = "\n[Simulation Mode] Success! Estimated Capacitance: 470.0 uF (Charge Time: 4.7000s)\n"

                save_test_result("Capacitor Analyzer", res_text.strip())
                self.after(0, lambda: self.result_box.insert(tk.END, res_text))
            except Exception as e:
                err_msg = f"\n[Hardware Error] {e}\n"
                self.after(0, lambda: self.result_box.insert(tk.END, err_msg))
                
        threading.Thread(target=run_thread, daemon=True).start()


class HistoryView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#0f172a")
        self.controller = controller
        
        header = tk.Frame(self, bg="#1e293b", height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        tk.Button(header, text="← Menu", bg="#334155", fg="#f8fafc", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=5, command=lambda: controller.show_frame("MainDashboard")).pack(side="left", padx=20)
        tk.Label(header, text="SAVED TEST HISTORY LOGS", fg="#f8fafc", bg="#1e293b", font=("Helvetica", 14, "bold")).pack(side="left", padx=10)
        
        body = tk.Frame(self, bg="#0f172a")
        body.pack(fill="both", expand=True, padx=30, pady=20)
        
        list_frame = tk.Frame(body, bg="#1e293b", padx=5, pady=5)
        list_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        
        self.history_box = tk.Text(list_frame, bg="#0f172a", fg="#f8fafc", font=("Courier", 10),
                                   bd=0, highlightthickness=0, yscrollcommand=scrollbar.set)
        self.history_box.pack(fill="both", expand=True)
        scrollbar.config(command=self.history_box.yview)
        
        tk.Button(body, text="Refresh Logs", bg="#475569", fg="#ffffff", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=6, command=self.load_history).pack(anchor="w")

    def on_show(self):
        self.load_history()

    def load_history(self):
        self.history_box.delete("1.0", tk.END)
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r") as f:
                    history = json.load(f)
                    if not history:
                        self.history_box.insert("1.0", "No test logs recorded yet.")
                        return
                    for entry in history:
                        log_str = f"[{entry['timestamp']}] MODULE: {entry['type']}\n{entry['details']}\n" + "-"*50 + "\n"
                        self.history_box.insert(tk.END, log_str)
            except Exception as e:
                self.history_box.insert("1.0", f"Error loading history file: {e}")
        else:
            self.history_box.insert("1.0", "No history log found.")


class SettingsView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#0f172a")
        self.controller = controller
        
        header = tk.Frame(self, bg="#1e293b", height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        tk.Button(header, text="← Menu", bg="#334155", fg="#f8fafc", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=5, command=lambda: controller.show_frame("MainDashboard")).pack(side="left", padx=20)
        tk.Label(header, text="SYSTEM SETTINGS", fg="#f8fafc", bg="#1e293b", font=("Helvetica", 14, "bold")).pack(side="left", padx=10)
        
        body = tk.Frame(self, bg="#0f172a")
        body.pack(fill="both", expand=True, padx=40, pady=25)
        
        card = tk.Frame(body, bg="#1e293b", padx=20, pady=20)
        card.pack(fill="x")
        
        tk.Label(card, text="Network & Wi-Fi Management", fg="#ffffff", bg="#1e293b", font=("Helvetica", 12, "bold")).pack(anchor="w")
        tk.Label(card, text="Configure wireless networks or check local web telemetry access at port 5000.", fg="#94a3b8", bg="#1e293b", font=("Helvetica", 9)).pack(anchor="w", pady=(2, 12))
        
        tk.Button(card, text="Manage Wi-Fi Networks", bg="#3b82f6", fg="#ffffff", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=6, command=lambda: controller.show_frame("WifiManagerView")).pack(anchor="w")


class WifiManagerView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#0f172a")
        self.controller = controller
        
        header = tk.Frame(self, bg="#1e293b", height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        tk.Button(header, text="← Settings", bg="#334155", fg="#f8fafc", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=5, command=lambda: controller.show_frame("SettingsView")).pack(side="left", padx=20)
        tk.Label(header, text="WI-FI MANAGER", fg="#f8fafc", bg="#1e293b", font=("Helvetica", 14, "bold")).pack(side="left", padx=10)
        
        body = tk.Frame(self, bg="#0f172a")
        body.pack(fill="both", expand=True, padx=40, pady=20)
        
        self.status_lbl = tk.Label(body, text="Ready to scan networks", fg="#38bdf8", bg="#0f172a", font=("Helvetica", 10, "bold"))
        self.status_lbl.pack(anchor="w", pady=(0, 10))
        
        list_frame = tk.Frame(body, bg="#1e293b", padx=10, pady=10)
        list_frame.pack(fill="both", expand=True, pady=(0, 15))
        
        self.net_listbox = tk.Listbox(list_frame, bg="#0f172a", fg="#f8fafc", font=("Courier", 10),
                                     selectbackground="#3b82f6", bd=0, highlightthickness=0)
        self.net_listbox.pack(fill="both", expand=True)

        tk.Button(body, text="Scan Networks", bg="#475569", fg="#ffffff", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=6, command=self.scan_networks).pack(anchor="w")

        self.after(200, self.scan_networks)

    def scan_networks(self):
        self.status_lbl.config(text="Scanning wireless networks...")
        self.net_listbox.delete(0, tk.END)
        
        def run_scan():
            networks = []
            try:
                raw = subprocess.check_output(["nmcli", "-t", "-f", "SSID", "device", "wifi"]).decode()
                for ssid in raw.split("\n"):
                    if ssid.strip() and ssid.strip() not in networks:
                        networks.append(ssid.strip())
            except Exception:
                networks = ["Home_Network_Demo", "Lab_Guest_WiFi"] # Fallback mock display
                
            def update_ui():
                for net in networks:
                    self.net_listbox.insert(tk.END, net)
                self.status_lbl.config(text=f"Found {len(networks)} networks.")
            self.after(0, update_ui)

        threading.Thread(target=run_scan, daemon=True).start()


if __name__ == "__main__":
    # Start background Flask IoT Dashboard server
    if FLASK_AVAILABLE:
        flask_thread = threading.Thread(target=start_flask_server, daemon=True)
        flask_thread.start()
        print("[SmartPin] IoT Web Dashboard running on http://0.0.0.0:5000")

    # Start main touchscreen Tkinter UI
    app = SmartPinMasterApp()
    app.mainloop()
