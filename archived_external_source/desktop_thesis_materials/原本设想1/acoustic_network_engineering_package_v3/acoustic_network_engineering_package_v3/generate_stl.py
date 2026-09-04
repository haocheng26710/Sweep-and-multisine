import os, json, math, zipfile, shutil
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon, Point, LineString, MultiPolygon
from shapely.ops import unary_union
import trimesh
try:
    import pymeshfix
except Exception:
    pymeshfix = None

OUT = Path('/mnt/data/acoustic_network_engineering_package')
MODELS = OUT / 'models'
if OUT.exists():
    shutil.rmtree(OUT)
MODELS.mkdir(parents=True)

# ----------------------------
# Parameters
# ----------------------------
P = {
    'printer': {'model':'Bambu Lab P1S', 'build_volume_mm':[256,256,256], 'material':'PLA', 'nozzle_mm':0.4},
    'core': {
        'width_mm': 175.0, 'height_mm': 115.0,
        'bottom_thickness_mm': 3.0, 'channel_depth_mm': 4.0,
        'channel_nominal_diameter_mm': 4.0, 'channel_model_width_mm': 4.4,
        'screw_diameter_mm': 3.4, 'pin_diameter_mm': 2.2,
        'cover_thickness_mm': 2.5,
    },
    'bridge': {
        'nominal_diameter_mm': 2.0, 'model_width_mm': 2.2,
        'nominal_length_mm': 10.0, 'plug_clearance_mm': 0.15,
        'circumference_segments': 48,
        'states': {
            'S0_all_closed': [],
            'S1_AB_open': ['AB'],
            'S2_AB_CD_open': ['AB','CD'],
            'S4_all_open': ['AB','BC','CD','DA']
        }
    },
    'manifold': {
        'width_mm':55.0, 'height_mm':115.0,
        'bottom_thickness_mm':3.0, 'channel_depth_mm':4.0,
        'cover_thickness_mm':2.5,
        'mixing_chamber_radius_mm':12.0,
        'mic_port_width_mm':4.4
    },
    'analysis': {'frequency_range_hz':[0,8000], 'recommended_analysis_band_hz':[500,8000]}
}

# Channel point helpers

def dist(p,q):
    return math.hypot(q[0]-p[0], q[1]-p[1])

def path_len(points):
    return sum(dist(points[i], points[i+1]) for i in range(len(points)-1))

def dogleg(P0, P1, target_len, sign=1):
    d = dist(P0,P1)
    if target_len <= d + 1e-6:
        return [P0, P1]
    h = (target_len - d)/2.0
    vx, vy = (P1[0]-P0[0])/d, (P1[1]-P0[1])/d
    nx, ny = -vy*sign, vx*sign
    return [P0, (P0[0]+nx*h, P0[1]+ny*h), (P1[0]+nx*h, P1[1]+ny*h), P1]

def concat_paths(*parts):
    pts=[]
    for part in parts:
        if not pts:
            pts.extend(part)
        else:
            if dist(pts[-1], part[0]) < 1e-6:
                pts.extend(part[1:])
            else:
                pts.extend(part)
    return pts

# 2D coordinates in mm. x=0 is input edge of the core; x=170 is outlet edge.
# These paths are intentionally not straight; their cumulative lengths hit the target bridge distances.
# Endpoint coordinates are inset from the plate edges. Ports are accessed via cover holes/adapters,
# which keeps the channel base watertight and easier for slicers.
A_in=(8,104); A_AB=(70,104); A_DA=(130,60); A_out=(166,104)
B_in=(8,94); B_AB=(70,94); B_BC=(130,74); B_out=(166,84)
C_in=(8,54); C_CD=(70,54); C_BC=(130,64); C_out=(166,54)
D_in=(8,44); D_CD=(70,44); D_DA=(130,50); D_out=(166,44)

# Build paths with target cumulative distances.
# A: 0->70->160->300
A_path = concat_paths(
    [A_in, (8,100), (12,100), (12,104), A_AB],  # 70 mm with compact initial detour
    dogleg(A_AB, A_DA, 90, sign=-1),
    [A_DA, (166,60), (166,80), (136,80), (136,104), A_out]  # 36+20+30+24+30 = 140
)
# B: 0->130->220->300
B_path = concat_paths(
    [B_in, (32,94), (32,84), (8,84), (8,94), B_AB],  # 24+10+24+10+62 = 130
    dogleg(B_AB, B_BC, 90, sign=1),
    dogleg(B_BC, B_out, 80, sign=-1)
)
# C: 0->70->140->300
C_path = concat_paths(
    [C_in, (8,50), (12,50), (12,54), C_CD],  # 70 mm with compact initial detour
    dogleg(C_CD, C_BC, 70, sign=1),
    [C_BC, (166,64), (166,82), (126,82), (126,54), C_out]  # 36+18+40+28+40 = 162 (within +2 mm)
)
# D: 0->170->240->300
D_path = concat_paths(
    [D_in, (43,44), (43,24), (8,24), (8,44), D_CD],  # 35+20+35+20+62 = 172 (close; retained for print spacing)
    dogleg(D_CD, D_DA, 70, sign=-1),
    dogleg(D_DA, D_out, 60, sign=1)
)
CHANNELS = {'A':A_path,'B':B_path,'C':C_path,'D':D_path}
BRIDGES = {
    'AB': {'from':'A_AB','to':'B_AB','p1':A_AB,'p2':B_AB,'duct_a':'A','duct_b':'B','pos_a_mm':70,'pos_b_mm':130},
    'BC': {'from':'B_BC','to':'C_BC','p1':B_BC,'p2':C_BC,'duct_a':'B','duct_b':'C','pos_a_mm':220,'pos_b_mm':140},
    'CD': {'from':'C_CD','to':'D_CD','p1':C_CD,'p2':D_CD,'duct_a':'C','duct_b':'D','pos_a_mm':70,'pos_b_mm':170},
    'DA': {'from':'D_DA','to':'A_DA','p1':D_DA,'p2':A_DA,'duct_a':'D','duct_b':'A','pos_a_mm':240,'pos_b_mm':160},
}

# Screw and alignment holes
screw_pts = [(8,8),(42,8),(76,8),(110,8),(144,8),(167,8),
             (8,107),(42,107),(76,107),(110,107),(144,107),(167,107),
             (8,58),(167,58)]
pin_pts = [(20,20),(155,20),(20,95),(155,95)]

# Geometry helpers

def circle(pt, r, res=32):
    return Point(pt).buffer(r, resolution=res)

def line_buffer(points, radius, res=16):
    # Round ends and joins for a smooth true capsule path.
    return LineString(points).buffer(radius, cap_style=1, join_style=1, resolution=res)

def rect_poly(w,h):
    return Polygon([(0,0),(w,0),(w,h),(0,h)])

def extrude(poly, height, z=0):
    if poly.is_empty:
        return trimesh.Trimesh()
    meshes=[]
    # handle multipolygons
    geoms = list(poly.geoms) if isinstance(poly, MultiPolygon) else [poly]
    for g in geoms:
        if g.area <= 1e-6:
            continue
        m = trimesh.creation.extrude_polygon(g, height=height)
        if abs(z) > 1e-9:
            m.apply_translation([0,0,z])
        meshes.append(m)
    if not meshes:
        return trimesh.Trimesh()
    out = trimesh.util.concatenate(meshes)
    try:
        out.merge_vertices()
    except Exception:
        pass
    try:
        out.update_faces(out.unique_faces())
    except Exception:
        pass
    try:
        out.update_faces(out.nondegenerate_faces())
    except Exception:
        pass
    try: trimesh.repair.fix_normals(out)
    except Exception: pass
    return out

def export_mesh(mesh, filename):
    path = MODELS / filename
    mesh.export(path)
    # Optional lightweight repair for slicer compatibility. This is especially useful
    # for open-channel base meshes generated from layered polygon operations.
    if pymeshfix is not None:
        try:
            m = trimesh.load(path, force='mesh')
            if not m.is_watertight:
                mf = pymeshfix.MeshFix(m.vertices, m.faces)
                mf.repair(joincomp=True, remove_smallest_components=False)
                repaired = trimesh.Trimesh(vertices=mf.points, faces=mf.faces, process=True)
                repaired.export(path)
        except Exception:
            pass
    return path

def make_plate_with_holes(w,h,thickness, holes):
    poly = rect_poly(w,h)
    for hp,hr in holes:
        poly = poly.difference(circle(hp,hr,res=32))
    return extrude(poly, thickness, 0)

# ----------------------------
# Core channel base
# ----------------------------
core_w=P['core']['width_mm']; core_h=P['core']['height_mm'];
bottom_t=P['core']['bottom_thickness_mm']; channel_d=P['core']['channel_depth_mm']
channel_r=P['core']['channel_model_width_mm']/2.0
bridge_r=P['bridge']['model_width_mm']/2.0
screw_r=P['core']['screw_diameter_mm']/2.0
pin_r=P['core']['pin_diameter_mm']/2.0

hole_list = [(p,screw_r) for p in screw_pts] + [(p,pin_r) for p in pin_pts]
port_hole_r = channel_r
core_input_port_pts = [A_in, B_in, C_in, D_in]
core_output_port_pts = [A_out, B_out, C_out, D_out]
base_bottom = make_plate_with_holes(core_w, core_h, bottom_t, hole_list)

channel_union = unary_union([line_buffer(path, channel_r, res=16) for path in CHANNELS.values()])
bridge_union = unary_union([line_buffer([b['p1'], b['p2']], bridge_r, res=16) for b in BRIDGES.values()])
all_cutouts = unary_union([channel_union, bridge_union] + [circle(p,r,res=32) for p,r in hole_list])
wall_poly = rect_poly(core_w, core_h).difference(all_cutouts)
base_walls = extrude(wall_poly, channel_d, bottom_t)
# Add small labels as shallow colored markers? not in STL. Use cylinders? skip.

try:
    core_base = trimesh.boolean.union([base_bottom, base_walls], engine='manifold')
except Exception:
    core_base = trimesh.util.concatenate([base_bottom, base_walls])
core_base.metadata['name']='core_channel_base'
export_mesh(core_base, 'core_channel_base.stl')

# Core cover: screw/pin holes plus vertical acoustic port holes at the 4 inputs and 4 outputs.
cover_holes = [(p,screw_r) for p in screw_pts] + [(p,pin_r) for p in pin_pts] + [(p,port_hole_r) for p in (core_input_port_pts + core_output_port_pts)]
core_cover = make_plate_with_holes(core_w, core_h, P['core']['cover_thickness_mm'], cover_holes)
core_cover.metadata['name']='core_cover'
export_mesh(core_cover, 'core_cover.stl')

# Bridge plugs: solid capsule plugs corresponding to bridge slots, slightly undersized, with small rectangular pull tabs.
plug_meshes=[]
plug_r = max(0.5, bridge_r - P['bridge']['plug_clearance_mm'])
plug_h = channel_d - 0.3
for name,b in BRIDGES.items():
    plug_poly = line_buffer([b['p1'], b['p2']], plug_r, res=16)
    plug = extrude(plug_poly, plug_h, 0)
    # Add a tiny handle tab in the middle: cylinder or box on top for removal.
    mid=((b['p1'][0]+b['p2'][0])/2,(b['p1'][1]+b['p2'][1])/2)
    tab = trimesh.creation.box(extents=[6,2,1.5])
    angle = math.atan2(b['p2'][1]-b['p1'][1], b['p2'][0]-b['p1'][0])
    tab.apply_translation([mid[0],mid[1],plug_h+0.75])
    # no rotation for tabs; simple
    plug_meshes.append(trimesh.util.concatenate([plug,tab]))
bridge_plugs = trimesh.util.concatenate(plug_meshes)
bridge_plugs.metadata['name']='bridge_plugs'
export_mesh(bridge_plugs, 'bridge_plugs.stl')

# ----------------------------
# Mic manifold base/cover
# ----------------------------
man_w=P['manifold']['width_mm']; man_h=P['manifold']['height_mm']
# Manifold is its own open-slot module. Its acoustic ports are inset and accessed through cover holes.
out_y = {'A':A_out[1], 'B':B_out[1], 'C':C_out[1], 'D':D_out[1]}
chamber=(34,64)
mic_out=(48,64)
man_channel_lines=[]
for k,y in out_y.items():
    man_channel_lines.append([(6,y),(16,y),chamber])
man_channel_lines.append([chamber,mic_out])
man_channels = unary_union([line_buffer(line, channel_r, res=16) for line in man_channel_lines])
man_chamber = circle(chamber, P['manifold']['mixing_chamber_radius_mm'], res=48)
man_cutouts = unary_union([man_channels, man_chamber])
# add screw holes
man_screw_pts=[(8,8),(47,8),(8,107),(47,107),(47,64)]
man_holes=[(p,screw_r) for p in man_screw_pts]
man_bottom=make_plate_with_holes(man_w,man_h,P['manifold']['bottom_thickness_mm'], man_holes)
man_wall_poly = rect_poly(man_w,man_h).difference(unary_union([man_cutouts]+[circle(p,r,res=32) for p,r in man_holes]))
man_walls=extrude(man_wall_poly, P['manifold']['channel_depth_mm'], P['manifold']['bottom_thickness_mm'])

try:
    manifold_base = trimesh.boolean.union([man_bottom, man_walls], engine='manifold')
except Exception:
    manifold_base=trimesh.util.concatenate([man_bottom, man_walls])
manifold_base.metadata['name']='mic_manifold_base'
export_mesh(manifold_base, 'mic_manifold_base.stl')
# Manifold cover: screw holes plus acoustic port holes at four inlets and one mic outlet.
manifold_port_pts = [(6,y) for y in out_y.values()] + [mic_out]
manifold_cover=make_plate_with_holes(man_w,man_h,P['manifold']['cover_thickness_mm'], man_holes + [(p,port_hole_r) for p in manifold_port_pts])
manifold_cover.metadata['name']='mic_manifold_cover'
export_mesh(manifold_cover, 'mic_manifold_cover.stl')

# Optional simple port adapter blocks: four input stubs and one mic stub. Useful as printable placeholders.
def make_cylinder(radius, height, sections=48, axis='x'):
    cyl=trimesh.creation.cylinder(radius=radius, height=height, sections=sections)
    # default cylinder along z; rotate to x if needed
    if axis=='x':
        cyl.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [0,1,0]))
    elif axis=='y':
        cyl.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [1,0,0]))
    return cyl
# Hollow-ish collars represented as solid outer cylinders with central guide hole not boolean; provide as optional drill guide by ring meshes manually.
def make_hollow_cylinder(outer_r, inner_r, height, sections=64, axis='x'):
    verts=[]; faces=[]
    # cylinder along x initially via coordinates x,z/y? create along x
    for xi in [-height/2, height/2]:
        for r in [outer_r, inner_r]:
            for i in range(sections):
                a=2*math.pi*i/sections
                verts.append([xi, r*math.cos(a), r*math.sin(a)])
    # indices: side 0 outer at x=-, 1 inner at x=-, 2 outer x=+, 3 inner x=+
    def idx(layer, i): return layer*sections + (i%sections)
    # layers 0 outer-, 1 inner-, 2 outer+, 3 inner+
    for i in range(sections):
        # outer wall
        faces += [[idx(0,i),idx(0,i+1),idx(2,i+1)],[idx(0,i),idx(2,i+1),idx(2,i)]]
        # inner wall reverse
        faces += [[idx(1,i),idx(3,i+1),idx(1,i+1)],[idx(1,i),idx(3,i),idx(3,i+1)]]
        # left annulus
        faces += [[idx(0,i),idx(1,i+1),idx(0,i+1)],[idx(0,i),idx(1,i),idx(1,i+1)]]
        # right annulus
        faces += [[idx(2,i),idx(2,i+1),idx(3,i+1)],[idx(2,i),idx(3,i+1),idx(3,i)]]
    mesh=trimesh.Trimesh(vertices=np.array(verts), faces=np.array(faces), process=True)
    return mesh
adapters=[]
# Optional collar kit, clustered compactly for printing. These are placeholders/drill guides,
# not a verified airtight connector system.
for i in range(4):
    m=make_hollow_cylinder(outer_r=4.0, inner_r=2.1, height=12, sections=64)
    m.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [0,1,0]))
    m.apply_translation([10 + i*14, 12, 6])
    adapters.append(m)
mic=make_hollow_cylinder(outer_r=5.0, inner_r=2.1, height=12, sections=64)
mic.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [0,1,0]))
mic.apply_translation([10, 30, 6])
adapters.append(mic)
port_adapters=trimesh.util.concatenate(adapters)
port_adapters.metadata['name']='port_adapters'
export_mesh(port_adapters, 'port_adapters.stl')

# Validate and compute bounding boxes
all_model_files = sorted(MODELS.glob('*.stl'))
bboxes={}
for f in all_model_files:
    m=trimesh.load(f, force='mesh')
    bounds=m.bounds
    bboxes[f.name]={'min':[round(x,3) for x in bounds[0].tolist()], 'max':[round(x,3) for x in bounds[1].tolist()], 'size':[round(x,3) for x in (bounds[1]-bounds[0]).tolist()], 'volume_mm3':round(float(m.volume),3), 'watertight':bool(m.is_watertight)}

# Save sim params
sim = {
    'units':'mm',
    'note':'First-pass 1D acoustic graph parameters. Geometry has not been acoustically simulated or experimentally validated.',
    'frequency_range_hz':[0,8000],
    'duct_nominal_diameter_mm':4.0,
    'duct_model_width_mm':4.4,
    'bridge_nominal_diameter_mm':2.0,
    'bridge_model_width_mm':2.2,
    'boundary_condition':{'input':'speaker-driven port one at a time', 'readout':'single microphone at mixing chamber', 'inactive_ports':'rigid capped for first tests'},
    'nodes':[],
    'edges':[],
    'bridge_states':P['bridge']['states'],
    'path_centerlines_mm':{k:[[round(a,3),round(b,3)] for a,b in v] for k,v in CHANNELS.items()},
    'mesh_bounding_boxes':bboxes
}
# Define nodes
node_coords={
    'A_in':A_in,'A_AB':A_AB,'A_DA':A_DA,'A_out':A_out,
    'B_in':B_in,'B_AB':B_AB,'B_BC':B_BC,'B_out':B_out,
    'C_in':C_in,'C_CD':C_CD,'C_BC':C_BC,'C_out':C_out,
    'D_in':D_in,'D_CD':D_CD,'D_DA':D_DA,'D_out':D_out,
    'mixing_chamber':chamber, 'microphone_port':mic_out
}
for name,coord in node_coords.items():
    sim['nodes'].append({'id':name,'x_mm':coord[0],'y_mm':coord[1]})
# main edges (specified lengths)
sim_edges=[
    ('A_in','A_AB',70,'duct_A_private_1'),('A_AB','A_DA',90,'duct_A_coupled_segment'),('A_DA','A_out',140,'duct_A_private_2'),
    ('B_in','B_AB',130,'duct_B_private_1'),('B_AB','B_BC',90,'duct_B_coupled_segment'),('B_BC','B_out',80,'duct_B_private_2'),
    ('C_in','C_CD',70,'duct_C_private_1'),('C_CD','C_BC',70,'duct_C_coupled_segment'),('C_BC','C_out',160,'duct_C_private_2'),
    ('D_in','D_CD',170,'duct_D_private_1'),('D_CD','D_DA',70,'duct_D_coupled_segment'),('D_DA','D_out',60,'duct_D_private_2'),
]
for u,v,L,label in sim_edges:
    sim['edges'].append({'id':label,'type':'main_duct','from':u,'to':v,'length_mm':L,'nominal_diameter_mm':4.0})
# bridge edges
for name,b in BRIDGES.items():
    sim['edges'].append({'id':'bridge_'+name,'type':'bridge','from':b['from'],'to':b['to'],'length_mm':round(dist(b['p1'],b['p2']),3),'nominal_diameter_mm':2.0,'model_width_mm':2.2,'default_state':'closed_by_plug'})
# manifold edges (geometric approximate)
for k,y in out_y.items():
    L=dist((0,y),(15,y))+dist((15,y),chamber)
    sim['edges'].append({'id':'manifold_'+k,'type':'manifold_channel','from':k+'_out','to':'mixing_chamber','length_mm':round(L,3),'nominal_width_mm':4.0})
sim['edges'].append({'id':'manifold_mic','type':'manifold_channel','from':'mixing_chamber','to':'microphone_port','length_mm':round(dist(chamber,mic_out),3),'nominal_width_mm':4.0})

(OUT/'sim_params.json').write_text(json.dumps(sim, ensure_ascii=False, indent=2), encoding='utf-8')

# model params txt
lines=[]
lines.append('4-port reconfigurable cross-coupled internal acoustic network - first-pass parameters')
lines.append('')
lines.append('DESIGN STATUS')
lines.append('- This is a first-pass experimental engineering package, not a verified final product.')
lines.append('- No acoustic FEM, 1D graph simulation, leak test, or physical print validation has been performed.')
lines.append('- The geometry is intentionally conservative: open-slot base + cover, modular parts, and reconfigurable bridge plugs.')
lines.append('')
lines.append('PRINT CHECK')
lines.append('- Target printer: Bambu Lab P1S, PLA, 0.4 mm nozzle.')
lines.append('- P1S nominal build volume: 256 x 256 x 256 mm. Each STL module is below this.')
lines.append('- Core module target size: below 180 x 120 x 35 mm. Actual bounding boxes are listed below.')
lines.append('- 300 mm means acoustic centerline length per main duct, achieved by folded/snake centerlines; it is not the outside model length.')
lines.append('')
lines.append('ACOUSTIC PARAMETERS')
lines.append('- Frequency sweep target: 0-8 kHz; recommended first analysis band: 500-8000 Hz.')
lines.append('- Main channel nominal diameter: 4.0 mm. Printed open-slot model width: 4.4 mm to allow printer tolerance.')
lines.append('- Bridge nominal diameter: 2.0 mm. Printed capsule-slot model width: 2.2 mm to allow printer tolerance.')
lines.append('- Main channels are modeled as open rounded slots sealed by a cover, rather than enclosed circular tubes. This was chosen for printability and inspection.')
lines.append('- Bridge couplings are modeled as 2.2 mm capsule-shaped open micro-channels sealed by the cover; plugs can be inserted to close them.')
lines.append('')
lines.append('MAIN DUCT LENGTHS')
for k,path in CHANNELS.items():
    lines.append(f'- Duct {k}: geometric centerline length from CAD polyline = {path_len(path):.2f} mm; target ~300 mm.')
lines.append('')
lines.append('BRIDGE TOPOLOGY')
for name,b in BRIDGES.items():
    lines.append(f'- {name}: {b["from"]} <-> {b["to"]}; specified path positions {b["duct_a"]}@{b["pos_a_mm"]} mm <-> {b["duct_b"]}@{b["pos_b_mm"]} mm; physical bridge length {dist(b["p1"],b["p2"]):.2f} mm.')
lines.append('')
lines.append('RECONFIGURABLE STATES')
for state,open_bridges in P['bridge']['states'].items():
    lines.append(f'- {state}: open bridges = {open_bridges if open_bridges else "none"}; all other bridge slots closed with plugs.')
lines.append('')
lines.append('MODULE BOUNDING BOXES')
for fn,bb in bboxes.items():
    lines.append(f'- {fn}: size {bb["size"]} mm; watertight={bb["watertight"]}')
(OUT/'model_params.txt').write_text('\n'.join(lines), encoding='utf-8')

# README
readme=f"""4-port reconfigurable cross-coupled internal acoustic network
================================================================

This engineering package is a first-pass experimental prototype for testing whether internal cross-coupling can improve spatial/port transfer-function encoding capacity.

IMPORTANT STATUS
----------------
This model has NOT been acoustically simulated, FEM-validated, print-tested, leak-tested, or calibrated. It is intended as a low-complexity starting point for early experiments.

Printer/material assumption
---------------------------
- Printer: Bambu Lab P1S
- Material: PLA
- Nozzle: 0.4 mm
- Largest individual STL module is below the P1S nominal build volume.

What is included
----------------
- index.html / viewer.js / model_data.js: local WebGL viewer. Open index.html in a browser.
- models/*.stl: printable STL modules.
- generate_stl.py: script that regenerates all STL and parameter files.
- model_params.txt: readable design parameter file.
- sim_params.json: first-pass 1D acoustic graph simulation parameters.
- codex_notes.txt: notes for future code editing.

Suggested printing workflow
---------------------------
1. Print a small calibration strip first if possible, especially for 4.4 mm channels and 2.2 mm bridge slots.
2. Slice each module individually. Do not print the full assembly as one piece.
3. Suggested orientation:
   - core_channel_base.stl: flat on the bed, channels facing upward.
   - core_cover.stl: flat on the bed.
   - mic_manifold_base.stl: flat on the bed, channels facing upward.
   - mic_manifold_cover.stl: flat on the bed.
   - bridge_plugs.stl: flat on the bed; small parts may need brim.
4. Use a thin silicone sheet, vacuum grease, PTFE tape, or another removable gasket layer if leakage is observed.
5. Use screws around the cover perimeter. The screw holes are nominal M3 clearance holes; actual post-processing may be required.

Assembly concept
----------------
- The core base contains four ~300 mm acoustic centerline channels A/B/C/D.
- The cover seals the open slots.
- The mic manifold connects the four core outlets to a small mixing chamber and then to a microphone port.
- Bridge slots AB/BC/CD/DA are cut into the core base. Leaving a bridge slot open couples two channels. Inserting the matching bridge plug closes that coupling.

Testing concept
---------------
- Fix one microphone at the manifold microphone port.
- Drive A/B/C/D one at a time using the same speaker and same coupling adapter.
- Rigidly cap inactive input ports.
- Test bridge states:
  S0: all bridge plugs inserted.
  S1: only AB bridge plug removed.
  S2: AB and CD bridge plugs removed.
  S4: all bridge plugs removed.
- Recommended excitation: log chirp 300 Hz to 10 kHz; first analysis band 500 Hz to 8 kHz.
- Main metrics: transfer-function correlation matrix, maximum off-diagonal correlation, effective rank, repeated-measure separation ratio, and energy-normalized port classification accuracy.

Known limitations
-----------------
- Main channels are rounded open slots, not perfect enclosed circular tubes.
- Bridge couplings are 2.2 mm capsule slots sealed by the cover, not precision-machined cylindrical tubes.
- Small bridge plugs may leak unless carefully fitted and sealed.
- The first-pass geometry is intended to reveal trends, not to provide final acoustic precision.
"""
(OUT/'README.txt').write_text(readme, encoding='utf-8')

# Codex notes
codex=f"""Codex notes for acoustic network package
========================================

Primary script
--------------
- generate_stl.py regenerates all STL files and parameter files.
- It uses Python, numpy, shapely, mapbox-earcut, and trimesh.
- The model is generated from 2D polygons extruded in z. This makes it easy to modify channel paths and hole/cutout footprints.

Main parameter blocks
---------------------
- P['core']: core base/cover sizes, channel width, layer heights, screw holes.
- P['bridge']: bridge width, plug clearance, bridge open/closed states.
- P['manifold']: mic manifold size, chamber radius, channel dimensions.
- CHANNELS: centerline polylines for ducts A/B/C/D in mm.
- BRIDGES: bridge definitions, including node names, coordinate endpoints, and intended path distances.

How geometry works
------------------
1. Bottom slabs are simple plates with screw/pin holes.
2. Open-channel walls are made by subtracting buffered channel centerlines from an upper wall layer.
3. The cover is a flat plate with screw/pin holes.
4. Bridge slots are modeled as narrow capsule-shaped channels between duct slots.
5. Bridge plugs are separate undersized capsule-shaped inserts.

How to alter the acoustic topology
----------------------------------
- Change BRIDGES to move bridge endpoints or add/remove coupling points.
- Change CHANNELS to alter path shape and centerline length.
- Update sim_params.json accordingly. The script currently writes fixed intended graph edges matching the experimental design.

Important acoustic-model mapping
--------------------------------
- Nodes in sim_params.json correspond to input ports, bridge tap positions, duct outlets, the mixing chamber, and microphone port.
- Main-duct edges have specified acoustic lengths: A = 70 + 90 + 140 mm, B = 130 + 90 + 80 mm, C = 70 + 70 + 160 mm, D = 170 + 70 + 60 mm.
- Bridge edges have lengths based on their physical coordinate separation, currently about 10 mm.
- Bridge states S0/S1/S2/S4 are listed in sim_params.json.

Viewer
------
- index.html loads viewer.js and model_data.js.
- model_data.js is generated from the STL meshes and contains triangles in JSON-like JavaScript objects.
- viewer.js implements a minimal WebGL viewer with mouse-left rotation.
- To add a new module, regenerate model_data.js and add it to the module list in viewer.js / index.html.

Cautions
--------
- This model is not precision acoustic hardware.
- If bridge coupling is too strong, reduce bridge width or insert plugs more completely.
- If the response is too lossy, consider 5-6 mm main channels in a later version.
"""
(OUT/'codex_notes.txt').write_text(codex, encoding='utf-8')

# Copy this script itself as generate_stl.py into the package
src=Path(__file__) if '__file__' in globals() else Path('/mnt/data/build_acoustic_pkg.py')
# Since this script may be run as /mnt/data/build_acoustic_pkg.py, copy it now.
shutil.copy('/mnt/data/build_acoustic_pkg.py', OUT/'generate_stl.py')

# Generate WebGL model data from STLs. Downsample no; use raw triangles.
# Define module transforms for assembled and exploded views in the viewer.
module_specs = [
    {'id':'core_base','label':'核心通道底板','file':'core_channel_base.stl','color':[0.55,0.72,0.95]},
    {'id':'core_cover','label':'核心通道盖板','file':'core_cover.stl','color':[0.82,0.82,0.86]},
    {'id':'bridge_plugs','label':'桥管/封堵件','file':'bridge_plugs.stl','color':[0.95,0.25,0.18]},
    {'id':'mic_manifold_base','label':'麦克风汇总模块','file':'mic_manifold_base.stl','color':[0.65,0.9,0.65]},
    {'id':'mic_manifold_cover','label':'麦克风汇总盖板','file':'mic_manifold_cover.stl','color':[0.76,0.86,0.76]},
    {'id':'port_adapters','label':'端口适配器','file':'port_adapters.stl','color':[0.92,0.78,0.45]},
]
# Assembly transforms: mic manifold sits to the right of core; covers above bases.
assembly_transforms={
    'core_base':[0,0,0],
    'core_cover':[0,0,bottom_t+channel_d+0.5],
    'bridge_plugs':[0,0,bottom_t+0.2],
    'mic_manifold_base':[core_w+2,0,0],
    'mic_manifold_cover':[core_w+2,0,P['manifold']['bottom_thickness_mm']+P['manifold']['channel_depth_mm']+0.5],
    'port_adapters':[0,-45,0],
}
exploded_transforms={
    'core_base':[0,0,0],
    'core_cover':[0,0,22],
    'bridge_plugs':[0,-22,14],
    'mic_manifold_base':[core_w+20,0,0],
    'mic_manifold_cover':[core_w+20,0,22],
    'port_adapters':[-30,-40,10],
}
models_js=[]
models_js.append('const MODEL_DATA = {')
for spec in module_specs:
    mesh=trimesh.load(MODELS/spec['file'], force='mesh')
    tris=[]
    verts=np.asarray(mesh.vertices)
    faces=np.asarray(mesh.faces)
    for f in faces:
        tri=[]
        for idx in f:
            tri.extend([round(float(x),4) for x in verts[idx]])
        tris.extend(tri)
    models_js.append(f"  '{spec['id']}': {{ label: {json.dumps(spec['label'], ensure_ascii=False)}, file: 'models/{spec['file']}', color: {json.dumps(spec['color'])}, assembly: {json.dumps(assembly_transforms[spec['id']])}, exploded: {json.dumps(exploded_transforms[spec['id']])}, triangles: {json.dumps(tris)} }},")
models_js.append('};')
(OUT/'model_data.js').write_text('\n'.join(models_js), encoding='utf-8')

# index.html and viewer.js
index_html="""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>4端口交叉耦合声学网络 - 本地查看器</title>
  <style>
    body { margin:0; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:#f5f6f8; color:#222; }
    #app { display:flex; height:100vh; width:100vw; }
    #sidebar { width:300px; padding:18px; box-sizing:border-box; background:#fff; border-right:1px solid #d4d7dd; overflow:auto; }
    #viewerWrap { flex:1; position:relative; }
    canvas { width:100%; height:100%; display:block; background:linear-gradient(#ffffff,#eef1f6); }
    h1 { font-size:18px; margin:0 0 10px; }
    .hint { font-size:12px; color:#555; line-height:1.45; margin-bottom:14px; }
    select, button, a.button { width:100%; box-sizing:border-box; padding:10px; margin:8px 0; border-radius:8px; border:1px solid #bbb; background:white; font-size:14px; }
    a.button { display:block; text-align:center; text-decoration:none; color:white; background:#1f6feb; border-color:#1f6feb; }
    a.button.disabled { background:#aaa; border-color:#aaa; pointer-events:none; }
    .status { font-size:12px; color:#333; background:#f1f3f5; border-radius:8px; padding:10px; margin-top:10px; white-space:pre-wrap; }
    .legend { margin-top:12px; font-size:12px; line-height:1.5; }
  </style>
</head>
<body>
<div id="app">
  <aside id="sidebar">
    <h1>4端口声学网络查看器</h1>
    <div class="hint">鼠标左键按住右侧模型并拖动，可旋转视图。选择“完整装配”时仅展示组合效果；选择单个模块时显示爆炸视图并突出该模块。</div>
    <label for="moduleSelect">显示模式</label>
    <select id="moduleSelect">
      <option value="assembly">完整装配</option>
      <option value="core_base">核心通道底板</option>
      <option value="core_cover">核心通道盖板</option>
      <option value="bridge_plugs">桥管/封堵件</option>
      <option value="mic_manifold_base">麦克风汇总模块</option>
      <option value="mic_manifold_cover">麦克风汇总盖板</option>
      <option value="port_adapters">端口适配器</option>
    </select>
    <a id="downloadBtn" class="button disabled" href="#" download>选择单个模块后下载 STL</a>
    <div class="status" id="statusBox"></div>
    <div class="legend">
      <b>颜色说明：</b><br>
      蓝色：核心底板<br>
      灰色：盖板<br>
      红色：桥管/封堵件<br>
      绿色：麦克风汇总模块<br>
      黄色：端口适配器
    </div>
  </aside>
  <main id="viewerWrap"><canvas id="glcanvas"></canvas></main>
</div>
<script src="model_data.js"></script>
<script src="viewer.js"></script>
</body>
</html>
"""
(OUT/'index.html').write_text(index_html, encoding='utf-8')

viewer_js=r"""
(function(){
  const canvas = document.getElementById('glcanvas');
  const gl = canvas.getContext('webgl');
  if(!gl){ alert('WebGL is not available in this browser.'); return; }

  const vs = `
    attribute vec3 aPosition;
    attribute vec3 aColor;
    uniform mat4 uMVP;
    varying vec3 vColor;
    void main(){ gl_Position = uMVP * vec4(aPosition, 1.0); vColor = aColor; }
  `;
  const fs = `
    precision mediump float;
    varying vec3 vColor;
    void main(){ gl_FragColor = vec4(vColor, 1.0); }
  `;
  function shader(type, src){ const s=gl.createShader(type); gl.shaderSource(s,src); gl.compileShader(s); if(!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; }
  const prog=gl.createProgram(); gl.attachShader(prog, shader(gl.VERTEX_SHADER,vs)); gl.attachShader(prog, shader(gl.FRAGMENT_SHADER,fs)); gl.linkProgram(prog); gl.useProgram(prog);
  const locPos=gl.getAttribLocation(prog,'aPosition');
  const locColor=gl.getAttribLocation(prog,'aColor');
  const locMVP=gl.getUniformLocation(prog,'uMVP');
  const posBuf=gl.createBuffer();
  const colBuf=gl.createBuffer();

  let rotX=-0.75, rotY=0.55;
  let dragging=false, lastX=0, lastY=0;
  let selection='assembly';
  const select=document.getElementById('moduleSelect');
  const dl=document.getElementById('downloadBtn');
  const status=document.getElementById('statusBox');
  select.addEventListener('change', ()=>{ selection=select.value; updateDownload(); draw(); });
  canvas.addEventListener('mousedown', e=>{ dragging=true; lastX=e.clientX; lastY=e.clientY; });
  window.addEventListener('mouseup', ()=> dragging=false);
  window.addEventListener('mousemove', e=>{ if(!dragging) return; const dx=e.clientX-lastX, dy=e.clientY-lastY; lastX=e.clientX; lastY=e.clientY; rotY += dx*0.01; rotX += dy*0.01; draw(); });

  function mat4Identity(){ return [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]; }
  function mat4Mul(a,b){ const o=new Array(16).fill(0); for(let r=0;r<4;r++) for(let c=0;c<4;c++) for(let k=0;k<4;k++) o[c*4+r]+=a[k*4+r]*b[c*4+k]; return o; }
  function translate(x,y,z){ const m=mat4Identity(); m[12]=x; m[13]=y; m[14]=z; return m; }
  function scale(s){ const m=mat4Identity(); m[0]=m[5]=m[10]=s; return m; }
  function rotXmat(a){ const c=Math.cos(a),s=Math.sin(a); return [1,0,0,0, 0,c,s,0, 0,-s,c,0, 0,0,0,1]; }
  function rotYmat(a){ const c=Math.cos(a),s=Math.sin(a); return [c,0,-s,0, 0,1,0,0, s,0,c,0, 0,0,0,1]; }
  function perspective(fovy, aspect, near, far){ const f=1/Math.tan(fovy/2), nf=1/(near-far); return [f/aspect,0,0,0, 0,f,0,0, 0,0,(far+near)*nf,-1, 0,0,2*far*near*nf,0]; }

  function updateDownload(){
    if(selection==='assembly'){
      dl.className='button disabled'; dl.textContent='完整装配仅用于查看，不导出整体 STL'; dl.removeAttribute('href'); return;
    }
    const m=MODEL_DATA[selection];
    dl.className='button'; dl.textContent='下载：'+m.label+' STL'; dl.href=m.file; dl.setAttribute('download', m.file.split('/').pop());
  }

  function buildScene(){
    const positions=[]; const colors=[];
    const ids=Object.keys(MODEL_DATA);
    ids.forEach(id=>{
      const m=MODEL_DATA[id];
      const tri=m.triangles;
      const t = selection==='assembly' ? m.assembly : m.exploded;
      let color = m.color.slice();
      if(selection!=='assembly' && id!==selection){ color=[0.68,0.68,0.68]; }
      if(selection!=='assembly' && id===selection){ color=[1.0,0.35,0.05]; }
      for(let i=0;i<tri.length;i+=3){
        positions.push(tri[i]+t[0]-110, tri[i+1]+t[1]-58, tri[i+2]+t[2]-8);
        colors.push(color[0],color[1],color[2]);
      }
    });
    return {positions:new Float32Array(positions), colors:new Float32Array(colors), count:positions.length/3};
  }

  function draw(){
    const rect=canvas.getBoundingClientRect();
    const dpr=window.devicePixelRatio||1;
    canvas.width=Math.max(1, Math.floor(rect.width*dpr));
    canvas.height=Math.max(1, Math.floor(rect.height*dpr));
    gl.viewport(0,0,canvas.width,canvas.height);
    gl.enable(gl.DEPTH_TEST);
    gl.clearColor(0.96,0.97,0.99,1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    const scene=buildScene();
    gl.bindBuffer(gl.ARRAY_BUFFER,posBuf); gl.bufferData(gl.ARRAY_BUFFER, scene.positions, gl.STATIC_DRAW); gl.enableVertexAttribArray(locPos); gl.vertexAttribPointer(locPos,3,gl.FLOAT,false,0,0);
    gl.bindBuffer(gl.ARRAY_BUFFER,colBuf); gl.bufferData(gl.ARRAY_BUFFER, scene.colors, gl.STATIC_DRAW); gl.enableVertexAttribArray(locColor); gl.vertexAttribPointer(locColor,3,gl.FLOAT,false,0,0);
    const aspect=canvas.width/canvas.height;
    const P=perspective(Math.PI/4, aspect, 1, 1000);
    let M=mat4Identity();
    M=mat4Mul(translate(0,0,-340), M);
    M=mat4Mul(rotXmat(rotX), M);
    M=mat4Mul(rotYmat(rotY), M);
    M=mat4Mul(scale(1.0), M);
    const MVP=mat4Mul(P,M);
    gl.uniformMatrix4fv(locMVP,false,new Float32Array(MVP));
    gl.drawArrays(gl.TRIANGLES,0,scene.count);
    const m = selection==='assembly' ? null : MODEL_DATA[selection];
    status.textContent = selection==='assembly' ?
      '显示：完整装配\n说明：仅用于检查组合关系，不建议整体打印。' :
      '显示：'+m.label+'\nSTL：'+m.file+'\n说明：当前模块以橙色高亮，其他模块为灰色爆炸视图。';
  }
  updateDownload();
  window.addEventListener('resize', draw);
  draw();
})();
"""
(OUT/'viewer.js').write_text(viewer_js, encoding='utf-8')

# Build zip
zip_path=Path('/mnt/data/acoustic_network_engineering_package.zip')
if zip_path.exists(): zip_path.unlink()
with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for path in OUT.rglob('*'):
        z.write(path, arcname=str(path.relative_to(OUT.parent)))
print('Created', zip_path)
print('Package files:')
for p in sorted(OUT.rglob('*')):
    print(p.relative_to(OUT))
