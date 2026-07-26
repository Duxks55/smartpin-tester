from flask import Flask, jsonify, render_template
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import threading
import time

app = Flask(__name__, template_folder='templates')

# Global storage for telemetry
telemetry_data = {"voltages": [0.0, 0.0, 0.0], "type": "DISCONNECTED"}
def scanner():
    while True:
        try:
            # Re-initialize the bus inside the loop for better error recovery
            i2c = busio.I2C(board.SCL, board.SDA)
            ads = ADS.ADS1115(i2c)
            ads.gain = 1
            
            while True: # Inner loop for continuous scanning
                v = [AnalogIn(ads, i).voltage for i in [ADS.P0, ADS.P1, ADS.P2]]
                telemetry_data["voltages"] = [round(x, 3) for x in v]
                
                # Logic: Detect PNP/NPN
                if v[0] > 2.5:
                    telemetry_data["type"] = "NPN DETECTED"
                elif 0.1 < v[0] < 1.0:
                    telemetry_data["type"] = "PNP DETECTED"
                else:
                    telemetry_data["type"] = "IDLE"
                
                time.sleep(0.2)
        except Exception as e:
            # If a sensor error occurs, the loop breaks, prints the error,
            # and restarts the I2C connection automatically.
            print(f"Sensor communication error: {e}")
            time.sleep(2) # Wait 2 seconds before trying to reconnect
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/telemetry')
def get_telemetry():
    return jsonify(telemetry_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
