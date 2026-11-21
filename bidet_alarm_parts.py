"""
Bidet alarm - parametric 3D-printable parts.

Generates:
  print/lever_cap_<bore>.stl   magnet cap that slips over the T-valve lever (print all, keep the snug one)
  print/sensor_cradle.stl      holds the reed sensor on the supply line, zip-tied
  print/enclosure_base.stl     box for the Arduino Nano
  print/enclosure_lid.stl      lid with speaker grille + buzzer holder
and assembly.html (3D viewer showing how it all goes together).

Run:  python bidet_alarm_parts.py      (needs: pip install manifold3d trimesh numpy)
All units are millimetres. Edit the PARAMETERS block and re-run.
"""
import json
import math
import os

import numpy as np
import trimesh
from manifold3d import Manifold

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "print")
os.makedirs(OUT, exist_ok=True)
SEG = 64

# ------------------------------------------------------------------ PARAMETERS
# Lever cap -- the lever looked ~6 mm thick in the video; several bores are printed.
LEVER_BORES = [5.6, 6.0, 6.4, 6.8]   # bore diameters to generate
CAP_BORE_DEPTH = 12.0                # how far the cap slides onto the lever
MAGNET_D, MAGNET_H = 6.0, 3.0        # neodymium disc magnet
MAGNET_FIT = 0.25                    # extra diameter for the magnet pocket

# Reed sensor (MC-38 style wired door contact, sensor half only)
SENSOR_W, SENSOR_D, SENSOR_L = 14.0, 8.0, 27.0
SENSOR_FIT = 0.6
STANDOFF = 14.0     # pipe centre -> sensor centre distance (how far the lever sits in front of the hose)
PIPE_D = 10.0       # braided supply line diameter (V-groove fits ~8-16 mm)

# Enclosure (Arduino Nano + 12 mm buzzer)
IN_L, IN_W, IN_H = 60.0, 30.0, 24.0  # inside dimensions
WALL = 2.0
LID_CLEAR = 0.2
BUZZER_D = 12.0
# ---------------------------------------------------------------------------


def box(x0, y0, z0, x1, y1, z1):
    return Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def cyl(d, h, seg=SEG):
    return Manifold.cylinder(h, d / 2, d / 2, seg)


def rounded_rect(l, w, h, r):
    corners = [cyl(2 * r, h).translate([sx * (l / 2 - r), sy * (w / 2 - r), 0]) for sx in (1, -1) for sy in (1, -1)]
    return Manifold.batch_hull(corners)


def to_trimesh(m):
    mesh = m.to_mesh()
    return trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts), process=False)


def save(m, name):
    path = os.path.join(OUT, name)
    to_trimesh(m).export(path)
    return path


# ------------------------------------------------------------------ PART: lever cap
def lever_cap(bore):
    """Printed with the magnet end on the bed. z=0 is the magnet face."""
    od = max(bore + 3.2, MAGNET_D + MAGNET_FIT + 2.4)
    floor = MAGNET_H + 0.2 + 1.0
    total = floor + CAP_BORE_DEPTH
    body = cyl(od, total)
    body -= cyl(MAGNET_D + MAGNET_FIT, MAGNET_H + 0.2).translate([0, 0, -0.01])
    body -= cyl(bore, CAP_BORE_DEPTH + 0.1).translate([0, 0, floor])
    # entry chamfer
    body -= Manifold.cylinder(1.0, bore / 2, bore / 2 + 0.8, SEG).translate([0, 0, total - 0.99])
    return body, total


# ------------------------------------------------------------------ PART: sensor cradle
def sensor_cradle():
    """Local frame: front face at y=0 (faces away from pipe), pipe behind (+y), z up, bottom at z=0."""
    pw, pd, pl = SENSOR_W + SENSOR_FIT, SENSOR_D - 0.5, SENSOR_L + SENSOR_FIT  # sensor stands 0.5 mm proud
    side, bottom, top = 2.4, 2.0, 1.2
    W = pw + 2 * side
    H = bottom + pl + top
    sensor_cy = (SENSOR_D) / 2 - 0.5          # sensor centre in y
    pipe_y = sensor_cy + STANDOFF
    r = PIPE_D / 2
    groove_depth = 5.5
    back_y = pipe_y - r * math.sqrt(2) + groove_depth   # pipe touches both V faces
    back_y = max(back_y, pd + 2.0 + groove_depth + 1.0)
    body = box(-W / 2, 0, 0, W / 2, back_y, H)
    # sensor pocket (open at front)
    body -= box(-pw / 2, -1, bottom, pw / 2, pd, bottom + pl)
    # wire exit slot through the floor
    body -= box(-2.2, -1, -1, 2.2, pd, bottom + 0.1)
    # 90 degree V-groove on the back, full height
    g = Manifold.cube([20, 20, H + 2], True).rotate([0, 0, 45]).translate([0, back_y + 20 / math.sqrt(2) - groove_depth, H / 2])
    body -= g
    # zip-tie channels (5 mm wide, 1.2 deep) around front + sides
    for zc in (bottom + 6, bottom + pl - 6):
        band = box(-W / 2 - 1, -1, zc - 2.6, W / 2 + 1, back_y - groove_depth, zc + 2.6)
        keep = box(-W / 2 + 1.2, 1.2, zc - 3, W / 2 - 1.2, back_y + 1, zc + 3)
        body -= (band - keep)
    info = dict(W=W, H=H, pipe_y=pipe_y, back_y=back_y, sensor_cy=sensor_cy, bottom=bottom, pd=pd)
    return body, info


# ------------------------------------------------------------------ PART: enclosure
def enclosure():
    OL, OW = IN_L + 2 * WALL, IN_W + 2 * WALL
    OH = IN_H + WALL
    base = rounded_rect(OL, OW, OH, 4) - rounded_rect(IN_L, IN_W, IN_H + 1, 2).translate([0, 0, WALL])
    fz = WALL  # floor top
    # Nano rails: PCB (18 mm wide) rests on ledges 3 mm high, held between outer bars
    nano_x0 = -IN_L / 2
    for s in (1, -1):
        base += box(nano_x0, s * 7.0, fz - 0.1, nano_x0 + 44, s * 9.3, fz + 3).translate([0, 0, 0]) if s > 0 else \
            box(nano_x0, -9.3, fz - 0.1, nano_x0 + 44, -7.0, fz + 3)
        base += box(nano_x0, 9.3, fz - 0.1, nano_x0 + 44, 11.3, fz + 6) if s > 0 else \
            box(nano_x0, -11.3, fz - 0.1, nano_x0 + 44, -9.3, fz + 6)
    # USB opening (-x wall), centred on the Nano's connector
    base -= box(-OL / 2 - 1, -6.5, fz + 2.5, -IN_L / 2 + 0.5, 6.5, fz + 11.5)
    # sensor cable hole (+x wall) with a slot from the top so a pre-wired cable drops in
    base -= cyl(5.0, 10).rotate([0, 90, 0]).translate([IN_L / 2 - 1, 0, fz + 14])
    base -= box(IN_L / 2 - 1, -1.6, fz + 14, OL / 2 + 1, 1.6, OH + 1)

    # lid
    lid = rounded_rect(OL, OW, 2.0, 4)
    lip_o = rounded_rect(IN_L - 2 * LID_CLEAR, IN_W - 2 * LID_CLEAR, 3.0, 2)
    lip_i = rounded_rect(IN_L - 2 * LID_CLEAR - 3.0, IN_W - 2 * LID_CLEAR - 3.0, 3.2, 1)
    lid += (lip_o - lip_i.translate([0, 0, -0.1])).translate([0, 0, 2.0])
    # speaker grille over the buzzer (centre of lid, toward +x so it clears the Nano's USB end)
    bx = 12.0
    for i in range(-2, 3):
        for j in range(-2, 3):
            if i * i + j * j <= 5:
                lid -= cyl(1.8, 5, 24).translate([bx + i * 2.6, j * 2.6, -1])
    # buzzer holder ring on the inside
    ring = cyl(BUZZER_D + 3.2, 6.0) - cyl(BUZZER_D + 0.4, 6.2).translate([0, 0, -0.1])
    lid += ring.translate([bx, 0, 1.9])
    # lid lip wall cut where the sensor-cable slot is, so the lid seats over the cable
    lid -= box(IN_L / 2 - 3, -1.6, 1.9, IN_L / 2 + 1, 1.6, 6)
    return base, lid, dict(OL=OL, OW=OW, OH=OH, bx=bx)


# ------------------------------------------------------------------ build + export
parts = {}
for b in LEVER_BORES:
    cap, cap_len = lever_cap(b)
    save(cap, f"lever_cap_{b:.1f}mm.stl")
cap, cap_len = lever_cap(6.0)
cradle, cinfo = sensor_cradle()
base, lid, einfo = enclosure()
save(cradle, "sensor_cradle.stl")
save(base, "enclosure_base.stl")
save(lid, "enclosure_lid.stl")

# ------------------------------------------------------------------ reference models for the viewer
LEVER_LEN, LEVER_Y = 26.0, -STANDOFF
valve = cyl(20, 55).translate([0, 0, -25])                                  # T-valve body
valve += cyl(30, 8).rotate([90, 0, 0]).translate([0, -10, 0])                 # knob disc
valve += cyl(22, 10, 6).translate([0, 0, -35])                                # coupling nut
valve += cyl(24, 12, 6).translate([0, 0, 30])                                 # tank adapter
pipe = cyl(PIPE_D, 70, 24).translate([0, 0, -105])
hose = cyl(9, 30, 24).rotate([0, 90, 0]).translate([22, 0, 5])
lever = cyl(6, LEVER_LEN, 24).translate([0, 0, -LEVER_LEN]).translate([0, LEVER_Y, 0])
# cap in assembly frame: open end up, magnet face down, slid onto lever tip
cap_asm = cap.rotate([180, 0, 0]).translate([0, LEVER_Y, -LEVER_LEN + CAP_BORE_DEPTH])
magnet_z = -LEVER_LEN + CAP_BORE_DEPTH - cap_len
magnet = cyl(MAGNET_D, MAGNET_H, 24).translate([0, LEVER_Y, magnet_z + 0.1])
# cradle: front faces -y (toward viewer); its sensor centre must line up under the lever (y = LEVER_Y)
gap = 5.0
c_top = magnet_z - gap
cradle_asm = cradle.translate([0, -cinfo["pipe_y"], c_top - cinfo["H"]])  # pipe at y=0, sensor under the lever
sensor = box(-SENSOR_W / 2, -SENSOR_D / 2, 0, SENSOR_W / 2, SENSOR_D / 2, SENSOR_L).translate(
    [0, cinfo["sensor_cy"] - cinfo["pipe_y"], c_top - cinfo["H"] + cinfo["bottom"] + SENSOR_FIT / 2])
# sensor centre y should equal LEVER_Y when STANDOFF == -LEVER_Y
fz = WALL
nano = box(-IN_L / 2 + 0.5, -9, fz + 3, -IN_L / 2 + 43.7, 9, fz + 4.6)
nano += box(-IN_L / 2 - 0.5, -4, fz + 4.6, -IN_L / 2 + 8.5, 4, fz + 8.6)       # USB connector
nano += box(-IN_L / 2 + 14, -5, fz + 4.6, -IN_L / 2 + 24, 5, fz + 6.0)        # chip
buzzer = cyl(BUZZER_D, 9.5).translate([einfo["bx"], 0, einfo["OH"] - 9.5 - 0.0])

M = lambda m: to_trimesh(m)


def pack(m, decimals=2):
    t = M(m)
    return {"v": np.round(t.vertices, decimals).flatten().tolist(), "f": t.faces.flatten().tolist()}


scene = {
    "valve": pack(valve), "pipe": pack(pipe), "hose": pack(hose), "lever": pack(lever),
    "cap": pack(cap_asm), "magnet": pack(magnet), "cradle": pack(cradle_asm), "sensor": pack(sensor),
    "base": pack(base), "lid": pack(lid), "nano": pack(nano), "buzzer": pack(buzzer),
    "meta": {"leverY": LEVER_Y, "lidZ": einfo["OH"], "magnetZ": magnet_z, "sensorTop": c_top},
}
with open(os.path.join(HERE, "assembly_data.js"), "w") as f:
    f.write("window.ASM=" + json.dumps(scene, separators=(",", ":")) + ";")

for p in sorted(os.listdir(OUT)):
    t = trimesh.load(os.path.join(OUT, p))
    print(f"{p:28s} watertight={t.is_watertight}  size={np.round(t.extents, 1)} mm")
