#!/usr/bin/env bash
# Run on the Mac after the freshly flashed Pi has booted (first boot takes ~2-3 min).
#   ./pi/setup_from_mac.sh
# Waits for bidet-alarm.local, checks SSH + Wi-Fi, copies this repo to the Pi and installs what the alarm needs.
set -euo pipefail
HOST=bidet-alarm            # ~/.ssh/config entry -> bidet-alarm.local, user pi, ~/.ssh/id_ed25519
REPO="$(cd "$(dirname "$0")/.." && pwd)"

echo "Waiting for bidet-alarm.local to appear on the network (up to 6 min)..."
for i in $(seq 1 72); do
  if ping -c1 -t2 bidet-alarm.local >/dev/null 2>&1; then echo "  found it"; break; fi
  [ "$i" = 72 ] && { echo "Not found. Check the Pi's power LED/green activity LED, and that the Wi-Fi name/password in Imager were right."; exit 1; }
  sleep 5
done

echo "Waiting for SSH..."
for i in $(seq 1 30); do
  ssh -o BatchMode=yes -o ConnectTimeout=5 "$HOST" true 2>/dev/null && break
  [ "$i" = 30 ] && { echo "SSH not answering. Was 'Enable SSH' + public key set in Imager?"; exit 1; }
  sleep 5
done

ssh "$HOST" 'echo "  logged in as $(whoami) on $(hostname), $(. /etc/os-release; echo $PRETTY_NAME)";
             echo "  Wi-Fi: $(iwgetid -r 2>/dev/null || nmcli -t -f active,ssid dev wifi | grep ^yes | cut -d: -f2)  IP: $(hostname -I | cut -d" " -f1)"'

echo "Copying the project to ~/bidet-alarm on the Pi..."
rsync -az --delete --exclude .git --exclude '__pycache__' --exclude '*.stl' "$REPO/" "$HOST:bidet-alarm/"

echo "Installing packages (gpiozero + ALSA tools; usually already present)..."
ssh "$HOST" 'sudo apt-get update -qq && sudo apt-get install -y -qq python3-gpiozero python3-lgpio alsa-utils >/dev/null && echo "  done"'

cat <<'EOF'

Pi is ready. Next (desk test):
  1. Shut it down:      ssh bidet-alarm sudo poweroff     (wait for the green LED to stop)
  2. Wire the KY-024:   + -> pin 1 (3.3V),  G -> pin 6 (GND),  D0 -> pin 11 (GPIO17)
  3. Power it back on, then:
       ssh bidet-alarm
       cd bidet-alarm && python3 pi/bidet_alarm.py --calibrate
EOF
