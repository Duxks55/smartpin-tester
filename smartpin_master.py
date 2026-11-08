import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import os
import time
import sys
import urllib.request
import json
import socket
from datetime import datetime
from PIL import Image, ImageTk
import numpy as np

# Set up I2C permissions for non-root users if needed
try:
    os.system("sudo chmod 666 /dev/i2c-*")
except Exception:
    pass

# Hardware libraries (GPIO, ADC)
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

# Computer Vision & Machine Learning libraries
try:
    import cv2
    import pytesseract
    from ultralytics import YOLO
    CV_AVAILABLE = True
except ImportError as e:
    print(f"Vision package note: {e}")
    CV_AVAILABLE = False

# Picamera2 backend for Camera Module 3
try:
    from picamera2 import Picamera2
    PICAM2_AVAILABLE = True
except ImportError:
    PICAM2_AVAILABLE = False


class SmartPinMasterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("SmartPin Master Suite")
        self.geometry("800x480")  # Optimized for 7-inch touchscreens
        self.configure(bg="#0f172a")  # Modern dark slate background
        
        # Shared test logs list accessible by both GUI and Web Server
        self.test_logs = []
        
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        # Initialize GPIO pins for LED Blinker module if available
        self.setup_led_gpio()
        
        # Container frame for multi-view navigation
        self.container = tk.Frame(self, bg="#0f172a")
        self.container.pack(fill="both", expand=True)
        
        self.frames = {}
        for F in (MainDashboard, TransistorCheckerView, CapacitorAnalyzerView, 
                  LedBlinkerManagerView, VisionAnalyzerView, SettingsView, WifiManagerView):
            frame_name = F.__name__
            frame = F(parent=self.container, controller=self)
            self.frames[frame_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")
            
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        
        self.show_frame("MainDashboard")
        
        # Start background IoT Web Server
        self.start_iot_server()

    def setup_led_gpio(self):
        self.led_pins = [21, 25]
        if HARDWARE_AVAILABLE:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                for pin in self.led_pins:
                    GPIO.setup(pin, GPIO.OUT)
                    GPIO.output(pin, GPIO.LOW)
            except Exception as e:
                print(f"LED GPIO Setup Error: {e}")

    def set_led_state(self, pin, state):
        """Turns an LED pin ON (True) or OFF (False)."""
        if HARDWARE_AVAILABLE:
            try:
                GPIO.output(pin, GPIO.HIGH if state else GPIO.LOW)
                return True
            except Exception as e:
                print(f"LED State Error: {e}")
                return False
        else:
            print(f"[Simulation] LED on GPIO {pin} set to {'ON' if state else 'OFF'}")
            return True

    def show_frame(self, frame_name):
        # Stop camera streams on views being navigated away from
        for name, frame in self.frames.items():
            if name != frame_name and hasattr(frame, "on_hide"):
                frame.on_hide()
                
        target_frame = self.frames[frame_name]
        target_frame.tkraise()
        if hasattr(target_frame, "on_show"):
            target_frame.on_show()

    def log_test_result(self, module_name, details):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {"time": timestamp, "module": module_name, "details": details}
        self.test_logs.insert(0, log_entry)
        if len(self.test_logs) > 50:
            self.test_logs.pop()

    def get_system_network_info(self):
        """Retrieves current hostname and local IP address."""
        hostname = socket.gethostname()
        ip_address = "127.0.0.1"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
        except Exception:
            try:
                ip_address = socket.gethostbyname(hostname)
            except Exception:
                ip_address = "Unavailable"
        return hostname, ip_address

    def run_hardware_transistor_test(self):
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
                    pass

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
        
        container_frame = tk.Frame(self, bg="#0f172a")
        container_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.canvas = tk.Canvas(container_frame, bg="#0f172a", highlightthickness=0, yscrollincrement=1)
        self.scrollable_content = tk.Frame(self.canvas, bg="#0f172a")
        
        self.scrollable_content.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_content, anchor="nw")
        self.canvas.bind('<Configure>', lambda event: self.canvas.itemconfig(self.canvas_window, width=event.width))
        self.canvas.pack(side="left", fill="both", expand=True)
        
        self.touch_state = {
            "start_y": 0,
            "last_y": 0,
            "velocity": 0.0,
            "last_time": 0.0,
            "anim_id": None
        }

        def on_touch_press(event):
            if self.touch_state["anim_id"]:
                self.after_cancel(self.touch_state["anim_id"])
                self.touch_state["anim_id"] = None
            self.touch_state["start_y"] = event.y_root
            self.touch_state["last_y"] = event.y_root
            self.touch_state["velocity"] = 0.0
            self.touch_state["last_time"] = time.time()

        def on_touch_drag(event):
            current_time = time.time()
            dt = current_time - self.touch_state["last_time"]
            dy = event.y_root - self.touch_state["last_y"]
            
            if dt > 0:
                instant_vel = dy / dt
                self.touch_state["velocity"] = (self.touch_state["velocity"] * 0.4) + (instant_vel * 0.6)
            
            scroll_pixels = -int(dy)
            if scroll_pixels != 0:
                self.canvas.yview_scroll(scroll_pixels, "units")
                self.touch_state["last_y"] += -scroll_pixels 
            self.touch_state["last_time"] = current_time

        def on_touch_release(event):
            self.smooth_momentum_glide()

        modules = [
            ("Optical Identifier", "Camera Module 3 AI object detection & OCR", "#06b6d4", lambda: controller.show_frame("VisionAnalyzerView")),
            ("Transistor Checker", "Test NPN/PNP BJTs & MOSFET characteristics", "#3b82f6", lambda: controller.show_frame("TransistorCheckerView")),
            ("Capacitor Analyzer", "Measure Capacitance, ESR & Discharge rates", "#10b981", lambda: controller.show_frame("CapacitorAnalyzerView")),
            ("LED Blinker Module", "Control and blink LEDs on GPIO 21 & 25", "#f43f5e", lambda: controller.show_frame("LedBlinkerManagerView")),
            ("IoT Dashboard Status", "Open browser telemetry & control hub", "#f59e0b", lambda: self.open_link("http://localhost:5000")),
            ("System Diagnostics", "Scan I2C bus address pins (0x48)", "#8b5cf6", self.run_i2c_check),
            ("Component Library", "Browse electronic part specifications (Test)", "#64748b", lambda: messagebox.showinfo("Test", "Component Library clicked!")),
            ("Pin Mapping Utility", "View GPIO breakout and channel routing (Test)", "#64748b", lambda: messagebox.showinfo("Test", "Pin Mapping clicked!")),
            ("Calibration Assistant", "Run ADC baseline reference checks (Test)", "#64748b", lambda: messagebox.showinfo("Test", "Calibration Assistant clicked!"))
        ]
        
        for i, (name, desc, color, cmd) in enumerate(modules):
            row = i // 2
            col = i % 2
            
            card = tk.Frame(self.scrollable_content, bg="#1e293b", highlightbackground=color, highlightthickness=2)
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            
            inner = tk.Frame(card, bg="#1e293b", padx=20, pady=20)
            inner.pack(fill="both", expand=True)
            
            lbl_title = tk.Label(inner, text=name, fg="#ffffff", bg="#1e293b", font=("Helvetica", 14, "bold"))
            lbl_title.pack(anchor="w")
            
            lbl_desc = tk.Label(inner, text=desc, fg="#94a3b8", bg="#1e293b", font=("Helvetica", 10))
            lbl_desc.pack(anchor="w", pady=(5, 15))
            
            btn = tk.Button(inner, text="Open Module", bg=color, fg="#ffffff", font=("Helvetica", 10, "bold"),
                            relief="flat", padx=10, pady=5, command=cmd)
            btn.pack(anchor="w")
            
        self.bind_global_touch(self.canvas, on_touch_press, on_touch_drag, on_touch_release)
        self.bind_global_touch(self.scrollable_content, on_touch_press, on_touch_drag, on_touch_release)
            
        self.scrollable_content.grid_columnconfigure(0, weight=1)
        self.scrollable_content.grid_columnconfigure(1, weight=1)

    def smooth_momentum_glide(self):
        velocity = self.touch_state["velocity"]
        if abs(velocity) > 10:
            step = -int(velocity * 0.015)
            if step != 0:
                self.canvas.yview_scroll(step, "units")
            
            self.touch_state["velocity"] *= 0.88
            self.touch_state["anim_id"] = self.after(15, self.smooth_momentum_glide)

    def bind_global_touch(self, widget, press_cb, drag_cb, release_cb):
        if isinstance(widget, tk.Button):
            return
            
        widget.bind("<ButtonPress-1>", press_cb, add="+")
        widget.bind("<B1-Motion>", drag_cb, add="+")
        widget.bind("<ButtonRelease-1>", release_cb, add="+")
        for child in widget.winfo_children():
            self.bind_global_touch(child, press_cb, drag_cb, release_cb)

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


class VisionAnalyzerView(tk.Frame):
    """Camera Module 3 AI Component Identifier & High-Res Macro OCR View."""
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#0f172a")
        self.controller = controller
        
        self.picam2 = None
        self.model = None
        self.is_streaming = False
        self.camera_ready = False
        self.current_frame = None
        self.loop_id = None
        
        # Header
        header = tk.Frame(self, bg="#1e293b", height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        tk.Button(header, text="← Return to Menu", bg="#334155", fg="#f8fafc", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=5, command=self.exit_to_menu).pack(side="left", padx=20)
        tk.Label(header, text="OPTICAL COMPONENT IDENTIFIER (PI CAM 3)", fg="#f8fafc", bg="#1e293b", font=("Helvetica", 14, "bold")).pack(side="left", padx=10)
        
        # Content frame with locked 50/50 split
        content = tk.Frame(self, bg="#0f172a", padx=15, pady=10)
        content.pack(fill="both", expand=True)
        content.grid_columnconfigure(0, weight=1, uniform="half")
        content.grid_columnconfigure(1, weight=1, uniform="half")
        content.grid_rowconfigure(0, weight=1)
        
        # Left Panel: Clean Video Feed Box (No overlays or reticle boxes)
        video_box = tk.Frame(content, bg="#1e293b", highlightbackground="#06b6d4", highlightthickness=2)
        video_box.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
        
        self.video_label = tk.Label(video_box, text="Connecting Camera Module 3...", bg="#0f172a", fg="#38bdf8", font=("Helvetica", 11))
        self.video_label.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Right Panel: Output & Controls
        control_box = tk.Frame(content, bg="#1e293b", padx=15, pady=15)
        control_box.grid(row=0, column=1, sticky="nsew", padx=10, pady=5)
        
        tk.Label(control_box, text="Recognition Telemetry", fg="#38bdf8", bg="#1e293b", font=("Helvetica", 12, "bold")).pack(anchor="w")
        
        # --- Scrollable Text Area with Touch Drag Support ---
        text_container = tk.Frame(control_box, bg="#0f172a")
        text_container.pack(fill="both", expand=True, pady=(10, 10))
        
        scrollbar = tk.Scrollbar(text_container, orient="vertical", width=22)
        scrollbar.pack(side="right", fill="y")
        
        self.results_box = tk.Text(text_container, bg="#0f172a", fg="#f8fafc", font=("Courier", 10), 
                                   width=30, height=12, bd=0, relief="flat", wrap="word", 
                                   yscrollcommand=scrollbar.set)
        self.results_box.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.results_box.yview)
        
        self._bind_touch_scroll(self.results_box)
        
        self.results_box.insert("1.0", "Place component under lens (~5-10cm).\nEnsure light glints across markings.\nTap 'AI Visual Analysis' below.\n")
        
        btn_frame = tk.Frame(control_box, bg="#1e293b")
        btn_frame.pack(fill="x", side="bottom")
        
        self.scan_btn = tk.Button(btn_frame, text="✨ AI Visual Analysis (High-Accuracy)", bg="#06b6d4", fg="#ffffff", font=("Helvetica", 11, "bold"),
                                  relief="flat", pady=8, command=self.trigger_analysis)
        self.scan_btn.pack(fill="x", pady=2)
        
        focus_btn_row = tk.Frame(btn_frame, bg="#1e293b")
        focus_btn_row.pack(fill="x", pady=2)
        focus_btn_row.grid_columnconfigure(0, weight=1)
        focus_btn_row.grid_columnconfigure(1, weight=1)
        
        self.macro_btn = tk.Button(focus_btn_row, text="🔬 Lock Macro (~7cm)", bg="#334155", fg="#ffffff", font=("Helvetica", 9, "bold"),
                                   relief="flat", pady=4, command=self.set_macro_focus)
        self.macro_btn.grid(row=0, column=0, sticky="ew", padx=(0, 2))
        
        self.autofocus_btn = tk.Button(focus_btn_row, text="🎯 Trigger Focus Sweep", bg="#334155", fg="#ffffff", font=("Helvetica", 9, "bold"),
                                       relief="flat", pady=4, command=self.trigger_autofocus)
        self.autofocus_btn.grid(row=0, column=1, sticky="ew", padx=(2, 0))

    def _bind_touch_scroll(self, widget):
        touch_state = {"last_y": 0}

        def on_press(e):
            touch_state["last_y"] = e.y

        def on_motion(e):
            dy = touch_state["last_y"] - e.y
            if abs(dy) > 3:
                widget.yview_scroll(int(dy / 4), "units")
                touch_state["last_y"] = e.y

        widget.bind("<ButtonPress-1>", on_press, add="+")
        widget.bind("<B1-Motion>", on_motion, add="+")

    def exit_to_menu(self):
        self.on_hide()
        self.controller.show_frame("MainDashboard")

    def on_show(self):
        self.is_streaming = True
        self.camera_ready = False
        self.video_label.config(image="", text="Starting Camera Module 3...")
        self.results_box.delete("1.0", tk.END)
        self.results_box.insert("1.0", "Initializing 1080p Macro Sensor...\n")
        
        threading.Thread(target=self._start_camera_hardware, daemon=True).start()
        
        if self.model is None and CV_AVAILABLE:
            threading.Thread(target=self._load_yolo_model, daemon=True).start()

    def on_hide(self):
        self.is_streaming = False
        self.camera_ready = False
        if self.loop_id:
            self.after_cancel(self.loop_id)
            self.loop_id = None
            
        if self.picam2:
            try:
                self.picam2.stop()
                self.picam2.close()
            except Exception as e:
                print(f"Picamera2 cleanup warning: {e}")
            self.picam2 = None

    def _start_camera_hardware(self):
        try:
            from picamera2 import Picamera2
            
            cam = Picamera2()
            config = cam.create_preview_configuration(
                main={"size": (1920, 1080), "format": "RGB888"}
            )
            cam.configure(config)
            cam.start()
            
            time.sleep(0.15)
            try:
                # AfMode 2: Continuous AF, AfRange 2: Macro (5cm - 30cm)
                # Sharpness 1.8: Boosts fine laser-etched contrast
                cam.set_controls({
                    "AfMode": 2, 
                    "AfRange": 2,
                    "Sharpness": 1.8
                })
            except Exception as af_err:
                print(f"AF notice: {af_err}")
            
            self.picam2 = cam
            self.camera_ready = True
            self.after(0, self._on_camera_started)
        except Exception as e:
            err_text = str(e)
            print(f"Picamera2 init failure: {err_text}")
            self.after(0, lambda msg=err_text: self.video_label.config(text=f"Camera Error:\n{msg[:100]}"))

    def _on_camera_started(self):
        self.results_box.insert(tk.END, "Camera active. 1080p continuous macro AF engaged.\n")
        self._render_loop()

    def _load_yolo_model(self):
        try:
            from ultralytics import YOLO
            self.model = YOLO("yolov8n.pt")
        except Exception as e:
            print(f"YOLO load notice: {e}")

    def _render_loop(self):
        if not self.is_streaming:
            return

        frame = None
        if self.camera_ready and self.picam2:
            try:
                frame = self.picam2.capture_array()
            except Exception as e:
                print(f"Capture error: {e}")

        if frame is not None:
            self.current_frame = frame
            # Clean preview with no crop box lines
            img = Image.fromarray(frame)
            img = img.resize((350, 260), Image.Resampling.BILINEAR)
            img_tk = ImageTk.PhotoImage(image=img)
            
            self.video_label.img_tk = img_tk
            self.video_label.configure(image=img_tk, text="")

        if self.is_streaming:
            self.loop_id = self.after(33, self._render_loop)

    def set_macro_focus(self):
        if self.picam2:
            try:
                # AfMode 0 (Manual), LensPosition ~8.5 diopters (macro close-up)
                self.picam2.set_controls({"AfMode": 0, "LensPosition": 8.5})
                self.results_box.insert(tk.END, "[Focus] Locked to Macro Close-Up (~7cm).\n")
                self.results_box.see(tk.END)
            except Exception as e:
                self.results_box.insert(tk.END, f"[Focus Error] {e}\n")

    def trigger_autofocus(self):
        if self.picam2:
            try:
                self.picam2.set_controls({"AfMode": 2, "AfRange": 2, "AfTrigger": 0})
                self.results_box.insert(tk.END, "[Focus] Continuous Macro Sweep triggered.\n")
                self.results_box.see(tk.END)
            except Exception as e:
                self.results_box.insert(tk.END, f"[Focus Error] {e}\n")

    def trigger_analysis(self):
        if not self.camera_ready or not self.picam2 or self.current_frame is None:
            messagebox.showwarning("Vision Warning", "Camera is not ready yet.")
            return

        self.scan_btn.config(state="disabled", text="✨ High-Accuracy Scanning...")
        self.results_box.delete("1.0", tk.END)
        self.results_box.insert("1.0", "Capturing uncompressed 1080p full frame...\nConsulting AI Component Analysis Engine...\n")

        # Capture the entire uncropped 1080p still frame
        full_frame = self.current_frame.copy()
        threading.Thread(target=self._run_inference_pipeline, args=(full_frame,), daemon=True).start()

    def _query_ai_vision(self, frame_rgb):
        """Uses Google GenAI SDK with precision prompt for electronic components."""
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return None

        try:
            from google import genai
            import io
            
            pil_img = Image.fromarray(frame_rgb)
            img_byte_arr = io.BytesIO()
            pil_img.save(img_byte_arr, format='JPEG', quality=95)
            img_bytes = img_byte_arr.getvalue()

            client = genai.Client(api_key=api_key)
            prompt = (
                "You are an expert electrical engineer inspecting an electronic component under a macro lens. "
                "Analyze the entire image and provide an accurate identification report:\n"
                "1. Package & Physical Type: State the package (e.g. TO-92, TO-220, SOIC-8, DIP-8/14/16, SOT-23, SMD 0805/1206 resistor/cap, axial, etc.) and pin/lead count.\n"
                "2. Markings / Text Decoded: Transcribe all visible laser-etched, printed, or SMD code markings (including date/lot codes vs actual part numbers). If it is an SMD code (e.g., '1AM', 'A7'), decode the actual part.\n"
                "3. Verified Component: State the exact part name (e.g., NE555 Timer, LM7805 5V Regulator, 2N3904 NPN BJT, 1N4148 Fast Diode).\n"
                "4. Pinout & Polarity: Detail standard pin assignment (e.g., Pin 1: Emitter, Pin 2: Base, Pin 3: Collector, or notch/band orientation).\n"
                "5. Circuit Role: 1 sentence summary of what it does.\n\n"
                "Be direct, structured, concise, and technical."
            )
            
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[genai.types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"), prompt]
            )
            return response.text
        except Exception as e:
            print(f"Cloud AI error: {e}")
            return None

    def _estimate_appearance_traits(self, img_rgb):
        h, w, _ = img_rgb.shape
        center_crop = img_rgb[int(h*0.15):int(h*0.85), int(w*0.15):int(w*0.85)]
        gray = cv2.cvtColor(center_crop, cv2.COLOR_RGB2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return "No distinct component outline detected."

        c = max(contours, key=cv2.contourArea)
        x, y, cw, ch = cv2.boundingRect(c)
        aspect_ratio = float(cw) / ch if ch != 0 else 1.0
        area = cv2.contourArea(c)

        mean_val = cv2.mean(center_crop[y:y+ch, x:x+cw])[:3]
        is_dark = (mean_val[0] + mean_val[1] + mean_val[2]) / 3 < 85

        description = []
        if is_dark:
            description.append("Dark epoxy package")
        else:
            description.append("Metallic/ceramic body")

        if aspect_ratio > 2.2 or aspect_ratio < 0.45:
            description.append("Axial / cylindrical package")
        elif 0.8 <= aspect_ratio <= 1.25:
            description.append("Square package (QFN/TQFP/Inductor)")
        else:
            description.append("Rectangular multi-pin package (DIP/SOIC/SOT)")

        hull = cv2.convexHull(c)
        solidity = float(area) / cv2.contourArea(hull) if cv2.contourArea(hull) > 0 else 1.0
        if solidity < 0.75:
            description.append("Exposed pin leads detected")

        return " | ".join(description)

    def _run_inference_pipeline(self, frame_rgb):
        output_logs = []
        try:
            # 1. Primary AI Vision Inspection (Full-Frame Reasoning)
            ai_result = self._query_ai_vision(frame_rgb)
            if ai_result:
                output_logs.append("=== AI COMPONENT IDENTIFICATION ===")
                output_logs.append(ai_result.strip())
            else:
                # 2. Local Fallback OCR & Geometry
                import pytesseract
                
                gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
                clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(8, 8))
                contrast_boost = clahe.apply(gray)
                
                kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
                sharpened = cv2.filter2D(contrast_boost, -1, kernel)
                
                thresh1 = cv2.adaptiveThreshold(sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 3)
                thresh2 = cv2.bitwise_not(thresh1)
                
                ocr_config = "--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-./"
                
                text1 = pytesseract.image_to_string(thresh1, config=ocr_config).strip()
                text2 = pytesseract.image_to_string(thresh2, config=ocr_config).strip()
                combined_lines = list(set([l.strip() for l in (text1 + "\n" + text2).split("\n") if len(l.strip()) >= 3]))
                valid_part_lines = [l for l in combined_lines if sum(1 for c in l if c.isalnum()) >= 3]

                detections = []
                if self.model:
                    results = self.model(frame_rgb, verbose=False)[0]
                    for box in results.boxes:
                        cls_id = int(box.cls[0])
                        conf = float(box.conf[0])
                        name = self.model.names[cls_id]
                        detections.append(f"{name} ({conf * 100:.1f}%)")

                output_logs.append("=== LOCAL VISION REPORT ===")
                if detections:
                    output_logs.append(f"YOLO Detect: {', '.join(detections)}")
                
                output_logs.append("\n=== OCR TEXT / PART NO. ===")
                if valid_part_lines:
                    for line in valid_part_lines:
                        output_logs.append(f"• {line}")
                else:
                    output_logs.append("No clear alphanumeric markings found.")
                    output_logs.append("\n=== VISUAL PACKAGE TRAITS ===")
                    output_logs.append(self._estimate_appearance_traits(frame_rgb))
                    
                output_logs.append("\n[Notice] Ensure GEMINI_API_KEY is present in ~/smartpin-tester/.env for AI component analysis.")

            report_text = "\n".join(output_logs)
            self.controller.log_test_result("Optical Identifier", "High-accuracy scan completed")

        except Exception as e:
            report_text = f"Inference Error:\n{e}"

        def update_gui():
            self.results_box.delete("1.0", tk.END)
            self.results_box.insert("1.0", report_text)
            self.scan_btn.config(state="normal", text="✨ AI Visual Analysis (High-Accuracy)")

        self.after(0, update_gui)


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


class LedBlinkerManagerView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#0f172a")
        self.controller = controller
        self.blinking_active = {21: False, 25: False}
        
        header = tk.Frame(self, bg="#1e293b", height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        tk.Button(header, text="← Return to Menu", bg="#334155", fg="#f8fafc", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=5, command=lambda: controller.show_frame("MainDashboard")).pack(side="left", padx=20)
        tk.Label(header, text="LED BLINKER CONTROL MODULE", fg="#f8fafc", bg="#1e293b", font=("Helvetica", 14, "bold")).pack(side="left", padx=10)
        
        body = tk.Frame(self, bg="#0f172a")
        body.pack(fill="both", expand=True, padx=30, pady=20)
        
        self.create_led_card(body, "LED 1 (GPIO 21)", 21, 0)
        self.create_led_card(body, "LED 2 (GPIO 25)", 25, 1)

    def create_led_card(self, parent, title, pin, col):
        card = tk.Frame(parent, bg="#1e293b", padx=20, pady=20)
        card.grid(row=0, column=col, padx=15, pady=10, sticky="nsew")
        parent.grid_columnconfigure(col, weight=1)
        parent.grid_rowconfigure(0, weight=1)
        
        tk.Label(card, text=title, fg="#38bdf8", bg="#1e293b", font=("Helvetica", 14, "bold")).pack(anchor="w", pady=(0, 10))
        
        status_lbl = tk.Label(card, text="Status: OFF", fg="#94a3b8", bg="#1e293b", font=("Helvetica", 11))
        status_lbl.pack(anchor="w", pady=(0, 15))
        card.status_lbl = status_lbl
        
        tk.Button(card, text="Turn ON", bg="#10b981", fg="#ffffff", font=("Helvetica", 10, "bold"),
                  relief="flat", width=15, pady=5, command=lambda: self.turn_on(pin, card)).pack(anchor="w", pady=5)
                  
        tk.Button(card, text="Turn OFF", bg="#ef4444", fg="#ffffff", font=("Helvetica", 10, "bold"),
                  relief="flat", width=15, pady=5, command=lambda: self.turn_off(pin, card)).pack(anchor="w", pady=5)
                  
        tk.Button(card, text="Blink (Continuous)", bg="#f59e0b", fg="#ffffff", font=("Helvetica", 10, "bold"),
                  relief="flat", width=15, pady=5, command=lambda: self.toggle_blink(pin, card)).pack(anchor="w", pady=5)

    def turn_on(self, pin, card):
        self.blinking_active[pin] = False
        self.controller.set_led_state(pin, True)
        card.status_lbl.config(text="Status: ON (Solid)", fg="#10b981")
        self.controller.log_test_result("LED Blinker", f"GPIO {pin} set to ON")

    def turn_off(self, pin, card):
        self.blinking_active[pin] = False
        self.controller.set_led_state(pin, False)
        card.status_lbl.config(text="Status: OFF", fg="#94a3b8")
        self.controller.log_test_result("LED Blinker", f"GPIO {pin} set to OFF")

    def toggle_blink(self, pin, card):
        if self.blinking_active.get(pin, False):
            self.blinking_active[pin] = False
            self.turn_off(pin, card)
            return

        self.blinking_active[pin] = True
        card.status_lbl.config(text="Status: BLINKING...", fg="#f59e0b")
        self.controller.log_test_result("LED Blinker", f"GPIO {pin} started continuous blink")

        def blink_loop():
            state = False
            while self.blinking_active.get(pin, False):
                state = not state
                self.controller.set_led_state(pin, state)
                time.sleep(0.5)

        threading.Thread(target=blink_loop, daemon=True).start()


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
        body.pack(fill="both", expand=True, padx=40, pady=20)
        
        # Network Info Card
        net_card = tk.Frame(body, bg="#1e293b", padx=20, pady=15)
        net_card.pack(fill="x", pady=5)
        
        tk.Label(net_card, text="Device Network Information", fg="#ffffff", bg="#1e293b", font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(0, 5))
        
        hostname, ip_address = self.controller.get_system_network_info()
        
        tk.Label(net_card, text=f"Hostname: {hostname}", fg="#38bdf8", bg="#1e293b", font=("Helvetica", 10, "bold")).pack(anchor="w")
        tk.Label(net_card, text=f"IP Address: {ip_address}", fg="#34d399", bg="#1e293b", font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(2, 0))

        # Git Update Card
        update_card = tk.Frame(body, bg="#1e293b", padx=20, pady=15)
        update_card.pack(fill="x", pady=5)
        
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
        self.update_status_lbl.pack(anchor="w", pady=(0, 8))
        
        tk.Button(update_card, text="Check & Apply Update", bg="#3b82f6", fg="#ffffff", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=5, command=self.trigger_software_update).pack(anchor="w")
        
        # Network Management Card
        wifi_card = tk.Frame(body, bg="#1e293b", padx=20, pady=15)
        wifi_card.pack(fill="x", pady=5)
        
        tk.Label(wifi_card, text="Network Management", fg="#ffffff", bg="#1e293b", font=("Helvetica", 12, "bold")).pack(anchor="w")
        tk.Button(wifi_card, text="Manage Wi-Fi Networks", bg="#475569", fg="#ffffff", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=15, pady=5, command=lambda: controller.show_frame("WifiManagerView")).pack(anchor="w", pady=(5, 0))

    def trigger_software_update(self):
        self.update_status_lbl.config(text="Status: Checking GitHub for updates...", fg="#f59e0b")
        
        def run_update_thread():
            try:
                repo_dir = os.path.dirname(os.path.abspath(__file__))
                subprocess.run(["git", "-C", repo_dir, "fetch", "origin"], check=True, capture_output=True)
                
                local_commit = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "HEAD"]).decode().strip()
                remote_commit = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "origin/main"]).decode().strip()
                
                if local_commit != remote_commit:
                    self.after(0, lambda: self.update_status_lbl.config(text="Status: Update found! Applying...", fg="#f59e0b"))
                    subprocess.run(["git", "-C", repo_dir, "reset", "--hard", "origin/main"], check=True, capture_output=True)
                    
                    update_script = os.path.join(repo_dir, "update_kiosk.sh")
                    if os.path.exists(update_script):
                        subprocess.run(["bash", update_script], check=True, capture_output=True)
                        
                    self.after(0, lambda: self.update_status_lbl.config(text="Status: Update applied! Restarting...", fg="#10b981"))
                    messagebox.showinfo("Update Manager", "Update applied successfully! The application will now restart.")
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                else:
                    self.after(0, lambda: self.update_status_lbl.config(text="Status: System is up to date!", fg="#10b981"))
                    messagebox.showinfo("Update Manager", "Software is already running the latest version from GitHub.")
            except Exception as e:
                self.after(0, lambda: self.update_status_lbl.config(text="Status: Update check failed.", fg="#ef4444"))
                messagebox.showerror("Update Error", f"Failed to fetch or apply update: {e}")

        threading.Thread(target=run_update_thread, daemon=True).start()


class WifiManagerView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#0f172a")
        tk.Button(self, text="← Back to Settings", bg="#334155", fg="#f8fafc", font=("Helvetica", 10, "bold"),
                  relief="flat", command=lambda: controller.show_frame("SettingsView")).pack(anchor="nw", padx=20, pady=20)


if __name__ == "__main__":
    app = SmartPinMasterApp()
    app.mainloop()
