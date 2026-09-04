from __future__ import annotations

import math
import struct
from collections import Counter, deque
from pathlib import Path


SAMPLES = 256
FLANGE_THICKNESS_MM = 2.4

# z is the print coordinate. In assembly, depth = z - FLANGE_THICKNESS_MM.
# Each row is: z, core width, core height, corner chamfer, crush-rib protrusion.
PROFILES = [
    (2.4, 15.80, 9.45, 0.30, 0.08),
    (8.4, 13.00, 9.43, 0.25, 0.14),
    (13.7, 10.53, 9.40, 0.20, 0.13),
    (14.4, 9.95, 9.15, 0.35, 0.00),
]
RIB_WIDTH_MM = 0.70


def rounded_rect(x0: float, y0: float, x1: float, y1: float, radius: float, arc_steps: int = 12):
    corners = [
        (x0 + radius, y0 + radius, math.pi, 1.5 * math.pi),
        (x1 - radius, y0 + radius, 1.5 * math.pi, 2.0 * math.pi),
        (x1 - radius, y1 - radius, 0.0, 0.5 * math.pi),
        (x0 + radius, y1 - radius, 0.5 * math.pi, math.pi),
    ]
    points = []
    for cx, cy, a0, a1 in corners:
        for i in range(arc_steps):
            a = a0 + (a1 - a0) * i / arc_steps
            points.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
    return points


def chamfered_rect(width: float, height: float, chamfer: float):
    w = width / 2.0
    h = height / 2.0
    c = min(chamfer, width / 4.0, height / 4.0)
    return [
        (-w + c, -h),
        (w - c, -h),
        (w, -h + c),
        (w, h - c),
        (w - c, h),
        (-w + c, h),
        (-w, h - c),
        (-w, -h + c),
    ]


def rectangle(x0: float, y0: float, x1: float, y1: float):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def cross2(a, b):
    return a[0] * b[1] - a[1] * b[0]


def ray_farthest_intersection(direction, polygons):
    best = None
    for polygon in polygons:
        for i, a in enumerate(polygon):
            b = polygon[(i + 1) % len(polygon)]
            edge = (b[0] - a[0], b[1] - a[1])
            denominator = cross2(direction, edge)
            if abs(denominator) < 1e-12:
                continue
            t = cross2(a, edge) / denominator
            u = cross2(a, direction) / denominator
            if t >= -1e-9 and -1e-9 <= u <= 1.0 + 1e-9:
                best = t if best is None else max(best, t)
    if best is None:
        raise RuntimeError(f"Ray missed all polygons: {direction}")
    return best


def radial_ring(polygons):
    ring = []
    for i in range(SAMPLES):
        angle = 2.0 * math.pi * i / SAMPLES
        direction = (math.cos(angle), math.sin(angle))
        radius = ray_farthest_intersection(direction, polygons)
        ring.append((radius * direction[0], radius * direction[1]))
    return ring


def profile_components(width, height, chamfer, rib):
    components = [chamfered_rect(width, height, chamfer)]
    if rib > 0.0:
        half_rw = RIB_WIDTH_MM / 2.0
        half_w = width / 2.0
        half_h = height / 2.0
        components.extend(
            [
                rectangle(half_w, -half_rw, half_w + rib, half_rw),
                rectangle(-half_w - rib, -half_rw, -half_w, half_rw),
                rectangle(-half_rw, half_h, half_rw, half_h + rib),
                rectangle(-half_rw, -half_h - rib, half_rw, -half_h),
            ]
        )
    return components


def add_ring(vertices, ring, z):
    start = len(vertices)
    vertices.extend((x, y, z) for x, y in ring)
    return list(range(start, start + len(ring)))


def build_mesh():
    flange_components = [
        rounded_rect(-12.0, -8.0, 12.0, 8.0, 1.5),
        rounded_rect(-4.0, 7.0, 4.0, 16.0, 1.1),
    ]
    flange_ring = radial_ring(flange_components)
    profile_rings = [
        radial_ring(profile_components(width, height, chamfer, rib))
        for _, width, height, chamfer, rib in PROFILES
    ]

    vertices = []
    faces = []
    bottom_center = len(vertices)
    vertices.append((0.0, 0.0, 0.0))
    outer_bottom = add_ring(vertices, flange_ring, 0.0)
    outer_top = add_ring(vertices, flange_ring, FLANGE_THICKNESS_MM)
    profile_indices = [
        add_ring(vertices, ring, profile[0])
        for ring, profile in zip(profile_rings, PROFILES)
    ]
    tip_center = len(vertices)
    vertices.append((0.0, 0.0, PROFILES[-1][0]))

    n = SAMPLES
    for i in range(n):
        j = (i + 1) % n
        # Bottom face, normal toward -Z.
        faces.append((bottom_center, outer_bottom[j], outer_bottom[i]))
        # Flange outer wall.
        faces.append((outer_bottom[i], outer_bottom[j], outer_top[j]))
        faces.append((outer_bottom[i], outer_top[j], outer_top[i]))
        # Flange top annulus around the tongue.
        inner = profile_indices[0]
        faces.append((outer_top[i], outer_top[j], inner[j]))
        faces.append((outer_top[i], inner[j], inner[i]))

    # Loft the four tongue profiles.
    for lower, upper in zip(profile_indices[:-1], profile_indices[1:]):
        for i in range(n):
            j = (i + 1) % n
            faces.append((lower[i], lower[j], upper[j]))
            faces.append((lower[i], upper[j], upper[i]))

    # Tip cap, normal toward +Z.
    tip = profile_indices[-1]
    for i in range(n):
        j = (i + 1) % n
        faces.append((tip_center, tip[i], tip[j]))

    if signed_volume(vertices, faces) < 0.0:
        faces = [(a, c, b) for a, b, c in faces]
    return vertices, faces


def signed_volume(vertices, faces):
    volume6 = 0.0
    for ia, ib, ic in faces:
        a, b, c = vertices[ia], vertices[ib], vertices[ic]
        cross_bc = (
            b[1] * c[2] - b[2] * c[1],
            b[2] * c[0] - b[0] * c[2],
            b[0] * c[1] - b[1] * c[0],
        )
        volume6 += a[0] * cross_bc[0] + a[1] * cross_bc[1] + a[2] * cross_bc[2]
    return volume6 / 6.0


def triangle_normal(a, b, c):
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    normal = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    length = math.sqrt(sum(v * v for v in normal))
    if length < 1e-12:
        raise RuntimeError("Degenerate triangle")
    return tuple(v / length for v in normal)


def validate(vertices, faces):
    edges = Counter()
    adjacency = [[] for _ in faces]
    edge_owner = {}
    for face_index, (a, b, c) in enumerate(faces):
        triangle_normal(vertices[a], vertices[b], vertices[c])
        for u, v in ((a, b), (b, c), (c, a)):
            edge = tuple(sorted((u, v)))
            edges[edge] += 1
            if edge in edge_owner:
                other = edge_owner[edge]
                adjacency[face_index].append(other)
                adjacency[other].append(face_index)
            else:
                edge_owner[edge] = face_index
    bad_edges = [edge for edge, count in edges.items() if count != 2]
    if bad_edges:
        raise RuntimeError(f"Mesh is not watertight; {len(bad_edges)} edges do not have incidence 2")

    seen = {0}
    queue = deque([0])
    while queue:
        face = queue.popleft()
        for neighbor in adjacency[face]:
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    if len(seen) != len(faces):
        raise RuntimeError("Mesh has more than one connected component")

    volume = signed_volume(vertices, faces)
    if volume <= 0.0:
        raise RuntimeError(f"Mesh orientation or volume invalid: {volume}")
    return volume


def write_binary_stl(path: Path, vertices, faces):
    path.parent.mkdir(parents=True, exist_ok=True)
    header = b"Adjusted P10 v2.1; units=mm; nominal assembled opening H=9.65 mm"
    header = header[:80].ljust(80, b" ")
    with path.open("wb") as stream:
        stream.write(header)
        stream.write(struct.pack("<I", len(faces)))
        for ia, ib, ic in faces:
            a, b, c = vertices[ia], vertices[ib], vertices[ic]
            normal = triangle_normal(a, b, c)
            stream.write(struct.pack("<12fH", *(normal + a + b + c), 0))


def main():
    package_root = Path(__file__).resolve().parent.parent
    output = package_root / "STL" / "P10_adjusted_v2_1_nominal_H9p65.stl"
    vertices, faces = build_mesh()
    volume = validate(vertices, faces)
    write_binary_stl(output, vertices, faces)
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    print(f"Wrote: {output}")
    print(f"Vertices: {len(vertices)}")
    print(f"Triangles: {len(faces)}")
    print("Watertight: True")
    print("Connected components: 1")
    print(f"Positive enclosed volume: {volume:.3f} mm^3")
    print(
        "Bounds: "
        f"X {min(xs):.3f}..{max(xs):.3f}, "
        f"Y {min(ys):.3f}..{max(ys):.3f}, "
        f"Z {min(zs):.3f}..{max(zs):.3f} mm"
    )


if __name__ == "__main__":
    main()
