#!/usr/bin/env python3
"""
Bidet alarm - Raspberry Pi version.

Hardware (no extra parts):
  KY-024 Hall sensor module    +  -> Pi pin 1  (3.3V)   <- NOT 5V: the Pi's GPIO is 3.3V only
                               G  -> Pi pin 6  (GND)
                               D0 -> Pi pin 11 (GPIO17)
                               A0 -> not used
  Magnet on the valve lever. Speaker on the 3.5 mm jack, or a USB speaker (set AUDIO_DEVICE).

Usage:
  python3 bidet_alarm.py --calibrate     # prints the sensor reading live; use it to set up
  python3 bidet_alarm.py --test          # alarm after 10 s instead of 10 min
  python3 bidet_alarm.py                 # normal run (see bidet-alarm.service to start at boot)

Status page: while it runs, http://bidet-alarm.local/ shows whether the valve is open, for how
long, and the recent history (port 80 under the service; WEB_PORT overrides it, 0 turns it off).
"""
import argparse
import json
import math
import os
import sqlite3
import struct
import subprocess
import sys
import threading
import time
import urllib.parse
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from gpiozero import DigitalInputDevice

SENSOR_GPIO = 17
# Reading of D0 when the magnet is NEXT to the sensor (valve CLOSED).
# KY-024 boards differ; run --calibrate and set this to what you see with the magnet near.
MAGNET_NEAR_VALUE = int(os.environ.get("MAGNET_NEAR_VALUE", "1"))   # this KY-024 reads 1 with the magnet near (measured)

ALARM_DELAY = 10 * 60       # seconds the valve may stay open
REPEAT_EVERY = 30           # seconds between repeated alarms
HERE = os.path.dirname(os.path.abspath(__file__))
CUSTOM_SOUND = os.path.join(HERE, "alarm.wav")   # drop your own recording here to use it
BEEP_SOUND = os.path.join(HERE, ".beep.wav")
# Audio output. Empty = system default. For a USB speaker that plays over USB, find its card
# name with `aplay -L | grep -i usb` and set e.g. AUDIO_DEVICE=plughw:CARD=Device,DEV=0
# If it's empty, a plugged-in USB sound device is used automatically, else the system default.
AUDIO_DEVICE = os.environ.get("AUDIO_DEVICE", "")
WEB_PORT = int(os.environ.get("WEB_PORT", "80"))
PAGE = os.path.join(HERE, "status.html")
STATIC = {"/manifest.json": "application/manifest+json", "/apple-touch-icon.png": "image/png",
          "/icon-192.png": "image/png", "/icon-512.png": "image/png", "/favicon.svg": "image/svg+xml",
          "/favicon-32.png": "image/png", "/favicon.ico": "image/png"}

# shared with the web page
state = {"open": False, "since": time.time(), "alarming": False, "alarm_delay": ALARM_DELAY,
         "started": time.time(), "last_read": None}
# open/closed history in SQLite, so it survives restarts. Old rows are pruned automatically:
# anything older than KEEP_DAYS, and anything beyond the newest MAX_EVENTS.
DB_PATH = os.environ.get("DB_PATH", os.path.expanduser("~/bidet-alarm.db"))
KEEP_DAYS = int(os.environ.get("KEEP_DAYS", "365"))
MAX_EVENTS = int(os.environ.get("MAX_EVENTS", "10000"))
lock = threading.Lock()
db = None


def open_db():
    global db
    db = sqlite3.connect(DB_PATH, check_same_thread=False)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, t REAL NOT NULL, "
               "event TEXT NOT NULL, open_for INTEGER)")
    db.execute("CREATE INDEX IF NOT EXISTS events_t ON events(t)")
    prune()


def prune():
    db.execute("DELETE FROM events WHERE t < ?", (time.time() - KEEP_DAYS * 86400,))
    db.execute("DELETE FROM events WHERE id <= (SELECT id FROM events ORDER BY id DESC LIMIT 1 OFFSET ?)",
               (MAX_EVENTS,))
    db.commit()


def last_valve_event():
    """The newest opened/closed row, to pick up where we left off after a restart."""
    with lock:
        return db.execute("SELECT t, event FROM events WHERE event IN ('opened','closed') "
                          "ORDER BY id DESC LIMIT 1").fetchone()


def make_beep(path):
    """Generate a loud two-tone beep pattern (no extra packages needed)."""
    rate, out = 44100, []
    for _ in range(6):
        for f, dur in ((2700, 0.18), (2300, 0.18)):
            n = int(rate * dur)
            out += [int(30000 * math.sin(2 * math.pi * f * i / rate)) for i in range(n)]
        out += [0] * int(rate * 0.08)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack(f"<{len(out)}h", *out))


def audio_device():
    if AUDIO_DEVICE:
        return AUDIO_DEVICE
    try:   # first USB sound card, e.g. plughw:CARD=Device,DEV=0
        out = subprocess.run(["aplay", "-L"], capture_output=True, text=True, timeout=5).stdout.splitlines()
        for i, line in enumerate(out):
            if line.startswith("plughw:CARD=") and i + 1 < len(out) and "usb" in out[i + 1].lower():
                return line.strip()
    except Exception:
        pass
    return ""


def play_alarm():
    sound = CUSTOM_SOUND if os.path.exists(CUSTOM_SOUND) else BEEP_SOUND
    if not os.path.exists(sound):
        make_beep(BEEP_SOUND)
    dev = audio_device()
    cmd = ["aplay", "-q"] + (["-D", dev] if dev else []) + [sound]
    subprocess.run(cmd, check=False)


class Web(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(url.query)
        if url.path == "/api/events":   # ?page=1&per=10, page 1 = newest
            try:
                page = max(1, int(q.get("page", ["1"])[0]))
                per = min(100, max(1, int(q.get("per", ["10"])[0])))
            except ValueError:
                page, per = 1, 10
            with lock:
                total = db.execute("SELECT COUNT(*) FROM events WHERE event != 'started'").fetchone()[0]
                rows = db.execute("SELECT t, event, open_for FROM events WHERE event != 'started' "
                                  "ORDER BY id DESC LIMIT ? OFFSET ?",
                                  (per, (page - 1) * per)).fetchall()
            items = [{"t": t, "event": e, "open_for": o} for t, e, o in rows]
            pages = max(1, -(-total // per))
            body = {"events": items, "page": page, "per": per, "total": total, "pages": pages}
            self._send(200, json.dumps(body).encode(), "application/json")
        elif self.path in ("/", "/index.html"):
            with open(PAGE, "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        elif self.path in STATIC:
            name = "favicon-32.png" if self.path == "/favicon.ico" else self.path[1:]
            with open(os.path.join(HERE, name), "rb") as f:
                self._send(200, f.read(), STATIC[self.path])
        elif self.path == "/api/state":
            with lock:
                n = db.execute("SELECT MAX(id) FROM events WHERE event != 'started'").fetchone()[0]
                body = dict(state, now=time.time(), latest=n)
            self._send(200, json.dumps(body).encode(), "application/json")
        else:
            self._send(404, b"not found", "text/plain")

    def log_message(self, *a):
        pass


def start_web():
    for port in ([WEB_PORT, 8080] if WEB_PORT == 80 else [WEB_PORT]):
        if not port:
            return
        try:
            srv = ThreadingHTTPServer(("", port), Web)
        except OSError as e:
            print(f"status page: can't use port {port} ({e})", file=sys.stderr)
            continue
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print(f"Status page on http://{os.uname().nodename}.local" + ("" if port == 80 else f":{port}") + "/")
        return


def record(event, is_open=None, alarming=None, open_for=None, since=None):
    now = time.time()
    with lock:
        if is_open is not None:
            state["open"], state["since"] = is_open, since or now
        if alarming is not None:
            state["alarming"] = alarming
        if event:
            try:
                db.execute("INSERT INTO events (t, event, open_for) VALUES (?, ?, ?)", (now, event, open_for))
                prune()
            except sqlite3.Error as e:   # never let logging stop the alarm
                print("can't write event:", e, file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()

    sensor = DigitalInputDevice(SENSOR_GPIO, pull_up=None, active_state=True)  # module drives D0 itself

    if args.calibrate:
        print("Move the magnet toward/away from the sensor. Ctrl+C to stop.")
        last = None
        while True:
            v = sensor.value
            if v != last:
                print(f"D0 = {v}   ({'magnet NEAR -> valve CLOSED' if v == MAGNET_NEAR_VALUE else 'magnet AWAY -> valve OPEN'})")
                last = v
            time.sleep(0.05)

    if not os.path.exists(BEEP_SOUND):
        make_beep(BEEP_SOUND)
    delay = 10 if args.test else ALARM_DELAY
    state["alarm_delay"] = delay
    opened_at = last_alarm = None
    print(f"Running. Alarm after {delay} s open.")
    open_db()
    start_web()
    # resume after a restart: if the valve is still open, keep the original open time
    last = last_valve_event()
    if sensor.value != MAGNET_NEAR_VALUE and last and last[1] == "opened":
        opened_at = time.monotonic() - (time.time() - last[0])
        record(None, is_open=True, since=last[0])
    elif sensor.value == MAGNET_NEAR_VALUE and last and last[1] == "closed":
        record(None, is_open=False, since=last[0])
    elif sensor.value == MAGNET_NEAR_VALUE and last and last[1] == "opened":
        record("closed", is_open=False)   # it was closed while this program wasn't running
    record("started")
    if args.test:
        play_alarm()   # one beep straight away, to check the speaker

    while True:
        is_open = sensor.value != MAGNET_NEAR_VALUE
        now = time.monotonic()
        if is_open and opened_at is None:
            opened_at, last_alarm = now, None
            print(time.strftime("%H:%M:%S"), "valve OPEN")
            record("opened", is_open=True)
        elif not is_open and opened_at is not None:
            print(time.strftime("%H:%M:%S"), "valve CLOSED")
            record("closed", is_open=False, alarming=False, open_for=round(now - opened_at))
            opened_at = None
        state["last_read"] = time.time()
        if opened_at is not None and now - opened_at >= delay:
            if last_alarm is None or now - last_alarm >= REPEAT_EVERY:
                if last_alarm is None:
                    record("alarm", alarming=True)
                play_alarm()
                last_alarm = time.monotonic()
        time.sleep(0.2)


if __name__ == "__main__":
    main()
