"""Gyroscope: lathe-turned rotor spinning inside two nodding gimbal rings on a stand."""
import math

from mathutils import Matrix

from builders.lathe import revolve

TITLE = "Gyroscope"
LOOP_SECONDS = 10
AZIMUTH = 45

ROTOR = [(0, 1.98), (0.11, 1.98), (0.11, 0.5), (0.36, 0.5), (0.36, 0.17), (1.22, 0.1),
         (1.22, 0.3), (1.66, 0.3), (1.78, 0.18), (1.78, -0.18), (1.66, -0.3), (1.22, -0.3),
         (1.22, -0.1), (0.36, -0.17), (0.36, -0.5), (0.11, -0.5), (0.11, -1.98), (0, -1.98)]


def ring(name, r_in, r_out, half):
    """Rectangular-section ring about local Z."""
    prof = [(r_in, -half), (r_out, -half), (r_out, half), (r_in, half)]
    return revolve(name, prof, cols=64, target=0.2, closed=True)


def pin(name, r, z0, z1, knob=0.0):
    prof = [(0, z1 + knob), (r, z1 + knob), (r, z0), (0, z0)]
    return revolve(name, prof, cols=8, target=0.16)


def build():
    global rotor, inner, outer
    rotor = revolve("rotor", ROTOR, cols=64, target=0.18)
    inner = ring("inner_gimbal", 1.98, 2.2, 0.17)
    outer = ring("outer_gimbal", 2.45, 2.68, 0.15)
    stand = revolve("stand", [(0, -4.25), (1.5, -4.25), (1.5, -4.0), (0.5, -3.85), (0.2, -3.6),
                              (0.2, -3.25), (0.42, -3.25), (0.42, -2.98), (0, -2.98)], cols=32, target=0.18)
    # pins: inner gimbal pivots on the outer ring along X; outer ring has knobs top and bottom
    pins = [pin("pin_x+", 0.09, 2.2, 2.45), pin("pin_x-", 0.09, 2.2, 2.45),
            pin("knob_top", 0.13, 2.68, 2.9), pin("knob_bottom", 0.13, 2.68, 2.98)]
    pins[0].matrix_basis = Matrix.Rotation(math.pi / 2, 4, "Y")
    pins[1].matrix_basis = Matrix.Rotation(-math.pi / 2, 4, "Y")
    pins[2].matrix_basis = Matrix.Rotation(-math.pi / 2, 4, "X")
    pins[3].matrix_basis = Matrix.Rotation(math.pi / 2, 4, "X")
    for p in pins[:2]:
        p.parent = inner
    for p in pins[2:]:
        p.parent = outer
    rotor.parent = inner
    inner.parent = outer
    return [stand, outer, inner, rotor] + pins


def animate(t):
    w = 2 * math.pi * t
    # rings stand upright in the XZ plane; local ring axis Z -> world Y
    upright = Matrix.Rotation(math.pi / 2, 4, "X")
    outer.matrix_basis = Matrix.Rotation(math.radians(-18 + 6 * math.sin(w)), 4, "Z") @ upright
    # inner gimbal nods about X (pins); expressed in the outer ring's local frame
    inner.matrix_basis = Matrix.Rotation(math.radians(-30 + 6 * math.sin(w + 1.2)), 4, "X")
    # rotor axis along the ring plane (local Y of ring frame), spins a quarter turn per loop
    rotor.matrix_basis = (Matrix.Rotation(-math.pi / 2, 4, "X")
                          @ Matrix.Rotation(math.pi / 2 * t, 4, "Z"))
