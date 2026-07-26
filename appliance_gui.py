import tkinter as tk
from tkinter import ttk
import os
import subprocess
import threading
import sys

# Project directory (~/smartpin-tester)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Hardcoded absolute path to your user virtual environment
VENV_DIR = "/home/tpj655/component_tester_env"

class SmartPinAppliance:
    def __init__(self, root):
        self.root = root
        self.root.title("SmartPin OS")
        self.root.attributes('-fullscreen', True)
        self.root.configure(bg='#0f111a')

        # UI Modern Styling & Touch-Friendly Sizing Config
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('.', background='#1a1e30', foreground='#a6accd', font=('Helvetica', 12))
        self.style.configure('TNotebook', background='#0f111a', borderwidth=0)
        self.style.configure('TNotebook.Tab', background='#292d3e', foreground='#a6accd', font=('Helvetica', 14, 'bold'), padding=[25, 12])
        self.style.map('TNotebook.Tab', background=[('selected', '#80cbc4')], foreground=[('selected', '#0f111a')])

        # Core Tab Navigation Setup with weight for scaling
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        self.tab_dashboard = ttk.Frame(self.notebook)
        self.tab_apps = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_dashboard, text=' Dashboard ')
        self.notebook.add(self.tab_apps, text=' Applications ')
        self.notebook.add(self.tab_settings, text=' Settings ')

        self.build_dashboard()
        self.build_apps_menu()
        self.build_settings()

    def build_dashboard(self):
        self.tab_dashboard.rowconfigure(1, weight=1)
        self.tab_dashboard.columnconfigure(0, weight=1)

        lbl = tk.Label(self.tab_dashboard, text="SMARTPIN OFFLINE CONSOLE", font=('Helvetica', 18, 'bold'), bg='#1a1e30', fg='#80cbc4')
        lbl.pack(pady=15)

        btn_action = tk.Button(self.tab_dashboard, text="PULSE SYSTEM DISCHARGE", font=('Helvetica', 14, 'bold'),
                               bg='#f07178', fg='#0f111a', activebackground='#f78c91', height=3, width=28, relief='raised', bd=3)
        btn_action.config(command=self.pulse_discharge)
        btn_action.pack(pady=20)

        self.status_lbl = tk.Label(self.tab_dashboard, text="System Ready | Offline Node", font=('Helvetica', 12, 'bold'), bg='#1a1e30', fg='#ffcb6b')
        self.status_lbl.pack(side='bottom', pady=15)

    def build_apps_menu(self):
        lbl = tk.Label(self.tab_apps, text="Available Modules & Apps", font=('Helvetica', 16, 'bold'), bg='#1a1e30', fg='#c792ea')
        lbl.pack(pady=10)

        # Responsive grid frame for touch scaling
        grid_frame = tk.Frame(self.tab_apps, bg='#1a1e30')
        grid_frame.pack(fill='both', expand=True, padx=10, pady=5)

        grid_frame.rowconfigure(0, weight=1)
        grid_frame.rowconfigure(1, weight=1)
        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1)

        # Apps mapped to your exact filenames in ~/smartpin-tester
        apps = [
            ("Capacitor Tester", "capacitor_tester.py"),
            ("Transistor Checker", "transistor_tester.py"),
            ("Signal Analyzer", None),
            ("GPIO Diagnostics", None)
        ]
        
        for idx, (app_name, script_file) in enumerate(apps):
            btn = tk.Button(grid_frame, text=app_name, font=('Helvetica', 13, 'bold'), bg='#292d3e', fg='#a6accd',
                            activebackground='#82aaff', activeforeground='#0f111a', relief='raised', bd=2,
                            command=lambda name=app_name, sf=script_file: self.launch_app(name, sf))
            btn.grid(row=idx // 2, column=idx % 2, padx=15, pady=15, sticky='nsew')

    def build_settings(self):
        lbl = tk.Label(self.tab_settings, text="Appliance Control Settings", font=('Helvetica', 16, 'bold'), bg='#1a1e30', fg='#82aaff')
        lbl.pack(pady=15)

        btn_close = tk.Button(self.tab_settings, text="Exit Application to Terminal", font=('Helvetica', 12, 'bold'),
                              bg='#3c4257', fg='#ffffff', height=2, width=25, relief='raised', bd=2, command=self.root.quit)
        btn_close.pack(pady=10)

        btn_reboot = tk.Button(self.tab_settings, text="Reboot Hardware Pi Unit", font=('Helvetica', 12, 'bold'),
                               bg='#ff5370', fg='#ffffff', height=2, width=25, relief='raised', bd=2, command=lambda: os.system('sudo reboot'))
        btn_reboot.pack(pady=10)

    def pulse_discharge(self):
        self.status_lbl.config(text="Executing Discharge Sequence...", fg='#f07178')
        self.root.after(1000, lambda: self.status_lbl.config(text="System Ready | Offline Node", fg='#ffcb6b'))

    def launch_app(self, name, script_file):
        self.status_lbl.config(text=f"Launching {name} module...", fg='#c3e88d')

        # Full-screen touch overlay window
        app_win = tk.Toplevel(self.root)
        app_win.title(name)
        app_win.attributes('-fullscreen', True)
        app_win.configure(bg='#0f111a')

        # Top control frame for header layout and Return to Menu button
        top_frame = tk.Frame(app_win, bg='#0f111a')
        top_frame.pack(fill='x', padx=20, pady=10)

        header = tk.Label(top_frame, text=f"{name.upper()} MODULE", font=('Helvetica', 16, 'bold'), bg='#0f111a', fg='#82aaff')
        header.pack(side='left', pady=5)

        # Return to Menu Button positioned at the top right
        btn_return = tk.Button(top_frame, text="RETURN TO MENU", font=('Helvetica', 11, 'bold'),
                               bg='#82aaff', fg='#0f111a', activebackground='#a6accd',
                               command=app_win.destroy, width=16, height=1, relief='raised', bd=2)
        btn_return.pack(side='right', pady=5)

        content_frame = tk.Frame(app_win, bg='#1a1e30', bd=1, relief='solid')
        content_frame.pack(fill='both', expand=True, padx=20, pady=5)

        # Terminal text display box optimized for small screens
        text_output = tk.Text(content_frame, font=('Courier New', 10), bg='#0f111a', fg='#a6accd', wrap='word', insertbackground='white')
        text_output.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        
        scrollbar = tk.Scrollbar(content_frame, command=text_output.yview)
        scrollbar.pack(side='right', fill='y', pady=5)
        text_output.config(yscrollcommand=scrollbar.set)

        btn_close = tk.Button(app_win, text="CLOSE MODULE", font=('Helvetica', 12, 'bold'),
                              bg='#ff5370', fg='#ffffff', activebackground='#ec5f67',
                              command=app_win.destroy, width=20, height=2, relief='raised', bd=2)
        btn_close.pack(side='bottom', pady=15)

        # Target script path resolution inside ~/smartpin-tester
        script_path = os.path.join(BASE_DIR, script_file) if script_file else None

        if script_path and os.path.exists(script_path):
            text_output.insert(tk.END, f"[System] Initializing via shell activation for {script_file}...\n\n")
            text_output.see(tk.END)
            
            def run_script():
                try:
                    cmd = f"source {VENV_DIR}/bin/activate && python {script_path}"
                    process = subprocess.Popen(
                        cmd,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        executable="/bin/bash",
                        cwd=BASE_DIR
                    )
                    for line in process.stdout:
                        text_output.insert(tk.END, line)
                        text_output.see(tk.END)
                    process.wait()
                except Exception as e:
                    text_output.insert(tk.END, f"\n[Error] Failed to execute process: {e}\n")
                    text_output.see(tk.END)

            threading.Thread(target=run_script, daemon=True).start()
        else:
            missing_name = script_file if script_file else "None"
            text_output.insert(tk.END, f"Active connection interface for {name}.\n\nMonitoring local hardware registers...\n[Info] Target script '{missing_name}' not found in {BASE_DIR}.\n\nPlease ensure the script is placed inside ~/smartpin-tester.")

if __name__ == "__main__":
    root = tk.Tk()
    app = SmartPinAppliance(root)
    root.mainloop()
