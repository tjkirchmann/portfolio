"""Involute spur gears with root fillets, polar quad faces and meshing gear trains.

Geometry follows standard spur gear proportions (module M, 20 degree pressure angle,
addendum 1.0 M, dedendum 1.25 M). Each tooth flank is a true involute sampled at
`flank_segs` segments, joined to the root circle by a circular fillet of `fillet_segs`
segments. Faces are polar quad grids: each tooth is one column of quads following its flanks, the
rim has two even columns per tooth, reduced 2:1 toward the hub with clean
quad-only reduction bands. Rims, webs and hubs are separate levels joined by real step
walls.
"""
import math
from fractions import Fraction

from mathutils import Matrix, Vector

from .mesh import MeshBuilder, build_annulus

TRAINS = []  # every Train built this session; the framework checks them automatically


def _inv(a):
    return math.tan(a) - a


def tooth_profile(N, M=1.0, pa_deg=20.0, backlash=0.05, fillet=0.4, flank_segs=4, fillet_segs=2,
                  min_land=0.26):
    """Positive-angle side of one tooth centred on angle 0, from root circle to tip corner.

    Returns dict with `side` [(x, y)], `centre_r` [radius per row on the tooth centre line],
    `phi_c` (angle of the fillet foot), and the circle radii.
    """
    pa = math.radians(pa_deg)
    rp = N * M / 2
    rb = rp * math.cos(pa)
    ra = rp + M
    rf = rp - 1.25 * M
    s = math.pi * M / 2 - backlash * M

    def psi(r):
        if r <= rb:
            return s / (2 * rp) + _inv(pa)
        return s / (2 * rp) + _inv(pa) - _inv(math.acos(rb / r))

    dense = []
    n = 800
    for i in range(n + 1):
        r = rf + (ra - rf) * i / n
        a = psi(r)
        dense.append((r * math.cos(a), r * math.sin(a)))

    def dist_to_flank(cx, cy):
        best, bi = 1e9, 0
        for i, (x, y) in enumerate(dense):
            d = math.hypot(x - cx, y - cy)
            if d < best:
                best, bi = d, i
        return best, bi

    gap_half = math.pi / N

    def solve(rho):
        """Fillet centre angle for radius rho, or None if the fillet does not fit the gap."""
        rc = rf + rho
        lo, hi = psi(rf), gap_half
        if dist_to_flank(rc * math.cos(hi), rc * math.sin(hi))[0] < rho * 1.02:
            return None
        for _ in range(50):
            mid = (lo + hi) / 2
            if dist_to_flank(rc * math.cos(mid), rc * math.sin(mid))[0] < rho:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    # largest fillet up to `fillet` that leaves a root land of at least min_land
    rho = fillet * M
    while True:
        phi_c = solve(rho)
        if phi_c is not None and (gap_half - phi_c) * rf >= min_land * M:
            break
        rho *= 0.94
    rc = rf + rho
    cx, cy = rc * math.cos(phi_c), rc * math.sin(phi_c)
    _, k = dist_to_flank(cx, cy)
    k = max(k, 1)

    # fillet arc from the root tangent point to the flank tangent point
    a0 = math.atan2(-cy, -cx)  # toward the gear centre: root circle tangent point
    fx, fy = dense[k]
    a1 = math.atan2(fy - cy, fx - cx)
    da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    fil = [(cx + rho * math.cos(a0 + da * i / fillet_segs),
            cy + rho * math.sin(a0 + da * i / fillet_segs)) for i in range(fillet_segs + 1)]
    # flank from tangent point to tip, resampled evenly by arc length
    fl = dense[k:]
    cum = [0.0]
    for i in range(1, len(fl)):
        cum.append(cum[-1] + math.hypot(fl[i][0] - fl[i - 1][0], fl[i][1] - fl[i - 1][1]))
    flank = []
    for j in range(flank_segs + 1):
        t = cum[-1] * j / flank_segs
        i = min(range(len(cum)), key=lambda q: abs(cum[q] - t))
        flank.append(fl[i])
    flank[0] = fil[-1]
    side = fil + flank[1:]
    lens = [0.0]
    for i in range(1, len(side)):
        lens.append(lens[-1] + math.hypot(side[i][0] - side[i - 1][0], side[i][1] - side[i - 1][1]))
    centre_r = [rf + (ra - rf) * L / lens[-1] for L in lens]
    return dict(side=side, centre_r=centre_r, phi_c=math.atan2(side[0][1], side[0][0]),
                rp=rp, rb=rb, ra=ra, rf=rf, rho=rho, tip_half=psi(ra))


class GearMesh:
    """Built gear: Blender object plus the data the checks need."""

    def __init__(self, obj, N, M, outline, sym, info):
        self.obj, self.N, self.M, self.outline, self.sym, self.info = obj, N, M, outline, sym, info
        self.rp = N * M / 2


def gear(name, N, M=1.0, thickness=2.2, bore=None, hub=None, rim=1.6, recess=0.35, boss=0.5,
         flank_segs=4, fillet_segs=2, wall_segs=None, backlash=0.1, web_aspect=1.15, grid=0.8):
    """Build one spur gear about local Z, centred on the origin, teeth at angle 0.

    Lengths are in modules except M itself. Returns a GearMesh.
    """
    prof = tooth_profile(N, M, backlash=backlash, flank_segs=flank_segs, fillet_segs=fillet_segs)
    side, cr, phi_c = prof["side"], prof["centre_r"], prof["phi_c"]
    rf, ra = prof["rf"], prof["ra"]
    T = thickness * M
    r_rim = rf - min(rim, 0.09 * N) * M
    r_hub = (hub if hub is not None else max(2.0, 0.32 * N / 2)) * M
    r_bore = (bore if bore is not None else 0.6 * r_hub / M) * M
    P = 2 * math.pi / N
    R = len(side) - 1

    def spacing(s, c):
        return 2 * math.pi * s / c

    mb = MeshBuilder()

    def rot(x, y, a):
        ca, sa = math.cos(a), math.sin(a)
        return (x * ca - y * sa, x * sa + y * ca)

    def face(sg):
        z_rim = sg * T / 2
        z_web = sg * (T / 2 - recess * M)
        z_hub = sg * (T / 2 + boss * M)
        root, root_p, outline = [], [], []
        F = fillet_segs
        ang = [math.atan2(y, x) for (x, y) in side[:F + 1]]  # fillet foot .. flank start
        for j in range(N):
            th = j * P
            sp = [mb.v((*rot(x, y, th), z_rim)) for (x, y) in side]
            sm = [mb.v((*rot(x, -y, th), z_rim)) for (x, y) in side]
            for i in range(F, R):  # one column of quads up the involute flanks
                mb.quad(sm[i], sp[i], sp[i + 1], sm[i + 1])
            # the rim band meets the outline at both fillets and the tooth base
            root += sm[:F + 1] + sp[:F + 1][::-1]
            root_p += [th - a for a in ang] + [th + a for a in ang[::-1]]
            outline += sm + sp[::-1]

        def at(z):
            return lambda a, s: (s * math.cos(a), s * math.sin(a), z)

        cols = len(root) // N
        even = [j * P + (k - (cols - 1) / 2) * P / cols for j in range(N) for k in range(cols)]
        # first rim ring: even spacing nudged 10% toward the outline angles, so the
        # fillet columns open out without bunching; deeper rings are even
        rows = max(1, round((rf - r_rim) / spacing(r_rim, cols * N)))
        ring, p = root, root_p
        for k in range(1, rows + 1):
            pk = [0.1 * a + 0.9 * e for a, e in zip(root_p, even)] if k == 1 else even
            nxt = mb.ring(at(z_rim), pk, rf - (rf - r_rim) * k / rows)
            mb.bridge(ring, nxt)
            ring, p = nxt, pk
        if p is not even:
            p = even if rows > 1 else p
        if recess:
            step = mb.ring(at(z_web), p, r_rim)
            mb.bridge(ring, step)
            ring = step
        n0 = len(ring)
        # web: 6 columns per tooth -> 2:1 band -> 3 per tooth -> 3:1 band -> 1 per tooth.
        # Every band repeats within two teeth, so the gear looks identical after a
        # two-tooth turn and trains loop after a short, slow rotation.
        tg = grid * M
        avail = r_rim - r_hub
        band = min(1.3 * tg, 0.45 * avail)
        band3 = min(1.2 * tg, 0.4 * avail)
        ring, p = mb.reduce_2to1(ring, p, at(z_web), r_rim - band / 2, r_rim - band)
        r0 = r_rim - band
        r_split = 0.65 * tg * len(ring) / (2 * math.pi)  # where 3 cols/tooth get too tight
        r_split = min(r0, max(r_hub + band3, r_split))
        if r0 - r_split < 0.5 * tg:
            r_split = r0
        else:
            ring, p = build_annulus(mb, ring, p, at(z_web), r0, r_split, spacing, target=tg,
                                    aspect=web_aspect, reduce=False)
        if r_split - band3 - r_hub < 0.5 * tg:
            band3 = r_split - r_hub
        ring, p = mb.reduce_3to1(ring, p, at(z_web), r_split - band3 / 2, r_split - band3)
        if r_split - band3 > r_hub + 1e-9:
            ring, p = build_annulus(mb, ring, p, at(z_web), r_split - band3, r_hub, spacing,
                                    target=tg, aspect=web_aspect, reduce=False)
        if boss != -recess:
            step = mb.ring(at(z_hub), p, r_hub)
            mb.bridge(ring, step)
            ring = step
        ring, p = build_annulus(mb, ring, p, at(z_hub), r_hub, r_bore, spacing, min_cols=len(ring),
                                target=grid * M, reduce=False)
        return outline, ring, n0

    of, bf, n0 = face(+1)
    ob, bb, _ = face(-1)
    segs = wall_segs if wall_segs is not None else max(2, round(T / (1.2 * M)))
    mb.bridge_loops(of, ob, segs - 1)
    bore_len = T + 2 * boss * M
    mb.bridge_loops(bf, bb, max(1, round(bore_len / (1.1 * M))) - 1)

    # rotational symmetry: the 2:1 band repeats every 4 of 6 columns per tooth (2/3 tooth),
    # combined with the N teeth that is every two teeth
    sym = N // 2 if N % 2 == 0 else 1
    obj = mb.to_object(name)
    outline2d = []
    for j in range(N):
        th = j * P
        pts = [rot(x, -y, th) for (x, y) in side]
        pts += [rot(x, y, th) for (x, y) in side[::-1]]
        outline2d += pts
    return GearMesh(obj, N, M, outline2d, sym, prof)


_AXES = {
    "X": Matrix(((0, 0, 1), (1, 0, 0), (0, 1, 0))),  # local x->Y, y->Z, z->X
    "Y": Matrix(((0, 1, 0), (0, 0, 1), (1, 0, 0))),  # local x->Z, y->X, z->Y
    "Z": Matrix.Identity(3),
}


class Train:
    """Meshing gear train in one plane, with compound gears stacked along the axis.

    `add` places a gear: either free at plane coordinates `at`, meshed with another gear at
    direction `angle` (degrees, in the plane) or on the same shaft as another gear
    (`shaft=`, a compound gear: same body, offset `layer` along the axis).
    The loop rotation is the smallest driver rotation after which every gear shows an
    identical image (each body turns a whole number of its gears' mesh symmetry periods),
    times `cycles`.
    """

    def __init__(self, module=1.0, axis="X", cycles=1):
        self.M = module
        self.axis = _AXES[axis]
        self.cycles = cycles
        self.gears = []  # dicts: mesh, body, centre, layer, partner
        self.bodies = []  # dicts: centre, ratio (Fraction, signed), phase
        TRAINS.append(self)

    def add(self, name, N, at=None, mesh=None, angle=0.0, shaft=None, layer=None, **kw):
        g = gear(name, N, self.M, **kw)
        if shaft is not None:
            body = shaft["body"]
            centre = shaft["centre"]
            lay = layer if layer is not None else shaft["layer"]
        elif mesh is not None:
            a = math.radians(angle)
            d = mesh["mesh"].rp + g.rp
            centre = (mesh["centre"][0] + d * math.cos(a), mesh["centre"][1] + d * math.sin(a))
            lay = mesh["layer"]
            pb = self.bodies[mesh["body"]]
            ratio = -pb["ratio"] * Fraction(mesh["mesh"].N, N)
            phi = a
            th_a = pb["phase"]
            f_a = (phi - th_a) * mesh["mesh"].N / (2 * math.pi)
            phase = phi + math.pi - (2 * math.pi / N) * (0.5 - f_a)
            self.bodies.append(dict(centre=centre, ratio=ratio, phase=phase))
            body = len(self.bodies) - 1
        else:
            centre = tuple(at or (0.0, 0.0))
            lay = layer or 0.0
            self.bodies.append(dict(centre=centre, ratio=Fraction(1), phase=0.0))
            body = len(self.bodies) - 1
        rec = dict(mesh=g, body=body, centre=centre, layer=lay, partner=mesh, name=name)
        self.gears.append(rec)
        return rec

    @property
    def objects(self):
        return [g["mesh"].obj for g in self.gears]

    def loop_turns(self):
        """Driver rotation per loop, in turns (Fraction)."""
        x = Fraction(0)
        for g in self.gears:
            r = abs(self.bodies[g["body"]]["ratio"])
            unit = 1 / (r * g["mesh"].sym)
            x = unit if x == 0 else Fraction(math.lcm(x.numerator, unit.numerator),
                                             math.gcd(x.denominator, unit.denominator))
        return x * self.cycles

    def body_angle(self, b, t):
        body = self.bodies[b]
        return body["phase"] + float(body["ratio"] * self.loop_turns()) * 2 * math.pi * t

    def plane_matrix(self, centre, layer, angle):
        m3 = self.axis
        pos = m3 @ Vector((centre[0], centre[1], layer))
        return Matrix.Translation(pos) @ m3.to_4x4() @ Matrix.Rotation(angle, 4, "Z")

    def pose(self, t):
        for g in self.gears:
            g["mesh"].obj.matrix_basis = self.plane_matrix(
                g["centre"], g["layer"], self.body_angle(g["body"], t))

    def report(self):
        turns = self.loop_turns()
        rows = []
        for g in self.gears:
            b = self.bodies[g["body"]]
            body_turns = b["ratio"] * turns
            rows.append(dict(name=g["name"], N=g["mesh"].N, sym=g["mesh"].sym,
                             ratio=str(b["ratio"]), turns=str(body_turns),
                             teeth_passed=float(abs(body_turns) * g["mesh"].N),
                             mesh_with=g["partner"]["name"] if g["partner"] else None,
                             layer=g["layer"]))
        return dict(driver_turns=str(turns), gears=rows)

    def outline_at(self, g, t):
        a = self.body_angle(g["body"], t)
        ca, sa = math.cos(a), math.sin(a)
        cx, cy = g["centre"]
        return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for (x, y) in g["mesh"].outline]
