"""
Raspberry Pi 4 Model B case for the bidet alarm.

Generates print/pi4_case_base.stl and print/pi4_case_lid.stl.

  - No screws: the Pi drops onto 4 pegs in the base; 4 posts on the lid press it down.
  - Lid has a slot over the whole 40-pin header, so the KY-024 jumper wires plug in and exit upward.
  - USB-C opening is oversized for a chunky power plug (USB_C_OPEN_W x USB_C_OPEN_H).
  - One USB-A opening (lower USB 2.0 port) for the speaker; the other USB ports and Ethernet are covered.
  - SD card stays inside: the SD end has room for an inserted card sticking out ~3 mm (plus 0.8 mm).
  - micro-HDMI and the 3.5 mm audio jack are covered (headless, USB speaker).

Run:  python pi_case.py   (needs manifold3d trimesh numpy)
Board coordinates follow the official Pi 4 drawing: x along the 85 mm edge from the SD-card end,
y across the 56 mm edge from the USB-C/HDMI side, z up. Units mm.
"""
import os

import numpy as np
import trimesh
from manifold3d import Manifold

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "print")
SEG = 48

# ------------------------------------------------------------------ PARAMETERS
USB_C_OPEN_W, USB_C_OPEN_H = 18.0, 12.5   # power plug opening (plug head must be smaller than this)
USB_A_OPEN_W, USB_A_OPEN_H = 18.0, 11.0   # speaker plug opening: lower USB 2.0 port only
USB_A_Y, USB_A_DZ = 9.0, 4.6              # that port's centre: y on the board, height above the PCB top
WALL, FLOOR, LID_T = 2.0, 2.0, 2.0
STANDOFF = 4.0          # floor top -> PCB bottom
PCB_T = 1.5
TOP_CLEAR = 1.0         # tallest part (USB stack, 16 mm) -> lid underside
FIT = 0.25              # lid lip clearance
# inside of the box, in board coordinates (board is 0..85 x 0..56)
IN_X0, IN_X1 = -4.0, 88.0   # SD end: inserted card (sticks out ~2.5-3 mm) clears the wall; port end: USB/Ethernet fronts (to 87.6) clear it
IN_Y0, IN_Y1 = -3.0, 57.0   # port side has 3 mm for the HDMI/audio/USB-C fronts
HOLES = [(3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5)]
# ---------------------------------------------------------------------------

PCB_Z0 = FLOOR + STANDOFF            # PCB bottom
PCB_Z1 = PCB_Z0 + PCB_T              # PCB top
LID_Z = PCB_Z1 + 16.0 + TOP_CLEAR    # lid underside = base wall top
OX0, OX1, OY0, OY1 = IN_X0 - WALL, IN_X1 + WALL, IN_Y0 - WALL, IN_Y1 + WALL


def box(x0, y0, z0, x1, y1, z1):
    return Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def cyl(d, h, seg=SEG):
    return Manifold.cylinder(h, d / 2, d / 2, seg)


def rrect(x0, y0, x1, y1, z0, z1, r):
    pts = [cyl(2 * r, z1 - z0).translate([x, y, z0]) for x in (x0 + r, x1 - r) for y in (y0 + r, y1 - r)]
    return Manifold.batch_hull(pts)


def to_trimesh(m):
    mesh = m.to_mesh()
    return trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts), process=False)


def pi4_model():
    """Envelope of the Pi 4 (generous), z relative to the case."""
    t = PCB_Z1
    parts = [
        rrect(0, 0, 85, 56, PCB_Z0, PCB_Z1, 3),
        box(6.7, -1.3, t, 15.7, 6.5, t + 3.3),          # USB-C
        box(22.2, -1.3, t, 29.8, 6.5, t + 3.6),         # micro-HDMI 0
        box(35.7, -1.3, t, 43.3, 6.5, t + 3.6),         # micro-HDMI 1
        box(50.5, -2.6, t, 57.5, 12.0, t + 6.0),        # audio jack
        box(69.0, 2.4, t, 87.2, 15.6, t + 16.0),        # USB 2 stack
        box(69.0, 20.4, t, 87.2, 33.6, t + 16.0),       # USB 3 stack
        box(65.0, 37.7, t, 87.6, 53.8, t + 13.6),       # Ethernet
        box(7.1, 49.9, t, 57.9, 55.1, t + 8.5),         # 40-pin header
        box(7.1, 49.9, t, 57.9, 55.1, t + 2.5 + 14.0),  # Dupont housings on the header
        box(-3.2, 21.0, PCB_Z0 - 2.0, 13.0, 35.0, PCB_Z0),  # SD socket + inserted card (sticks out ~3 mm)
        box(5, 5, PCB_Z0 - 1.5, 80, 51, PCB_Z0),        # misc underside parts
    ]
    m = _union(parts)
    for x, y in HOLES:   # mounting holes (2.7 mm) and their 6 mm keep-out pads
        m -= cyl(2.7, 10).translate([x, y, PCB_Z0 - 5])
        m -= cyl(6.2, PCB_Z0 - FLOOR).translate([x, y, FLOOR])
    return m


def _union(parts):
    out = parts[0]
    for p in parts[1:]:
        out += p
    return out


def plug_envelope(w, h, length=30.0):
    """USB-C plug head of w x h mm, inserted into the port (head starts ~1 mm outside the board edge)."""
    cz = PCB_Z1 + 1.65
    return box(11.2 - w / 2, -1.0 - length, cz - h / 2, 11.2 + w / 2, -1.0, cz + h / 2)


def base():
    b = rrect(OX0, OY0, OX1, OY1, 0, LID_Z, 3) - rrect(IN_X0, IN_Y0, IN_X1, IN_Y1, FLOOR, LID_Z + 1, 1)
    for x, y in HOLES:
        b += cyl(6.0, STANDOFF + 0.01).translate([x, y, FLOOR - 0.01])
        b += cyl(2.3, PCB_T - 0.2).translate([x, y, PCB_Z0])          # peg into the 2.7 mm hole
    cz = PCB_Z1 + 1.65
    # USB-C power (chunky plug)
    b -= box(11.2 - USB_C_OPEN_W / 2, OY0 - 1, max(FLOOR + 0.6, cz - USB_C_OPEN_H / 2),
             11.2 + USB_C_OPEN_W / 2, IN_Y0 + 1, cz + USB_C_OPEN_H / 2)
    # one USB-A opening (lower USB 2.0 port) for the speaker; the rest of that end stays closed
    az = PCB_Z1 + USB_A_DZ
    b -= box(IN_X1 - 1, USB_A_Y - USB_A_OPEN_W / 2, az - USB_A_OPEN_H / 2,
             OX1 + 1, USB_A_Y + USB_A_OPEN_W / 2, az + USB_A_OPEN_H / 2)
    # floor vents
    for i in range(7):
        x = 14 + i * 6
        b -= rrect(x, 12, x + 2.5, 44, -1, FLOOR + 1, 1.2)
    return b


def lid():
    lz = LID_Z
    l = rrect(OX0, OY0, OX1, OY1, lz, lz + LID_T, 3)
    # locating lip on the two long sides and the SD end (not at the port end)
    lip_out = rrect(IN_X0 + FIT, IN_Y0 + FIT, IN_X1 - FIT, IN_Y1 - FIT, lz - 3, lz + 0.01, 1)
    lip_in = rrect(IN_X0 + FIT + 1.2, IN_Y0 + FIT + 1.2, IN_X1 + 5, IN_Y1 - FIT - 1.2, lz - 4, lz + 1, 1)
    lip = (lip_out - lip_in) - box(62, IN_Y0 - 5, lz - 5, IN_X1 + 5, IN_Y1 + 5, lz + 1)
    l += lip
    # port end: two corner tabs (clear of the USB/Ethernet fronts) stop the lid sliding that way
    for y0, y1 in ((IN_Y0 + 1.2, 1.6), (54.6, IN_Y1 - 1.2)):   # kept off the rounded inner corners
        l += box(IN_X1 - FIT - 1.2, y0, lz - 3, IN_X1 - FIT, y1, lz + 0.01)
    # hold-down posts onto the PCB at the 4 mounting holes
    for x, y in HOLES:
        l += cyl(4.5, lz - PCB_Z1 - 0.2 + 0.01).translate([x, y, PCB_Z1 + 0.2])
    # GPIO slot (whole 40-pin header)
    l -= box(6.6, 49.4, lz - 10, 58.4, 55.6, lz + LID_T + 1)
    # pin-1 marker: small triangle engraved next to pin 1 (x=8.37)
    tri = Manifold.cylinder(1.0, 2.0, 2.0, 3).rotate([0, 0, 90]).translate([8.37, 46.6, lz + LID_T - 0.6])
    l -= tri
    # vents over the SoC
    for i in range(7):
        x = 14 + i * 6
        l -= rrect(x, 12, x + 2.5, 42, lz - 1, lz + LID_T + 1, 1.2)
    return l


def vol(m):
    return m.volume() if hasattr(m, "volume") else m.get_volume()


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    B, L, P = base(), lid(), pi4_model()
    print(f"base vs Pi        {vol(B ^ P):.1f} mm^3")
    print(f"lid vs Pi         {vol(L ^ P):.1f} mm^3")
    print(f"lid vs base       {vol(L ^ B):.1f} mm^3")
    for w, h in [(12, 7), (16, 10), (17.5, 12)]:
        print(f"USB-C plug head {w:>4} x {h:<4} mm vs case: {vol((B + L) ^ plug_envelope(w, h)):.1f} mm^3")
    az = PCB_Z1 + USB_A_DZ
    for w, h in [(16, 8), (17.5, 10.5)]:
        plug = box(87.3, USB_A_Y - w / 2, az - h / 2, 87.3 + 30, USB_A_Y + w / 2, az + h / 2)
        print(f"USB-A plug head {w:>4} x {h:<4} mm vs case: {vol((B + L) ^ plug):.1f} mm^3")
    # Pi must drop straight down into the base: sweep it upward and check
    sweep = _union([P.translate([0, 0, dz]) for dz in np.arange(0, LID_Z, 2.0)])
    print(f"drop-in sweep     {vol(B ^ sweep):.1f} mm^3")
    to_trimesh(B).export(os.path.join(OUT, "pi4_case_base.stl"))
    # lid printed top face down
    Lp = L.rotate([180, 0, 0])
    Lp = Lp.translate([0, 0, -Lp.bounding_box()[2]])
    to_trimesh(Lp).export(os.path.join(OUT, "pi4_case_lid.stl"))
    for n in ("pi4_case_base.stl", "pi4_case_lid.stl"):
        m = trimesh.load(os.path.join(OUT, n))
        print(f"{n:22} watertight={m.is_watertight} size={np.round(m.extents, 1)} mm")
