#!/usr/bin/env python3
import os, csv, time, fcntl
from datetime import datetime, timedelta

# ---- SETTINGS ----
LOG = "/home/pi/sensor_project/logs/sensor_log.csv"
RUN_LOG = "/home/pi/sensor_project/logs/run.log"
PERIOD_SEC = 600          # 10 minutes
USE_2400 = False          # set True to represent midnight as 2400 of previous day
GPIO_PIN = 4              # CHANGE if your DHT22 is on another pin

# ---- SENSOR READ (Adafruit_DHT) ----
try:
    import Adafruit_DHT
    DHT_SENSOR = Adafruit_DHT.DHT22
except Exception as e:
    raise SystemExit(f"Failed to import Adafruit_DHT: {e}")

def c_to_f(c): 
    return c * 9/5 + 32

def read_once():
    hum, temp_c = Adafruit_DHT.read_retry(DHT_SENSOR, GPIO_PIN)
    if hum is None or temp_c is None:
        raise RuntimeError("Sensor read failed")
    return float(temp_c), float(hum)

def timestamp_fields(dt):
    date_str = dt.strftime("%Y-%m-%d")
    time_str = dt.strftime("%H%M")  # 0000–2359
    if USE_2400 and time_str == "0000":
        date_str = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
        time_str = "2400"
    return date_str, time_str

def ensure_header(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new_file = not os.path.exists(path) or os.path.getsize(path) == 0
    if new_file:
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date","time_24h","temp_F","humidity_pct"])
            f.flush(); os.fsync(f.fileno())

def append_row(path, row):
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        w.writerow(row)
        f.flush(); os.fsync(f.fileno())

def aligned_dt(period=PERIOD_SEC):
    """Datetime snapped to the most recent period boundary."""
    slot = int(time.time() // period) * period
    return datetime.fromtimestamp(slot)

def sleep_to_next_boundary(period=PERIOD_SEC):
    """Sleep until next :00/:10/:20/... boundary."""
    delay = period - (time.time() % period)
    if delay < 0.5:  # avoid sub-second naps due to jitter
        delay += period
    time.sleep(delay)

def main():
    # Single-instance lock (second copy exits quietly)
    _lock = open('/tmp/log_dht22_loop.lock', 'w')
    try:
        fcntl.flock(_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Another instance is already running. Exiting.")
        return

    ensure_header(LOG)

    # Align BEFORE first write so first row lands exactly on a boundary
    sleep_to_next_boundary()

    while True:
        try:
            dt = aligned_dt()
            temp_c, hum = read_once()
            temp_f = c_to_f(temp_c)
            date_str, time_str = timestamp_fields(dt)
            row = [date_str, time_str, f"{temp_f:.2f}", f"{hum:.2f}"]
            append_row(LOG, row)
            print(f"Wrote {row}")
        except Exception as e:
            os.makedirs(os.path.dirname(RUN_LOG), exist_ok=True)
            with open(RUN_LOG, "a") as ef:
                ef.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: {e}\n")
            print(f"{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: {e}")
        # wait for the next 10-minute mark
        sleep_to_next_boundary()

if __name__ == "__main__":
    main()
