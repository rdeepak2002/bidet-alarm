#!/usr/bin/env bash
# Run on the Mac right after Raspberry Pi Imager has written Raspberry Pi OS Lite (64-bit)
# to the card with NO customisation, while the card's "bootfs" volume is still mounted.
#   ./pi/prepare_sd_card.sh [wifi-name]
# Writes the first-boot settings (hostname bidet-alarm, user pi, SSH key login, Wi-Fi, US/Pacific)
# onto the card. The Wi-Fi password is typed into a macOS dialog and stored on the card only as
# a WPA key hash; it is never written to this repo.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
BOOT=/Volumes/bootfs
KEY="$HOME/.ssh/id_ed25519.pub"
[ -f "$BOOT/cmdline.txt" ] || { echo "No Raspberry Pi boot volume at $BOOT. Write the card with Imager first."; exit 1; }
[ -f "$KEY" ] || { echo "No SSH key at $KEY. Create one with: ssh-keygen -t ed25519"; exit 1; }
SSID="${1:-}"
[ -n "$SSID" ] || read -r -p "Wi-Fi network name: " SSID
python3 - "$HERE/firstboot" "$BOOT" "$SSID" "$KEY" <<'PY'
import hashlib, json, subprocess, sys
src, boot, ssid, keyfile = sys.argv[1:]
scr = ('with timeout of 600 seconds\ntell application "System Events"\nactivate\n'
       f'set t to text returned of (display dialog "Wi-Fi password for {ssid}:" default answer "" '
       'with hidden answer with title "Bidet alarm Pi setup")\nend tell\nend timeout\nreturn t')
r = subprocess.run(["osascript", "-e", scr], capture_output=True, text=True)
pw = r.stdout.rstrip("\n")
if r.returncode or not pw:
    sys.exit("No password entered.")
psk = hashlib.pbkdf2_hmac("sha1", pw.encode(), ssid.encode(), 4096, 32).hex()
del pw
key = open(keyfile).read().strip()
ud = open(f"{src}/user-data").read().replace("SSH_PUBLIC_KEY        # filled in by prepare_sd_card.sh from ~/.ssh/id_ed25519.pub", key)
nc = open(f"{src}/network-config.template").read().split("network:", 1)[1]
nc = "network:" + nc.replace('"WIFI_SSID"', json.dumps(ssid)).replace("WIFI_PSK_HEX", psk)
open(f"{boot}/user-data", "w").write(ud)
open(f"{boot}/network-config", "w").write(nc)
print("Wrote user-data and network-config to the card.")
PY
rm -f "$BOOT"/._user-data "$BOOT"/._network-config
sync && diskutil eject "$BOOT" && echo "Card ejected. Put it in the Pi, power on, then run ./pi/setup_from_mac.sh"
