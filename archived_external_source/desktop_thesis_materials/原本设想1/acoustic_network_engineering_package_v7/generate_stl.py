import json
import math
import shutil
import sys
import zipfile
from pathlib import Path

LOCAL_PYDEPS = Path(__file__).resolve().parent.parent / "pydeps"
if LOCAL_PYDEPS.exists():
    sys.path.insert(0, str(LOCAL_PYDEPS))

import numpy as np
import trimesh
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union


VERSION = "V7"
PACKAGE_NAME = "acoustic_network_engineering_package_v7"

# Regenerate the package in the directory containing this script. This makes the
# workflow portable between the original /mnt/data environment and Windows.
OUT = Path(__file__).resolve().parent
MODELS = OUT / "models"

W = 160.0
H = 140.0
BOTTOM_THICKNESS = 2.0
WALL_HEIGHT = 5.0
BASE_TOTAL_HEIGHT = BOTTOM_THICKNESS + WALL_HEIGHT
COVER_THICKNESS = 2.5

MAIN_CHANNEL_NOMINAL = 4.0
MAIN_CHANNEL_WIDTH = 4.4
BRIDGE_CHANNEL_NOMINAL = 2.0
BRIDGE_CHANNEL_WIDTH = 2.2
MIC_PORT_NOMINAL = 4.0
MIC_PORT_WIDTH = 4.4

SCREW_DIAM = 3.2
SCREW_R = SCREW_DIAM / 2.0

# Compact output junction. V6 used radius 16 mm; V7 intentionally reduces this
# to limit baseline terminal coupling in S0.
CHAMBER_C = (145.0, 60.0)
CHAMBER_R = 8.0
NECK_LENGTH = 6.0
NECK_OVERLAP = 1.0
NECK_WIDTH = MAIN_CHANNEL_WIDTH

# Each duct remains a single non-self-intersecting serpentine:
# right -> down -> left -> down -> right -> approach -> short neck -> chamber.
# The final chamber connection is determined by an entry angle around the compact
# chamber, not by a direct cut into a large common cavity.
LANES = {
    "A": {"ys": (104.0, 97.0, 90.0), "xR": 110.0, "xL": 42.0, "xOut": 124.0, "entry_angle_deg": 105.0},
    "B": {"ys": (82.0, 75.0, 68.0), "xR": 116.0, "xL": 40.0, "xOut": 125.0, "entry_angle_deg": 150.0},
    "C": {"ys": (60.0, 53.0, 46.0), "xR": 116.0, "xL": 40.0, "xOut": 125.0, "entry_angle_deg": 210.0},
    "D": {"ys": (38.0, 31.0, 24.0), "xR": 110.0, "xL": 42.0, "xOut": 124.0, "entry_angle_deg": 255.0},
}

SCREW_HOLES = [
    (12, 10),
    (46, 10),
    (80, 10),
    (114, 10),
    (148, 10),
    (12, 130),
    (46, 130),
    (80, 130),
    (114, 130),
    (148, 130),
]

# Bridges connect a late/final segment of one duct to an early/first segment of
# the next duct. This preserves the V6 chain topology and avoids DA closure.
BRIDGES = {
    "AB": {"from": "A", "to": "B", "x": 80.0, "from_pass": "final", "to_pass": "first"},
    "BC": {"from": "B", "to": "C", "x": 80.0, "from_pass": "final", "to_pass": "first"},
    "CD": {"from": "C", "to": "D", "x": 80.0, "from_pass": "final", "to_pass": "first"},
}

STATES = {
    "S0_no_bridges": [],
    "S1_AB": ["AB"],
    "S2_AB_CD": ["AB", "CD"],
    "Smax_chain_AB_BC_CD": ["AB", "BC", "CD"],
}


def ensure_dirs():
    if MODELS.exists():
        shutil.rmtree(MODELS)
    MODELS.mkdir(parents=True, exist_ok=True)


def polar_point(radius, angle_deg):
    angle = math.radians(angle_deg)
    return (
        CHAMBER_C[0] + radius * math.cos(angle),
        CHAMBER_C[1] + radius * math.sin(angle),
    )


def neck_points(lane):
    angle = LANES[lane]["entry_angle_deg"]
    boundary = polar_point(CHAMBER_R, angle)
    start = polar_point(CHAMBER_R + NECK_LENGTH, angle)
    inside = polar_point(CHAMBER_R - NECK_OVERLAP, angle)
    return {"start": start, "boundary": boundary, "inside": inside, "angle_deg": angle}


def path_points(lane):
    p = LANES[lane]
    y0, y1, y2 = p["ys"]
    xR = p["xR"]
    xL = p["xL"]
    xOut = p["xOut"]
    neck = neck_points(lane)
    return [
        (0, y0),
        (xR, y0),
        (xR, y1),
        (xL, y1),
        (xL, y2),
        (xOut, y2),
        neck["start"],
        neck["inside"],
    ]


def path_length(pts):
    return sum(math.hypot(x1 - x0, y1 - y0) for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]))


def chamber_volume_mm3():
    # Estimate for the compact circular chamber only, excluding neck and mic-port overlap.
    return math.pi * CHAMBER_R * CHAMBER_R * WALL_HEIGHT


def point_on_pass(lane, pass_name, x):
    y0, y1, y2 = LANES[lane]["ys"]
    if pass_name == "first":
        return (x, y0)
    if pass_name == "return":
        return (x, y1)
    if pass_name == "final":
        return (x, y2)
    raise ValueError(pass_name)


def buffered_line(points, width, cap_style=2, resolution=20):
    return LineString(points).buffer(width / 2.0, cap_style=cap_style, join_style=1, resolution=resolution)


def chamber_shape():
    return Point(*CHAMBER_C).buffer(CHAMBER_R, resolution=96)


def mic_port_shape():
    return buffered_line([CHAMBER_C, (W, CHAMBER_C[1])], MIC_PORT_WIDTH, cap_style=2, resolution=24)


def channel_shapes(open_bridges):
    regions = []
    for lane in LANES:
        regions.append(buffered_line(path_points(lane), MAIN_CHANNEL_WIDTH, cap_style=2, resolution=24))

    regions.append(chamber_shape())
    regions.append(mic_port_shape())

    for bridge_name in open_bridges:
        info = BRIDGES[bridge_name]
        p0 = point_on_pass(info["from"], info["from_pass"], info["x"])
        p1 = point_on_pass(info["to"], info["to_pass"], info["x"])
        regions.append(buffered_line([p0, p1], BRIDGE_CHANNEL_WIDTH, cap_style=1, resolution=24))

    return unary_union(regions).intersection(box(0, 0, W, H)).buffer(0)


def bridge_shapes(open_bridges):
    regs = []
    for bridge_name in open_bridges:
        info = BRIDGES[bridge_name]
        p0 = point_on_pass(info["from"], info["from_pass"], info["x"])
        p1 = point_on_pass(info["to"], info["to_pass"], info["x"])
        regs.append(buffered_line([p0, p1], BRIDGE_CHANNEL_WIDTH, cap_style=1, resolution=24))
    return unary_union(regs) if regs else Polygon()


def screw_poly():
    return unary_union([Point(x, y).buffer(SCREW_R, resolution=24) for x, y in SCREW_HOLES])


def extrude_geom_trimesh(g, height):
    if g.is_empty:
        return trimesh.Trimesh(vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=int), process=False)
    if isinstance(g, MultiPolygon):
        meshes = [extrude_geom_trimesh(poly, height) for poly in g.geoms if poly.area > 1e-6]
        if meshes:
            return trimesh.util.concatenate(meshes)
        return trimesh.Trimesh(vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=int), process=False)
    return trimesh.creation.extrude_polygon(g.buffer(0), height=height)


def make_base_mesh(open_bridges):
    rect = box(0, 0, W, H)
    screw = screw_poly()
    ch = channel_shapes(open_bridges).difference(screw).buffer(0)
    bottom = rect.difference(screw).buffer(0)
    walls = rect.difference(unary_union([ch, screw])).buffer(0)

    bottom_mesh = extrude_geom_trimesh(bottom, BOTTOM_THICKNESS)
    wall_mesh = extrude_geom_trimesh(walls, WALL_HEIGHT)
    wall_mesh.apply_translation([0, 0, BOTTOM_THICKNESS])

    mesh = trimesh.util.concatenate([bottom_mesh, wall_mesh])
    trimesh.repair.fix_normals(mesh)
    return mesh


def make_cover_mesh():
    region = box(0, 0, W, H).difference(screw_poly()).buffer(0)
    mesh = extrude_geom_trimesh(region, COVER_THICKNESS)
    trimesh.repair.fix_normals(mesh)
    return mesh


def make_tube_adapter_test():
    meshes = []
    meshes.append(
        trimesh.creation.box(
            extents=[70, 14, 3],
            transform=trimesh.transformations.translation_matrix([35, 7, 1.5]),
        )
    )
    xs = [14, 35, 56]
    radii = [2.05, 2.10, 2.15]
    for x, r in zip(xs, radii):
        cyl = trimesh.creation.cylinder(radius=r, height=16, sections=64)
        cyl.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [0, 1, 0]))
        cyl.apply_transform(trimesh.transformations.translation_matrix([x, 17, 7]))
        meshes.append(cyl)
    return trimesh.util.concatenate(meshes)


def export_mesh(mesh, path):
    mesh.export(str(path))
    return {
        "file": path.name,
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
        "bounds": np.round(mesh.bounds, 3).tolist(),
    }


def poly_to_path(poly, scale=5, yflip=True):
    def one(p):
        coords = list(p.exterior.coords)
        if not coords:
            return ""
        parts = []
        for i, (x, y) in enumerate(coords):
            yy = H - y if yflip else y
            parts.append(("M" if i == 0 else "L") + f"{x * scale:.2f},{yy * scale:.2f}")
        parts.append("Z")
        return " ".join(parts)

    if poly.is_empty:
        return ""
    if isinstance(poly, MultiPolygon):
        return " ".join(one(g) for g in poly.geoms)
    return one(poly)


def centerline_svg(scale=5):
    colors = {"A": "#1f77ff", "B": "#1ca34a", "C": "#b000ff", "D": "#d99a00"}
    lines = []
    for lane in LANES:
        pts = path_points(lane)
        s = " ".join(f"{x * scale:.2f},{(H - y) * scale:.2f}" for x, y in pts)
        lines.append(
            f'<polyline points="{s}" fill="none" stroke="{colors[lane]}" '
            f'stroke-width="2" opacity="0.9"/>'
        )
        x0, y0 = pts[0]
        lines.append(f'<text x="{(x0 + 2) * scale:.2f}" y="{(H - y0 - 3) * scale:.2f}" font-size="14" fill="{colors[lane]}">{lane}</text>')
    return "\n".join(lines)


def screw_svg(scale=5):
    return "\n".join(
        [
            f'<circle cx="{x * scale:.2f}" cy="{(H - y) * scale:.2f}" r="{SCREW_R * scale:.2f}" '
            f'fill="#111" opacity="0.35" />'
            for x, y in SCREW_HOLES
        ]
    )


def neck_svg(scale=5):
    rows = []
    for lane in LANES:
        pts = neck_points(lane)
        x0, y0 = pts["start"]
        x1, y1 = pts["boundary"]
        rows.append(
            f'<line x1="{x0 * scale:.2f}" y1="{(H - y0) * scale:.2f}" '
            f'x2="{x1 * scale:.2f}" y2="{(H - y1) * scale:.2f}" '
            f'stroke="#111" stroke-width="1.4" stroke-dasharray="4 3" opacity="0.7"/>'
        )
    return "\n".join(rows)


def model_data():
    files = {
        "S0_no_bridges": "core_base_S0_no_bridges.stl",
        "S1_AB": "core_base_S1_AB.stl",
        "S2_AB_CD": "core_base_S2_AB_CD.stl",
        "Smax_chain_AB_BC_CD": "core_base_Smax_chain_AB_BC_CD.stl",
        "cover": "core_cover_common.stl",
        "adapter": "tube_adapter_gauge.stl",
    }
    lanes = {}
    for lane in LANES:
        pts = path_points(lane)
        neck = neck_points(lane)
        lanes[lane] = {
            "label": lane,
            "duct_points": pts[:-1],
            "centerline_points": pts,
            "neck_points": [neck["start"], neck["inside"]],
            "neck_boundary": neck["boundary"],
            "length_mm": round(path_length(pts), 3),
            "color": {
                "A": "#1f77ff",
                "B": "#1ca34a",
                "C": "#b000ff",
                "D": "#d99a00",
            }[lane],
        }
    bridges = {}
    for name, info in BRIDGES.items():
        p0 = point_on_pass(info["from"], info["from_pass"], info["x"])
        p1 = point_on_pass(info["to"], info["to_pass"], info["x"])
        bridges[name] = {**info, "p0": p0, "p1": p1, "length_mm": round(math.hypot(p1[0] - p0[0], p1[1] - p0[1]), 3)}
    return {
        "version": VERSION,
        "meta": {
            "base": [W, H, BASE_TOTAL_HEIGHT],
            "cover": [W, H, COVER_THICKNESS],
            "mainChannelWidth": MAIN_CHANNEL_WIDTH,
            "bridgeChannelWidth": BRIDGE_CHANNEL_WIDTH,
            "micPortWidth": MIC_PORT_WIDTH,
            "chamberCenter": CHAMBER_C,
            "chamberRadius": CHAMBER_R,
            "chamberEstimatedVolumeMm3": round(chamber_volume_mm3(), 1),
            "neckLength": NECK_LENGTH,
            "scale": 5,
            "screwRadius": SCREW_R,
        },
        "states": STATES,
        "stateNames": list(STATES.keys()),
        "lanes": lanes,
        "bridges": bridges,
        "screwHoles": SCREW_HOLES,
        "micPort": {"from": CHAMBER_C, "to": [W, CHAMBER_C[1]], "width_mm": MIC_PORT_WIDTH},
        "files": files,
    }


def write_index():
    state_options = "".join([f'<option value="{s}">{s}</option>' for s in STATES])
    index = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{VERSION} Four-Port Acoustic Network Viewer</title>
  <style>
    :root {{
      --ink: #111827;
      --muted: #4b5563;
      --panel: #ffffff;
      --line: #d1d5db;
      --blue: #2563eb;
      --bg: #eef3fa;
      --soft: #f8fafc;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, "Microsoft YaHei", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }}
    #layout {{ display: flex; height: 100vh; min-height: 620px; }}
    #side {{
      width: 400px;
      background: var(--panel);
      border-right: 1px solid var(--line);
      padding: 18px;
      overflow: auto;
    }}
    #main {{
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: auto;
      padding: 18px;
    }}
    h1 {{ font-size: 20px; line-height: 1.2; margin: 0 0 10px; }}
    h2 {{ font-size: 13px; margin: 18px 0 8px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); }}
    p, .small {{ font-size: 12px; line-height: 1.5; color: var(--muted); }}
    select, button {{
      width: 100%;
      padding: 10px;
      border-radius: 8px;
      border: 1px solid #b8c0cc;
      margin: 7px 0;
      font-size: 14px;
      background: #fff;
    }}
    button {{ cursor: pointer; }}
    button.primary {{ background: var(--blue); color: white; border-color: var(--blue); }}
    .mode-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 8px 0; }}
    .mode-row button {{ margin: 0; }}
    .mode-row button.active {{ background: #111827; color: white; border-color: #111827; }}
    label {{ display: flex; gap: 8px; align-items: center; font-size: 13px; margin: 9px 0; color: var(--ink); }}
    #view2d, #view3d {{
      width: min(100%, 980px);
    }}
    svg, canvas {{
      width: min(100%, 980px);
      height: auto;
      background: #f8fbff;
      border: 1px solid #c8d2e2;
      box-shadow: 0 2px 12px #0001;
    }}
    canvas {{ aspect-ratio: 4 / 3; background: #f8fbff; display: block; }}
    pre {{
      white-space: pre-wrap;
      background: var(--soft);
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 10px;
    }}
    .hidden {{ display: none !important; }}
    .hint {{ font-size: 12px; color: var(--muted); line-height: 1.45; margin-top: 8px; }}
  </style>
</head>
<body>
  <div id="layout">
    <aside id="side">
      <h1>{VERSION} acoustic network</h1>
      <p>Four input ports, one microphone output, compact junction radius {CHAMBER_R:g} mm. Bridge states preserve the V6 AB/BC/CD chain without a DA bridge.</p>
      <h2>Base state</h2>
      <select id="state">{state_options}</select>
      <button class="primary" id="dlbase">Download selected base STL</button>
      <button id="dlcover">Download common cover STL</button>
      <button id="dladapter">Download tube adapter gauge STL</button>
      <h2>View mode</h2>
      <div class="mode-row">
        <button id="modeTop" class="active" type="button">Top view</button>
        <button id="mode3d" type="button">3D STL</button>
      </div>
      <h2>Layers</h2>
      <label><input type="checkbox" id="showMain" checked> Show main channel footprints</label>
      <label><input type="checkbox" id="showActiveBridges" checked> Show active bridge slots</label>
      <label><input type="checkbox" id="showCandidateBridges"> Show all candidate bridges</label>
      <label><input type="checkbox" id="showCenterlines" checked> Show centerlines</label>
      <label><input type="checkbox" id="showChamber" checked> Show mixing chamber</label>
      <label><input type="checkbox" id="showScrews" checked> Show screw holes</label>
      <label><input type="checkbox" id="show3dPreview"> Show STL/3D preview</label>
      <h2>State info</h2>
      <pre id="info" class="small"></pre>
    </aside>
    <main id="main">
      <div id="view2d">
        <svg id="topSvg" width="900" height="800" viewBox="-20 -20 {W * 5 + 40:.0f} {H * 5 + 40:.0f}" xmlns="http://www.w3.org/2000/svg">
          <g id="gBase"></g>
          <g id="gMain"></g>
          <g id="gCandidateBridges"></g>
          <g id="gActiveBridges"></g>
          <g id="gChamber"></g>
          <g id="gCenterlines"></g>
          <g id="gLabels"></g>
        </svg>
      </div>
      <div id="view3d" class="hidden">
        <canvas id="stlCanvas" width="960" height="720"></canvas>
        <div id="stlStatus" class="hint"></div>
      </div>
    </main>
  </div>
  <script src="model_data.js"></script>
  <script src="viewer.js"></script>
</body>
</html>
"""
    (OUT / "index.html").write_text(index, encoding="utf-8")


def write_viewer_files():
    data = model_data()
    (OUT / "model_data.js").write_text(
        "window.V7_MODEL_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    viewer = """const DATA = window.V7_MODEL_DATA;
const SVG_NS = "http://www.w3.org/2000/svg";

const stateSelect = document.getElementById("state");
const info = document.getElementById("info");
const topSvg = document.getElementById("topSvg");
const view2d = document.getElementById("view2d");
const view3d = document.getElementById("view3d");
const stlCanvas = document.getElementById("stlCanvas");
const stlStatus = document.getElementById("stlStatus");
const modeTop = document.getElementById("modeTop");
const mode3d = document.getElementById("mode3d");

const controls = {
  showMain: document.getElementById("showMain"),
  showActiveBridges: document.getElementById("showActiveBridges"),
  showCandidateBridges: document.getElementById("showCandidateBridges"),
  showCenterlines: document.getElementById("showCenterlines"),
  showChamber: document.getElementById("showChamber"),
  showScrews: document.getElementById("showScrews"),
  show3dPreview: document.getElementById("show3dPreview"),
};

const groups = {
  base: document.getElementById("gBase"),
  main: document.getElementById("gMain"),
  candidates: document.getElementById("gCandidateBridges"),
  active: document.getElementById("gActiveBridges"),
  chamber: document.getElementById("gChamber"),
  centerlines: document.getElementById("gCenterlines"),
  labels: document.getElementById("gLabels"),
};

const meta = DATA.meta;
const scale = meta.scale || 5;
let activeMode = "top";
let stlModel = null;
let loadedStlFile = "";
let yaw = -0.55;
let pitch = 0.72;
let zoom = 1.0;
let dragStart = null;

function sx(x) {
  return x * scale;
}

function sy(y) {
  return (meta.base[1] - y) * scale;
}

function pointsAttr(points) {
  return points.map(([x, y]) => `${sx(x).toFixed(2)},${sy(y).toFixed(2)}`).join(" ");
}

function svgEl(tag, attrs = {}) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) {
    el.setAttribute(key, String(value));
  }
  return el;
}

function clearSvgLayers() {
  for (const group of Object.values(groups)) {
    group.innerHTML = "";
  }
}

function addLine(group, points, attrs) {
  const el = svgEl("polyline", {
    points: pointsAttr(points),
    fill: "none",
    ...attrs,
  });
  group.appendChild(el);
  return el;
}

function addText(group, text, x, y, attrs = {}) {
  const el = svgEl("text", {
    x: sx(x).toFixed(2),
    y: sy(y).toFixed(2),
    "font-size": 12,
    fill: "#111827",
    ...attrs,
  });
  el.textContent = text;
  group.appendChild(el);
  return el;
}

function drawBase() {
  groups.base.appendChild(svgEl("rect", {
    x: 0,
    y: 0,
    width: sx(meta.base[0]).toFixed(2),
    height: sx(meta.base[1]).toFixed(2),
    fill: "#dce9f9",
    stroke: "#111827",
    "stroke-width": 2,
  }));

  if (!controls.showScrews.checked) return;
  for (const [x, y] of DATA.screwHoles) {
    groups.base.appendChild(svgEl("circle", {
      cx: sx(x).toFixed(2),
      cy: sy(y).toFixed(2),
      r: sx(meta.screwRadius).toFixed(2),
      fill: "#6b7280",
      opacity: 0.62,
      stroke: "#374151",
      "stroke-width": 0.8,
    }));
  }
}

function drawMainDucts() {
  if (!controls.showMain.checked) return;
  for (const laneName of Object.keys(DATA.lanes)) {
    const lane = DATA.lanes[laneName];
    addLine(groups.main, lane.duct_points, {
      stroke: lane.color,
      "stroke-width": (meta.mainChannelWidth * scale).toFixed(2),
      "stroke-linecap": "round",
      "stroke-linejoin": "round",
      opacity: 0.33,
    });
  }
}

function drawBridgeLayer(stateName) {
  const active = DATA.states[stateName] || [];
  const activeSet = new Set(active);

  if (controls.showCandidateBridges.checked) {
    for (const [name, bridge] of Object.entries(DATA.bridges)) {
      if (activeSet.has(name)) continue;
      addLine(groups.candidates, [bridge.p0, bridge.p1], {
        stroke: "#6b7280",
        "stroke-width": (meta.bridgeChannelWidth * scale).toFixed(2),
        "stroke-linecap": "round",
        "stroke-dasharray": "7 6",
        opacity: 0.38,
      });
    }
  }

  if (!controls.showActiveBridges.checked) return;
  for (const name of active) {
    const bridge = DATA.bridges[name];
    addLine(groups.active, [bridge.p0, bridge.p1], {
      stroke: "#ef3b2d",
      "stroke-width": (meta.bridgeChannelWidth * scale).toFixed(2),
      "stroke-linecap": "round",
      opacity: 0.82,
    });
  }
}

function drawChamber() {
  if (!controls.showChamber.checked) return;
  const [cx, cy] = meta.chamberCenter;

  addLine(groups.chamber, [DATA.micPort.from, DATA.micPort.to], {
    stroke: "#67c7d4",
    "stroke-width": (meta.micPortWidth * scale).toFixed(2),
    "stroke-linecap": "butt",
    opacity: 0.42,
  });

  for (const laneName of Object.keys(DATA.lanes)) {
    const lane = DATA.lanes[laneName];
    addLine(groups.chamber, lane.neck_points, {
      stroke: lane.color,
      "stroke-width": (meta.mainChannelWidth * scale).toFixed(2),
      "stroke-linecap": "round",
      "stroke-linejoin": "round",
      opacity: 0.44,
    });
    addLine(groups.chamber, lane.neck_points, {
      stroke: "#111827",
      "stroke-width": 1.1,
      "stroke-dasharray": "4 4",
      opacity: 0.62,
    });
  }

  groups.chamber.appendChild(svgEl("circle", {
    cx: sx(cx).toFixed(2),
    cy: sy(cy).toFixed(2),
    r: sx(meta.chamberRadius).toFixed(2),
    fill: "#bfeff5",
    opacity: 0.48,
    stroke: "#111827",
    "stroke-width": 1.6,
    "stroke-dasharray": "6 4",
  }));
  addText(groups.chamber, "compact chamber", cx - 24, cy + 12, {
    "font-size": 11,
    fill: "#111827",
  });
}

function drawCenterlines(stateName) {
  if (!controls.showCenterlines.checked) return;
  for (const laneName of Object.keys(DATA.lanes)) {
    const lane = DATA.lanes[laneName];
    addLine(groups.centerlines, lane.centerline_points, {
      stroke: lane.color,
      "stroke-width": 2.0,
      "stroke-linecap": "round",
      "stroke-linejoin": "round",
      opacity: 0.95,
    });
    const [x, y] = lane.centerline_points[0];
    addText(groups.labels, laneName, x + 2, y + 5, {
      "font-size": 14,
      fill: lane.color,
      "font-weight": 700,
    });
  }

  const active = DATA.states[stateName] || [];
  for (const name of active) {
    const bridge = DATA.bridges[name];
    addLine(groups.centerlines, [bridge.p0, bridge.p1], {
      stroke: "#b91c1c",
      "stroke-width": 1.8,
      "stroke-linecap": "round",
      opacity: 0.98,
    });
    addText(
      groups.labels,
      name,
      (bridge.p0[0] + bridge.p1[0]) / 2 + 1.5,
      (bridge.p0[1] + bridge.p1[1]) / 2,
      { "font-size": 11, fill: "#b91c1c", "font-weight": 700 }
    );
  }
}

function updateInfo(stateName) {
  const active = DATA.states[stateName] || [];
  const baseFile = DATA.files[stateName];
  info.textContent = [
    `Current base state: ${stateName}`,
    `Active bridges: ${active.length ? active.join(", ") : "none"}`,
    `Current base STL: ${baseFile}`,
    `Current base downloadable: ${baseFile ? "yes" : "no"}`,
    `Common cover STL: ${DATA.files.cover}`,
    `Tube adapter STL: ${DATA.files.adapter}`,
    "",
    `Main slot width: ${meta.mainChannelWidth} mm`,
    `Bridge slot width: ${meta.bridgeChannelWidth} mm`,
    `Compact chamber radius: ${meta.chamberRadius} mm`,
    `Chamber estimated volume: ${meta.chamberEstimatedVolumeMm3} mm3`,
    `Nominal neck length: ${meta.neckLength} mm`,
  ].join("\\n");
}

function renderState(stateName) {
  clearSvgLayers();
  drawBase();
  drawMainDucts();
  drawBridgeLayer(stateName);
  drawChamber();
  drawCenterlines(stateName);
  updateInfo(stateName);
  if (activeMode === "3d" && controls.show3dPreview.checked) {
    loadCurrentStl();
  }
}

function setMode(mode) {
  activeMode = mode;
  const show3d = mode === "3d" && controls.show3dPreview.checked;
  view2d.classList.toggle("hidden", show3d);
  view3d.classList.toggle("hidden", !show3d);
  modeTop.classList.toggle("active", !show3d);
  mode3d.classList.toggle("active", show3d);
  if (show3d) loadCurrentStl();
}

function downloadFile(file) {
  const a = document.createElement("a");
  a.href = "models/" + file;
  a.download = file;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function parseStl(buffer) {
  const view = new DataView(buffer);
  const triangles = [];
  const triCount = buffer.byteLength >= 84 ? view.getUint32(80, true) : 0;
  const expectedBinaryLength = 84 + triCount * 50;
  const isBinary = triCount > 0 && expectedBinaryLength === buffer.byteLength;

  if (isBinary) {
    let offset = 84;
    for (let i = 0; i < triCount; i += 1) {
      const n = [view.getFloat32(offset, true), view.getFloat32(offset + 4, true), view.getFloat32(offset + 8, true)];
      offset += 12;
      const v = [];
      for (let j = 0; j < 3; j += 1) {
        v.push([view.getFloat32(offset, true), view.getFloat32(offset + 4, true), view.getFloat32(offset + 8, true)]);
        offset += 12;
      }
      triangles.push({ n, v });
      offset += 2;
    }
    return triangles;
  }

  const text = new TextDecoder().decode(buffer);
  const nums = [...text.matchAll(/vertex\\s+([-+0-9.eE]+)\\s+([-+0-9.eE]+)\\s+([-+0-9.eE]+)/g)].map((m) => [
    Number(m[1]),
    Number(m[2]),
    Number(m[3]),
  ]);
  for (let i = 0; i + 2 < nums.length; i += 3) {
    triangles.push({ n: [0, 0, 1], v: [nums[i], nums[i + 1], nums[i + 2]] });
  }
  return triangles;
}

function normalizeModel(triangles) {
  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];
  for (const tri of triangles) {
    for (const p of tri.v) {
      for (let i = 0; i < 3; i += 1) {
        min[i] = Math.min(min[i], p[i]);
        max[i] = Math.max(max[i], p[i]);
      }
    }
  }
  const center = min.map((v, i) => (v + max[i]) / 2);
  const span = Math.max(max[0] - min[0], max[1] - min[1], max[2] - min[2]) || 1;
  return triangles.map((tri) => ({
    v: tri.v.map((p) => [(p[0] - center[0]) / span, (p[1] - center[1]) / span, (p[2] - center[2]) / span]),
  }));
}

function rotatePoint(p) {
  const cy = Math.cos(yaw);
  const syaw = Math.sin(yaw);
  const cp = Math.cos(pitch);
  const sp = Math.sin(pitch);
  const x1 = p[0] * cy - p[1] * syaw;
  const y1 = p[0] * syaw + p[1] * cy;
  const z1 = p[2];
  return [x1, y1 * cp - z1 * sp, y1 * sp + z1 * cp];
}

function drawStl() {
  const ctx = stlCanvas.getContext("2d");
  const w = stlCanvas.width;
  const h = stlCanvas.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#f8fbff";
  ctx.fillRect(0, 0, w, h);

  if (!stlModel) return;
  const tris = stlModel.map((tri) => {
    const rv = tri.v.map(rotatePoint);
    const depth = (rv[0][2] + rv[1][2] + rv[2][2]) / 3;
    return { rv, depth };
  }).sort((a, b) => a.depth - b.depth);

  const light = [0.2, -0.4, 0.9];
  const size = Math.min(w, h) * 1.25 * zoom;
  for (const tri of tris) {
    const [a, b, c] = tri.rv;
    const ux = b[0] - a[0], uy = b[1] - a[1], uz = b[2] - a[2];
    const vx = c[0] - a[0], vy = c[1] - a[1], vz = c[2] - a[2];
    let nx = uy * vz - uz * vy;
    let ny = uz * vx - ux * vz;
    let nz = ux * vy - uy * vx;
    const nl = Math.hypot(nx, ny, nz) || 1;
    nx /= nl; ny /= nl; nz /= nl;
    const shade = Math.max(0.18, Math.min(0.92, nx * light[0] + ny * light[1] + nz * light[2]));
    const tone = Math.round(105 + shade * 105);

    ctx.beginPath();
    for (let i = 0; i < 3; i += 1) {
      const p = tri.rv[i];
      const persp = 1.8 / (2.3 - p[2]);
      const x = w / 2 + p[0] * size * persp;
      const y = h / 2 - p[1] * size * persp;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.fillStyle = `rgb(${tone}, ${tone + 6}, ${tone + 12})`;
    ctx.fill();
    ctx.strokeStyle = "rgba(17,24,39,0.12)";
    ctx.stroke();
  }
}

async function loadCurrentStl() {
  const file = DATA.files[stateSelect.value];
  if (loadedStlFile === file && stlModel) {
    drawStl();
    return;
  }
  loadedStlFile = file;
  stlModel = null;
  stlStatus.textContent = `Loading ${file}...`;
  try {
    const response = await fetch(`models/${file}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const buffer = await response.arrayBuffer();
    const triangles = parseStl(buffer);
    stlModel = normalizeModel(triangles);
    stlStatus.textContent = `${file}: ${triangles.length} triangles. Drag to rotate, wheel to zoom.`;
    drawStl();
  } catch (error) {
    stlStatus.textContent = `Could not load ${file} from this browser context. Open the folder through a local web server for automatic STL preview; downloads still work.`;
  }
}

stateSelect.addEventListener("change", () => renderState(stateSelect.value));
for (const control of Object.values(controls)) {
  control.addEventListener("change", () => {
    if (control === controls.show3dPreview) {
      setMode(control.checked ? "3d" : "top");
    }
    renderState(stateSelect.value);
  });
}

modeTop.addEventListener("click", () => {
  controls.show3dPreview.checked = false;
  setMode("top");
});
mode3d.addEventListener("click", () => {
  controls.show3dPreview.checked = true;
  setMode("3d");
});

document.getElementById("dlbase").addEventListener("click", () => downloadFile(DATA.files[stateSelect.value]));
document.getElementById("dlcover").addEventListener("click", () => downloadFile(DATA.files.cover));
document.getElementById("dladapter").addEventListener("click", () => downloadFile(DATA.files.adapter));

stlCanvas.addEventListener("pointerdown", (event) => {
  dragStart = { x: event.clientX, y: event.clientY, yaw, pitch };
  stlCanvas.setPointerCapture(event.pointerId);
});
stlCanvas.addEventListener("pointermove", (event) => {
  if (!dragStart) return;
  yaw = dragStart.yaw + (event.clientX - dragStart.x) * 0.01;
  pitch = Math.max(-1.4, Math.min(1.4, dragStart.pitch + (event.clientY - dragStart.y) * 0.01));
  drawStl();
});
stlCanvas.addEventListener("pointerup", () => {
  dragStart = null;
});
stlCanvas.addEventListener("wheel", (event) => {
  event.preventDefault();
  zoom = Math.max(0.55, Math.min(2.2, zoom * (event.deltaY > 0 ? 0.92 : 1.08)));
  drawStl();
});

setMode("top");
renderState(stateSelect.value);
"""
    (OUT / "viewer.js").write_text(viewer, encoding="utf-8")


def bridge_lengths():
    out = {}
    for name, info in BRIDGES.items():
        p0 = point_on_pass(info["from"], info["from_pass"], info["x"])
        p1 = point_on_pass(info["to"], info["to_pass"], info["x"])
        out[name] = round(math.hypot(p1[0] - p0[0], p1[1] - p0[1]), 2)
    return out


def write_docs(checks):
    lengths = {lane: round(path_length(path_points(lane)), 2) for lane in LANES}
    bridge_len = bridge_lengths()
    necks = {lane: neck_points(lane) for lane in LANES}
    expected_stls = [
        "core_base_S0_no_bridges.stl",
        "core_base_S1_AB.stl",
        "core_base_S2_AB_CD.stl",
        "core_base_Smax_chain_AB_BC_CD.stl",
        "core_cover_common.stl",
        "tube_adapter_gauge.stl",
    ]
    all_stls_exist = all((MODELS / name).exists() for name in expected_stls)
    bbox_limit = (180.0, 150.0, 35.0)
    bbox_ok = {}
    for name, result in checks.items():
        bounds = result["bounds"]
        span = [round(bounds[1][i] - bounds[0][i], 3) for i in range(3)]
        bbox_ok[name] = {"span_mm": span, "within_180x150x35": all(span[i] <= bbox_limit[i] for i in range(3))}
    length_range_ok = {lane: 290.0 <= length <= 310.0 for lane, length in lengths.items()}
    states_ok = {
        "S0_no_bridges": STATES["S0_no_bridges"] == [],
        "S1_AB": STATES["S1_AB"] == ["AB"],
        "S2_AB_CD": STATES["S2_AB_CD"] == ["AB", "CD"],
        "Smax_chain_AB_BC_CD": STATES["Smax_chain_AB_BC_CD"] == ["AB", "BC", "CD"],
    }

    lines = [
        f"{VERSION} four-port cross-coupled internal acoustic network",
        "",
        "Purpose",
        "- Early 2.5D mechanism-validation coupon, not a final acoustic product.",
        "- Tests whether internal bridge interconnects improve transfer-function separability from A/B/C/D to one microphone output.",
        "",
        "Key V7 changes relative to V6",
        f"- Mixing chamber radius reduced from 16 mm to {CHAMBER_R:g} mm.",
        "- The output junction is now a compact circular chamber rather than a large terminal cavity.",
        f"- Four ducts enter the compact chamber through short radial necks, nominal neck length {NECK_LENGTH:g} mm.",
        "- The mic port remains horizontal to the right and is sized for a nominal 4 mm ID tube.",
        "- The four main ducts remain single continuous, non-self-intersecting serpentine paths.",
        "- No V4-style long vertical collector and no V5-style self-intersecting/trident duct geometry.",
        "",
        "Dimensions",
        f"- Base: {W:g} x {H:g} x {BASE_TOTAL_HEIGHT:g} mm",
        f"- Common cover: {W:g} x {H:g} x {COVER_THICKNESS:g} mm",
        f"- Main channels: nominal {MAIN_CHANNEL_NOMINAL:g} mm, modeled slot width {MAIN_CHANNEL_WIDTH:g} mm",
        f"- Bridge channels: nominal {BRIDGE_CHANNEL_NOMINAL:g} mm, modeled slot width {BRIDGE_CHANNEL_WIDTH:g} mm",
        f"- Mic port: nominal {MIC_PORT_NOMINAL:g} mm, modeled slot width {MIC_PORT_WIDTH:g} mm",
        f"- Compact chamber: center {CHAMBER_C}, radius {CHAMBER_R:g} mm",
        f"- Compact chamber estimated volume: {chamber_volume_mm3():.1f} mm3, circular chamber only, excluding neck and mic-port overlap",
        "",
        "Centerline lengths",
    ]
    for lane, length in lengths.items():
        lines.append(f"- {lane}: {length} mm")

    lines += ["", "Compact-junction necks"]
    for lane, pts in necks.items():
        lines.append(
            f"- {lane}: angle {pts['angle_deg']:.1f} deg, start {tuple(round(v, 3) for v in pts['start'])}, "
            f"boundary {tuple(round(v, 3) for v in pts['boundary'])}"
        )

    lines += ["", "Bridge lengths"]
    for name, length in bridge_len.items():
        lines.append(f"- {name}: {length} mm")

    lines += [
        "",
        "Bridge states",
        "- S0_no_bridges: no bridges",
        "- S1_AB: AB",
        "- S2_AB_CD: AB + CD",
        "- Smax_chain_AB_BC_CD: AB + BC + CD",
        "",
        "Simulation notes",
        "- The printed ducts are rounded 2.5D slots sealed by a flat cover, not ideal circular tubes.",
        "- For 1D acoustic graph simulation, use equivalent area / hydraulic diameter and include empirical loss terms.",
        "- S0 still has the unavoidable single-microphone compact junction, but the terminal cavity volume is much smaller than in V6.",
        "- Because the main-duct geometry is shared across bridge states, relative comparisons of correlation, effective rank, classification accuracy, and repeatability remain meaningful.",
        "- V7 has not yet been validated by real acoustic simulation, slicing, printing, leak testing, or measured transfer functions.",
        "",
        "Generated-file and topology checks",
        f"- All expected STL files exist: {all_stls_exist}",
        f"- Bounding boxes within {bbox_limit[0]:.0f} x {bbox_limit[1]:.0f} x {bbox_limit[2]:.0f} mm: {all(v['within_180x150x35'] for v in bbox_ok.values())}",
        f"- Centerline lengths within 290-310 mm: {all(length_range_ok.values())} ({length_range_ok})",
        "- S0/S1/S2/Smax share the same LANES centerline definitions; only STATES bridge lists change.",
        f"- Bridge state definitions correct: {all(states_ok.values())} ({states_ok})",
        "- Viewer topology check: top-view rendering clears all SVG layer groups on every state switch.",
        "- Viewer topology check: S0 active bridge count 0, S1 active bridge count 1, S2 active bridge count 2, Smax active bridge count 3.",
        "- Viewer topology check: candidate bridges are hidden by default and drawn gray/dashed only when enabled.",
        "- Viewer topology check: A/B/C/D main ducts, active bridges, chamber, necks, and centerlines are separate layers.",
        "",
        "Bounding-box checks",
    ]
    for name, result in bbox_ok.items():
        lines.append(f"- {name}: {result}")

    lines += [
        "",
        "Mesh checks",
    ]
    for name, result in checks.items():
        lines.append(f"- {name}: {result}")

    (OUT / "model_params.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    sim = {
        "version": VERSION,
        "units": "mm",
        "purpose": "2.5D mechanism validation coupon for internal cross-coupled acoustic duct network",
        "frequency_range_hz": [0, 8000],
        "dimensions": {"W": W, "H": H, "base_height": BASE_TOTAL_HEIGHT, "cover_thickness": COVER_THICKNESS},
        "main_channel": {
            "nominal_diameter_mm": MAIN_CHANNEL_NOMINAL,
            "modeled_slot_width_mm": MAIN_CHANNEL_WIDTH,
            "note": "rounded slot sealed with common flat cover; not ideal circle",
        },
        "bridge_channel": {
            "nominal_diameter_mm": BRIDGE_CHANNEL_NOMINAL,
            "modeled_slot_width_mm": BRIDGE_CHANNEL_WIDTH,
        },
        "ports": {"inputs": list(LANES.keys()), "output": "mic_port"},
        "centerlines": {lane: path_points(lane) for lane in LANES},
        "centerline_lengths_mm": {lane: round(path_length(path_points(lane)), 3) for lane in LANES},
        "mixing_chamber": {
            "type": "compact_junction",
            "center": CHAMBER_C,
            "radius_mm": CHAMBER_R,
            "estimated_volume_mm3": round(chamber_volume_mm3(), 1),
            "estimated_volume_note": "circular compact chamber only; excludes neck and mic-port overlap",
            "previous_v6_radius_mm": 16.0,
            "design_note": "small compact chamber intended to reduce output-end coupling relative to V6",
        },
        "junction_necks": {
            lane: {
                "angle_deg": pts["angle_deg"],
                "start": pts["start"],
                "boundary": pts["boundary"],
                "inside_endpoint": pts["inside"],
                "nominal_length_to_boundary_mm": NECK_LENGTH,
                "width_mm": NECK_WIDTH,
            }
            for lane, pts in necks.items()
        },
        "mic_port": {"from": CHAMBER_C, "to": [W, CHAMBER_C[1]], "width_mm": MIC_PORT_WIDTH},
        "bridges": {
            name: {
                **info,
                "p0": point_on_pass(info["from"], info["from_pass"], info["x"]),
                "p1": point_on_pass(info["to"], info["to_pass"], info["x"]),
            }
            for name, info in BRIDGES.items()
        },
        "states": STATES,
        "screw_holes": {"diameter_mm": SCREW_DIAM, "centers_mm": SCREW_HOLES},
    }
    (OUT / "sim_params.json").write_text(json.dumps(sim, indent=2, ensure_ascii=False), encoding="utf-8")

    readme = f"""{VERSION} engineering package
======================

This is an early mechanism-validation coupon for a four-port internal acoustic
network. It is not a final acoustic product.

Recommended print order
-----------------------
1. Print core_base_S0_no_bridges.stl and core_cover_common.stl first.
2. Check sealing, tube fit, microphone mounting, and measurement repeatability.
3. Print the S1/S2/Smax bases after the baseline setup is reliable.
4. Before every print, inspect the STL in Bambu Studio for layer height, hole
   diameter, support settings, top sealing contact, and possible thin-wall issues.

Important V7 design notes
-------------------------
- The V6 large 16 mm radius mixing chamber has been replaced by an 8 mm radius
  compact junction.
- Four main ducts enter the compact junction through short radial necks.
- The mic port remains horizontal to the right for a nominal 4 mm ID plastic tube.
- Each main duct is one continuous non-self-intersecting serpentine path.
- Smax is the chain AB + BC + CD; no DA bridge is included.
- Do not reintroduce a long vertical collector or self-intersecting/trident paths.
- This package has not yet been validated by real acoustic simulation, slicing,
  printing, leak testing, or measured transfer functions.

Viewer checks
-------------
- Top view is the default mode for acoustic topology inspection.
- S0 shows no red bridge slot.
- S1_AB shows only AB.
- S2_AB_CD shows only AB and CD.
- Smax_chain_AB_BC_CD shows AB, BC, and CD.
- Candidate bridges are hidden by default and appear only as gray dashed slots.
- The STL/3D preview mode is separate from the engineering top view.

Printing suggestions
--------------------
- Bambu Lab P1S, PLA, 0.4 mm nozzle.
- Layer height 0.16-0.20 mm.
- Print the base and common cover flat.
- Use a thin silicone sheet, vacuum grease, or a thin gasket between base and cover.
- Use tube_adapter_gauge.stl to test 4 mm ID tube fit before committing to the bases.

Experiment suggestions
----------------------
- Fix the microphone at the right-side output port.
- Connect the speaker to A/B/C/D in sequence through a short 4 mm ID tube.
- Seal inactive input ports in the same repeatable way.
- Use a log chirp or white noise excitation.
- Compare S0/S1/S2/Smax by transfer-function correlation, effective rank,
  repeatability, and energy-normalized classification accuracy.
"""
    (OUT / "README.txt").write_text(readme, encoding="utf-8")

    notes = f"""Codex notes for {VERSION}
===================

generate_stl.py regenerates the complete package in its own directory.

Important geometry functions
----------------------------
- path_points(lane): four single continuous duct centerlines.
- neck_points(lane): compact-junction neck start, boundary point, and overlap endpoint.
- channel_shapes(open_bridges): union of main ducts, compact chamber, mic port, and selected bridges.
- model_data(): topology-only data for the layered SVG viewer; keep this separated by lane and bridge.
- write_viewer_files(): local viewer logic. renderState() clears every SVG layer group before drawing the new state.
- BRIDGES: chain topology AB, BC, CD. Bridges connect the final pass of the upper duct to the first pass of the next duct.
- STATES: S0/S1/S2/Smax.

Core parameters
---------------
- Chamber radius: CHAMBER_R.
- Estimated chamber volume: pi * CHAMBER_R^2 * WALL_HEIGHT.
- Neck length: NECK_LENGTH.
- Main channel slot width: MAIN_CHANNEL_WIDTH.
- Bridge slot width: BRIDGE_CHANNEL_WIDTH.
- Bridge state combinations: STATES.
- Candidate bridge geometry: BRIDGES.

Design constraints to preserve
------------------------------
- Keep the chamber compact; V7 uses radius {CHAMBER_R:g} mm.
- V7 uses a small chamber because V6's 16 mm radius chamber was large enough to act as a strong shared terminal cavity in S0, potentially masking the intended bridge-coupling experiment.
- Keep the mic port horizontal to the right.
- Do not add a DA bridge unless the experiment explicitly asks for it.
- Do not reintroduce V4's long vertical collector.
- Do not reintroduce V5's self-intersecting/trident main ducts.
- Do not merge all SVG channel footprints into one green union for topology inspection; keep main ducts, active bridges, candidate bridges, chamber, necks, and centerlines in separate viewer layers.
"""
    (OUT / "codex_notes.txt").write_text(notes, encoding="utf-8")


def write_zip():
    zip_path = OUT.parent / f"{PACKAGE_NAME}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in OUT.rglob("*"):
            if "__pycache__" in p.parts or p.suffix == ".pyc":
                continue
            z.write(p, p.relative_to(OUT.parent))
    return zip_path


def main():
    ensure_dirs()
    checks = {}
    for state, bridges in STATES.items():
        mesh = make_base_mesh(bridges)
        fname = f"core_base_{state}.stl"
        checks[fname] = export_mesh(mesh, MODELS / fname)
    checks["core_cover_common.stl"] = export_mesh(make_cover_mesh(), MODELS / "core_cover_common.stl")
    checks["tube_adapter_gauge.stl"] = export_mesh(make_tube_adapter_test(), MODELS / "tube_adapter_gauge.stl")

    write_index()
    write_viewer_files()
    write_docs(checks)
    zip_path = write_zip()

    print(zip_path)
    print("lengths", {lane: round(path_length(path_points(lane)), 2) for lane in LANES})
    print("checks", checks)


if __name__ == "__main__":
    main()
