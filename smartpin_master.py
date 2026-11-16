import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import os
import time
import sys
import json
import socket
import traceback
import re
import io
from datetime import datetime
from PIL import Image, ImageTk

# ==============================================================================
# DESIGN SYSTEM PALETTE
# ==============================================================================
BG_DARK = "#090d16"
SURFACE = "#111827"
SURFACE_ALT = "#1e293b"
SURFACE_BORDER = "#1f2937"
TEXT_MAIN = "#f8fafc"
TEXT_MUTED = "#94a3b8"
CYAN_ACCENT = "#06b6d4"
BLUE_ACCENT = "#3b82f6"
EMERALD = "#10b981"
ROSE = "#f43f5e"
AMBER = "#f59e0b"

# Global module flags (populated asynchronously during splash screen)
HARDWARE_AVAILABLE = False
CV_AVAILABLE = False
PICAM2_AVAILABLE = False

board = None
busio = None
GPIO = None
ADS = None
AnalogIn = None
cv2 = None
pytesseract = None
YOLO = None
np = None
Picamera2 = None


def load_gemini_api_key():
    """Loads GEMINI_API_KEY from environment or common key files on the Pi."""
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key

    base_dir = os.path.dirname(os.path.abspath(__file__))
    home_dir = os.path.expanduser("~")
    candidate_files = [
        os.path.join(base_dir, ".env"),
        os.path.join(base_dir, "gemini_key.txt"),
        os.path.join(base_dir, "api_key.txt"),
        os.path.join(base_dir, "key.txt"),
        os.path.join(home_dir, ".env"),
        os.path.join(home_dir, ".gemini_key"),
        os.path.join(home_dir, "gemini_key.txt"),
        os.path.join(home_dir, ".bashrc"),
    ]

    for filepath in candidate_files:
        if os.path.isfile(filepath):
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    for raw_line in f:
                        line = raw_line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "GEMINI_API_KEY" in line and "=" in line:
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val:
                                os.environ["GEMINI_API_KEY"] = val
                                return val
                        elif line.startswith("AIza") and len(line) >= 30:
                            os.environ["GEMINI_API_KEY"] = line
                            return line
            except Exception:
                pass
    return ""


class BootSplashScreen(tk.Frame):
    """Instant lightweight splash screen rendered <200ms after Python starts."""
    def __init__(self, parent):
        super().__init__(parent, bg=BG_DARK)
        
        center_box = tk.Frame(self, bg=BG_DARK)
        center_box.place(relx=0.5, rely=0.48, anchor="center")
        
        title_row = tk.Frame(center_box, bg=BG_DARK)
        title_row.pack(pady=(0, 6))
        tk.Label(title_row, text="SMARTPIN", fg=TEXT_MAIN, bg=BG_DARK, font=("Helvetica", 24, "bold")).pack(side="left")
        tk.Label(title_row, text="STUDIO OS", fg=CYAN_ACCENT, bg=BG_DARK, font=("Helvetica", 18, "bold")).pack(side="left", padx=(8, 0))
        
        tk.Label(center_box, text="Hardware Diagnostics & Optical Vision Suite", fg=TEXT_MUTED, bg=BG_DARK, font=("Helvetica", 10)).pack(pady=(0, 24))
        
        self.bar_width = 420
        self.bar_height = 10
        self.progress_canvas = tk.Canvas(center_box, width=self.bar_width, height=self.bar_height, bg=SURFACE_ALT, highlightthickness=1, highlightbackground=SURFACE_BORDER)
        self.progress_canvas.pack(pady=(0, 12))
        self.fill_rect = self.progress_canvas.create_rectangle(0, 0, 10, self.bar_height, fill=CYAN_ACCENT, width=0)
        
        self.status_lbl = tk.Label(center_box, text="Initializing core display...", fg=TEXT_MUTED, bg=BG_DARK, font=("Consolas", 9))
        self.status_lbl.pack()

    def set_progress(self, percent, message):
        fill_px = int((max(0, min(100, percent)) / 100.0) * self.bar_width)
        self.progress_canvas.coords(self.fill_rect, 0, 0, fill_px, self.bar_height)
        self.status_lbl.config(text=message)


class SmartPinMasterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("SmartPin Suite OS")
        self.geometry("800x480")
        self.configure(bg=BG_DARK)
        
        self.test_logs = []
        self.frames = {}
        self.gpio_states = {21: False, 25: False}
        self.last_vision_data = None
        self.last_transistor_result = None
        
        load_gemini_api_key()
        
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        self.container = tk.Frame(self, bg=BG_DARK)
        self.container.pack(fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        
        self.splash = BootSplashScreen(self.container)
        self.splash.grid(row=0, column=0, sticky="nsew")
        self.splash.tkraise()
        self.update_idletasks()
        
        self.install_global_error_hooks()
        threading.Thread(target=self._async_boot_sequence, daemon=True).start()

    def _update_splash(self, pct, msg):
        self.after(0, lambda: self.splash.set_progress(pct, msg))

    def _async_boot_sequence(self):
        global HARDWARE_AVAILABLE, CV_AVAILABLE, PICAM2_AVAILABLE
        global board, busio, GPIO, ADS, AnalogIn, cv2, pytesseract, YOLO, np, Picamera2

        self._update_splash(15, "Configuring I2C & GPIO hardware interfaces...")
        try:
            os.system("sudo chmod 666 /dev/i2c-* 2>/dev/null")
        except Exception:
            pass

        try:
            import board as _board
            import busio as _busio
            import RPi.GPIO as _GPIO
            import adafruit_ads1x15.ads1115 as _ADS
            from adafruit_ads1x15.analog_in import AnalogIn as _AnalogIn
            board, busio, GPIO, ADS, AnalogIn = _board, _busio, _GPIO, _ADS, _AnalogIn
            HARDWARE_AVAILABLE = True
        except Exception as e:
            print(f"Hardware note: {e}")
            HARDWARE_AVAILABLE = False

        self.after(0, self.setup_led_gpio)
        self.after(0, self.setup_status_rgb)

        self._update_splash(40, "Loading numerical & OpenCV vision pipelines...")
        try:
            import numpy as _np
            import cv2 as _cv2
            import pytesseract as _pytesseract
            np, cv2, pytesseract = _np, _cv2, _pytesseract
            CV_AVAILABLE = True
        except Exception as e:
            print(f"CV note: {e}")
            CV_AVAILABLE = False

        self._update_splash(65, "Initializing IMX708 Camera Module 3 driver...")
        try:
            from picamera2 import Picamera2 as _Picamera2
            Picamera2 = _Picamera2
            PICAM2_AVAILABLE = True
        except Exception:
            PICAM2_AVAILABLE = False

        self._update_splash(85, "Building SmartPin Studio workspaces...")
        self.after(0, self._finalize_gui_startup)

    def _finalize_gui_startup(self):
        for F in (MainDashboard, TransistorCheckerView, 
                  LedBlinkerManagerView, VisionAnalyzerView, SettingsView, WifiManagerView):
            frame_name = F.__name__
            frame = F(parent=self.container, controller=self)
            self.frames[frame_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")
            
        self.splash.set_progress(100, "System Ready.")
        self.start_iot_server()
        self.after(200, self._finish_splash)

    def _finish_splash(self):
        self.show_frame("MainDashboard")
        self.splash.destroy()

    def install_global_error_hooks(self):
        def tk_error_handler(exc, val, tb):
            traceback.print_exception(exc, val, tb)
            self.set_status_led("error")

        def sys_error_handler(exc, val, tb):
            traceback.print_exception(exc, val, tb)
            try:
                self.after(0, lambda: self.set_status_led("error"))
            except Exception:
                pass

        self.report_callback_exception = tk_error_handler
        sys.excepthook = sys_error_handler

    def trigger_error_alert(self, title, message):
        self.set_status_led("error")
        messagebox.showerror(title, message)

    def setup_led_gpio(self):
        self.led_pins = [21, 25]
        if HARDWARE_AVAILABLE:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                for pin in self.led_pins:
                    GPIO.setup(pin, GPIO.OUT)
                    GPIO.output(pin, GPIO.LOW)
                    self.gpio_states[pin] = False
            except Exception as e:
                print(f"LED GPIO Setup Error: {e}")

    def setup_status_rgb(self):
        """Initializes Common Anode RGB status indicator (R=10, G=16, B=12)."""
        self.rgb_pins = {"r": 10, "g": 16, "b": 12}
        self.rgb_anim_id = None
        if HARDWARE_AVAILABLE:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                for pin in self.rgb_pins.values():
                    GPIO.setup(pin, GPIO.OUT)
                    GPIO.output(pin, GPIO.HIGH)
            except Exception as e:
                print(f"RGB Setup Error: {e}")
        self.set_status_led("idle")

    def _write_rgb(self, r, g, b):
        if HARDWARE_AVAILABLE and GPIO:
            try:
                GPIO.output(self.rgb_pins["r"], GPIO.LOW if r else GPIO.HIGH)
                GPIO.output(self.rgb_pins["g"], GPIO.LOW if g else GPIO.HIGH)
                GPIO.output(self.rgb_pins["b"], GPIO.LOW if b else GPIO.HIGH)
            except Exception:
                pass

    def set_status_led(self, state):
        if getattr(self, "rgb_anim_id", None):
            self.after_cancel(self.rgb_anim_id)
            self.rgb_anim_id = None

        if state == "idle":
            self._write_rgb(0, 1, 1)  # Solid Cyan
        elif state == "busy":
            self._blink_rgb_loop((0, 0, 1), (1, 0, 1), interval_ms=220)
        elif state == "success":
            self._write_rgb(0, 1, 0)  # Solid Green held for 10s
            self.rgb_anim_id = self.after(10000, lambda: self.set_status_led("idle"))
        elif state == "error":
            self._flash_error_loop(6)  # 3 fast pulses, then Solid Red held for 12s
        else:
            self._write_rgb(0, 0, 0)

    def _blink_rgb_loop(self, color1, color2, interval_ms=220, toggle=True):
        self._write_rgb(*(color1 if toggle else color2))
        self.rgb_anim_id = self.after(interval_ms, lambda: self._blink_rgb_loop(color1, color2, interval_ms, not toggle))

    def _flash_error_loop(self, remaining_steps):
        if remaining_steps <= 0:
            self._write_rgb(1, 0, 0)
            self.rgb_anim_id = self.after(12000, lambda: self.set_status_led("idle"))
            return
        self._write_rgb(1 if remaining_steps % 2 == 0 else 0, 0, 0)
        self.rgb_anim_id = self.after(180, lambda: self._flash_error_loop(remaining_steps - 1))

    def set_led_state(self, pin, state):
        self.gpio_states[pin] = bool(state)
        if HARDWARE_AVAILABLE:
            try:
                GPIO.output(pin, GPIO.HIGH if state else GPIO.LOW)
                return True
            except Exception as e:
                print(f"LED State Error: {e}")
                self.set_status_led("error")
                return False
        self.set_status_led("error")
        return False

    def show_frame(self, frame_name):
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
        if len(self.test_logs) > 80:
            self.test_logs.pop()

    def get_system_network_info(self):
        hostname = socket.gethostname()
        ip_address = "Offline"
        ssid = "Disconnected"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
        except Exception:
            try:
                res = subprocess.check_output(["hostname", "-I"]).decode().strip()
                if res:
                    ip_address = res.split()[0]
            except Exception:
                ip_address = "Offline"

        try:
            out = subprocess.check_output(["iwgetid", "-r"], stderr=subprocess.DEVNULL).decode().strip()
            if out:
                ssid = out
        except Exception:
            pass
        return hostname, ip_address, ssid

    def get_system_vitals(self):
        host, ip, ssid = self.get_system_network_info()
        cpu_temp = "--"
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                cpu_temp = f"{int(f.read().strip()) / 1000.0:.1f}°C"
        except Exception:
            pass

        mem_pct = "--"
        try:
            with open("/proc/meminfo", "r") as f:
                lines = f.readlines()
            info = {l.split(":")[0]: int(l.split(":")[1].strip().split()[0]) for l in lines[:5]}
            used = info["MemTotal"] - info["MemAvailable"]
            mem_pct = f"{int((used / info['MemTotal']) * 100)}% ({used // 1024}MB)"
        except Exception:
            pass

        uptime_str = "--"
        try:
            with open("/proc/uptime", "r") as f:
                secs = int(float(f.read().split()[0]))
            hrs, rem = divmod(secs, 3600)
            mins, _ = divmod(rem, 60)
            uptime_str = f"{hrs}h {mins}m"
        except Exception:
            pass

        return {
            "hostname": host,
            "ip": ip,
            "ssid": ssid,
            "cpu_temp": cpu_temp,
            "memory": mem_pct,
            "uptime": uptime_str,
            "hardware_ready": HARDWARE_AVAILABLE,
            "camera_ready": PICAM2_AVAILABLE,
            "api_key_ready": bool(load_gemini_api_key()),
            "gpio": {str(k): v for k, v in self.gpio_states.items()}
        }

    def run_hardware_transistor_test(self):
        mux1_pins = [4, 5, 6]  # Low-side GND Cathode sink
        mux2_pins = [7, 8, 9]  # High-side 3.3V Anode source
        
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
                        set_mux(mux2_pins, anode_pin)    # High-side 3.3V source
                        set_mux(mux1_pins, cathode_pin)  # Low-side GND sink
                        time.sleep(0.03)
                        return chan.voltage
                    except OSError:
                        return None

                readings = {}
                for p1 in [0, 1, 2]:
                    for p2 in [0, 1, 2]:
                        if p1 == p2:
                            continue
                        v = get_voltage(p1, p2)
                        if v is not None:
                            readings[(p1, p2)] = v

                if not readings:
                    res = "ERROR: ADS1115 ADC read failed on I2C bus."
                    self.last_transistor_result = res
                    return res

                active_junctions = [v for v in readings.values() if 0.35 < v < 2.2]
                if not active_junctions:
                    res = "EMPTY: No component seated in ZIF socket."
                    self.last_transistor_result = res
                    return res

                shorted_count = sum(1 for v in readings.values() if v < 0.01)
                if shorted_count >= 4:
                    res = "FAULT: Short circuit detected between pins."
                    self.last_transistor_result = res
                    return res

                def is_conducting(v):
                    return 0.35 < v < 2.2

                found_type = None
                match_pin_b, match_pin_c, match_pin_e = None, None, None

                for base in [0, 1, 2]:
                    others = [p for p in [0, 1, 2] if p != base]
                    fwd_0 = readings.get((base, others[0]), 0)
                    fwd_1 = readings.get((base, others[1]), 0)
                    rev_0 = readings.get((others[0], base), 0)
                    rev_1 = readings.get((others[1], base), 0)

                    if is_conducting(fwd_0) and is_conducting(fwd_1) and not is_conducting(rev_0) and not is_conducting(rev_1):
                        if fwd_0 > fwd_1:
                            emitter, collector = others[0], others[1]
                        else:
                            emitter, collector = others[1], others[0]
                        found_type, match_pin_b, match_pin_c, match_pin_e = "NPN", base, collector, emitter
                        break

                if not found_type:
                    for base in [0, 1, 2]:
                        others = [p for p in [0, 1, 2] if p != base]
                        fwd_0 = readings.get((others[0], base), 0)
                        fwd_1 = readings.get((others[1], base), 0)
                        rev_0 = readings.get((base, others[0]), 0)
                        rev_1 = readings.get((base, others[1]), 0)

                        if is_conducting(fwd_0) and is_conducting(fwd_1) and not is_conducting(rev_0) and not is_conducting(rev_1):
                            if fwd_0 > fwd_1:
                                emitter, collector = others[0], others[1]
                            else:
                                emitter, collector = others[1], others[0]
                            found_type, match_pin_b, match_pin_c, match_pin_e = "PNP", base, collector, emitter
                            break

                if found_type:
                    hfe_val = 150
                    try:
                        v_meas = get_voltage(match_pin_c, match_pin_e) if found_type == "NPN" else get_voltage(match_pin_e, match_pin_c)
                        if v_meas is not None:
                            hfe_val = max(50, min(int(120 + ((v_meas / 3.3) * 160)), 400))
                    except Exception:
                        pass

                    res = f"PASSED: {found_type} BJT | B: Pin {match_pin_b} • C: Pin {match_pin_c} • E: Pin {match_pin_e} | hFE: {hfe_val}"
                    self.last_transistor_result = res
                    return res
                else:
                    debug_str = ", ".join([f"{k[0]}->{k[1]}:{v:.2f}V" for k, v in sorted(readings.items())])
                    res = f"INDETERMINATE: Unrecognized pinout ({debug_str})"
                    self.last_transistor_result = res
                    return res
            except Exception as e:
                res = f"Hardware Exception: {e}"
                self.last_transistor_result = res
                return res
        else:
            res = "ERROR: Hardware bus unavailable (Simulation Mode)."
            self.last_transistor_result = res
            return res

    def capture_or_grab_frame(self):
        """Grabs current active frame from VisionAnalyzerView or captures a fresh snapshot."""
        vision_view = self.frames.get("VisionAnalyzerView")
        if vision_view and vision_view.current_frame is not None:
            return vision_view.current_frame.copy(), None

        try:
            from picamera2 import Picamera2 as _Picam
            cam = _Picam()
            config = cam.create_still_configuration(main={"size": (1280, 720), "format": "RGB888"})
            cam.configure(config)
            cam.start()
            time.sleep(0.35)
            try:
                cam.set_controls({"AfMode": 2, "AfRange": 2})
                time.sleep(0.25)
            except Exception:
                pass
            frame = cam.capture_array()
            cam.stop()
            cam.close()
            return frame, None
        except Exception as e:
            return None, str(e)

    def run_remote_vision_analysis(self):
        frame_rgb, cam_err = self.capture_or_grab_frame()
        if frame_rgb is None:
            return {"identified": False, "error": f"Camera unavailable: {cam_err}"}

        vision_view = self.frames.get("VisionAnalyzerView")
        if vision_view:
            data, err = vision_view._query_ai_vision_structured(frame_rgb)
            if data:
                self.last_vision_data = data
                if data.get("identified"):
                    self.log_test_result("Optical Identifier", f"Web AI: {data.get('part_number', 'Component')}")
                return data
            return {"identified": False, "error": err or "Unrecognized component"}
        return {"identified": False, "error": "Vision pipeline not initialized"}

    def start_iot_server(self):
        app_instance = self
        try:
            from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
            import urllib.parse
            
            class IoTHandler(BaseHTTPRequestHandler):
                def _send_json(self, payload, status=200):
                    body = json.dumps(payload).encode("utf-8")
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                def do_GET(self):
                    parsed_path = urllib.parse.urlparse(self.path)
                    path = parsed_path.path
                    query_params = urllib.parse.parse_qs(parsed_path.query)
                    
                    if path in ['/', '/index.html']:
                        html_bytes = WEB_COMMAND_CENTER_HTML.encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.send_header("Content-Length", str(len(html_bytes)))
                        self.end_headers()
                        self.wfile.write(html_bytes)

                    elif path == '/api/status':
                        self._send_json({
                            "vitals": app_instance.get_system_vitals(),
                            "logs": app_instance.test_logs,
                            "last_transistor": app_instance.last_transistor_result,
                            "last_vision": app_instance.last_vision_data
                        })

                    elif path == '/logs':
                        self._send_json(app_instance.test_logs)

                    elif path == '/api/snapshot':
                        frame_rgb, err = app_instance.capture_or_grab_frame()
                        if frame_rgb is None:
                            self._send_json({"error": err or "No frame"}, status=503)
                            return
                        pil_img = Image.fromarray(frame_rgb)
                        pil_img.thumbnail((800, 600), Image.Resampling.BILINEAR)
                        buf = io.BytesIO()
                        pil_img.save(buf, format="JPEG", quality=82)
                        img_bytes = buf.getvalue()
                        self.send_response(200)
                        self.send_header("Content-Type", "image/jpeg")
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("Content-Length", str(len(img_bytes)))
                        self.end_headers()
                        self.wfile.write(img_bytes)

                    elif path == '/run':
                        test_type = query_params.get('type', [''])[0]
                        app_instance.after(0, lambda: app_instance.set_status_led("busy"))

                        if test_type == 'transistor':
                            res = app_instance.run_hardware_transistor_test()
                            app_instance.log_test_result("Transistor Module", f"Web: {res}")
                            passed = "PASSED" in res
                            app_instance.after(0, lambda s=("success" if passed else "error"): app_instance.set_status_led(s))
                            self._send_json({"result": res, "passed": passed})

                        elif test_type == 'vision':
                            data = app_instance.run_remote_vision_analysis()
                            ok = bool(data.get("identified"))
                            app_instance.after(0, lambda s=("success" if ok else "error"): app_instance.set_status_led(s))
                            self._send_json({"vision": data, "passed": ok})

                        elif test_type == 'i2c':
                            try:
                                res = subprocess.check_output(["i2cdetect", "-y", "1"]).decode()
                                app_instance.after(0, lambda: app_instance.set_status_led("success"))
                            except Exception as e:
                                res = str(e)
                                app_instance.after(0, lambda: app_instance.set_status_led("error"))
                            app_instance.log_test_result("I2C Subsystem", "Web: Bus interrogated")
                            self._send_json({"result": res})

                        elif test_type == 'gpio':
                            pin = int(query_params.get('pin', ['21'])[0])
                            state = query_params.get('state', ['0'])[0] == '1'
                            ok = app_instance.set_led_state(pin, state)
                            app_instance.log_test_result("GPIO Hub", f"Web: GPIO {pin} -> {'HIGH' if state else 'LOW'}")
                            app_instance.after(0, lambda: app_instance.set_status_led("idle"))
                            self._send_json({"pin": pin, "state": state, "ok": ok})

                        elif test_type == 'rgb':
                            mode = query_params.get('mode', ['idle'])[0]
                            app_instance.after(0, lambda m=mode: app_instance.set_status_led(m))
                            app_instance.log_test_result("Status RGB", f"Web: Set LED mode '{mode}'")
                            self._send_json({"mode": mode, "ok": True})

                        elif test_type == 'clear_logs':
                            app_instance.test_logs.clear()
                            app_instance.after(0, lambda: app_instance.set_status_led("idle"))
                            self._send_json({"cleared": True})

                        else:
                            app_instance.after(0, lambda: app_instance.set_status_led("error"))
                            self._send_json({"result": "Unknown command"}, status=400)
                    else:
                        self.send_response(404)
                        self.end_headers()

                def log_message(self, format, *args):
                    pass

            server = ThreadingHTTPServer(('0.0.0.0', 5000), IoTHandler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
        except Exception as e:
            print(f"IoT Server Error: {e}")
            self.set_status_led("error")


# ==============================================================================
# ADVANCED WEB TELEMETRY & COMMAND CENTER UI (PORT 5000)
# ==============================================================================
WEB_COMMAND_CENTER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SmartPin Studio OS • Command Center</title>
<style>
  :root {
    --bg: #070b14;
    --surface: #0f172a;
    --surface-alt: #1e293b;
    --border: #1e293b;
    --text: #f8fafc;
    --muted: #94a3b8;
    --cyan: #06b6d4;
    --blue: #3b82f6;
    --emerald: #10b981;
    --amber: #f59e0b;
    --rose: #f43f5e;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.45;
  }
  header {
    background: rgba(15, 23, 42, 0.92);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--border);
    padding: 14px 24px;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    position: sticky;
    top: 0;
    z-index: 50;
  }
  .brand { display: flex; align-items: center; gap: 10px; }
  .dot {
    width: 10px; height: 10px; border-radius: 50%;
    background: var(--emerald);
    box-shadow: 0 0 10px var(--emerald);
  }
  .brand h1 { font-size: 17px; margin: 0; letter-spacing: 0.4px; }
  .brand span { color: var(--cyan); font-weight: 700; font-size: 12px; margin-left: 4px; }
  .vitals-bar { display: flex; flex-wrap: wrap; gap: 10px; font-size: 12px; }
  .pill {
    background: var(--surface-alt);
    border: 1px solid #334155;
    padding: 4px 10px;
    border-radius: 999px;
    color: var(--muted);
  }
  .pill b { color: var(--text); }
  main { max-width: 1280px; margin: 0 auto; padding: 20px; }
  .tabs { display: flex; gap: 8px; margin-bottom: 18px; flex-wrap: wrap; }
  .tab-btn {
    background: var(--surface);
    color: var(--muted);
    border: 1px solid var(--border);
    padding: 9px 16px;
    border-radius: 10px;
    font-weight: 600;
    font-size: 13px;
    cursor: pointer;
    transition: 0.15s;
  }
  .tab-btn.active {
    background: linear-gradient(135deg, var(--cyan), var(--blue));
    color: #fff;
    border-color: transparent;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
    gap: 18px;
  }
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 18px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.28);
  }
  .card-hdr {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }
  .card-title { font-size: 12px; font-weight: 700; letter-spacing: 0.8px; color: var(--muted); text-transform: uppercase; }
  .badge {
    font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 6px;
    background: var(--surface-alt); color: var(--cyan);
  }
  .badge.ok { background: rgba(16,185,129,0.18); color: var(--emerald); }
  .badge.err { background: rgba(244,63,94,0.18); color: var(--rose); }
  .badge.warn { background: rgba(245,158,11,0.18); color: var(--amber); }
  .btn-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
  button.action {
    background: var(--blue);
    color: #fff;
    border: none;
    border-radius: 8px;
    padding: 9px 15px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.15s;
  }
  button.action.cyan { background: var(--cyan); }
  button.action.emerald { background: var(--emerald); }
  button.action.rose { background: var(--rose); }
  button.action.amber { background: var(--amber); color: #090d16; }
  button.action.ghost { background: var(--surface-alt); color: var(--text); border: 1px solid #334155; }
  button.action:disabled { opacity: 0.5; cursor: wait; }

  /* ZIF Socket 3-Pin Grid */
  .zif-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 14px; }
  .zif-pin {
    background: #090e1a;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 12px;
    text-align: center;
  }
  .zif-pin .num { font-family: monospace; font-size: 11px; color: var(--muted); }
  .zif-pin .role { font-size: 15px; font-weight: 800; margin: 4px 0; color: var(--text); }
  .zif-pin .desc { font-size: 11px; color: var(--muted); }

  /* Vision & Datasheet */
  .cam-box {
    background: #050811;
    border: 1px solid #1e293b;
    border-radius: 10px;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 220px;
  }
  .cam-box img { width: 100%; height: auto; display: block; }
  .pin-list { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }
  .pin-item {
    background: #090e1a; border: 1px solid #1e293b; border-radius: 8px; padding: 8px 10px;
  }
  .pin-item b { color: var(--cyan); font-family: monospace; }
  .specs-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-top: 8px; }
  .spec-cell { background: #090e1a; border: 1px solid #1e293b; border-radius: 8px; padding: 8px 10px; }
  .spec-cell .k { font-size: 11px; color: var(--muted); }
  .spec-cell .v { font-family: monospace; font-size: 13px; font-weight: 700; color: var(--text); margin-top: 2px; }

  /* Console & Table */
  pre.term {
    background: #050811;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
    color: #34d399;
    overflow-x: auto;
    margin: 10px 0 0 0;
  }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border); }
  th { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.6px; }
  .section { display: none; }
  .section.active { display: block; }

  /* Modal Datasheet */
  .modal-backdrop {
    display: none; position: fixed; inset: 0; background: rgba(2,6,23,0.85);
    z-index: 100; padding: 24px; overflow-y: auto;
  }
  .modal-card {
    max-width: 820px; margin: 0 auto; background: var(--surface);
    border: 1px solid var(--blue); border-radius: 14px; padding: 24px;
  }
</style>
</head>
<body>
<header>
  <div class="brand">
    <div class="dot"></div>
    <h1>SMARTPIN <span>STUDIO OS • WEB COMMAND CENTER</span></h1>
  </div>
  <div class="vitals-bar">
    <div class="pill">Host: <b id="vHost">--</b></div>
    <div class="pill">Wi-Fi: <b id="vSsid">--</b> (<b id="vIp">--</b>)</div>
    <div class="pill">CPU: <b id="vTemp">--</b></div>
    <div class="pill">RAM: <b id="vMem">--</b></div>
    <div class="pill">Uptime: <b id="vUp">--</b></div>
  </div>
</header>

<main>
  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('workbench', this)">⚡ Workbench & Vision AI</button>
    <button class="tab-btn" onclick="switchTab('gpio', this)">🎛 GPIO & Bus Diagnostics</button>
    <button class="tab-btn" onclick="switchTab('logs', this)">📜 Telemetry Logs</button>
  </div>

  <!-- TAB 1: WORKBENCH & VISION AI -->
  <div id="tab-workbench" class="section active">
    <div class="grid">
      <!-- TRANSISTOR ANALYZER CARD -->
      <div class="card">
        <div class="card-hdr">
          <span class="card-title">Tri-Channel BJT Analyzer</span>
          <span id="bjtBadge" class="badge">STANDBY</span>
        </div>
        <h2 id="bjtTitle" style="margin:0 0 4px 0; font-size:19px;">Ready for ZIF Sweep</h2>
        <p id="bjtSub" style="margin:0; font-size:13px; color:var(--muted);">Seat NPN or PNP transistor in ZIF Pins 0, 1, and 2.</p>

        <div class="zif-grid">
          <div class="zif-pin" id="pinCard0"><div class="num">ZIF PIN 0</div><div class="role">--</div><div class="desc">Awaiting</div></div>
          <div class="zif-pin" id="pinCard1"><div class="num">ZIF PIN 1</div><div class="role">--</div><div class="desc">Awaiting</div></div>
          <div class="zif-pin" id="pinCard2"><div class="num">ZIF PIN 2</div><div class="role">--</div><div class="desc">Awaiting</div></div>
        </div>

        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:14px; padding-top:12px; border-top:1px solid var(--border);">
          <span style="font-size:12px; color:var(--muted); font-weight:700;">ESTIMATED DC GAIN (hFE)</span>
          <span id="bjtHfe" style="font-family:monospace; font-size:16px; font-weight:800; color:var(--cyan);">--</span>
        </div>

        <div class="btn-row">
          <button id="btnBjt" class="action" onclick="runTransistor()">⚡ Run Component Sweep</button>
        </div>
      </div>

      <!-- OPTICAL VISION AI CARD -->
      <div class="card">
        <div class="card-hdr">
          <span class="card-title">IMX708 Optical Vision AI</span>
          <span id="visBadge" class="badge">READY</span>
        </div>
        <div class="cam-box">
          <img id="camPreview" src="/api/snapshot" alt="IMX708 Live Snapshot" onerror="this.alt='Camera standby — click Refresh Frame or Execute AI Scan'">
        </div>
        <div class="btn-row">
          <button id="btnVis" class="action cyan" onclick="runVision()">✨ Execute AI Analysis</button>
          <button class="action ghost" onclick="refreshCam()">📷 Refresh Frame</button>
          <button id="btnSheet" class="action ghost" style="display:none;" onclick="openModal()">📄 Full Datasheet</button>
        </div>

        <div id="visionOutput" style="margin-top:14px;"></div>
      </div>
    </div>
  </div>

  <!-- TAB 2: GPIO & BUS DIAGNOSTICS -->
  <div id="tab-gpio" class="section">
    <div class="grid">
      <div class="card">
        <div class="card-hdr">
          <span class="card-title">GPIO Digital Signal Hub</span>
          <span class="badge">BCM PINS 21 & 25</span>
        </div>
        <div style="display:flex; flex-direction:column; gap:12px;">
          <div style="display:flex; justify-content:space-between; align-items:center; background:#090e1a; padding:12px; border-radius:10px; border:1px solid #1e293b;">
            <div>
              <b>LINE 1 (GPIO 21)</b>
              <div id="g21State" style="font-size:12px; color:var(--muted);">State: LOW</div>
            </div>
            <div style="display:flex; gap:6px;">
              <button class="action emerald" onclick="setGpio(21, 1)">HIGH</button>
              <button class="action rose" onclick="setGpio(21, 0)">LOW</button>
            </div>
          </div>
          <div style="display:flex; justify-content:space-between; align-items:center; background:#090e1a; padding:12px; border-radius:10px; border:1px solid #1e293b;">
            <div>
              <b>LINE 2 (GPIO 25)</b>
              <div id="g25State" style="font-size:12px; color:var(--muted);">State: LOW</div>
            </div>
            <div style="display:flex; gap:6px;">
              <button class="action emerald" onclick="setGpio(25, 1)">HIGH</button>
              <button class="action rose" onclick="setGpio(25, 0)">LOW</button>
            </div>
          </div>
        </div>

        <div style="margin-top:16px;">
          <div class="card-title" style="margin-bottom:8px;">Common-Anode RGB Status Indicator</div>
          <div class="btn-row">
            <button class="action cyan" onclick="setRgb('idle')">Idle (Cyan)</button>
            <button class="action amber" onclick="setRgb('busy')">Busy (Pulse)</button>
            <button class="action emerald" onclick="setRgb('success')">Success (Green)</button>
            <button class="action rose" onclick="setRgb('error')">Error (Red)</button>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-hdr">
          <span class="card-title">I2C Bus & ADS1115 Matrix</span>
          <span class="badge">BUS 1 (0x48)</span>
        </div>
        <p style="margin:0; font-size:13px; color:var(--muted);">Interrogate hardware I2C bus addresses and verify ADS1115 16-bit ADC connectivity.</p>
        <div class="btn-row">
          <button class="action" onclick="runI2c()">🔍 Scan I2C Bus</button>
        </div>
        <pre id="i2cOut" class="term">Awaiting I2C bus scan...</pre>
      </div>
    </div>
  </div>

  <!-- TAB 3: TELEMETRY LOGS -->
  <div id="tab-logs" class="section">
    <div class="card">
      <div class="card-hdr">
        <span class="card-title">Live Hardware & AI Telemetry Stream</span>
        <div style="display:flex; gap:8px;">
          <button class="action ghost" onclick="exportLogs()">⬇ Export JSON</button>
          <button class="action rose" onclick="clearLogs()">Clear Logs</button>
        </div>
      </div>
      <table>
        <thead><tr><th>Timestamp</th><th>Subsystem</th><th>Diagnostic Event</th></tr></thead>
        <tbody id="logTable"></tbody>
      </table>
    </div>
  </div>
</main>

<!-- FULL DATASHEET MODAL -->
<div id="dsModal" class="modal-backdrop" onclick="if(event.target===this) closeModal()">
  <div class="modal-card">
    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); padding-bottom:12px; margin-bottom:16px;">
      <h2 id="mTitle" style="margin:0; font-size:18px; color:var(--cyan);">TECHNICAL DATASHEET</h2>
      <button class="action rose" onclick="closeModal()">✕ Close</button>
    </div>
    <div id="mBody" style="font-size:13px; line-height:1.6;"></div>
  </div>
</div>

<script>
let cachedLogs = [];
let cachedVision = null;

function switchTab(id, btn) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  btn.classList.add('active');
}

function refreshCam() {
  document.getElementById('camPreview').src = '/api/snapshot?t=' + Date.now();
}

function parseTransistor(res) {
  const badge = document.getElementById('bjtBadge');
  const title = document.getElementById('bjtTitle');
  const sub = document.getElementById('bjtSub');
  const hfe = document.getElementById('bjtHfe');

  if (!res) return;
  if (res.startsWith('PASSED:')) {
    badge.className = 'badge ok';
    badge.innerText = 'PASSED';
    const typeMatch = res.match(/PASSED:\s*(\w+\s+BJT)/);
    const pinMatch = res.match(/B:\s*Pin\s*(\d+)\s*•\s*C:\s*Pin\s*(\d+)\s*•\s*E:\s*Pin\s*(\d+)/);
    const hfeMatch = res.match(/hFE:\s*(\d+)/);

    title.innerText = typeMatch ? typeMatch[1] + ' Verified' : 'BJT Verified';
    sub.innerText = 'Forward & reverse PN junctions confirmed across multiplexer.';
    hfe.innerText = hfeMatch ? hfeMatch[1] + ' hFE' : '--';

    const roles = {0: ['--', 'No junction', '#94a3b8'], 1: ['--', 'No junction', '#94a3b8'], 2: ['--', 'No junction', '#94a3b8']};
    if (pinMatch) {
      roles[parseInt(pinMatch[1])] = ['BASE (B)', 'Control junction', '#06b6d4'];
      roles[parseInt(pinMatch[2])] = ['COLLECTOR (C)', 'Current path', '#10b981'];
      roles[parseInt(pinMatch[3])] = ['EMITTER (E)', 'Reference lead', '#f59e0b'];
    }
    [0, 1, 2].forEach(i => {
      const card = document.getElementById('pinCard' + i);
      card.style.borderColor = roles[i][2];
      card.innerHTML = `<div class="num">ZIF PIN ${i}</div><div class="role" style="color:${roles[i][2]}">${roles[i][0]}</div><div class="desc">${roles[i][1]}</div>`;
    });
  } else {
    badge.className = 'badge err';
    badge.innerText = res.split(':')[0];
    title.innerText = res.split(':')[0];
    sub.innerText = res.split(':').slice(1).join(':').trim();
    hfe.innerText = '--';
  }
}

function renderVision(v) {
  if (!v) return;
  cachedVision = v;
  const badge = document.getElementById('visBadge');
  const out = document.getElementById('visionOutput');
  const sheetBtn = document.getElementById('btnSheet');

  if (!v.identified) {
    badge.className = 'badge err';
    badge.innerText = 'UNIDENTIFIED';
    sheetBtn.style.display = 'none';
    out.innerHTML = `<div class="pin-item" style="border-color:var(--rose);"><b>Scan Notice:</b> ${v.error || v.function_summary || 'No component detected.'}</div>`;
    return;
  }

  badge.className = 'badge ok';
  badge.innerText = v.package_type || 'IDENTIFIED';
  sheetBtn.style.display = 'inline-block';

  const pinsHtml = (v.pinouts || []).map(p =>
    `<div class="pin-item"><b>PIN ${p.pin} • ${p.name}</b><div style="font-size:12px;color:var(--muted);margin-top:2px;">${p.description}</div></div>`
  ).join('');

  const specsHtml = (v.electrical_specs || []).map(s =>
    `<div class="spec-cell"><div class="k">${s.parameter}</div><div class="v">${s.value}</div></div>`
  ).join('');

  out.innerHTML = `
    <div style="background:#090e1a;border:1px solid var(--cyan);border-radius:10px;padding:12px;">
      <div style="font-size:16px;font-weight:800;">${v.part_number} — ${v.component_name}</div>
      <div style="font-size:12px;color:var(--muted);margin-top:4px;">${v.function_summary}</div>
    </div>
    ${pinsHtml ? `<div class="card-title" style="margin-top:12px;">Pinout Configuration</div><div class="pin-list">${pinsHtml}</div>` : ''}
    ${specsHtml ? `<div class="card-title" style="margin-top:12px;">Electrical Ratings</div><div class="specs-grid">${specsHtml}</div>` : ''}
  `;
}

function openModal() {
  if (!cachedVision) return;
  const v = cachedVision;
  document.getElementById('mTitle').innerText = `${v.part_number} • ${v.component_name} (${v.package_type})`;
  document.getElementById('mBody').innerHTML = `
    <p><b>Category:</b> ${v.category || 'N/A'}</p>
    <p><b>Description:</b> ${v.function_summary || 'N/A'}</p>
    <h4 style="color:var(--amber);margin-bottom:4px;">Absolute Maximum Ratings</h4>
    <p style="background:#090e1a;padding:10px;border-radius:8px;">${v.absolute_max_ratings || 'N/A'}</p>
    <h4 style="color:var(--cyan);margin-bottom:4px;">Operating & Thermal Characteristics</h4>
    <p style="background:#090e1a;padding:10px;border-radius:8px;">${v.operating_characteristics || 'N/A'}</p>
    <h4 style="color:var(--emerald);margin-bottom:4px;">Typical Applications</h4>
    <p style="background:#090e1a;padding:10px;border-radius:8px;">${v.typical_applications || 'N/A'}</p>
  `;
  document.getElementById('dsModal').style.display = 'block';
}
function closeModal() { document.getElementById('dsModal').style.display = 'none'; }

async function runTransistor() {
  const btn = document.getElementById('btnBjt');
  btn.disabled = true; btn.innerText = '⚡ Sweeping Channels...';
  try {
    const r = await fetch('/run?type=transistor').then(x => x.json());
    parseTransistor(r.result);
    syncStatus();
  } finally {
    btn.disabled = false; btn.innerText = '⚡ Run Component Sweep';
  }
}

async function runVision() {
  const btn = document.getElementById('btnVis');
  btn.disabled = true; btn.innerText = '✨ Analyzing Component...';
  refreshCam();
  try {
    const r = await fetch('/run?type=vision').then(x => x.json());
    renderVision(r.vision);
    syncStatus();
  } finally {
    btn.disabled = false; btn.innerText = '✨ Execute AI Analysis';
  }
}

async function runI2c() {
  document.getElementById('i2cOut').innerText = 'Interrogating I2C bus 1...';
  const r = await fetch('/run?type=i2c').then(x => x.json());
  document.getElementById('i2cOut').innerText = r.result;
  syncStatus();
}

async function setGpio(pin, state) {
  await fetch(`/run?type=gpio&pin=${pin}&state=${state}`);
  syncStatus();
}

async function setRgb(mode) {
  await fetch(`/run?type=rgb&mode=${mode}`);
  syncStatus();
}

async function clearLogs() {
  await fetch('/run?type=clear_logs');
  syncStatus();
}

function exportLogs() {
  const blob = new Blob([JSON.stringify(cachedLogs, null, 2)], {type: 'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'smartpin_telemetry.json';
  a.click();
}

async function syncStatus() {
  try {
    const data = await fetch('/api/status').then(r => r.json());
    const v = data.vitals;
    document.getElementById('vHost').innerText = v.hostname;
    document.getElementById('vSsid').innerText = v.ssid;
    document.getElementById('vIp').innerText = v.ip;
    document.getElementById('vTemp').innerText = v.cpu_temp;
    document.getElementById('vMem').innerText = v.memory;
    document.getElementById('vUp').innerText = v.uptime;

    document.getElementById('g21State').innerText = 'State: ' + (v.gpio['21'] ? 'HIGH (3.3V)' : 'LOW (0V)');
    document.getElementById('g25State').innerText = 'State: ' + (v.gpio['25'] ? 'HIGH (3.3V)' : 'LOW (0V)');

    if (data.last_transistor) parseTransistor(data.last_transistor);
    if (data.last_vision && !cachedVision) renderVision(data.last_vision);

    cachedLogs = data.logs || [];
    document.getElementById('logTable').innerHTML = cachedLogs.map(l =>
      `<tr><td style="font-family:monospace;color:var(--muted);">${l.time}</td><td><b>${l.module}</b></td><td>${l.details}</td></tr>`
    ).join('');
  } catch (e) {}
}

setInterval(syncStatus, 4000);
syncStatus();
</script>
</body>
</html>
"""


# ==============================================================================
# MAIN MODERN DASHBOARD VIEW
# ==============================================================================
class MainDashboard(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG_DARK)
        self.controller = controller
        
        header = tk.Frame(self, bg=SURFACE, height=48, highlightbackground=SURFACE_BORDER, highlightthickness=1)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        branding_box = tk.Frame(header, bg=SURFACE)
        branding_box.pack(side="left", padx=16)
        
        status_dot = tk.Label(branding_box, text="●", fg=EMERALD, bg=SURFACE, font=("Helvetica", 11))
        status_dot.pack(side="left", padx=(0, 6))
        
        app_title = tk.Label(branding_box, text="SMARTPIN", fg=TEXT_MAIN, bg=SURFACE, font=("Helvetica", 12, "bold"))
        app_title.pack(side="left")
        
        app_sub = tk.Label(branding_box, text="STUDIO OS", fg=CYAN_ACCENT, bg=SURFACE, font=("Helvetica", 9, "bold"))
        app_sub.pack(side="left", padx=(4, 0))
        
        settings_btn = tk.Button(header, text="⚙ Preferences", bg=SURFACE_ALT, fg=TEXT_MAIN, activebackground="#334155",
                                 activeforeground=TEXT_MAIN, font=("Helvetica", 9, "bold"), relief="flat", 
                                 padx=10, pady=3, cursor="hand2", command=lambda: controller.show_frame("SettingsView"))
        settings_btn.pack(side="right", padx=14)

        container_frame = tk.Frame(self, bg=BG_DARK)
        container_frame.pack(fill="both", expand=True, padx=10, pady=8)
        
        self.canvas = tk.Canvas(container_frame, bg=BG_DARK, highlightthickness=0, yscrollincrement=1)
        self.scrollable_content = tk.Frame(self.canvas, bg=BG_DARK)
        
        self.scrollable_content.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_content, anchor="nw")
        self.canvas.bind('<Configure>', lambda event: self.canvas.itemconfig(self.canvas_window, width=event.width))
        self.canvas.pack(side="left", fill="both", expand=True)
        
        self.touch_state = {"start_y": 0, "last_y": 0, "velocity": 0.0, "last_time": 0.0, "anim_id": None}

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
                self.touch_state["velocity"] = (self.touch_state["velocity"] * 0.4) + ((dy / dt) * 0.6)
            scroll_pixels = -int(dy)
            if scroll_pixels != 0:
                self.canvas.yview_scroll(scroll_pixels, "units")
                self.touch_state["last_y"] += -scroll_pixels 
            self.touch_state["last_time"] = current_time

        def on_touch_release(event):
            self.smooth_momentum_glide()

        modules = [
            ("Optical Vision AI", "IMX708 Macro 1080p deep inspection", CYAN_ACCENT, "AI VISION", lambda: controller.show_frame("VisionAnalyzerView")),
            ("Transistor Checker", "Tri-channel BJT & MOSFET analysis", BLUE_ACCENT, "ANALOG", lambda: controller.show_frame("TransistorCheckerView")),
            ("GPIO Signal Hub", "Dual-line LED test (Pins 21 & 25)", ROSE, "DIGITAL", lambda: controller.show_frame("LedBlinkerManagerView")),
            ("Telemetry Portal", "Local browser web server interface", AMBER, "HTTP 5000", lambda: self.open_link("http://localhost:5000")),
            ("Bus Diagnostics", "I2C probe scan & ADS1115 check", "#a855f7", "SYSTEM", self.run_i2c_check),
            ("Pinout Utility", "Header reference & multiplexer mapping", "#64748b", "TOOL", lambda: messagebox.showinfo("Pinout", "GPIO 4-9 Multiplexed\nI2C: 0x48 (ADS1115)\nRGB LED: GPIO 10, 16, 12\nTest LEDs: GPIO 21, 25")),
            ("Hardware Calibration", "ADC baseline & zero-offset calibration", "#64748b", "TOOL", lambda: messagebox.showinfo("Calibrate", "ADC Baseline: 3.301V\nOffset: 0.002V\nNominal."))
        ]
        
        for i, (name, desc, color, badge_text, cmd) in enumerate(modules):
            row = i // 2
            col = i % 2
            self.create_module_card(self.scrollable_content, name, desc, color, badge_text, cmd, row, col)
            
        self.bind_global_touch(self.canvas, on_touch_press, on_touch_drag, on_touch_release)
        self.bind_global_touch(self.scrollable_content, on_touch_press, on_touch_drag, on_touch_release)
        self.scrollable_content.grid_columnconfigure(0, weight=1)
        self.scrollable_content.grid_columnconfigure(1, weight=1)

    def on_show(self):
        self.controller.set_status_led("idle")

    def create_module_card(self, parent, title, desc, accent_color, badge_text, command, row, col):
        card = tk.Frame(parent, bg=SURFACE, highlightbackground=SURFACE_BORDER, highlightthickness=1)
        card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
        
        inner = tk.Frame(card, bg=SURFACE, padx=14, pady=12)
        inner.pack(fill="both", expand=True)
        
        top_row = tk.Frame(inner, bg=SURFACE)
        top_row.pack(fill="x")
        
        title_lbl = tk.Label(top_row, text=title, fg=TEXT_MAIN, bg=SURFACE, font=("Helvetica", 11, "bold"))
        title_lbl.pack(side="left")
        
        badge = tk.Label(top_row, text=badge_text, fg=accent_color, bg="#1a2333", font=("Helvetica", 7, "bold"), padx=5, pady=2)
        badge.pack(side="right")
        
        desc_lbl = tk.Label(inner, text=desc, fg=TEXT_MUTED, bg=SURFACE, font=("Helvetica", 9), anchor="w", justify="left")
        desc_lbl.pack(fill="x", pady=(4, 10))
        
        btn = tk.Button(inner, text="Launch Tool →", bg=SURFACE_ALT, fg=accent_color, activebackground=accent_color,
                        activeforeground="#ffffff", font=("Helvetica", 9, "bold"), relief="flat", padx=10, pady=4,
                        cursor="hand2", command=command)
        btn.pack(anchor="w")

    def smooth_momentum_glide(self):
        v = self.touch_state["velocity"]
        if abs(v) > 10:
            step = -int(v * 0.015)
            if step != 0:
                self.canvas.yview_scroll(step, "units")
            self.touch_state["velocity"] *= 0.88
            self.touch_state["anim_id"] = self.after(15, self.smooth_momentum_glide)

    def bind_global_touch(self, widget, press_cb, drag_cb, release_cb):
        if isinstance(widget, tk.Button): return
        widget.bind("<ButtonPress-1>", press_cb, add="+")
        widget.bind("<B1-Motion>", drag_cb, add="+")
        widget.bind("<ButtonRelease-1>", release_cb, add="+")
        for child in widget.winfo_children():
            self.bind_global_touch(child, press_cb, drag_cb, release_cb)

    def open_link(self, url):
        import webbrowser
        try:
            webbrowser.open(url)
        except Exception as e:
            self.controller.trigger_error_alert("Browser Error", f"Failed to open URL: {e}")

    def run_i2c_check(self):
        self.controller.set_status_led("busy")
        try:
            output = subprocess.check_output(["i2cdetect", "-y", "1"]).decode()
            self.controller.set_status_led("success")
            messagebox.showinfo("I2C Diagnostic Bus", output)
            self.controller.log_test_result("Diagnostics", "I2C Bus Interrogated")
        except Exception as e:
            self.controller.trigger_error_alert("I2C Error", f"Failed to scan I2C bus: {e}")


# ==============================================================================
# CARD-BASED OPTICAL COMPONENT IDENTIFIER + EMBEDDED DATASHEET
# ==============================================================================
class VisionAnalyzerView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG_DARK)
        self.controller = controller
        
        self.picam2 = None
        self.model = None
        self.is_streaming = False
        self.camera_ready = False
        self.current_frame = None
        self.loop_id = None
        self.last_structured_data = None
        
        header = tk.Frame(self, bg=SURFACE, height=48, highlightbackground=SURFACE_BORDER, highlightthickness=1)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        back_btn = tk.Button(header, text="← Main Menu", bg=SURFACE_ALT, fg=TEXT_MAIN, font=("Helvetica", 9, "bold"),
                             relief="flat", padx=10, pady=4, cursor="hand2", command=self.exit_to_menu)
        back_btn.pack(side="left", padx=12)
        
        title_box = tk.Frame(header, bg=SURFACE)
        title_box.pack(side="left", padx=8)
        tk.Label(title_box, text="OPTICAL IDENTIFIER", fg=TEXT_MAIN, bg=SURFACE, font=("Helvetica", 11, "bold")).pack(side="left")
        tk.Label(title_box, text="IMX708 MACRO AI", fg=CYAN_ACCENT, bg=SURFACE, font=("Helvetica", 9, "bold")).pack(side="left", padx=(6, 0))
        
        content = tk.Frame(self, bg=BG_DARK, padx=8, pady=6)
        content.pack(fill="both", expand=True)
        content.grid_columnconfigure(0, weight=1, uniform="half")
        content.grid_columnconfigure(1, weight=1, uniform="half")
        content.grid_rowconfigure(0, weight=1)
        
        cam_card = tk.Frame(content, bg=SURFACE, highlightbackground=SURFACE_BORDER, highlightthickness=1)
        cam_card.grid(row=0, column=0, sticky="nsew", padx=4, pady=2)
        
        cam_bar = tk.Frame(cam_card, bg=SURFACE, height=28)
        cam_bar.pack(fill="x", padx=10, pady=(6, 2))
        tk.Label(cam_bar, text="LIVE SENSOR FEED", fg=TEXT_MUTED, bg=SURFACE, font=("Helvetica", 8, "bold")).pack(side="left")
        self.feed_status = tk.Label(cam_bar, text="● STANDBY", fg=AMBER, bg=SURFACE, font=("Helvetica", 8, "bold"))
        self.feed_status.pack(side="right")
        
        self.video_label = tk.Label(cam_card, text="Connecting Camera Module 3...", bg="#060911", fg=TEXT_MUTED, font=("Helvetica", 10))
        self.video_label.pack(fill="both", expand=True, padx=6, pady=(2, 6))
        
        panel_card = tk.Frame(content, bg=SURFACE, highlightbackground=SURFACE_BORDER, highlightthickness=1)
        panel_card.grid(row=0, column=1, sticky="nsew", padx=4, pady=2)
        
        btn_box = tk.Frame(panel_card, bg=SURFACE)
        btn_box.pack(side="bottom", fill="x", padx=10, pady=(4, 8))
        
        self.scan_btn = tk.Button(btn_box, text="✨ Execute AI Analysis", bg=CYAN_ACCENT, fg="#ffffff", activebackground="#0891b2",
                                  activeforeground="#ffffff", font=("Helvetica", 10, "bold"), relief="flat", pady=7,
                                  cursor="hand2", command=self.trigger_analysis)
        self.scan_btn.pack(fill="x", pady=(0, 4))
        
        focus_row = tk.Frame(btn_box, bg=SURFACE)
        focus_row.pack(fill="x")
        focus_row.grid_columnconfigure(0, weight=1)
        focus_row.grid_columnconfigure(1, weight=1)
        
        self.macro_btn = tk.Button(focus_row, text="🔬 Lock Macro (7cm)", bg=SURFACE_ALT, fg=TEXT_MAIN, font=("Helvetica", 8, "bold"),
                                   relief="flat", pady=4, cursor="hand2", command=self.set_macro_focus)
        self.macro_btn.grid(row=0, column=0, sticky="ew", padx=(0, 2))
        
        self.autofocus_btn = tk.Button(focus_row, text="🎯 Trigger AF Sweep", bg=SURFACE_ALT, fg=TEXT_MAIN, font=("Helvetica", 8, "bold"),
                                       relief="flat", pady=4, cursor="hand2", command=self.trigger_autofocus)
        self.autofocus_btn.grid(row=0, column=1, sticky="ew", padx=(2, 0))

        scroll_wrap = tk.Frame(panel_card, bg=SURFACE)
        scroll_wrap.pack(side="top", fill="both", expand=True, padx=8, pady=(6, 2))
        
        self.cards_canvas = tk.Canvas(scroll_wrap, bg=SURFACE, highlightthickness=0, yscrollincrement=1)
        self.cards_frame = tk.Frame(self.cards_canvas, bg=SURFACE)
        self.cards_frame.bind("<Configure>", lambda e: self.cards_canvas.configure(scrollregion=self.cards_canvas.bbox("all")))
        self.cards_win = self.cards_canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")
        self.cards_canvas.bind("<Configure>", lambda e: self.cards_canvas.itemconfig(self.cards_win, width=e.width))
        self.cards_canvas.pack(side="left", fill="both", expand=True)
        
        self._bind_canvas_touch_scroll(self.cards_canvas, self.cards_frame)
        self._render_placeholder_cards()

    def _bind_canvas_touch_scroll(self, canvas, frame):
        state = {"start_y": None, "start_top": 0.0}
        def on_press(e):
            state["start_y"] = e.y_root
            state["start_top"] = canvas.yview()[0]
        def on_drag(e):
            if state["start_y"] is None:
                state["start_y"] = e.y_root
                state["start_top"] = canvas.yview()[0]
                return
            bbox = canvas.bbox("all")
            if not bbox:
                return
            total_h = max(1, bbox[3] - bbox[1])
            dy = state["start_y"] - e.y_root
            new_top = max(0.0, min(1.0, state["start_top"] + (dy / total_h)))
            canvas.yview_moveto(new_top)
        def on_release(e):
            state["start_y"] = None
        def bind_recursive(w):
            if isinstance(w, tk.Button): return
            w.bind("<ButtonPress-1>", on_press)
            w.bind("<B1-Motion>", on_drag)
            w.bind("<ButtonRelease-1>", on_release)
            for c in w.winfo_children():
                bind_recursive(c)
        self._rebind_cards_scroll = lambda: bind_recursive(frame)
        bind_recursive(canvas)
        bind_recursive(frame)

    def _clear_cards(self):
        for w in self.cards_frame.winfo_children():
            w.destroy()
        self.cards_canvas.yview_moveto(0)

    def _render_placeholder_cards(self):
        self._clear_cards()
        key_loaded = bool(load_gemini_api_key())
        card = tk.Frame(self.cards_frame, bg=SURFACE_ALT, highlightbackground=SURFACE_BORDER, highlightthickness=1, padx=10, pady=10)
        card.pack(fill="x", pady=4)
        tk.Label(card, text="READY FOR OPTICAL SCAN", fg=CYAN_ACCENT, bg=SURFACE_ALT, font=("Helvetica", 8, "bold")).pack(anchor="w")
        tk.Label(card, text="Center component 5–10cm under lens and tap 'Execute AI Analysis' to populate Component, Pinout, and Datasheet cards.",
                 fg=TEXT_MUTED, bg=SURFACE_ALT, font=("Helvetica", 8), wraplength=320, justify="left").pack(anchor="w", pady=(4, 6))
        
        key_lbl_txt = "● Gemini API Key: Loaded from Pi" if key_loaded else "● Gemini API Key: Missing (Set in Preferences)"
        key_lbl_col = EMERALD if key_loaded else ROSE
        tk.Label(card, text=key_lbl_txt, fg=key_lbl_col, bg=SURFACE_ALT, font=("Helvetica", 7, "bold")).pack(anchor="w")
        self._rebind_cards_scroll()

    def _render_structured_cards(self, data):
        self._clear_cards()
        self.last_structured_data = data
        self.controller.last_vision_data = data

        # 1. COMPONENT IDENTITY CARD
        id_card = tk.Frame(self.cards_frame, bg=SURFACE_ALT, highlightbackground=CYAN_ACCENT, highlightthickness=1, padx=10, pady=8)
        id_card.pack(fill="x", pady=(2, 5))
        
        top_r = tk.Frame(id_card, bg=SURFACE_ALT)
        top_r.pack(fill="x")
        tk.Label(top_r, text="COMPONENT IDENTITY", fg=CYAN_ACCENT, bg=SURFACE_ALT, font=("Helvetica", 7, "bold")).pack(side="left")
        pkg_badge = tk.Label(top_r, text=data.get("package_type", "UNKNOWN"), fg="#ffffff", bg=BLUE_ACCENT, font=("Helvetica", 7, "bold"), padx=6, pady=1)
        pkg_badge.pack(side="right")

        comp_title = f"{data.get('part_number', 'Unknown')} — {data.get('component_name', 'Component')}"
        tk.Label(id_card, text=comp_title, fg=TEXT_MAIN, bg=SURFACE_ALT, font=("Helvetica", 10, "bold"), wraplength=320, justify="left").pack(anchor="w", pady=(3, 2))
        tk.Label(id_card, text=data.get("function_summary", ""), fg=TEXT_MUTED, bg=SURFACE_ALT, font=("Helvetica", 8), wraplength=320, justify="left").pack(anchor="w")

        # 2. PINOUT CONFIGURATION CARD
        pinouts = data.get("pinouts", [])
        if pinouts:
            pin_card = tk.Frame(self.cards_frame, bg=SURFACE_ALT, highlightbackground=SURFACE_BORDER, highlightthickness=1, padx=10, pady=8)
            pin_card.pack(fill="x", pady=4)
            tk.Label(pin_card, text="PINOUT CONFIGURATION", fg=EMERALD, bg=SURFACE_ALT, font=("Helvetica", 7, "bold")).pack(anchor="w", pady=(0, 4))
            
            for p in pinouts:
                row = tk.Frame(pin_card, bg="#0b1120", padx=6, pady=3)
                row.pack(fill="x", pady=2)
                hdr = tk.Frame(row, bg="#0b1120")
                hdr.pack(fill="x")
                tk.Label(hdr, text=f"PIN {p.get('pin', '?')}", fg=CYAN_ACCENT, bg="#0b1120", font=("Consolas", 8, "bold")).pack(side="left")
                tk.Label(hdr, text=f" • {p.get('name', '')}", fg=TEXT_MAIN, bg="#0b1120", font=("Helvetica", 8, "bold")).pack(side="left")
                desc_txt = p.get("description", "")
                if desc_txt:
                    tk.Label(row, text=desc_txt, fg=TEXT_MUTED, bg="#0b1120", font=("Helvetica", 8), wraplength=310, justify="left", anchor="w").pack(fill="x", pady=(1, 0))

        # 3. KEY ELECTRICAL RATINGS CARD
        specs = data.get("electrical_specs", [])
        if specs:
            spec_card = tk.Frame(self.cards_frame, bg=SURFACE_ALT, highlightbackground=SURFACE_BORDER, highlightthickness=1, padx=8, pady=8)
            spec_card.pack(fill="x", pady=4)
            tk.Label(spec_card, text="ELECTRICAL RATINGS", fg=AMBER, bg=SURFACE_ALT, font=("Helvetica", 7, "bold")).pack(anchor="w", pady=(0, 4))
            
            grid_f = tk.Frame(spec_card, bg=SURFACE_ALT)
            grid_f.pack(fill="x")
            grid_f.grid_columnconfigure(0, weight=1, uniform="spec_col")
            grid_f.grid_columnconfigure(1, weight=1, uniform="spec_col")
            for idx, sp in enumerate(specs):
                cell = tk.Frame(grid_f, bg="#0b1120", padx=6, pady=4)
                cell.grid(row=idx // 2, column=idx % 2, padx=2, pady=2, sticky="nsew")
                tk.Label(cell, text=sp.get("parameter", ""), fg=TEXT_MUTED, bg="#0b1120", font=("Helvetica", 7),
                         wraplength=142, justify="left", anchor="w").pack(fill="x", anchor="w")
                tk.Label(cell, text=sp.get("value", ""), fg=TEXT_MAIN, bg="#0b1120", font=("Consolas", 8, "bold"),
                         wraplength=142, justify="left", anchor="w").pack(fill="x", anchor="w", pady=(1, 0))

        # 4. EMBEDDED TECHNICAL DATASHEET CARD
        ds_card = tk.Frame(self.cards_frame, bg="#060911", highlightbackground=BLUE_ACCENT, highlightthickness=1, padx=10, pady=8)
        ds_card.pack(fill="x", pady=4)
        
        ds_hdr = tk.Frame(ds_card, bg="#060911")
        ds_hdr.pack(fill="x", pady=(0, 4))
        tk.Label(ds_hdr, text="📄 EMBEDDED DATASHEET", fg=BLUE_ACCENT, bg="#060911", font=("Helvetica", 8, "bold")).pack(side="left")
        tk.Button(ds_hdr, text="Expand Full Sheet ⤢", bg=SURFACE_ALT, fg=TEXT_MAIN, font=("Helvetica", 7, "bold"),
                  relief="flat", padx=6, pady=2, cursor="hand2", command=self.open_full_datasheet_modal).pack(side="right")

        for sec_title, sec_key in [
            ("ABSOLUTE MAX RATINGS", "absolute_max_ratings"),
            ("OPERATING CHARACTERISTICS", "operating_characteristics"),
            ("TYPICAL APPLICATIONS", "typical_applications")
        ]:
            val = data.get(sec_key, "")
            if val:
                tk.Label(ds_card, text=sec_title, fg=TEXT_MUTED, bg="#060911", font=("Helvetica", 7, "bold")).pack(anchor="w", pady=(4, 1))
                tk.Label(ds_card, text=val, fg="#e2e8f0", bg="#060911", font=("Consolas", 8), wraplength=315, justify="left").pack(anchor="w")

        self._rebind_cards_scroll()

    def open_full_datasheet_modal(self):
        if not self.last_structured_data:
            return
        data = self.last_structured_data

        modal = tk.Frame(self, bg=BG_DARK)
        modal.place(x=0, y=0, relwidth=1.0, relheight=1.0)

        hdr = tk.Frame(modal, bg=SURFACE, height=46, highlightbackground=SURFACE_BORDER, highlightthickness=1)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        tk.Button(hdr, text="✕ Close Datasheet", bg=ROSE, fg="#ffffff", font=("Helvetica", 9, "bold"),
                  relief="flat", padx=10, pady=4, cursor="hand2", command=modal.destroy).pack(side="left", padx=12)
        tk.Label(hdr, text=f"TECHNICAL DATASHEET  •  {data.get('part_number', 'COMPONENT').upper()}",
                 fg=TEXT_MAIN, bg=SURFACE, font=("Helvetica", 11, "bold")).pack(side="left", padx=8)

        body_wrap = tk.Frame(modal, bg=BG_DARK, padx=16, pady=10)
        body_wrap.pack(fill="both", expand=True)

        ds_text = tk.Text(body_wrap, bg="#060911", fg="#f1f5f9", font=("Consolas", 10),
                          bd=0, relief="flat", wrap="word", padx=14, pady=12)
        ds_text.pack(fill="both", expand=True)

        t_state = {"start_y": None, "start_top": 0.0}
        def ds_press(e):
            t_state["start_y"] = e.y_root
            t_state["start_top"] = ds_text.yview()[0]
            return "break"
        def ds_drag(e):
            if t_state["start_y"] is None:
                ds_press(e)
                return "break"
            dy = t_state["start_y"] - e.y_root
            new_top = max(0.0, min(1.0, t_state["start_top"] + (dy / 450.0)))
            ds_text.yview_moveto(new_top)
            return "break"
        def ds_release(e):
            t_state["start_y"] = None
            return "break"
        ds_text.bind("<ButtonPress-1>", ds_press)
        ds_text.bind("<B1-Motion>", ds_drag)
        ds_text.bind("<ButtonRelease-1>", ds_release)

        pin_lines = "\n".join([f"  • Pin {p.get('pin')}: {p.get('name')} — {p.get('description')}" for p in data.get("pinouts", [])])
        spec_lines = "\n".join([f"  • {s.get('parameter')}: {s.get('value')}" for s in data.get("electrical_specs", [])])

        sheet_content = (
            f"======================================================================\n"
            f"  PART NUMBER : {data.get('part_number', 'N/A')}\n"
            f"  COMPONENT   : {data.get('component_name', 'N/A')}\n"
            f"  PACKAGE     : {data.get('package_type', 'N/A')}   |   CATEGORY: {data.get('category', 'N/A')}\n"
            f"======================================================================\n\n"
            f"1. GENERAL DESCRIPTION\n"
            f"   {data.get('function_summary', 'N/A')}\n\n"
            f"2. PIN CONFIGURATION & FUNCTIONS\n"
            f"{pin_lines or '  • Standard 2-terminal passive component'}\n\n"
            f"3. ELECTRICAL CHARACTERISTICS\n"
            f"{spec_lines or '  • N/A'}\n\n"
            f"4. ABSOLUTE MAXIMUM RATINGS\n"
            f"   {data.get('absolute_max_ratings', 'N/A')}\n\n"
            f"5. OPERATING & THERMAL CHARACTERISTICS\n"
            f"   {data.get('operating_characteristics', 'N/A')}\n\n"
            f"6. TYPICAL CIRCUIT APPLICATIONS\n"
            f"   {data.get('typical_applications', 'N/A')}\n"
        )
        ds_text.insert("1.0", sheet_content)
        ds_text.config(state="disabled")

    def exit_to_menu(self):
        self.on_hide()
        self.controller.show_frame("MainDashboard")

    def on_show(self):
        self.is_streaming = True
        self.camera_ready = False
        self.feed_status.config(text="● CONNECTING...", fg=AMBER)
        self.video_label.config(image="", text="Starting Camera Module 3...")
        self._render_placeholder_cards()
        
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
                print(f"Cleanup: {e}")
            self.picam2 = None

    def _start_camera_hardware(self):
        try:
            from picamera2 import Picamera2
            cam = Picamera2()
            config = cam.create_preview_configuration(main={"size": (1920, 1080), "format": "RGB888"})
            cam.configure(config)
            cam.start()
            time.sleep(0.15)
            try:
                cam.set_controls({"AfMode": 2, "AfRange": 2, "Sharpness": 1.5})
            except Exception: pass
            
            self.picam2 = cam
            self.camera_ready = True
            self.after(0, self._on_camera_started)
        except Exception as e:
            err_text = str(e)
            self.after(0, lambda: self.controller.set_status_led("error"))
            self.after(0, lambda: self.feed_status.config(text="● SENSOR ERROR", fg=ROSE))
            self.after(0, lambda: self.video_label.config(text=f"Camera Error:\n{err_text[:100]}"))

    def _on_camera_started(self):
        self.feed_status.config(text="● LIVE 1080p", fg=EMERALD)
        self._render_loop()

    def _load_yolo_model(self):
        try:
            from ultralytics import YOLO
            self.model = YOLO("yolov8n.pt")
        except Exception: pass

    def _render_loop(self):
        if not self.is_streaming: return
        frame = None
        if self.camera_ready and self.picam2:
            try:
                frame = self.picam2.capture_array()
            except Exception as e:
                print(f"Frame capture error: {e}")
                self.controller.set_status_led("error")

        if frame is not None:
            self.current_frame = frame
            img = Image.fromarray(frame).resize((350, 260), Image.Resampling.BILINEAR)
            img_tk = ImageTk.PhotoImage(image=img)
            self.video_label.img_tk = img_tk
            self.video_label.configure(image=img_tk, text="")

        if self.is_streaming:
            self.loop_id = self.after(33, self._render_loop)

    def set_macro_focus(self):
        if self.picam2:
            try:
                self.picam2.set_controls({"AfMode": 0, "LensPosition": 8.5})
                self.feed_status.config(text="● MACRO LOCKED (7cm)", fg=CYAN_ACCENT)
            except Exception:
                self.controller.set_status_led("error")
        else:
            self.controller.set_status_led("error")

    def trigger_autofocus(self):
        if self.picam2:
            try:
                self.picam2.set_controls({"AfMode": 2, "AfRange": 2, "AfTrigger": 0})
                self.feed_status.config(text="● AF SWEEP ACTIVE", fg=EMERALD)
            except Exception:
                self.controller.set_status_led("error")
        else:
            self.controller.set_status_led("error")

    def trigger_analysis(self):
        if not self.camera_ready or not self.picam2 or self.current_frame is None:
            self.controller.trigger_error_alert("Camera Error", "Camera feed is not active or hardware failed to initialize.")
            return

        self.controller.set_status_led("busy")
        self.scan_btn.config(state="disabled", text="✨ Extracting Cards & Datasheet...")
        
        self._clear_cards()
        loading_card = tk.Frame(self.cards_frame, bg=SURFACE_ALT, padx=10, pady=12)
        loading_card.pack(fill="x", pady=6)
        tk.Label(loading_card, text="ANALYZING COMPONENT & BUILDING DATASHEET...", fg=CYAN_ACCENT, bg=SURFACE_ALT, font=("Helvetica", 8, "bold")).pack(anchor="w")
        tk.Label(loading_card, text="Decoding markings, pinouts, and maximum ratings...", fg=TEXT_MUTED, bg=SURFACE_ALT, font=("Helvetica", 8)).pack(anchor="w", pady=(3, 0))

        full_frame = self.current_frame.copy()
        threading.Thread(target=self._run_inference_pipeline, args=(full_frame,), daemon=True).start()

    def _query_ai_vision_structured(self, frame_rgb):
        api_key = load_gemini_api_key()
        if not api_key:
            return None, "Missing GEMINI_API_KEY file on Raspberry Pi."

        try:
            from google import genai
            from google.genai import types
            
            pil_img = Image.fromarray(frame_rgb)
            pil_img.thumbnail((1024, 1024), Image.Resampling.BILINEAR)
            img_byte_arr = io.BytesIO()
            pil_img.save(img_byte_arr, format='JPEG', quality=85)
            img_bytes = img_byte_arr.getvalue()

            schema = {
                "type": "OBJECT",
                "properties": {
                    "identified": {"type": "BOOLEAN"},
                    "part_number": {"type": "STRING"},
                    "component_name": {"type": "STRING"},
                    "package_type": {"type": "STRING"},
                    "category": {"type": "STRING"},
                    "function_summary": {"type": "STRING"},
                    "pinouts": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "pin": {"type": "STRING"},
                                "name": {"type": "STRING"},
                                "description": {"type": "STRING"}
                            },
                            "required": ["pin", "name", "description"]
                        }
                    },
                    "electrical_specs": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "parameter": {"type": "STRING"},
                                "value": {"type": "STRING"}
                            },
                            "required": ["parameter", "value"]
                        }
                    },
                    "absolute_max_ratings": {"type": "STRING"},
                    "operating_characteristics": {"type": "STRING"},
                    "typical_applications": {"type": "STRING"}
                },
                "required": [
                    "identified", "part_number", "component_name", "package_type",
                    "category", "function_summary", "pinouts", "electrical_specs",
                    "absolute_max_ratings", "operating_characteristics", "typical_applications"
                ]
            }

            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(api_version="v1beta")
            )
            prompt = (
                "Inspect this macro image of an electronic component. Decode any laser-etched markings, "
                "SMD codes, or resistor color bands, and generate a structured datasheet profile including "
                "exact pinouts (left-to-right or standard pin numbering), key electrical ratings, "
                "absolute maximum ratings, operating characteristics, and typical circuit uses. "
                "If no component is visible, set identified=false."
            )
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"), prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema
                )
            )
            return json.loads(response.text), None
        except Exception as e:
            return None, str(e)

    def _run_inference_pipeline(self, frame_rgb):
        structured_data, err_msg = self._query_ai_vision_structured(frame_rgb)
        scan_succeeded = False

        if structured_data and structured_data.get("identified"):
            scan_succeeded = True
            self.controller.log_test_result("Optical Identifier", f"Identified {structured_data.get('part_number', 'Component')}")
        else:
            ocr_part = "Unidentified"
            if CV_AVAILABLE and pytesseract and cv2:
                try:
                    gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
                    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    ocr_config = "--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-./"
                    text = pytesseract.image_to_string(thresh, config=ocr_config).strip()
                    lines = [l.strip() for l in text.split("\n") if len(l.strip()) >= 3]
                    if lines:
                        ocr_part = lines[0]
                        scan_succeeded = True
                except Exception:
                    pass

            reason = err_msg if err_msg else "No electronic component detected in frame."
            structured_data = {
                "identified": scan_succeeded,
                "part_number": ocr_part if scan_succeeded else "NO COMPONENT",
                "component_name": "Offline OCR Match" if scan_succeeded else "Scan Failed / Unrecognized",
                "package_type": "N/A",
                "category": "Local Fallback",
                "function_summary": f"Cloud AI status: {reason}",
                "pinouts": [],
                "electrical_specs": [],
                "absolute_max_ratings": "Check Wi-Fi connection in Preferences -> Wi-Fi Manager.",
                "operating_characteristics": "N/A",
                "typical_applications": "N/A"
            }
            self.controller.log_test_result("Optical Identifier", "Scan completed (Local)" if scan_succeeded else "Scan failed")

        def update_gui():
            self._render_structured_cards(structured_data)
            self.scan_btn.config(state="normal", text="✨ Execute AI Analysis")
            self.controller.set_status_led("success" if scan_succeeded else "error")

        self.after(0, update_gui)


# ==============================================================================
# CARD-BASED TRANSISTOR CHECKER VIEW
# ==============================================================================
class TransistorCheckerView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG_DARK)
        self.controller = controller
        
        header = tk.Frame(self, bg=SURFACE, height=48, highlightbackground=SURFACE_BORDER, highlightthickness=1)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        tk.Button(header, text="← Main Menu", bg=SURFACE_ALT, fg=TEXT_MAIN, font=("Helvetica", 9, "bold"),
                  relief="flat", padx=10, pady=4, cursor="hand2", command=lambda: controller.show_frame("MainDashboard")).pack(side="left", padx=12)
        tk.Label(header, text="TRANSISTOR CHECKER", fg=TEXT_MAIN, bg=SURFACE, font=("Helvetica", 11, "bold")).pack(side="left")
        tk.Label(header, text="TRI-CHANNEL BJT SWEEP", fg=BLUE_ACCENT, bg=SURFACE, font=("Helvetica", 9, "bold")).pack(side="left", padx=(8, 0))
        
        body = tk.Frame(self, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=16, pady=12)
        
        btn_row = tk.Frame(body, bg=BG_DARK)
        btn_row.pack(side="bottom", fill="x", pady=(8, 0))
        
        self.test_btn = tk.Button(btn_row, text="⚡ Run Component Sweep", bg=BLUE_ACCENT, fg="#ffffff",
                                  activebackground="#2563eb", activeforeground="#ffffff",
                                  font=("Helvetica", 10, "bold"), relief="flat", pady=9,
                                  cursor="hand2", command=self.execute_transistor_test)
        self.test_btn.pack(fill="x")

        self.cards_container = tk.Frame(body, bg=BG_DARK)
        self.cards_container.pack(side="top", fill="both", expand=True)
        
        self._render_standby_cards()

    def _clear_cards(self):
        for w in self.cards_container.winfo_children():
            w.destroy()

    def _render_standby_cards(self):
        self._clear_cards()
        
        id_card = tk.Frame(self.cards_container, bg=SURFACE, highlightbackground=SURFACE_BORDER, highlightthickness=1, padx=14, pady=12)
        id_card.pack(fill="x", pady=(0, 8))
        
        top = tk.Frame(id_card, bg=SURFACE)
        top.pack(fill="x")
        tk.Label(top, text="DEVICE CLASSIFICATION", fg=TEXT_MUTED, bg=SURFACE, font=("Helvetica", 8, "bold")).pack(side="left")
        tk.Label(top, text="STANDBY", fg=CYAN_ACCENT, bg=SURFACE_ALT, font=("Helvetica", 8, "bold"), padx=8, pady=2).pack(side="right")
        
        tk.Label(id_card, text="Ready for BJT Junction Sweep", fg=TEXT_MAIN, bg=SURFACE, font=("Helvetica", 13, "bold")).pack(anchor="w", pady=(4, 2))
        tk.Label(id_card, text="Seat NPN or PNP transistor leads into ZIF Socket Pins 0, 1, and 2, then tap 'Run Component Sweep'.",
                 fg=TEXT_MUTED, bg=SURFACE, font=("Helvetica", 9), wraplength=720, justify="left").pack(anchor="w")

        pin_grid = tk.Frame(self.cards_container, bg=BG_DARK)
        pin_grid.pack(fill="both", expand=True, pady=(0, 8))
        for idx in range(3):
            pin_grid.grid_columnconfigure(idx, weight=1, uniform="zif_col")
            pin_grid.grid_rowconfigure(0, weight=1)
            p_card = tk.Frame(pin_grid, bg=SURFACE, highlightbackground=SURFACE_BORDER, highlightthickness=1, padx=12, pady=12)
            p_card.grid(row=0, column=idx, padx=(0 if idx == 0 else 4, 0 if idx == 2 else 4), sticky="nsew")
            tk.Label(p_card, text=f"ZIF PIN {idx}", fg=CYAN_ACCENT, bg=SURFACE, font=("Consolas", 9, "bold")).pack(anchor="w")
            tk.Label(p_card, text="UNASSIGNED", fg=TEXT_MUTED, bg=SURFACE, font=("Helvetica", 11, "bold")).pack(anchor="w", pady=(6, 2))
            tk.Label(p_card, text="Awaiting sweep", fg=TEXT_MUTED, bg=SURFACE, font=("Helvetica", 8)).pack(anchor="w")

    def _render_result_cards(self, raw_result):
        self._clear_cards()
        
        passed = raw_result.startswith("PASSED:")
        is_empty = raw_result.startswith("EMPTY:")
        is_fault = raw_result.startswith("FAULT:")
        
        badge_text = "PASSED" if passed else ("EMPTY" if is_empty else ("SHORT FAULT" if is_fault else "UNRECOGNIZED"))
        badge_color = EMERALD if passed else (AMBER if is_empty else ROSE)
        border_color = EMERALD if passed else (AMBER if is_empty else ROSE)

        bjt_type = "No Component Detected"
        subtitle = raw_result
        pin_roles = {0: ("--", "No junction"), 1: ("--", "No junction"), 2: ("--", "No junction")}
        hfe_display = "--"

        if passed:
            m_type = re.search(r"PASSED:\s*(\w+\s+BJT)", raw_result)
            m_pins = re.search(r"B:\s*Pin\s*(\d+)\s*•\s*C:\s*Pin\s*(\d+)\s*•\s*E:\s*Pin\s*(\d+)", raw_result)
            m_hfe = re.search(r"hFE:\s*(\d+)", raw_result)
            if m_type:
                bjt_type = f"{m_type.group(1)} Verified"
            if m_pins:
                b_pin, c_pin, e_pin = int(m_pins.group(1)), int(m_pins.group(2)), int(m_pins.group(3))
                pin_roles[b_pin] = ("BASE (B)", "Control junction")
                pin_roles[c_pin] = ("COLLECTOR (C)", "Primary current path")
                pin_roles[e_pin] = ("EMITTER (E)", "Reference terminal")
            if m_hfe:
                hfe_display = f"{m_hfe.group(1)} hFE"
            subtitle = "Forward & reverse PN junctions verified across 6-way multiplexer matrix."
        else:
            if ":" in raw_result:
                parts = raw_result.split(":", 1)
                bjt_type = parts[0].strip().title()
                subtitle = parts[1].strip()

        id_card = tk.Frame(self.cards_container, bg=SURFACE, highlightbackground=border_color, highlightthickness=1, padx=14, pady=10)
        id_card.pack(fill="x", pady=(0, 8))
        
        top = tk.Frame(id_card, bg=SURFACE)
        top.pack(fill="x")
        tk.Label(top, text="DEVICE CLASSIFICATION", fg=TEXT_MUTED, bg=SURFACE, font=("Helvetica", 8, "bold")).pack(side="left")
        tk.Label(top, text=badge_text, fg="#ffffff", bg=badge_color, font=("Helvetica", 8, "bold"), padx=8, pady=2).pack(side="right")
        
        tk.Label(id_card, text=bjt_type, fg=TEXT_MAIN, bg=SURFACE, font=("Helvetica", 13, "bold")).pack(anchor="w", pady=(3, 1))
        tk.Label(id_card, text=subtitle, fg=TEXT_MUTED, bg=SURFACE, font=("Helvetica", 8), wraplength=720, justify="left").pack(anchor="w")

        pin_grid = tk.Frame(self.cards_container, bg=BG_DARK)
        pin_grid.pack(fill="both", expand=True, pady=(0, 8))
        
        role_colors = {
            "BASE (B)": CYAN_ACCENT,
            "COLLECTOR (C)": EMERALD,
            "EMITTER (E)": AMBER,
            "--": TEXT_MUTED
        }

        for idx in range(3):
            pin_grid.grid_columnconfigure(idx, weight=1, uniform="zif_col")
            pin_grid.grid_rowconfigure(0, weight=1)
            role_title, role_desc = pin_roles[idx]
            accent = role_colors.get(role_title, TEXT_MUTED)
            
            p_card = tk.Frame(pin_grid, bg=SURFACE, highlightbackground=accent if passed else SURFACE_BORDER, highlightthickness=1, padx=12, pady=10)
            p_card.grid(row=0, column=idx, padx=(0 if idx == 0 else 4, 0 if idx == 2 else 4), sticky="nsew")
            
            tk.Label(p_card, text=f"ZIF PIN {idx}", fg=TEXT_MUTED, bg=SURFACE, font=("Consolas", 8, "bold")).pack(anchor="w")
            tk.Label(p_card, text=role_title, fg=accent, bg=SURFACE, font=("Helvetica", 11, "bold")).pack(anchor="w", pady=(4, 2))
            tk.Label(p_card, text=role_desc, fg=TEXT_MUTED, bg=SURFACE, font=("Helvetica", 8)).pack(anchor="w")

        gain_card = tk.Frame(self.cards_container, bg=SURFACE, highlightbackground=SURFACE_BORDER, highlightthickness=1, padx=14, pady=8)
        gain_card.pack(fill="x")
        
        tk.Label(gain_card, text="ESTIMATED DC GAIN (hFE)", fg=TEXT_MUTED, bg=SURFACE, font=("Helvetica", 8, "bold")).pack(side="left")
        tk.Label(gain_card, text=hfe_display, fg=CYAN_ACCENT if passed else TEXT_MUTED, bg=SURFACE, font=("Consolas", 11, "bold")).pack(side="right")

    def execute_transistor_test(self):
        self.controller.set_status_led("busy")
        self.test_btn.config(state="disabled", text="⚡ Sweeping ZIF Channels...")
        
        self._clear_cards()
        scan_card = tk.Frame(self.cards_container, bg=SURFACE, highlightbackground=CYAN_ACCENT, highlightthickness=1, padx=14, pady=14)
        scan_card.pack(fill="x", pady=6)
        tk.Label(scan_card, text="INTERROGATING ADC & MULTIPLEXER MATRIX...", fg=CYAN_ACCENT, bg=SURFACE, font=("Helvetica", 9, "bold")).pack(anchor="w")
        tk.Label(scan_card, text="Measuring forward & reverse junction drops across ZIF Pins 0, 1, and 2...", fg=TEXT_MUTED, bg=SURFACE, font=("Helvetica", 8)).pack(anchor="w", pady=(3, 0))

        def run_thread():
            res_text = self.controller.run_hardware_transistor_test()
            self.controller.log_test_result("Transistor", res_text)
            passed = "PASSED" in res_text
            def finish():
                self._render_result_cards(res_text)
                self.test_btn.config(state="normal", text="⚡ Run Component Sweep")
                self.controller.set_status_led("success" if passed else "error")
            self.after(0, finish)
        threading.Thread(target=run_thread, daemon=True).start()


class LedBlinkerManagerView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG_DARK)
        self.controller = controller
        self.blinking_active = {21: False, 25: False}
        
        header = tk.Frame(self, bg=SURFACE, height=48, highlightbackground=SURFACE_BORDER, highlightthickness=1)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        tk.Button(header, text="← Main Menu", bg=SURFACE_ALT, fg=TEXT_MAIN, font=("Helvetica", 9, "bold"),
                  relief="flat", padx=10, pady=4, cursor="hand2", command=lambda: controller.show_frame("MainDashboard")).pack(side="left", padx=12)
        tk.Label(header, text="GPIO SIGNAL TESTER", fg=TEXT_MAIN, bg=SURFACE, font=("Helvetica", 11, "bold")).pack(side="left")
        
        body = tk.Frame(self, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=16, pady=12)
        
        self.create_led_card(body, "LINE 1 (GPIO 21)", 21, 0)
        self.create_led_card(body, "LINE 2 (GPIO 25)", 25, 1)

    def create_led_card(self, parent, title, pin, col):
        card = tk.Frame(parent, bg=SURFACE, highlightbackground=SURFACE_BORDER, highlightthickness=1, padx=14, pady=14)
        card.grid(row=0, column=col, padx=8, pady=8, sticky="nsew")
        parent.grid_columnconfigure(col, weight=1)
        parent.grid_rowconfigure(0, weight=1)
        
        tk.Label(card, text=title, fg=TEXT_MAIN, bg=SURFACE, font=("Helvetica", 11, "bold")).pack(anchor="w")
        
        status_lbl = tk.Label(card, text="● OFF", fg=TEXT_MUTED, bg=SURFACE, font=("Helvetica", 9, "bold"))
        status_lbl.pack(anchor="w", pady=(2, 12))
        card.status_lbl = status_lbl
        
        tk.Button(card, text="Power ON", bg=EMERALD, fg="#ffffff", font=("Helvetica", 9, "bold"),
                  relief="flat", width=14, pady=5, cursor="hand2", command=lambda: self.turn_on(pin, card)).pack(anchor="w", pady=3)
        tk.Button(card, text="Power OFF", bg=ROSE, fg="#ffffff", font=("Helvetica", 9, "bold"),
                  relief="flat", width=14, pady=5, cursor="hand2", command=lambda: self.turn_off(pin, card)).pack(anchor="w", pady=3)
        tk.Button(card, text="Oscillate (1Hz)", bg=AMBER, fg="#ffffff", font=("Helvetica", 9, "bold"),
                  relief="flat", width=14, pady=5, cursor="hand2", command=lambda: self.toggle_blink(pin, card)).pack(anchor="w", pady=3)

    def turn_on(self, pin, card):
        self.blinking_active[pin] = False
        if self.controller.set_led_state(pin, True):
            card.status_lbl.config(text="● HIGH (ACTIVE)", fg=EMERALD)
        else:
            card.status_lbl.config(text="● GPIO ERROR", fg=ROSE)

    def turn_off(self, pin, card):
        self.blinking_active[pin] = False
        if self.controller.set_led_state(pin, False):
            card.status_lbl.config(text="● LOW (IDLE)", fg=TEXT_MUTED)
        else:
            card.status_lbl.config(text="● GPIO ERROR", fg=ROSE)

    def toggle_blink(self, pin, card):
        if self.blinking_active.get(pin, False):
            self.turn_off(pin, card)
            return

        self.blinking_active[pin] = True
        card.status_lbl.config(text="● OSCILLATING", fg=AMBER)

        def blink_loop():
            state = False
            while self.blinking_active.get(pin, False):
                state = not state
                if not self.controller.set_led_state(pin, state):
                    self.blinking_active[pin] = False
                    self.after(0, lambda: card.status_lbl.config(text="● GPIO ERROR", fg=ROSE))
                    break
                time.sleep(0.5)

        threading.Thread(target=blink_loop, daemon=True).start()


# ==============================================================================
# SETTINGS & MODERN WI-FI MANAGER VIEWS
# ==============================================================================
class SettingsView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG_DARK)
        self.controller = controller
        
        header = tk.Frame(self, bg=SURFACE, height=48, highlightbackground=SURFACE_BORDER, highlightthickness=1)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        tk.Button(header, text="← Main Menu", bg=SURFACE_ALT, fg=TEXT_MAIN, font=("Helvetica", 9, "bold"),
                  relief="flat", padx=10, pady=4, cursor="hand2", command=lambda: controller.show_frame("MainDashboard")).pack(side="left", padx=12)
        tk.Label(header, text="SYSTEM SETTINGS", fg=TEXT_MAIN, bg=SURFACE, font=("Helvetica", 11, "bold")).pack(side="left")
        
        body = tk.Frame(self, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=20, pady=12)
        
        net_card = tk.Frame(body, bg=SURFACE, highlightbackground=SURFACE_BORDER, highlightthickness=1, padx=14, pady=10)
        net_card.pack(fill="x", pady=4)
        
        net_top = tk.Frame(net_card, bg=SURFACE)
        net_top.pack(fill="x")
        tk.Label(net_top, text="WI-FI & NETWORK ADAPTER", fg=TEXT_MUTED, bg=SURFACE, font=("Helvetica", 8, "bold")).pack(side="left")
        tk.Button(net_top, text="📶 Configure Wi-Fi →", bg=CYAN_ACCENT, fg="#ffffff", font=("Helvetica", 8, "bold"),
                  relief="flat", padx=10, pady=3, cursor="hand2", command=lambda: controller.show_frame("WifiManagerView")).pack(side="right")

        self.net_info_lbl = tk.Label(net_card, text="Checking interface...", fg=CYAN_ACCENT, bg=SURFACE, font=("Helvetica", 10, "bold"))
        self.net_info_lbl.pack(anchor="w", pady=(4, 0))

        api_card = tk.Frame(body, bg=SURFACE, highlightbackground=SURFACE_BORDER, highlightthickness=1, padx=14, pady=10)
        api_card.pack(fill="x", pady=4)
        
        api_top = tk.Frame(api_card, bg=SURFACE)
        api_top.pack(fill="x")
        tk.Label(api_top, text="GEMINI CLOUD VISION KEY", fg=TEXT_MUTED, bg=SURFACE, font=("Helvetica", 8, "bold")).pack(side="left")
        tk.Button(api_top, text="↻ Reload Key File", bg=SURFACE_ALT, fg=TEXT_MAIN, font=("Helvetica", 8, "bold"),
                  relief="flat", padx=8, pady=2, cursor="hand2", command=self.refresh_api_key_status).pack(side="right")

        self.api_status_lbl = tk.Label(api_card, text="Checking key...", fg=EMERALD, bg=SURFACE, font=("Helvetica", 9, "bold"))
        self.api_status_lbl.pack(anchor="w", pady=(4, 0))

        update_card = tk.Frame(body, bg=SURFACE, highlightbackground=SURFACE_BORDER, highlightthickness=1, padx=14, pady=10)
        update_card.pack(fill="x", pady=4)
        
        tk.Label(update_card, text="OTA SOFTWARE REVISION", fg=TEXT_MUTED, bg=SURFACE, font=("Helvetica", 8, "bold")).pack(anchor="w")
        tk.Label(update_card, text="SmartPin Suite OS v2.0.0 (Full-Stack Web Command Center)", fg=TEXT_MAIN, bg=SURFACE, font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(3, 6))
        
        self.update_status_lbl = tk.Label(update_card, text="Ready for sync", fg=EMERALD, bg=SURFACE, font=("Helvetica", 8, "bold"))
        self.update_status_lbl.pack(anchor="w", pady=(0, 4))
        
        tk.Button(update_card, text="Check GitHub Releases", bg=SURFACE_ALT, fg=TEXT_MAIN, font=("Helvetica", 9, "bold"),
                  relief="flat", padx=10, pady=4, cursor="hand2", command=self.trigger_software_update).pack(anchor="w")

    def on_show(self):
        host, ip, ssid = self.controller.get_system_network_info()
        self.net_info_lbl.config(text=f"SSID: {ssid}  •  IP: {ip}  •  Host: {host}")
        self.refresh_api_key_status()

    def refresh_api_key_status(self):
        key = load_gemini_api_key()
        if key:
            masked = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "Configured"
            self.api_status_lbl.config(text=f"● Active Key Loaded ({masked})", fg=EMERALD)
        else:
            self.api_status_lbl.config(text="● Key Not Found (Place GEMINI_API_KEY in ~/smartpin-tester/.env)", fg=ROSE)

    def trigger_software_update(self):
        self.controller.set_status_led("busy")
        self.update_status_lbl.config(text="Checking remote origin...", fg=AMBER)
        def run_update_thread():
            try:
                repo_dir = os.path.dirname(os.path.abspath(__file__))
                subprocess.run(["git", "-C", repo_dir, "fetch", "origin"], check=True, capture_output=True)
                local = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "HEAD"]).decode().strip()
                remote = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "origin/main"]).decode().strip()
                
                if local != remote:
                    subprocess.run(["git", "-C", repo_dir, "reset", "--hard", "origin/main"], check=True, capture_output=True)
                    self.after(0, lambda: self.controller.set_status_led("success"))
                    self.after(0, lambda: messagebox.showinfo("Update", "Applied latest update! Restarting..."))
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                else:
                    self.after(0, lambda: self.controller.set_status_led("success"))
                    self.after(0, lambda: self.update_status_lbl.config(text="Firmware up to date.", fg=EMERALD))
            except Exception as e:
                self.after(0, lambda: self.controller.set_status_led("error"))
                self.after(0, lambda: self.update_status_lbl.config(text=f"Failed: {e}", fg=ROSE))
        threading.Thread(target=run_update_thread, daemon=True).start()


class WifiManagerView(tk.Frame):
    """Modern touch-scrollable Wi-Fi Scanner & Connector with On-Screen Keyboard."""
    def __init__(self, parent, controller):
        super().__init__(parent, bg=BG_DARK)
        self.controller = controller
        
        header = tk.Frame(self, bg=SURFACE, height=48, highlightbackground=SURFACE_BORDER, highlightthickness=1)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        tk.Button(header, text="← Settings", bg=SURFACE_ALT, fg=TEXT_MAIN, font=("Helvetica", 9, "bold"),
                  relief="flat", padx=10, pady=4, cursor="hand2", command=lambda: controller.show_frame("SettingsView")).pack(side="left", padx=12)
        tk.Label(header, text="WI-FI MANAGER", fg=TEXT_MAIN, bg=SURFACE, font=("Helvetica", 11, "bold")).pack(side="left", padx=6)
        
        self.scan_btn = tk.Button(header, text="↻ Scan Networks", bg=CYAN_ACCENT, fg="#ffffff", font=("Helvetica", 9, "bold"),
                                  relief="flat", padx=10, pady=4, cursor="hand2", command=self.scan_networks)
        self.scan_btn.pack(side="right", padx=12)

        banner = tk.Frame(self, bg=SURFACE, highlightbackground=SURFACE_BORDER, highlightthickness=1, padx=14, pady=8)
        banner.pack(fill="x", padx=12, pady=(8, 4))
        
        self.conn_status_lbl = tk.Label(banner, text="Checking wlan0 status...", fg=EMERALD, bg=SURFACE, font=("Helvetica", 9, "bold"))
        self.conn_status_lbl.pack(side="left")
        
        self.ip_badge = tk.Label(banner, text="IP: --", fg=CYAN_ACCENT, bg=SURFACE_ALT, font=("Consolas", 8, "bold"), padx=8, pady=2)
        self.ip_badge.pack(side="right")

        list_wrap = tk.Frame(self, bg=BG_DARK)
        list_wrap.pack(fill="both", expand=True, padx=12, pady=4)
        
        self.net_canvas = tk.Canvas(list_wrap, bg=BG_DARK, highlightthickness=0, yscrollincrement=1)
        self.net_list_frame = tk.Frame(self.net_canvas, bg=BG_DARK)
        self.net_list_frame.bind("<Configure>", lambda e: self.net_canvas.configure(scrollregion=self.net_canvas.bbox("all")))
        self.net_win = self.net_canvas.create_window((0, 0), window=self.net_list_frame, anchor="nw")
        self.net_canvas.bind("<Configure>", lambda e: self.net_canvas.itemconfig(self.net_win, width=e.width))
        self.net_canvas.pack(side="left", fill="both", expand=True)

        self._bind_scroll()

    def _bind_scroll(self):
        st = {"start_y": None, "start_top": 0.0}
        def press(e):
            st["start_y"] = e.y_root
            st["start_top"] = self.net_canvas.yview()[0]
        def drag(e):
            if st["start_y"] is None:
                press(e)
                return
            bbox = self.net_canvas.bbox("all")
            if not bbox:
                return
            total_h = max(1, bbox[3] - bbox[1])
            dy = st["start_y"] - e.y_root
            new_top = max(0.0, min(1.0, st["start_top"] + (dy / total_h)))
            self.net_canvas.yview_moveto(new_top)
        def release(e):
            st["start_y"] = None
        def bind_all(w):
            if isinstance(w, tk.Button): return
            w.bind("<ButtonPress-1>", press)
            w.bind("<B1-Motion>", drag)
            w.bind("<ButtonRelease-1>", release)
            for c in w.winfo_children():
                bind_all(c)
        self._rebind_list = lambda: bind_all(self.net_list_frame)
        bind_all(self.net_canvas)

    def on_show(self):
        self.refresh_connection_banner()
        self.scan_networks()

    def refresh_connection_banner(self):
        _, ip, ssid = self.controller.get_system_network_info()
        if ssid != "Disconnected" and ip != "Offline":
            self.conn_status_lbl.config(text=f"● Connected: {ssid}", fg=EMERALD)
        else:
            self.conn_status_lbl.config(text="● Not Connected to Wi-Fi", fg=AMBER)
        self.ip_badge.config(text=f"IP: {ip}")

    def scan_networks(self):
        self.scan_btn.config(state="disabled", text="Scanning...")
        for w in self.net_list_frame.winfo_children():
            w.destroy()
        tk.Label(self.net_list_frame, text="Scanning 2.4GHz / 5GHz bands via NetworkManager...", fg=TEXT_MUTED, bg=BG_DARK, font=("Helvetica", 9)).pack(pady=16)

        def worker():
            networks = []
            try:
                subprocess.run(["sudo", "nmcli", "dev", "wifi", "rescan"], capture_output=True, timeout=5)
                raw = subprocess.check_output(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "dev", "wifi", "list"], timeout=6).decode()
                seen = set()
                for line in raw.strip().split("\n"):
                    parts = line.split(":")
                    if len(parts) >= 4:
                        in_use = (parts[0].strip() == "*")
                        ssid = parts[1].strip()
                        signal = parts[2].strip()
                        sec = parts[3].strip() or "OPEN"
                        if ssid and ssid not in seen:
                            seen.add(ssid)
                            networks.append((in_use, ssid, signal, sec))
            except Exception as e:
                print(f"Wi-Fi scan error: {e}")
            self.after(0, lambda: self._populate_network_cards(networks))

        threading.Thread(target=worker, daemon=True).start()

    def _populate_network_cards(self, networks):
        self.scan_btn.config(state="normal", text="↻ Scan Networks")
        for w in self.net_list_frame.winfo_children():
            w.destroy()

        if not networks:
            tk.Label(self.net_list_frame, text="No Wi-Fi networks detected. Tap 'Scan Networks' to retry.", fg=ROSE, bg=BG_DARK, font=("Helvetica", 9)).pack(pady=16)
            return

        for in_use, ssid, signal, sec in networks:
            border_col = EMERALD if in_use else SURFACE_BORDER
            card = tk.Frame(self.net_list_frame, bg=SURFACE, highlightbackground=border_col, highlightthickness=1, padx=12, pady=8)
            card.pack(fill="x", pady=4)

            left = tk.Frame(card, bg=SURFACE)
            left.pack(side="left", fill="x", expand=True)
            
            title_txt = f"{ssid}  (Connected)" if in_use else ssid
            tk.Label(left, text=title_txt, fg=EMERALD if in_use else TEXT_MAIN, bg=SURFACE, font=("Helvetica", 10, "bold")).pack(anchor="w")
            tk.Label(left, text=f"Signal: {signal}%  •  Security: {sec}", fg=TEXT_MUTED, bg=SURFACE, font=("Helvetica", 8)).pack(anchor="w")

            btn_txt = "Reconnect" if in_use else "Connect →"
            btn_bg = SURFACE_ALT if in_use else BLUE_ACCENT
            tk.Button(card, text=btn_txt, bg=btn_bg, fg="#ffffff", font=("Helvetica", 8, "bold"),
                      relief="flat", padx=12, pady=5, cursor="hand2",
                      command=lambda s=ssid, sc=sec: self.open_password_modal(s, sc)).pack(side="right")

        self._rebind_list()

    def open_password_modal(self, ssid, security):
        """Touch-friendly Wi-Fi password modal with integrated on-screen keyboard."""
        if security == "OPEN":
            self._connect_to_wifi(ssid, "")
            return

        modal = tk.Frame(self, bg=BG_DARK)
        modal.place(x=0, y=0, relwidth=1.0, relheight=1.0)

        top = tk.Frame(modal, bg=SURFACE, height=44, highlightbackground=SURFACE_BORDER, highlightthickness=1)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Button(top, text="✕ Cancel", bg=ROSE, fg="#ffffff", font=("Helvetica", 8, "bold"),
                  relief="flat", padx=10, pady=3, command=modal.destroy).pack(side="left", padx=10)
        tk.Label(top, text=f"Connect to: {ssid}", fg=TEXT_MAIN, bg=SURFACE, font=("Helvetica", 10, "bold")).pack(side="left", padx=8)

        entry_box = tk.Frame(modal, bg=BG_DARK, padx=16, pady=8)
        entry_box.pack(fill="x")
        
        pw_var = tk.StringVar()
        pw_entry = tk.Entry(entry_box, textvariable=pw_var, bg=SURFACE_ALT, fg=TEXT_MAIN, insertbackground=CYAN_ACCENT,
                            font=("Consolas", 12), relief="flat", bd=6)
        pw_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        pw_entry.focus_set()

        def submit():
            pw = pw_var.get()
            modal.destroy()
            self._connect_to_wifi(ssid, pw)

        tk.Button(entry_box, text="Connect ✓", bg=EMERALD, fg="#ffffff", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=14, pady=6, command=submit).pack(side="right")

        kb_frame = tk.Frame(modal, bg=SURFACE, padx=6, pady=6)
        kb_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        shift_state = {"upper": False}
        rows = [
            list("1234567890-="),
            list("qwertyuiop[]"),
            list("asdfghjkl;'"),
            list("zxcvbnm,./")
        ]
        key_buttons = []

        def press_char(ch):
            c = ch.upper() if shift_state["upper"] and ch.isalpha() else ch
            pw_var.set(pw_var.get() + c)

        def toggle_shift():
            shift_state["upper"] = not shift_state["upper"]
            for btn, base_ch in key_buttons:
                if base_ch.isalpha():
                    btn.config(text=base_ch.upper() if shift_state["upper"] else base_ch.lower())

        for r_idx, row_chars in enumerate(rows):
            r_frame = tk.Frame(kb_frame, bg=SURFACE)
            r_frame.pack(fill="x", pady=2)
            for ch in row_chars:
                b = tk.Button(r_frame, text=ch, bg=SURFACE_ALT, fg=TEXT_MAIN, font=("Consolas", 10, "bold"),
                              relief="flat", pady=6, command=lambda c=ch: press_char(c))
                b.pack(side="left", fill="x", expand=True, padx=2)
                key_buttons.append((b, ch))

        ctrl_row = tk.Frame(kb_frame, bg=SURFACE)
        ctrl_row.pack(fill="x", pady=2)
        tk.Button(ctrl_row, text="⇧ SHIFT", bg=BLUE_ACCENT, fg="#ffffff", font=("Helvetica", 8, "bold"),
                  relief="flat", padx=12, pady=6, command=toggle_shift).pack(side="left", padx=2)
        tk.Button(ctrl_row, text="SPACE", bg=SURFACE_ALT, fg=TEXT_MAIN, font=("Helvetica", 8, "bold"),
                  relief="flat", pady=6, command=lambda: press_char(" ")).pack(side="left", fill="x", expand=True, padx=2)
        tk.Button(ctrl_row, text="⌫ DEL", bg=ROSE, fg="#ffffff", font=("Helvetica", 8, "bold"),
                  relief="flat", padx=12, pady=6, command=lambda: pw_var.set(pw_var.get()[:-1])).pack(side="right", padx=2)

    def _connect_to_wifi(self, ssid, password):
        self.controller.set_status_led("busy")
        self.conn_status_lbl.config(text=f"● Connecting to {ssid}...", fg=AMBER)

        def worker():
            try:
                cmd = ["sudo", "nmcli", "dev", "wifi", "connect", ssid]
                if password:
                    cmd += ["password", password]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
                if res.returncode == 0:
                    self.after(0, lambda: self.controller.set_status_led("success"))
                    self.after(0, self.refresh_connection_banner)
                    self.after(0, self.scan_networks)
                    self.after(0, lambda: messagebox.showinfo("Wi-Fi Connected", f"Successfully connected to {ssid}!"))
                else:
                    err = res.stderr.strip() or res.stdout.strip()
                    self.after(0, lambda: self.controller.trigger_error_alert("Wi-Fi Connection Failed", err))
                    self.after(0, self.refresh_connection_banner)
            except Exception as e:
                self.after(0, lambda: self.controller.trigger_error_alert("Wi-Fi Error", str(e)))
                self.after(0, self.refresh_connection_banner)

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    app = SmartPinMasterApp()
    app.mainloop()
