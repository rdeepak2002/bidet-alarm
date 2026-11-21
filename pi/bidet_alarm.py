#!/usr/bin/env python3
"""
Bidet alarm - Raspberry Pi version.

Hardware (no extra parts):
  KY-024 Hall sensor module    +  -> Pi pin 1  (3.3V)   <- NOT 5V: the Pi's GPIO is 3.3V only
                               G  -> Pi pin 6  (GND)
                               D0 -> Pi pin 11 (GPIO17)
                               A0 -> not used
  Magnet on the valve lever. Speaker/headphones on the 3.5 mm jack (or HDMI/Bluetooth audio).

Usage:
  python3 bidet_alarm.py --calibrate     # prints the sensor reading live; use it to set up
  python3 bidet_alarm.py --test          # alarm after 10 s instead of 10 min
  python3 bidet_alarm.py                 # normal run (see bidet-alarm.service to start at boot)

Optional phone notification: set NTFY_TOPIC to a long random name, install the free
"ntfy" app on the phone and subscribe to the same topic. Anyone who knows the topic
name can read it, so make it unguessable.
"""
import argparse
import math
import os
import struct
import subprocess
import sys
import time
import urllib.request
import wave

from gpiozero import DigitalInputDevice

SENSOR_GPIO = 17
# Reading of D0 when the magnet is NEXT to the sensor (valve CLOSED).
# KY-024 boards differ; run --calibrate and set this to what you see with the magnet near.
MAGNET_NEAR_VALUE = int(os.environ.get("MAGNET_NEAR_VALUE", "0"))

ALARM_DELAY = 10 * 60       # seconds the valve may stay open
REPEAT_EVERY = 30           # seconds between repeated alarms
HERE = os.path.dirname(os.path.abspath(__file__))
CUSTOM_SOUND = os.path.join(HERE, "alarm.wav")   # drop your own recording here to use it
BEEP_SOUND = os.path.join(HERE, ".beep.wav")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")


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


def play_alarm():
    sound = CUSTOM_SOUND if os.path.exists(CUSTOM_SOUND) else BEEP_SOUND
    subprocess.run(["aplay", "-q", sound], check=False)


def notify(msg):
    if not NTFY_TOPIC:
        return
    try:
        req = urllib.request.Request(f"https://ntfy.sh/{NTFY_TOPIC}", data=msg.encode(),
                                     headers={"Title": "Bidet alarm", "Priority": "high"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:  # never let a network hiccup stop the local alarm
        print("notify failed:", e, file=sys.stderr)


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
    opened_at = last_alarm = None
    print(f"Running. Alarm after {delay} s open.")
    play_alarm() if args.test else None

    while True:
        is_open = sensor.value != MAGNET_NEAR_VALUE
        now = time.monotonic()
        if is_open and opened_at is None:
            opened_at, last_alarm = now, None
            print(time.strftime("%H:%M:%S"), "valve OPEN")
        elif not is_open and opened_at is not None:
            opened_at = None
            print(time.strftime("%H:%M:%S"), "valve CLOSED")
        if opened_at is not None and now - opened_at >= delay:
            if last_alarm is None or now - last_alarm >= REPEAT_EVERY:
                if last_alarm is None:
                    notify(f"The bidet valve has been open for {int((now - opened_at) / 60)} min. Please turn it off.")
                play_alarm()
                last_alarm = time.monotonic()
        time.sleep(0.2)


if __name__ == "__main__":
    main()
