"""
Pi / KY-024 alternate design - parametric printable parts + viewer data.

Reuses the lever cap and reference valve from ../archive/nano-design/bidet_alarm_parts.py and adds a holder
for the KY-024 Hall sensor board. Run:  python pi_parts.py   (needs manifold3d trimesh numpy)

KY-024 sizes below are typical values - MEASURE YOUR BOARD and edit them before printing.
"""
import json
import math
import os
import runpy

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "print")
os.makedirs(OUT, exist_ok=True)
g = runpy.run_path(os.path.join(HERE, "..", "archive", "nano-design", "bidet_alarm_parts.py"))  # shared valve + lever cap geometry
Manifold, box, cyl, to_trimesh = g["Manifold"], g["box"], g["cyl"], g["to_trimesh"]

# ------------------------------------------------------------------ PARAMETERS
KY_L, KY_W, PCB_T = 34.7, 15.3, 1.6   # KY-024 board: measured 34.7 x 15.3 mm (header end to far edge), thickness
SENSOR_ABOVE_PCB = -3.5               # Hall sensor face vs the board's end: it stands upright in the slot ~3.5 mm
                                      # back from the prong tips, flat face toward the end (photo IMG_1584)
HALL_OUT = 5.0                        # how far the upright sensor sticks out from the board's component face
SENSOR_GAP = 12.5                     # magnet face -> Hall sensor face, valve closed (user: 10-15 mm triggers reliably)
PCB_PROUD = 3.0                       # board sticks out this far above the holder
FIT = 0.3                             # slot clearance
PIPE_D = g["PIPE_D"]
LEVER_Y = g["MAGNET_Y"]               # magnet centre (lever axis, shifted away from the valve for wide magnets)
# ---------------------------------------------------------------------------

# Assembly frame: supply line axis = z axis, lever/magnet at y = LEVER_Y, z up.
magnet_z = g["magnet_z"]                          # magnet face (bottom of lever cap)
ROOF = 0.8           # plastic over the board end - magnetic field passes straight through
sensor_face_z = magnet_z - SENSOR_GAP
pcb_top_z = sensor_face_z - SENSOR_ABOVE_PCB       # board's end (prong tips)
z_roof = pcb_top_z + 0.3                           # cover roof underside, just over the prong tips
tray_top = pcb_top_z - PCB_PROUD
STOP_H = 1.5                                       # the board's header end rests on two stops this tall
tray_bot = pcb_top_z - KY_L - STOP_H
board_z0 = tray_bot + STOP_H                       # board's header end
POT_SCREW, POT_X = 16.3, 3.5                       # trimmer screw: mm from the header end, and sideways (photo)
y_f = LEVER_Y + HALL_OUT / 2                       # board's component face: the upright sensor's centre lines up under the magnet
y_b = y_f + PCB_T                                  # board's back face (toward the hose)
r = PIPE_D / 2
apex = -r * math.sqrt(2)                           # V-groove apex so the hose touches both faces
groove_depth = 4.0
y_back = apex + groove_depth
rail = 2.4
xo = KY_W / 2 + FIT
H = tray_top - tray_bot


def ky024_holder():
    body = box(-xo - rail, y_f - 2.0, tray_bot, xo + rail, y_back, tray_top)
    # board slot (edges captured by 1 mm lips in front)
    body -= box(-xo, y_f - FIT, tray_bot - 1, xo, y_b + FIT, tray_top + 1)
    body -= box(-xo + 1.0, y_f - 3, tray_bot - 1, xo - 1.0, y_f, tray_top + 1)   # open front for components
    # stops at the bottom corners so the board can't slide through (header pins pass between them)
    for s in (1, -1):
        body += box(min(s * (xo - 2.0), s * xo), y_f - FIT, tray_bot, max(s * (xo - 2.0), s * xo), y_b + FIT, tray_bot + STOP_H)
    # V-groove for the supply line
    body -= Manifold.cube([20, 20, H + 4], True).rotate([0, 0, 45]).translate([0, y_back + 20 / math.sqrt(2) - groove_depth, (tray_top + tray_bot) / 2])
    # two zip-tie tunnels through the plate (tie goes through here and around the hose)
    for zc in (tray_bot + 8, tray_top - 8):
        body -= box(-xo - rail - 1, y_b + 0.8, zc - 2.6, xo + rail + 1, y_b + 2.8, zc + 2.6)
    return body


holder = ky024_holder()


# ------------------------------------------------------------------ cover (splash / condensation / bump protection)
COVER_WALL = 1.6
COMP_H = 10.0        # tallest part on the board's front (the threshold potentiometer)


def ky024_cover():
    xi = xo + rail + 0.25                       # slides over the holder with 0.25 mm clearance
    yi = y_f - COMP_H                           # inside front face
    shell = box(-xi - COVER_WALL, yi - COVER_WALL, tray_bot + 2, xi + COVER_WALL, y_back, z_roof + ROOF)
    shell -= box(-xi, yi, tray_bot, xi, y_back + 1, z_roof)          # open back (hose side) and bottom (cable, drainage)
    shell -= cyl(4.5, 20, 24).rotate([90, 0, 0]).translate([POT_X, yi + 5, board_z0 + POT_SCREW])   # screwdriver hole for the threshold pot
    for zc in (tray_bot + 8, tray_top - 8):                         # zip ties pass through the sides, into the tunnels
        shell -= box(-xi - COVER_WALL - 1, y_b + 0.6, zc - 2.8, xi + COVER_WALL + 1, y_b + 3.0, zc + 2.8)
    # recess for the coupling nut above (cover top sits just below it); Hall sensor stays covered
    shell -= cyl(g["NUT_D"] + 1.0, 30).translate([0, 0, z_roof - 2])
    return shell


cover = ky024_cover()

# reference KY-024 board for the viewer
board = box(-KY_W / 2, y_f, board_z0, KY_W / 2, y_b, pcb_top_z)
board_parts = box(-5, y_f - 10, board_z0 + 14.5, 5, y_f, board_z0 + 25.5)     # blue trimmer (measured from photo)
board_parts += box(-2.5, y_f - 2, board_z0 + 18, 2.5, y_f, board_z0 + 22)     # comparator chip
board_parts += box(-5.1, y_f - 2.6, board_z0, 5.1, y_f, board_z0 + 2.6)       # right-angle header body
hall = box(-2, y_f - HALL_OUT, sensor_face_z - 3.0, 2, y_f, sensor_face_z)   # TO-92 standing upright in the slot
legs = box(-1.5, y_f - 0.5, sensor_face_z - 4.0, 1.5, y_f + 0.01, sensor_face_z - 3.0)
pins = box(-5.1, y_f - 2.6, board_z0 - 16, 5.1, y_f, board_z0)               # pins + Dupont plugs, straight out the end

# exports (print orientation: standing upright on z = 0)
save = lambda m, name: to_trimesh(m).export(os.path.join(OUT, name))
save(holder.translate([0, 0, -tray_bot]), "ky024_holder.stl")
cv = cover.rotate([90, 0, 0])                    # front face down on the bed: no supports needed
save(cv.translate([0, 0, -cv.bounding_box()[2]]), "ky024_cover.stl")
for b in g["LEVER_BORES"]:
    save(g["lever_cap"](b)[0], f"lever_cap_{b:.1f}mm.stl")


def pack(m):
    t = to_trimesh(m)
    return {"v": np.round(t.vertices, 2).flatten().tolist(), "f": t.faces.flatten().tolist()}


data = {k: pack(v) for k, v in {
    "valve": g["valve"], "pipe": g["pipe"], "lever": g["lever"], "cap": g["cap_asm"], "magnet": g["magnet"],
    "holder": holder, "cover": cover, "board": board, "boardParts": board_parts, "hall": hall + legs, "pins": pins}.items()}
data["meta"] = {"leverY": LEVER_Y, "magnetZ": magnet_z, "sensorZ": sensor_face_z, "trayBot": tray_bot,
                "trayTop": tray_top, "yBack": y_back, "yB": y_b}
with open(os.path.join(HERE, "pi_assembly_data.js"), "w") as f:
    f.write("window.ASM=" + json.dumps(data, separators=(",", ":")) + ";")

# --- self-checks
v = lambda m: m.volume()
print("holder vs valve/nut     ", round(v(holder ^ g["valve"]), 2), "mm^3")
print("holder vs supply line   ", round(v(holder ^ g["pipe"]), 2), "mm^3")
print("holder vs board         ", round(v(holder ^ board), 2), "mm^3")
worst = max(v((g["lever"] + g["cap_asm"]).rotate([0, -a, 0]) ^ (holder + board + hall)) for a in range(0, 91, 5))
print("lever swing vs holder   ", round(worst, 2), "mm^3")
print("cover vs holder         ", round(v(cover ^ holder), 2), "mm^3")
print("holder vs pins/plugs    ", round(v(holder ^ pins), 2), "mm^3")
print("cover vs pins/plugs     ", round(v(cover ^ pins), 2), "mm^3")
print("cover vs board+parts+hall", round(v(cover ^ (board + board_parts + hall + legs)), 2), "mm^3")
print("cover vs valve/pipe     ", round(v(cover ^ (g["valve"] + g["pipe"])), 2), "mm^3")
worst_c = max(v((g["lever"] + g["cap_asm"]).rotate([0, -a, 0]) ^ cover) for a in range(0, 91, 5))
print("lever swing vs cover    ", round(worst_c, 2), "mm^3")
print(f"magnet face -> cover roof clearance = {magnet_z - (z_roof + ROOF):.1f} mm")
print(f"magnet centre y={LEVER_Y:.2f}  sensor centre y={y_f - HALL_OUT / 2:.2f}")
print(f"magnet face z={magnet_z:.1f}  sensor face z={sensor_face_z:.1f}  gap={magnet_z - sensor_face_z:.1f} mm")
print(f"holder size: {2 * (xo + rail):.1f} x {y_back - (y_f - 2):.1f} x {H:.1f} mm")
