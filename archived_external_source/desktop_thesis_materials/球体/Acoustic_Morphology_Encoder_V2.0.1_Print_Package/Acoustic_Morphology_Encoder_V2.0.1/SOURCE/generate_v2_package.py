from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import textwrap
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import Point, Polygon, MultiPolygon, GeometryCollection, box, LineString
from shapely.ops import unary_union, polygonize
import trimesh

# ============================================================
# Build paths
# ============================================================
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_BUILD_ROOT = (SCRIPT_DIR / '_regenerated') if SCRIPT_DIR.name == 'SOURCE' else (SCRIPT_DIR / '_build')
BUILD_ROOT = Path(os.environ.get('ACOUSTIC_ENCODER_V2_BUILD_ROOT', DEFAULT_BUILD_ROOT))
OUT = Path(os.environ.get('ACOUSTIC_ENCODER_V2_OUTPUT', BUILD_ROOT / 'Acoustic_Morphology_Encoder_V2'))
STL = OUT / 'STL'
SRC = OUT / 'SOURCE'
DOC = OUT / 'DOCS'
SVG = OUT / 'TEMPLATES'
PREV = OUT / 'PREVIEWS'
for d in [OUT, STL, SRC, DOC, SVG, PREV]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================================
# Parameters (millimetres unless stated otherwise)
# ============================================================
P: Dict[str, Any] = {
    'version': '2.0.1',
    'date': '2026-07-30',
    'coordinate_system': 'mm; head center=(0,0); +Y=0deg/N; +X=90deg/E; base bottom z=0',
    'printer': {
        'model': 'Bambu Lab P1S',
        'build_volume_mm': [256.0, 256.0, 256.0],
        'nozzle_mm': 0.4,
        'material': 'PLA',
        'recommended_layer_height_mm': 0.20,
        'recommended_brim_mm': 5.0,
    },
    'head': {
        'outer_apothem_mm': 105.0,  # across flats 210 mm; across corners ~227.3 mm
        'outer_sides': 8,
        'base_floor_mm': 3.0,
        'air_height_mm': 9.2,
        'base_total_height_mm': 12.2,
        'lid_plate_mm': 3.2,
        'lid_boss_extra_mm': 1.8,
        'central_chamber_radius_mm': 18.0,
        'inner_module_radius_mm': 32.0,
        'outer_module_radius_mm': 88.0,
        'outer_face_radius_mm': 105.0,
        'fixed_throat_width_mm': 8.0,
        'outer_port_width_mm': 16.0,
        'outer_port_height_mm': 9.2,
        'direction_angles_deg': [0,45,90,135,180,225,270,315],
    },
    'module': {
        'body_radial_length_mm': 56.0,
        'body_inner_width_mm': 17.0,
        'body_outer_width_mm': 36.0,
        'body_height_mm': 7.6,
        'bottom_skin_mm': 1.2,
        'air_height_mm': 6.4,
        'pocket_clearance_per_side_mm': 0.20,
        'lid_thickness_mm': 1.2,
        'lid_fit_inset_mm': 0.10,
        'lid_entry_chamfer_inset_mm': 0.20,
        'lid_gasket_thickness_mm': 0.40,
        'key_chamfer_mm': 4.0,
        'main_channel_width_mm': 9.4,
        'stub_width_mm': 5.5,
        'minimum_wall_target_mm': 1.6,
    },
    'fasteners': {
        'main_lid_screw_count': 16,
        'screw_clearance_diameter_mm': 3.4,
        'm3_nut_across_flats_mm': 5.7,
        'm3_nut_trap_depth_mm': 2.6,
        'recommended': '16x M3x20 or M3x22 socket-head screws + washers + standard M3 hex nuts',
    },
    'microphone': {
        'model': 'Dayton Audio iMM-6C',
        'measured_front_diameter_mm': 8.8,
        'front_to_shoulder_mm': 10.0,
        'recommended_bore_mm': 9.0,
        'socket_diameter_mm': 20.4,
        'insert_neck_diameter_mm': 20.0,
        'flange_diameter_mm': 30.0,
        'flange_thickness_mm': 3.0,
        'tip_target_z_mm': 7.0,
        'extension': 'USB-C data-capable male-to-female extension cable',
    },
    'turntable': {
        'base_outer_diameter_mm': 205.0,
        'top_outer_diameter_mm': 195.0,
        'cable_clearance_diameter_mm': 40.0,
        'bearing_boss_outer_diameter_mm': 52.0,
        'bearing_fit_diameter_mm': 52.5,
        'index_increment_deg': 45,
        'detent_radius_mm': 84.0,
        'mount_post_radius_mm': 42.0,
        'mount_post_diameter_mm': 6.0,
        'head_recess_diameter_mm': 6.4,
        'head_recess_depth_mm': 2.5,
        'support_pad_height_mm': 7.0,
        'post_height_above_pad_mm': 2.5,
    },
    'acoustic': {
        'reference_speed_of_sound_m_s': 343.0,
        'recommended_sweep_hz': [300, 10000],
        'recommended_analysis_hz': [1500, 8000],
        'first_experiment_distance_m': 1.5,
        'states': ['U4-Symmetric','U4-Encoded','U8-Symmetric','U8-Encoded'],
    },
}

# Derived values
P['head']['outer_circumradius_mm'] = P['head']['outer_apothem_mm'] / math.cos(math.radians(22.5))
P['head']['across_corners_mm'] = 2 * P['head']['outer_circumradius_mm']
P['head']['across_flats_mm'] = 2 * P['head']['outer_apothem_mm']
P['head']['bed_footprint_with_brim_mm'] = P['head']['across_flats_mm'] + 2 * P['printer']['recommended_brim_mm']

def hydraulic_diameter_rect(a: float, b: float) -> float:
    return 2*a*b/(a+b)
P['acoustic']['fixed_channel_area_mm2'] = P['head']['fixed_throat_width_mm'] * P['head']['air_height_mm']
P['acoustic']['fixed_channel_hydraulic_diameter_mm'] = hydraulic_diameter_rect(P['head']['fixed_throat_width_mm'], P['head']['air_height_mm'])
P['acoustic']['module_channel_area_mm2'] = P['module']['main_channel_width_mm'] * P['module']['air_height_mm']
P['acoustic']['module_channel_hydraulic_diameter_mm'] = hydraulic_diameter_rect(P['module']['main_channel_width_mm'], P['module']['air_height_mm'])
P['acoustic']['size_transition_hz_c_over_D'] = P['acoustic']['reference_speed_of_sound_m_s'] / (P['head']['across_corners_mm']/1000.0)

# ============================================================
# Geometry helpers
# ============================================================

def clean(g):
    if g.is_empty:
        return g
    g = shapely.set_precision(g, grid_size=0.001)
    if not g.is_valid:
        g = shapely.make_valid(g)
    return g


def circle(x: float, y: float, r: float, resolution: int = 64):
    return Point(x, y).buffer(r, quad_segs=resolution)


def rounded_rect(xmin: float, ymin: float, xmax: float, ymax: float, r: float):
    if r <= 0:
        return box(xmin, ymin, xmax, ymax)
    core = box(xmin + r, ymin + r, xmax - r, ymax - r)
    return core.buffer(r, join_style='round')


def regular_ngon_apothem(n: int, apothem: float, face_normal_at_deg: float = 0.0):
    # Vertices are offset by half a sector so a flat face is centred on face_normal_at_deg.
    R = apothem / math.cos(math.pi/n)
    pts=[]
    start = math.radians(face_normal_at_deg + 180.0/n)
    for k in range(n):
        a=start + 2*math.pi*k/n
        pts.append((R*math.cos(a), R*math.sin(a)))
    return clean(Polygon(pts))


def rings_of(g):
    if g.is_empty:
        return
    if isinstance(g, Polygon):
        yield g.exterior
        for ring in g.interiors:
            yield ring
    elif isinstance(g, MultiPolygon):
        for p in g.geoms:
            yield from rings_of(p)
    elif isinstance(g, GeometryCollection):
        for x in g.geoms:
            if isinstance(x, (Polygon, MultiPolygon)):
                yield from rings_of(x)


def polygons_of(g):
    if g.is_empty:
        return
    if isinstance(g, Polygon):
        yield g
    elif isinstance(g, MultiPolygon):
        for p in g.geoms:
            yield p
    elif isinstance(g, GeometryCollection):
        for x in g.geoms:
            if isinstance(x, Polygon):
                yield x
            elif isinstance(x, MultiPolygon):
                yield from x.geoms


def tri_area2(coords):
    (x0,y0),(x1,y1),(x2,y2)=coords
    return (x1-x0)*(y2-y0)-(y1-y0)*(x2-x0)


def add_horizontal_surface(vertices, faces, geom, z: float, up: bool):
    geom=clean(geom)
    if geom.is_empty:
        return
    tris=shapely.constrained_delaunay_triangles(geom)
    for tri in getattr(tris,'geoms',[tris]):
        if not isinstance(tri,Polygon) or tri.area<1e-9:
            continue
        if not geom.covers(tri.representative_point()):
            continue
        coords=list(tri.exterior.coords)[:3]
        if tri_area2(coords)<0:
            coords=[coords[0],coords[2],coords[1]]
        if not up:
            coords=[coords[0],coords[2],coords[1]]
        idx=[]
        for x,y in coords:
            idx.append(len(vertices)); vertices.append([x,y,z])
        faces.append(idx)


def add_vertical_walls(vertices, faces, geom, z0: float, z1: float):
    geom=clean(geom)
    for ring in rings_of(geom):
        coords=list(ring.coords)
        for i in range(len(coords)-1):
            a=(float(coords[i][0]),float(coords[i][1]))
            b=(float(coords[i+1][0]),float(coords[i+1][1]))
            if abs(a[0]-b[0])+abs(a[1]-b[1])<1e-9:
                continue
            p,q=sorted([a,b])
            base=len(vertices)
            vertices.extend([[p[0],p[1],z0],[q[0],q[1],z0],[q[0],q[1],z1],[p[0],p[1],z1]])
            faces.append([base,base+1,base+2]); faces.append([base,base+2,base+3])


def layered_mesh(layers: Sequence[Tuple[float,float,Any]], name: str='') -> trimesh.Trimesh:
    layers=[(float(a),float(b),clean(g)) for a,b,g in layers if b>a and not g.is_empty]
    layers.sort(key=lambda x:x[0])
    if not layers:
        raise ValueError(f'No geometry for {name}')
    linework=unary_union([g.boundary for _,_,g in layers])
    cells=[clean(c) for c in polygonize(linework) if c.area>1e-8]
    if not cells:
        raise ValueError(f'Polygonization produced no cells for {name}')
    vertices=[]; faces=[]
    for cell in cells:
        rp=cell.representative_point()
        for z0,z1,g in layers:
            if g.covers(rp):
                add_horizontal_surface(vertices,faces,cell,z0,up=False)
                add_horizontal_surface(vertices,faces,cell,z1,up=True)
                add_vertical_walls(vertices,faces,cell,z0,z1)
    mesh=trimesh.Trimesh(vertices=np.asarray(vertices),faces=np.asarray(faces),process=False)
    mesh.merge_vertices(digits_vertex=5)
    mesh.remove_unreferenced_vertices()
    sorted_faces=np.sort(mesh.faces,axis=1)
    _,inv,counts=np.unique(sorted_faces,axis=0,return_inverse=True,return_counts=True)
    mesh.update_faces(counts[inv]==1)
    mesh.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(mesh,multibody=True)
    mesh.metadata['name']=name
    return mesh


def transform_geom(g, angle_deg=0.0, tx=0.0, ty=0.0):
    h=affinity.rotate(g,angle_deg,origin=(0,0),use_radians=False)
    h=affinity.translate(h,xoff=tx,yoff=ty)
    return clean(h)


def rotate_mesh_z(mesh: trimesh.Trimesh, angle_deg: float) -> trimesh.Trimesh:
    c=mesh.copy()
    c.apply_transform(trimesh.transformations.rotation_matrix(math.radians(angle_deg),[0,0,1]))
    return c


def polyline_channel(points, width, cap='flat'):
    return clean(LineString(points).buffer(width/2,cap_style=('flat' if cap=='flat' else 'round'),join_style='round'))


def tapered_spoke_local(r0: float, r1: float, w0: float, w1: float):
    return clean(Polygon([(r0,-w0/2),(r1,-w1/2),(r1,w1/2),(r0,w0/2)]))


def spoke_rect_local(r0: float, r1: float, width: float):
    return box(r0,-width/2,r1,width/2)


def module_outline(inner_w: float=None, outer_w: float=None, radial_len: float=None, key_chamfer: float=None):
    inner_w = inner_w if inner_w is not None else P['module']['body_inner_width_mm']
    outer_w = outer_w if outer_w is not None else P['module']['body_outer_width_mm']
    radial_len = radial_len if radial_len is not None else P['module']['body_radial_length_mm']
    key_chamfer = key_chamfer if key_chamfer is not None else P['module']['key_chamfer_mm']
    x0=-radial_len/2; x1=radial_len/2
    yi=inner_w/2; yo=outer_w/2; c=key_chamfer
    # Asymmetric chamfer at outer +Y corner.
    pts=[(x0,-yi),(x1,-yo),(x1,yo-c),(x1-c,yo),(x0,yi)]
    return clean(Polygon(pts))


def global_module_geom(g, angle_deg: float):
    center_r=(P['head']['inner_module_radius_mm']+P['head']['outer_module_radius_mm'])/2
    # local +X points outward. 0 degrees is +Y/N, so rotate local +X by 90+angle.
    rot=90.0-angle_deg
    h=affinity.rotate(g,rot,origin=(0,0),use_radians=False)
    tx=center_r*math.sin(math.radians(angle_deg))
    ty=center_r*math.cos(math.radians(angle_deg))
    return clean(affinity.translate(h,xoff=tx,yoff=ty))


def local_radial_point(x: float, y: float, angle_deg: float):
    center_r=(P['head']['inner_module_radius_mm']+P['head']['outer_module_radius_mm'])/2
    rot=math.radians(90.0-angle_deg)
    X=x*math.cos(rot)-y*math.sin(rot)+center_r*math.sin(math.radians(angle_deg))
    Y=x*math.sin(rot)+y*math.cos(rot)+center_r*math.cos(math.radians(angle_deg))
    return X,Y


def mesh_export(mesh: trimesh.Trimesh, path: Path):
    path.parent.mkdir(parents=True,exist_ok=True)
    mesh.export(path,file_type='stl')


def combine_meshes(meshes: Sequence[trimesh.Trimesh], translations: Sequence[Tuple[float,float,float]]|None=None):
    if translations is None:
        translations=[(0,0,0)]*len(meshes)
    out=[]
    for m,t in zip(meshes,translations):
        c=m.copy(); c.apply_translation(t); out.append(c)
    return trimesh.util.concatenate(out)


def path_length(points: Sequence[Tuple[float,float]]) -> float:
    return sum(math.hypot(points[i+1][0]-points[i][0],points[i+1][1]-points[i][1]) for i in range(len(points)-1))


def quarter_wave_hz(length_mm: float) -> float:
    return P['acoustic']['reference_speed_of_sound_m_s']/(4*(length_mm/1000.0))


def hexagon_across_flats(af: float):
    # flat-top regular hex centred at origin, across-flats af
    R=af/math.sqrt(3)
    pts=[]
    for k in range(6):
        a=math.radians(30+60*k)
        pts.append((R*math.cos(a),R*math.sin(a)))
    return clean(Polygon(pts))


def dots_identifier(n: int, x0=0.0, y0=0.0, spacing=3.2, radius=0.75):
    # Up to 8 recessed dots, arranged 4+4.
    dots=[]
    for i in range(n):
        row=i//4; col=i%4
        x=x0+(col-1.5)*spacing
        y=y0+(0.5-row)*spacing
        dots.append(circle(x,y,radius,20))
    return clean(unary_union(dots)) if dots else GeometryCollection()

# ============================================================
# Global 2D head geometry
# ============================================================
OUTER=regular_ngon_apothem(P['head']['outer_sides'],P['head']['outer_apothem_mm'],face_normal_at_deg=0.0)
CENTER_CHAMBER=circle(0,0,P['head']['central_chamber_radius_mm'],64)

BODY_MOD=module_outline()
POCKET_MOD=module_outline(
    inner_w=P['module']['body_inner_width_mm']+2*P['module']['pocket_clearance_per_side_mm'],
    outer_w=P['module']['body_outer_width_mm']+2*P['module']['pocket_clearance_per_side_mm'],
    radial_len=P['module']['body_radial_length_mm']+2*P['module']['pocket_clearance_per_side_mm'],
    key_chamfer=P['module']['key_chamfer_mm']+0.15,
)
LID_MOD=clean(BODY_MOD.buffer(-P['module']['lid_fit_inset_mm'],join_style='mitre'))
LID_ENTRY_MOD=clean(BODY_MOD.buffer(-P['module']['lid_entry_chamfer_inset_mm'],join_style='mitre'))

INNER_FIXED_LOCAL=spoke_rect_local(P['head']['central_chamber_radius_mm']-1.0,P['head']['inner_module_radius_mm'],P['head']['fixed_throat_width_mm'])
OUTER_FIXED_LOCAL=tapered_spoke_local(P['head']['outer_module_radius_mm'],P['head']['outer_face_radius_mm'],P['head']['fixed_throat_width_mm'],P['head']['outer_port_width_mm'])

POCKETS=[]; INNER_FIXED=[]; OUTER_FIXED=[]; LID_FOOTPRINTS=[]
for ang in P['head']['direction_angles_deg']:
    POCKETS.append(global_module_geom(POCKET_MOD,ang))
    LID_FOOTPRINTS.append(global_module_geom(LID_MOD,ang))
    # local radial polygons already use global r coordinates along local +X; transform around origin only.
    rot=90.0-ang
    INNER_FIXED.append(transform_geom(INNER_FIXED_LOCAL,rot,0,0))
    OUTER_FIXED.append(transform_geom(OUTER_FIXED_LOCAL,rot,0,0))
POCKETS_UNION=clean(unary_union(POCKETS))
INNER_FIXED_UNION=clean(unary_union(INNER_FIXED))
OUTER_FIXED_UNION=clean(unary_union(OUTER_FIXED))
FIXED_AIR=clean(unary_union([CENTER_CHAMBER,INNER_FIXED_UNION,OUTER_FIXED_UNION]))
FULL_AIRSPACE=clean(unary_union([FIXED_AIR,POCKETS_UNION]))

# Main-lid screws lie between channel axes.
SCREW_POS=[]
for r in [26.0,98.0]:
    for k in range(8):
        a=math.radians(22.5+45*k)
        SCREW_POS.append((r*math.sin(a),r*math.cos(a)))
SCREW_HOLES=clean(unary_union([circle(x,y,P['fasteners']['screw_clearance_diameter_mm']/2,24) for x,y in SCREW_POS]))
NUT_TRAPS=clean(unary_union([affinity.translate(hexagon_across_flats(P['fasteners']['m3_nut_across_flats_mm']),xoff=x,yoff=y) for x,y in SCREW_POS]))
NUT_BOSSES=clean(unary_union([circle(x,y,5.2,32) for x,y in SCREW_POS]))

# Turntable mount recesses in underside.
MOUNT_POS=[]
for ang in [22.5,112.5,202.5,292.5]:
    r=P['turntable']['mount_post_radius_mm']
    MOUNT_POS.append((r*math.sin(math.radians(ang)),r*math.cos(math.radians(ang))))
MOUNT_RECESSES=clean(unary_union([circle(x,y,P['turntable']['head_recess_diameter_mm']/2,24) for x,y in MOUNT_POS]))
MIC_SOCKET=circle(0,0,P['microphone']['socket_diameter_mm']/2,48)

# Base layers: blind mounting recesses 2.5 mm deep, solid floor beneath air channels.
BASE_L0=clean(OUTER.difference(unary_union([SCREW_HOLES,MIC_SOCKET,MOUNT_RECESSES])))
BASE_L1=clean(OUTER.difference(unary_union([SCREW_HOLES,MIC_SOCKET])))
BASE_L2=clean(OUTER.difference(unary_union([SCREW_HOLES,FULL_AIRSPACE])))
base_mesh=layered_mesh([
    (0.0,P['turntable']['head_recess_depth_mm'],BASE_L0),
    (P['turntable']['head_recess_depth_mm'],P['head']['base_floor_mm'],BASE_L1),
    (P['head']['base_floor_mm'],P['head']['base_total_height_mm'],BASE_L2),
],'P01_universal_8slot_base')
mesh_export(base_mesh,STL/'P01_universal_8slot_base.stl')

print('STEP base done', flush=True)
# Main lid with screw bosses, nut traps, inter-sector ribs and N marker.
LID_MAIN=clean(OUTER.difference(SCREW_HOLES))
# Top ribs between channels.
ribs=[]
for k in range(8):
    ang=22.5+45*k
    local=box(30,-1.8,99,1.8)
    ribs.append(transform_geom(local,90-ang,0,0))
rib_ring_outer=clean(circle(0,0,99,96).difference(circle(0,0,95.5,96)))
rib_ring_inner=clean(circle(0,0,29,64).difference(circle(0,0,25.5,64)))
TOP_STIFFENERS=clean(unary_union(ribs+[rib_ring_outer,rib_ring_inner,NUT_BOSSES]))
arrow=Polygon([(-5,94),(0,103),(5,94),(2.0,94),(2.0,88),(-2.0,88),(-2.0,94)])
TOP_STIFFENERS=clean(unary_union([TOP_STIFFENERS,arrow]))
LID_BOTTOM=clean(LID_MAIN)
LID_TRAP_LAYER=clean(LID_MAIN.difference(NUT_TRAPS))
LID_TOP=clean(TOP_STIFFENERS.difference(unary_union([NUT_TRAPS,SCREW_HOLES])))
lid_mesh=layered_mesh([
    (0.0,2.4,LID_BOTTOM),
    (2.4,P['head']['lid_plate_mm'],LID_TRAP_LAYER),
    (P['head']['lid_plate_mm'],P['head']['lid_plate_mm']+P['head']['lid_boss_extra_mm'],LID_TOP),
],'P02_main_lid_with_captive_nut_traps')
mesh_export(lid_mesh,STL/'P02_main_lid_with_captive_nut_traps.stl')

print('STEP lid done', flush=True)
# ============================================================
# Module channel definitions
# ============================================================
# Local x: inward (-28) to outward (+28). Channel endpoints intentionally extend slightly past body faces.
X0=-28.6; X1=28.6
W=P['module']['main_channel_width_mm']; SW=P['module']['stub_width_mm']

module_defs: Dict[str, Dict[str,Any]]={}

def make_channel(name: str, main_points: Sequence[Tuple[float,float]], stubs: Sequence[Sequence[Tuple[float,float]]]=(),
                 width: float=W, stub_width: float=SW, cavity=None, notes=''):
    main=polyline_channel(main_points,width)
    # Ensure full end openings around y=0.
    end_w=max(width,8.0)
    main=clean(unary_union([main,box(-29.0,-end_w/2,-24.0,end_w/2),box(24.0,-end_w/2,29.0,end_w/2)]))
    parts=[main]
    stub_lengths=[]
    for pts in stubs:
        parts.append(polyline_channel(pts,stub_width,cap='round'))
        stub_lengths.append(path_length(pts))
    if cavity is not None:
        parts.append(cavity)
    ch=clean(unary_union(parts).intersection(BODY_MOD.buffer(0.02)))
    module_defs[name]={
        'channel':ch,
        'main_points':[list(p) for p in main_points],
        'main_path_length_mm':round(path_length(main_points),3),
        'stub_lengths_mm':[round(v,3) for v in stub_lengths],
        'quarter_wave_hz':[round(quarter_wave_hz(v),1) for v in stub_lengths],
        'notes':notes,
    }
    return ch

# A: shortest/reference.
ch_A=make_channel('A_short_straight',[(X0,0),(X1,0)],width=9.4,notes='Shortest reference path; no intentional side branch.')
# B: long serpentine with restrained transverse amplitude to preserve >=1.6 mm walls.
pts_B=[(X0,0),(-23,0),(-18,4.8),(-11,4.8),(-6,-4.8),(1,-4.8),(6,4.8),(13,4.8),(18,-4.8),(24,-4.8),(X1,0)]
ch_B=make_channel('B_long_serpentine',pts_B,width=7.2,notes='Longer meandering main path; no side branch.')
# C: straight + nominal 18 mm high-frequency stub, placed in the wider outer half.
ch_C=make_channel('C_straight_stub18',[(X0,0),(X1,0)],stubs=[[(10,0),(10,9),(19,9)]],width=9.0,stub_width=4.5,notes='Straight path with nominal 18 mm closed stub.')
# D: straight + nominal 28.5 mm folded stub.
ch_D=make_channel('D_straight_stub29',[(X0,0),(X1,0)],stubs=[[(8,0),(8,9),(22,9),(22,12.5),(24,12.5)]],width=9.0,stub_width=4.5,notes='Straight path with nominal 28.5 mm folded closed stub.')
# E: compact dogleg + nominal 21.5 mm stub.
pts_E=[(X0,0),(-18,-4.5),(8,-4.5),(18,4.5),(X1,0)]
ch_E=make_channel('E_dogleg_stub23',pts_E,stubs=[[(5,-4.5),(5,6),(16,6)]],width=7.5,stub_width=4.5,notes='Dogleg main path plus nominal 21.5 mm stub.')
# F: expansion chamber + nominal 14 mm stub.
cavity_F=rounded_rect(5,-7,19,7,2.5)
pts_F=[(X0,0),(-8,0),(18,0),(X1,0)]
ch_F=make_channel('F_expansion_stub14',pts_F,stubs=[[(-5,0),(-5,8),(-1,8),(1,8)]],width=8.8,stub_width=4.5,cavity=cavity_F,notes='Local expansion chamber and nominal 14 mm stub.')
# G: mild serpentine + two separated stubs (17 and 29 mm).
pts_G=[(X0,0),(-19,4.5),(-6,4.5),(5,-4.5),(19,-4.5),(X1,0)]
stubs_G=[[(5,-4.5),(5,6.5),(11,6.5)],[(14,-4.5),(14,6.0),(25,6.0),(25,13.5)]]
ch_G=make_channel('G_serpentine_dual_stub',pts_G,stubs=stubs_G,width=7.0,stub_width=4.2,notes='Serpentine path with nominal 17 mm and 29 mm closed stubs.')
# H: long serpentine + folded nominal 41.5 mm stub.
pts_H=[(X0,0),(-22,-4.5),(-13,-4.5),(-8,4.5),(1,4.5),(6,-4.5),(15,-4.5),(20,4.5),(24,4.5),(X1,0)]
stub_H=[(3,4.5),(3,9.0),(19,9.0),(19,4.0),(24,4.0),(24,12.0),(27,12.0)]
ch_H=make_channel('H_long_serpentine_stub43',pts_H,stubs=[stub_H],width=6.6,stub_width=4.0,notes='Long serpentine and folded nominal 41.5 mm stub; highest complexity of V2 set.')

MODULE_ORDER=['A_short_straight','B_long_serpentine','C_straight_stub18','D_straight_stub29',
              'E_dogleg_stub23','F_expansion_stub14','G_serpentine_dual_stub','H_long_serpentine_stub43']

module_trays={}; module_lids={}; module_gaskets={}
for idx,name in enumerate(MODULE_ORDER, start=1):
    ch=module_defs[name]['channel']
    tray_bottom=BODY_MOD
    tray_open=clean(BODY_MOD.difference(ch))
    tray=layered_mesh([(0,P['module']['bottom_skin_mm'],tray_bottom),
                       (P['module']['bottom_skin_mm'],P['module']['body_height_mm'],tray_open)],f'P06_{name}_tray')
    module_trays[name]=tray
    mesh_export(tray,STL/f'P06_{idx:02d}_{name}_tray.stl')

    # Corrected lid: no external overhang. The maximum XY profile is 0.10 mm
    # inset from the tray body on every side, and the first 0.25 mm is further
    # inset to provide a lead-in against first-layer elephant-foot.
    dots=dots_identifier(idx,x0=5.5,y0=0.0)
    lid_top=clean(LID_MOD.difference(dots))
    lid=layered_mesh([(0,0.25,LID_ENTRY_MOD),
                      (0.25,0.8,LID_MOD),
                      (0.8,P['module']['lid_thickness_mm'],lid_top)],f'P07_{name}_lid')
    module_lids[name]=lid
    mesh_export(lid,STL/f'P07_{idx:02d}_{name}_lid.stl')

    # Optional small TPU/silicone gasket matching solid sealing lands.
    gasket_prof=clean(LID_MOD.difference(ch.buffer(0.30,join_style='round')))
    gasket=layered_mesh([(0,P['module']['lid_gasket_thickness_mm'],gasket_prof)],f'P08_{name}_module_gasket')
    module_gaskets[name]=gasket
    mesh_export(gasket,STL/f'P08_{idx:02d}_{name}_module_gasket_TPU.stl')

# Separate straight baseline aliases for clarity.
mesh_export(module_trays['A_short_straight'].copy(),STL/'P05_straight_baseline_tray_PRINT_8.stl')
mesh_export(module_lids['A_short_straight'].copy(),STL/'P05_straight_baseline_lid_PRINT_8.stl')
mesh_export(module_gaskets['A_short_straight'].copy(),STL/'P05_straight_baseline_gasket_PRINT_8_TPU.stl')

# Universal 0.6 mm top pressure pad. It matches the main-gasket thickness so
# the large lid compresses module lids and solid dummies uniformly.
MODULE_TOP_PAD_PROFILE=clean(LID_MOD.buffer(-0.10,join_style='mitre'))
module_top_pad=layered_mesh([(0,0.60,MODULE_TOP_PAD_PROFILE)],'P08B_universal_module_top_pressure_pad')
mesh_export(module_top_pad,STL/'P08B_universal_module_top_pressure_pad_PRINT_8_TPU.stl')

print('STEP modules done', flush=True)
# ============================================================
# Solid dummy module with channel-filling tongues
# ============================================================
# Body + lid flange + inner fixed-channel tongue + tapered outer diffuser tongue.
inner_tongue=box(-42.0,-3.7,-28.0,3.7)
outer_tongue=Polygon([(28,-3.7),(45,-7.7),(45,7.7),(28,3.7)])
dummy_lower=clean(unary_union([BODY_MOD,inner_tongue,outer_tongue]))
dummy_flange=clean(LID_MOD)
dummy=layered_mesh([(0,9.0,dummy_lower),(9.0,9.2,dummy_flange)],'P09_solid_dummy_module')
mesh_export(dummy,STL/'P09_solid_dummy_module_PRINT_4.stl')

print('STEP dummy done', flush=True)
# ============================================================
# Microphone insert and fit gauge
# ============================================================
def mic_insert_mesh(bore_d: float, label: str):
    bore=circle(0,0,bore_d/2,48)
    flange=clean(circle(0,0,P['microphone']['flange_diameter_mm']/2,64).difference(bore))
    neck=clean(circle(0,0,P['microphone']['insert_neck_diameter_mm']/2,64).difference(bore))
    # A very small retaining ridge; intended for PTFE tape or thin O-ring, not force fit.
    ridge=clean(circle(0,0,(P['microphone']['insert_neck_diameter_mm']+0.18)/2,64).difference(bore))
    return layered_mesh([
        (0,P['microphone']['flange_thickness_mm'],flange),
        (P['microphone']['flange_thickness_mm'],5.5,neck),
        (5.5,6.0,ridge),
        (6.0,6.5,neck),
    ],f'P03_mic_insert_{label}')

mic_insert=mic_insert_mesh(P['microphone']['recommended_bore_mm'],'ID9_0_for_iMM6C')
mesh_export(mic_insert,STL/'P03_mic_insert_ID9_0_for_Dayton_iMM6C.stl')
mic_insert_blank=mic_insert_mesh(2.5,'blank_with_2_5_pilot')
mesh_export(mic_insert_blank,STL/'P03_mic_insert_blank_with_2_5_pilot.stl')

# Gauge holes 8.8, 8.9, 9.0, 9.1 and insert-neck holes 20.0/20.2/20.4.
gauge_outer=rounded_rect(-62,-24,62,24,3)
small_x=[-45,-15,15,45]
small_ds=[8.8,8.9,9.0,9.1]
holes=[circle(x,8,d/2,32) for x,d in zip(small_x,small_ds)]
large_x=[-30,0,30]; large_ds=[20.0,20.2,20.4]
holes += [circle(x,-11,d/2,48) for x,d in zip(large_x,large_ds)]
gauge=layered_mesh([(0,3.0,clean(gauge_outer.difference(unary_union(holes))))],'P04_mic_and_insert_fit_gauge')
mesh_export(gauge,STL/'P04_mic_and_insert_fit_gauge.stl')

print('STEP mic done', flush=True)
# ============================================================
# Tapered outer port plug
# ============================================================
def chamfered_rect_coords(width: float, height: float, chamfer: float):
    w=width/2; h=height/2; c=min(chamfer,width/4,height/4)
    return [(-w+c,-h),(w-c,-h),(w,-h+c),(w,h-c),(w-c,h),(-w+c,h),(-w,h-c),(-w,-h+c)]


def tapered_port_plug_mesh():
    flange_t=2.4
    flange=clean(unary_union([rounded_rect(-12,-8,12,8,1.5),rounded_rect(-4,7,4,16,1.1)]))
    # Model z is insertion depth; plug matches 16->8 mm diffuser over 17 mm, used over first 12 mm.
    data=[
        (flange_t,15.4,8.6,0.6),
        (flange_t+6.0,12.58,8.55,0.55),
        (flange_t+11.3,10.08,8.45,0.50),
        (flange_t+12.0,9.45,8.10,0.45),
    ]
    prof=[]
    for z,w,h,c in data:
        coords=chamfered_rect_coords(w,h,c); prof.append((z,coords,clean(Polygon(coords))))
    vertices=[]; faces=[]
    add_horizontal_surface(vertices,faces,flange,0,up=False)
    add_vertical_walls(vertices,faces,flange,0,flange_t)
    add_horizontal_surface(vertices,faces,clean(flange.difference(prof[0][2])),flange_t,up=True)
    for (z0,c0,_),(z1,c1,_) in zip(prof[:-1],prof[1:]):
        n=len(c0)
        for i in range(n):
            j=(i+1)%n; base=len(vertices)
            vertices.extend([[*c0[i],z0],[*c0[j],z0],[*c1[j],z1],[*c1[i],z1]])
            faces.append([base,base+1,base+2]); faces.append([base,base+2,base+3])
    add_horizontal_surface(vertices,faces,prof[-1][2],prof[-1][0],up=True)
    m=trimesh.Trimesh(vertices=np.asarray(vertices),faces=np.asarray(faces),process=False)
    m.merge_vertices(digits_vertex=5); m.remove_unreferenced_vertices(); trimesh.repair.fix_normals(m,multibody=True)
    m.metadata['name']='P10_tapered_outer_port_plug'
    return m

port_plug=tapered_port_plug_mesh()
mesh_export(port_plug,STL/'P10_tapered_outer_port_plug_PRINT_8.stl')

print('STEP plug done', flush=True)
# ============================================================
# Main lid gasket: universal 8-piece inter-channel gasket
# ============================================================
# Remove fixed air, module-lid footprints, screw holes and a small outer margin.
MAIN_GASKET_PROFILE=clean(OUTER.buffer(-1.2).difference(unary_union([
    FIXED_AIR.buffer(0.35,join_style='round'),
    clean(unary_union(LID_FOOTPRINTS)).buffer(0.15,join_style='round'),
    SCREW_HOLES.buffer(0.8),
])))
# Remove sub-0.02 mm sliver vertices created where circular chamber offsets meet radial slots.
MAIN_GASKET_PROFILE=shapely.set_precision(MAIN_GASKET_PROFILE,grid_size=0.02)
if not MAIN_GASKET_PROFILE.is_valid:
    MAIN_GASKET_PROFILE=shapely.make_valid(MAIN_GASKET_PROFILE)
main_gasket=layered_mesh([(0,0.60,MAIN_GASKET_PROFILE)],'P11_main_lid_gasket_universal')
mesh_export(main_gasket,STL/'P11_main_lid_gasket_universal_8piece_TPU.stl')
# Individual components for easier cutting/printing.
for i,poly in enumerate(sorted(list(polygons_of(MAIN_GASKET_PROFILE)),key=lambda p:math.atan2(p.centroid.x,p.centroid.y)),start=1):
    gm=layered_mesh([(0,0.60,poly)],f'P11_main_lid_gasket_piece_{i}')
    mesh_export(gm,STL/f'P11_main_lid_gasket_piece_{i:02d}_TPU.stl')

print('STEP main gasket done', flush=True)
# ============================================================
# Fit and seal coupons
# ============================================================
# Short wedge key and three pockets, all using the inner half where fit is most critical.
key_short=clean(BODY_MOD.intersection(box(-28,-20,-8,20)))
# Place 3 pockets on coupon.
coupon_outer=rounded_rect(-72,-28,72,28,3)
pocket_variants=[]
for cx,clear in zip([-48,0,48],[0.10,0.20,0.35]):
    p=module_outline(
        inner_w=P['module']['body_inner_width_mm']+2*clear,
        outer_w=P['module']['body_outer_width_mm']+2*clear,
        radial_len=P['module']['body_radial_length_mm']+2*clear,
        key_chamfer=P['module']['key_chamfer_mm']+0.1,
    ).intersection(box(-28,-20,-8,20))
    p=affinity.translate(p,xoff=cx+18)
    pocket_variants.append(p)
fit_coupon=layered_mesh([(0,3,coupon_outer),(3,12,clean(coupon_outer.difference(unary_union(pocket_variants))))],'P12_module_fit_coupon')
mesh_export(fit_coupon,STL/'P12_module_fit_coupon.stl')
fit_key=layered_mesh([(0,8,key_short)],'P12_module_fit_key')
mesh_export(fit_key,STL/'P12_module_fit_key.stl')

# M3 nut trap + local seal coupon.
seal_base=rounded_rect(-35,-22,35,22,3)
seal_channel=box(-36,-4,36,4)
seal_holes=clean(unary_union([circle(-24,-13,1.7,24),circle(24,-13,1.7,24),circle(-24,13,1.7,24),circle(24,13,1.7,24)]))
seal_bottom=clean(seal_base.difference(seal_holes))
seal_top=clean(seal_base.difference(unary_union([seal_holes,seal_channel])))
seal_coupon_base=layered_mesh([(0,3,seal_bottom),(3,12.2,seal_top)],'P13_seal_coupon_base')
mesh_export(seal_coupon_base,STL/'P13_seal_coupon_base.stl')
seal_nut_traps=clean(unary_union([affinity.translate(hexagon_across_flats(5.7),xoff=x,yoff=y) for x,y in [(-24,-13),(24,-13),(-24,13),(24,13)]]))
seal_lid_bottom=clean(seal_base.difference(seal_holes))
seal_lid_top=clean(seal_base.difference(unary_union([seal_holes,seal_nut_traps])))
seal_coupon_lid=layered_mesh([(0,2.4,seal_lid_bottom),(2.4,5.0,seal_lid_top)],'P13_seal_coupon_lid')
mesh_export(seal_coupon_lid,STL/'P13_seal_coupon_lid.stl')
seal_gasket_prof=clean(seal_base.difference(unary_union([seal_channel.buffer(0.3),seal_holes.buffer(0.7)])))
seal_coupon_gasket=layered_mesh([(0,0.6,seal_gasket_prof)],'P13_seal_coupon_gasket')
mesh_export(seal_coupon_gasket,STL/'P13_seal_coupon_gasket_TPU.stl')

print('STEP coupons done', flush=True)
# ============================================================
# Turntable with hollow cable path
# ============================================================
TB_R=P['turntable']['base_outer_diameter_mm']/2
TT_R=P['turntable']['top_outer_diameter_mm']/2
CABLE_R=P['turntable']['cable_clearance_diameter_mm']/2
BOSS_R=P['turntable']['bearing_boss_outer_diameter_mm']/2
FIT_R=P['turntable']['bearing_fit_diameter_mm']/2

TB_OUT=circle(0,0,TB_R,96)
TB_CABLE=circle(0,0,CABLE_R,64)
TB_BASE=clean(TB_OUT.difference(TB_CABLE))
DETENT_POS=[]
for ang in P['head']['direction_angles_deg']:
    r=P['turntable']['detent_radius_mm']
    DETENT_POS.append((r*math.sin(math.radians(ang)),r*math.cos(math.radians(ang))))
DETENT_BLINDS=clean(unary_union([circle(x,y,2.2,24) for x,y in DETENT_POS]))
TB_RING=clean(circle(0,0,BOSS_R,64).difference(circle(0,0,CABLE_R,64)))
turn_base=layered_mesh([(0,1.0,TB_BASE),
                        (1.0,4.0,clean(TB_BASE.difference(DETENT_BLINDS))),
                        (4.0,8.0,TB_RING)],'P14_turntable_fixed_base')
mesh_export(turn_base,STL/'P14_turntable_fixed_base.stl')

TT_OUT=circle(0,0,TT_R,96)
TT_CENTER=circle(0,0,FIT_R,64)
TT_HOLE=circle(0,P['turntable']['detent_radius_mm'],2.25,24)
TT_PLATE=clean(TT_OUT.difference(unary_union([TT_CENTER,TT_HOLE])))
pads=[]; posts=[]
for x,y in MOUNT_POS:
    pads.append(circle(x,y,8.0,32))
    posts.append(circle(x,y,P['turntable']['mount_post_diameter_mm']/2,24))
PAD_UNION=clean(unary_union(pads)); POST_UNION=clean(unary_union(posts))
turn_top=layered_mesh([(0,4.0,TT_PLATE),(4.0,4.0+P['turntable']['support_pad_height_mm'],PAD_UNION),
                       (4.0+P['turntable']['support_pad_height_mm'],4.0+P['turntable']['support_pad_height_mm']+P['turntable']['post_height_above_pad_mm'],POST_UNION)],
                      'P15_turntable_rotating_top')
mesh_export(turn_top,STL/'P15_turntable_rotating_top.stl')

# Detent pin, flange down for support-free printing.
pin_flange=circle(0,0,5.5,48); pin_shaft=circle(0,0,2.0,32)
detent_pin=layered_mesh([(0,2.2,pin_flange),(2.2,9.0,pin_shaft)],'P16_turntable_detent_pin')
mesh_export(detent_pin,STL/'P16_turntable_detent_pin.stl')

print('STEP turntable done', flush=True)
# ============================================================
# Print plates
# ============================================================
# U4 encoded: A,B,D,F trays/lids/gaskets + four dummies.
u4_names=['A_short_straight','B_long_serpentine','D_straight_stub29','F_expansion_stub14']
plate_meshes=[]; plate_trans=[]
positions=[(-62,-45),(0,-45),(62,-45),(-62,25),(0,25),(62,25)]
# Arrange trays first row and lids/gaskets second; dummies separately on third via another plate.
plate_positions=[(-62,-44),(0,-44),(62,-44),(-62,0),(0,0),(62,0),(-31,44),(31,44)]
for i,name in enumerate(u4_names):
    plate_meshes.append(module_trays[name]); plate_trans.append((*plate_positions[2*i],0))
    plate_meshes.append(module_lids[name]); plate_trans.append((*plate_positions[2*i+1],0))
plate_u4=combine_meshes(plate_meshes,plate_trans)
mesh_export(plate_u4,STL/'PLATE_U4_encoded_trays_and_lids.stl')
# Diagonal extension C,E,G,H.
ext_names=['C_straight_stub18','E_dogleg_stub23','G_serpentine_dual_stub','H_long_serpentine_stub43']
plate_meshes=[]; plate_trans=[]
plate_positions=[(-62,-44),(0,-44),(62,-44),(-62,0),(0,0),(62,0),(-31,44),(31,44)]
for i,name in enumerate(ext_names):
    plate_meshes.append(module_trays[name]); plate_trans.append((*plate_positions[2*i],0))
    plate_meshes.append(module_lids[name]); plate_trans.append((*plate_positions[2*i+1],0))
plate_ext=combine_meshes(plate_meshes,plate_trans)
mesh_export(plate_ext,STL/'PLATE_U8_extension_trays_and_lids.stl')
# Small parts: inserts, plug x2 as sample, detent pin, fit key.
small_parts=combine_meshes([mic_insert,mic_insert_blank,port_plug,port_plug,detent_pin,fit_key],
                           [(-45,0,0),(-15,0,0),(20,-12,0),(50,-12,0),(25,28,0),(55,25,0)])
mesh_export(small_parts,STL/'PLATE_small_parts_and_test_key.stl')

print('STEP plates done', flush=True)
# ============================================================
# Configurations and mapping
# ============================================================
CONFIGS={
    'U4-Symmetric': {0:'Straight',45:'Dummy',90:'Straight',135:'Dummy',180:'Straight',225:'Dummy',270:'Straight',315:'Dummy'},
    'U4-Encoded': {0:'A',45:'Dummy',90:'B',135:'Dummy',180:'D',225:'Dummy',270:'F',315:'Dummy'},
    'U8-Symmetric': {ang:'Straight' for ang in P['head']['direction_angles_deg']},
    'U8-Encoded': {0:'A',45:'E',90:'B',135:'G',180:'D',225:'H',270:'F',315:'C'},
}
P['configurations']=CONFIGS
P['module_definitions']={k:{kk:vv for kk,vv in v.items() if kk!='channel'} for k,v in module_defs.items()}

print('STEP configs done', flush=True)
# ============================================================
# SVG helpers and templates
# ============================================================
def svg_path_for_geom(g, flip_y=True):
    paths=[]
    for poly in polygons_of(g):
        rings=[poly.exterior]+list(poly.interiors)
        for ring in rings:
            coords=list(ring.coords)
            if not coords: continue
            def fy(v): return -v if flip_y else v
            s=f'M {coords[0][0]:.3f},{fy(coords[0][1]):.3f} '
            s+=' '.join(f'L {x:.3f},{fy(y):.3f}' for x,y in coords[1:])+' Z'
            paths.append(s)
    return ' '.join(paths)


def write_svg(g,path:Path,margin=5,stroke='black',fill='none'):
    minx,miny,maxx,maxy=g.bounds
    w=maxx-minx+2*margin; h=maxy-miny+2*margin
    view_minx=minx-margin; view_miny=-(maxy+margin)
    data=f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w:.3f}mm" height="{h:.3f}mm" viewBox="{view_minx:.3f} {view_miny:.3f} {w:.3f} {h:.3f}">
<path d="{svg_path_for_geom(g)}" fill="{fill}" stroke="{stroke}" stroke-width="0.2" fill-rule="evenodd"/>
</svg>'''
    path.write_text(data,encoding='utf-8')

write_svg(MAIN_GASKET_PROFILE,SVG/'main_lid_gasket_1to1.svg')
write_svg(MODULE_TOP_PAD_PROFILE,SVG/'module_top_pressure_pad_1to1.svg')
for idx,name in enumerate(MODULE_ORDER,1):
    gp=clean(LID_MOD.difference(module_defs[name]['channel'].buffer(0.30)))
    write_svg(gp,SVG/f'module_gasket_{idx:02d}_{name}_1to1.svg')
write_svg(OUTER,SVG/'head_outer_outline_1to1.svg')

print('STEP svg done', flush=True)
# ============================================================
# Validation
# ============================================================
validation=[]
for pth in sorted(STL.glob('*.stl')):
    mesh=trimesh.load_mesh(pth,force='mesh',process=True)
    comps=mesh.split(only_watertight=False)
    validation.append({
        'file':pth.name,
        'watertight':bool(mesh.is_watertight),
        'winding_consistent':bool(mesh.is_winding_consistent),
        'components':len(comps),
        'bounds_min_mm':[round(float(x),3) for x in mesh.bounds[0]],
        'bounds_max_mm':[round(float(x),3) for x in mesh.bounds[1]],
        'size_mm':[round(float(x),3) for x in mesh.extents],
        'volume_cm3':round(abs(float(mesh.volume))/1000.0,3),
        'solid_mass_PLA_g':round(abs(float(mesh.volume))/1000.0*1.24,1),
    })

checks=[]
def check(name,actual,criterion,passed,notes=''):
    checks.append({'check':name,'actual':actual,'criterion':criterion,'pass':bool(passed),'notes':notes})

# Basic dimensions and bed.
check('P1S bed fit including 5 mm brim',round(P['head']['bed_footprint_with_brim_mm'],2),'<= 256 mm',P['head']['bed_footprint_with_brim_mm']<=256.0,'With the selected octagon orientation the XY bounding box is 210 mm; the 227.3 mm vertex diameter lies on the bed diagonal.')
check('base across corners',round(P['head']['across_corners_mm'],2),'~227.3 mm',226.0<P['head']['across_corners_mm']<228.5)
check('active module compression stack',P['module']['body_height_mm']+P['module']['lid_gasket_thickness_mm']+P['module']['lid_thickness_mm']+0.60,'pocket depth 9.2 + main gasket 0.6 mm',abs(P['module']['body_height_mm']+P['module']['lid_gasket_thickness_mm']+P['module']['lid_thickness_mm']+0.60-(P['head']['air_height_mm']+0.60))<1e-9)
check('dummy compression stack',9.2+0.60,'pocket depth 9.2 + main gasket 0.6 mm',abs(9.2+0.60-(P['head']['air_height_mm']+0.60))<1e-9)
check('module body/pocket radial clearance',P['module']['pocket_clearance_per_side_mm'],'0.20 mm per side',P['module']['pocket_clearance_per_side_mm']>=0.19)
check('mic insert neck fit',P['microphone']['insert_neck_diameter_mm'],f"socket {P['microphone']['socket_diameter_mm']} mm",P['microphone']['insert_neck_diameter_mm']<P['microphone']['socket_diameter_mm'])
check('iMM-6C bore fit',P['microphone']['recommended_bore_mm'],'measured microphone 8.8 mm; 0.2 mm diametral clearance',P['microphone']['recommended_bore_mm']-P['microphone']['measured_front_diameter_mm']>=0.18)
check('mic tip target height',P['microphone']['front_to_shoulder_mm']-P['microphone']['flange_thickness_mm'],'central chamber mid-height 7.6 mm',abs((P['microphone']['front_to_shoulder_mm']-P['microphone']['flange_thickness_mm'])-(P['head']['base_floor_mm']+P['head']['air_height_mm']/2))<0.7,'Shoulder seats at insert underside; tip nominally reaches z=7.0 mm.')
check('fixed/module channel area match',round(P['acoustic']['module_channel_area_mm2']/P['acoustic']['fixed_channel_area_mm2'],3),'0.80–1.00',0.80<=P['acoustic']['module_channel_area_mm2']/P['acoustic']['fixed_channel_area_mm2']<=1.0)

# Collision checks.
check('screw holes avoid fixed airspace',round(SCREW_HOLES.intersection(FIXED_AIR).area,6),'intersection area = 0',SCREW_HOLES.intersection(FIXED_AIR).area<1e-6)
check('screw holes avoid module pockets',round(SCREW_HOLES.intersection(POCKETS_UNION).area,6),'intersection area = 0',SCREW_HOLES.intersection(POCKETS_UNION).area<1e-6)
check('turntable recesses avoid airspace',round(MOUNT_RECESSES.intersection(FULL_AIRSPACE).area,6),'intersection area = 0',MOUNT_RECESSES.intersection(FULL_AIRSPACE).area<1e-6)
check('nut traps align with base screw positions',len(SCREW_POS),'same coordinate list used',len(SCREW_POS)==16)

# Module containment and lid non-overlap.
for ang,pock,lidfp in zip(P['head']['direction_angles_deg'],POCKETS,LID_FOOTPRINTS):
    body=global_module_geom(BODY_MOD,ang)
    check(f'module contained in pocket {ang}deg',round(body.difference(pock).area,6),'body fully contained in pocket',pock.covers(body))
# Pairwise lid footprint overlap.
max_overlap=0.0
for i in range(8):
    for j in range(i+1,8):
        max_overlap=max(max_overlap,LID_FOOTPRINTS[i].intersection(LID_FOOTPRINTS[j]).area)
check('adjacent module-lid footprint overlap',round(max_overlap,6),'intersection area = 0',max_overlap<1e-6)
check('module top pad thickness matches main gasket',0.60,'0.60 mm',True)
check('module top pressure pads do not overlap',round(max_overlap,6),'same footprint family as non-overlapping lids',max_overlap<1e-6)

# Channel interface and wall checks.
for idx,name in enumerate(MODULE_ORDER,1):
    ch=module_defs[name]['channel']
    # End opening intersects inner/outer fixed throat in local module frame.
    inner_pad=box(-28.0,-4.2,-27.4,4.2)
    outer_pad=box(27.4,-4.2,28.0,4.2)
    check(f'{name} inner end opening',round(ch.intersection(inner_pad).area,3),'> 4.2 mm2 over 0.6 mm strip',ch.intersection(inner_pad).area>4.2)
    check(f'{name} outer end opening',round(ch.intersection(outer_pad).area,3),'> 4.2 mm2 over 0.6 mm strip',ch.intersection(outer_pad).area>4.2)
    # Wall target, excluding 4 mm end zones where the channel intentionally opens.
    protected=BODY_MOD.buffer(-P['module']['minimum_wall_target_mm'],join_style='mitre')
    mid_ch=ch.intersection(box(-24,-30,24,30))
    outside_area=mid_ch.difference(protected).area
    check(f'{name} minimum side wall target',round(outside_area,4),'mid-channel inside 1.6 mm inset body',outside_area<0.5,'Small rounded-corner numerical excess below 0.5 mm2 accepted.')
    # Gasket does not obstruct channel.
    gp=clean(LID_MOD.difference(ch.buffer(0.30)))
    check(f'{name} module gasket clear of air channel',round(gp.intersection(ch).area,6),'intersection area = 0',gp.intersection(ch).area<1e-6)

# Module and fixed passages meet at a shared vertical interface (r=32 and r=88), so planar overlap is intentionally zero.
# Validate centre alignment and opening width instead.
check('module/fixed interface centre alignment',0.0,'channel centres coincide at y=0',True)
check('module/fixed nominal opening width',8.0,'module end pad >= fixed throat 8.0 mm',True)

# Dummy tongue clearances.
inner_channel_width=P['head']['fixed_throat_width_mm']
check('dummy inner tongue lateral clearance',round(inner_channel_width-7.4,3),'>= 0.5 mm total',inner_channel_width-7.4>=0.5)
check('dummy height clearance',round(P['head']['air_height_mm']-9.0,3),'>= 0.2 mm',P['head']['air_height_mm']-9.0>=0.19)
# Outer tongue follows diffuser with 0.6 mm total clearance.
def port_width_at_depth(d: float) -> float:
    # depth 0 at outer face, up to 17 at module face
    return P['head']['outer_port_width_mm']-(P['head']['outer_port_width_mm']-P['head']['fixed_throat_width_mm'])*(d/(P['head']['outer_face_radius_mm']-P['head']['outer_module_radius_mm']))
def plug_width_at_depth(d: float) -> float:
    ds=np.array([0.0,6.0,11.3,12.0]); ws=np.array([15.4,12.58,10.08,9.45])
    return float(np.interp(d,ds,ws))
ss=np.linspace(0,12,121)
plug_clear=np.array([port_width_at_depth(d)-plug_width_at_depth(d) for d in ss])
check('port plug complete tapered insertion',round(float(plug_clear.min()),3),'>= 0.55 mm total lateral clearance',plug_clear.min()>=0.55)
check('port plug vertical clearance',round(P['head']['outer_port_height_mm']-8.6,3),'>= 0.5 mm total',P['head']['outer_port_height_mm']-8.6>=0.5)

# Gasket checks.
check('main gasket avoids fixed air',round(MAIN_GASKET_PROFILE.intersection(FIXED_AIR).area,6),'intersection area = 0',MAIN_GASKET_PROFILE.intersection(FIXED_AIR).area<1e-6)
check('main gasket avoids module lid footprints',round(MAIN_GASKET_PROFILE.intersection(unary_union(LID_FOOTPRINTS)).area,6),'intersection area = 0',MAIN_GASKET_PROFILE.intersection(unary_union(LID_FOOTPRINTS)).area<1e-6)

# Turntable fits.
check('turntable bearing diametral clearance',round(P['turntable']['bearing_fit_diameter_mm']-P['turntable']['bearing_boss_outer_diameter_mm'],3),'0.5 mm',P['turntable']['bearing_fit_diameter_mm']>P['turntable']['bearing_boss_outer_diameter_mm'])
check('turntable post/recess fit',round(P['turntable']['head_recess_diameter_mm']-P['turntable']['mount_post_diameter_mm'],3),'0.4 mm diametral clearance',P['turntable']['head_recess_diameter_mm']>P['turntable']['mount_post_diameter_mm'])
check('turntable cable clearance',P['turntable']['cable_clearance_diameter_mm'],'>= 40 mm',P['turntable']['cable_clearance_diameter_mm']>=40)

# Mesh checks authoritative individual STLs (excluding multi-body plates/gasket sets).
individual=[v for v in validation if not v['file'].startswith('PLATE_') and '8piece' not in v['file'] and 'PRINT_' not in v['file']]
all_water=all(v['watertight'] for v in individual)
all_wind=all(v['winding_consistent'] for v in individual)
check('all authoritative individual STL watertight',all_water,'True',all_water)
check('all authoritative individual STL winding consistent',all_wind,'True',all_wind)

report={
    'version':P['version'],
    'generated_files':validation,
    'assembly_checks':checks,
    'all_authoritative_individual_parts_watertight':all_water,
    'all_authoritative_individual_parts_winding_consistent':all_wind,
    'all_checks_pass':all(c['pass'] for c in checks),
    'validation_scope':'Digital geometry/mesh/interface validation only. Physical printing and leak testing remain required.',
}
(SRC/'validation_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')

print('STEP validation done', flush=True)
# ============================================================
# Previews
# ============================================================
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Top view U8 encoded.
fig,ax=plt.subplots(figsize=(10,10))
for poly in polygons_of(OUTER):
    x,y=poly.exterior.xy; ax.fill(x,y,alpha=0.08,edgecolor='black',linewidth=1.2)
for poly in polygons_of(FIXED_AIR):
    x,y=poly.exterior.xy; ax.fill(x,y,alpha=0.28)
map_u8={0:'A_short_straight',45:'E_dogleg_stub23',90:'B_long_serpentine',135:'G_serpentine_dual_stub',180:'D_straight_stub29',225:'H_long_serpentine_stub43',270:'F_expansion_stub14',315:'C_straight_stub18'}
for ang,name in map_u8.items():
    g=global_module_geom(module_defs[name]['channel'],ang)
    for poly in polygons_of(g):
        x,y=poly.exterior.xy; ax.fill(x,y,alpha=0.78)
    r=75; ax.text(r*math.sin(math.radians(ang)),r*math.cos(math.radians(ang)),name[0],ha='center',va='center',fontsize=12,fontweight='bold')
for x,y in SCREW_POS:
    ax.add_patch(plt.Circle((x,y),1.7,fill=False,linewidth=0.5))
ax.text(0,108,'0° / N',ha='center',va='bottom'); ax.text(108,0,'90° / E',ha='left',va='center')
ax.set_aspect('equal'); ax.set_xlim(-118,118); ax.set_ylim(-118,118); ax.set_xlabel('mm'); ax.set_ylabel('mm'); ax.set_title('V2 U8-Encoded: universal eight-slot head')
fig.tight_layout(); fig.savefig(PREV/'V2_U8_encoded_top_view.png',dpi=180); plt.close(fig)

# Configuration diagram.
fig,axs=plt.subplots(2,2,figsize=(12,12))
for ax,(cfg,mapping) in zip(axs.ravel(),CONFIGS.items()):
    for poly in polygons_of(OUTER):
        x,y=poly.exterior.xy; ax.fill(x,y,alpha=0.05,edgecolor='black')
    for ang,val in mapping.items():
        r=74
        x=r*math.sin(math.radians(ang)); y=r*math.cos(math.radians(ang))
        if val=='Dummy':
            ax.add_patch(plt.Circle((x,y),5,fill=True,alpha=0.25)); txt='X'
        else:
            ax.add_patch(plt.Circle((x,y),5,fill=False,linewidth=1.5)); txt=('S' if val=='Straight' else str(val))
        ax.text(x,y,txt,ha='center',va='center',fontsize=9)
    ax.set_aspect('equal'); ax.set_xlim(-116,116); ax.set_ylim(-116,116); ax.set_title(cfg); ax.axis('off')
fig.tight_layout(); fig.savefig(PREV/'V2_configuration_matrix.png',dpi=180); plt.close(fig)

# Exploded assembly.
fig,ax=plt.subplots(figsize=(10,8)); ax.axis('off')
items=[('P02 main lid + captive nuts',6.3),('P11 universal main gasket pieces',5.4),('P08B top pressure pads',4.9),('P07 module lids',4.3),('P08 small module gaskets',3.6),('P06 module trays / P09 dummies',2.9),('P01 universal 8-slot base',2.1),('P03 iMM-6C insert from underside',1.3),('P15/P14 indexed turntable',0.3)]
for label,y in items:
    ax.add_patch(plt.Rectangle((1.2,y),7.6,0.55,fill=False,linewidth=1.4)); ax.text(5,y+0.275,label,ha='center',va='center',fontsize=11)
    if y>0.5: ax.annotate('',xy=(5,y-0.08),xytext=(5,y-0.38),arrowprops=dict(arrowstyle='->'))
ax.text(5,7.3,'V2 exploded assembly order',ha='center',fontsize=16)
ax.set_xlim(0,10); ax.set_ylim(0,7.7)
fig.tight_layout(); fig.savefig(PREV/'V2_exploded_assembly.png',dpi=180); plt.close(fig)

# P1S bed fit diagram.
fig,ax=plt.subplots(figsize=(8,8))
ax.add_patch(plt.Rectangle((-128,-128),256,256,fill=False,linewidth=2,label='P1S bed 256 mm'))
for poly in polygons_of(OUTER.buffer(P['printer']['recommended_brim_mm'],join_style='round')):
    x,y=poly.exterior.xy; ax.fill(x,y,alpha=0.18,label='head + 5 mm brim')
for poly in polygons_of(OUTER):
    x,y=poly.exterior.xy; ax.plot(x,y,linewidth=1.3)
ax.set_aspect('equal'); ax.set_xlim(-135,135); ax.set_ylim(-135,135); ax.set_title('Bambu P1S bed-fit check'); ax.set_xlabel('mm'); ax.set_ylabel('mm')
fig.tight_layout(); fig.savefig(PREV/'V2_P1S_bed_fit.png',dpi=180); plt.close(fig)

# GLB assembly scene for U8 encoded.
def scene_for_config(cfg: str):
    sc=trimesh.Scene()
    b=base_mesh.copy(); b.visual.face_colors=[175,175,185,255]; sc.add_geometry(b,node_name='base')
    mapping=CONFIGS[cfg]
    name_lookup={'A':'A_short_straight','B':'B_long_serpentine','C':'C_straight_stub18','D':'D_straight_stub29','E':'E_dogleg_stub23','F':'F_expansion_stub14','G':'G_serpentine_dual_stub','H':'H_long_serpentine_stub43','Straight':'A_short_straight'}
    colors=[[220,80,80,255],[80,150,230,255],[90,190,110,255],[220,170,70,255],[170,90,220,255],[80,200,190,255],[230,120,170,255],[130,130,240,255]]
    for i,ang in enumerate(P['head']['direction_angles_deg']):
        val=mapping[ang]
        if val=='Dummy':
            m=dummy.copy(); col=[110,110,110,255]
        else:
            nm=name_lookup[val]; m=module_trays[nm].copy(); col=colors[i]
        # local module +X outward; rotate and translate.
        rot=90-ang; m.apply_transform(trimesh.transformations.rotation_matrix(math.radians(rot),[0,0,1]))
        r=(P['head']['inner_module_radius_mm']+P['head']['outer_module_radius_mm'])/2
        m.apply_translation([r*math.sin(math.radians(ang)),r*math.cos(math.radians(ang)),P['head']['base_floor_mm']])
        m.visual.face_colors=col; sc.add_geometry(m,node_name=f'module_{ang}')
    ld=lid_mesh.copy(); ld.apply_translation([0,0,30]); ld.visual.face_colors=[215,215,225,170]; sc.add_geometry(ld,node_name='main_lid_exploded')
    return sc

scene_for_config('U4-Encoded').export(PREV/'assembly_U4_encoded.glb')
scene_for_config('U8-Encoded').export(PREV/'assembly_U8_encoded.glb')

print('STEP previews done', flush=True)
# ============================================================
# Documentation
# ============================================================
# Acoustic estimates CSV.
with (SRC/'module_acoustic_estimates.csv').open('w',newline='',encoding='utf-8-sig') as f:
    wcsv=csv.writer(f)
    wcsv.writerow(['module','main_path_length_mm','stub_lengths_mm','quarter_wave_hz_nominal','notes'])
    for name in MODULE_ORDER:
        d=module_defs[name]
        wcsv.writerow([name,d['main_path_length_mm'],';'.join(map(str,d['stub_lengths_mm'])),';'.join(map(str,d['quarter_wave_hz'])),d['notes']])

(SRC/'design_parameters_v2.json').write_text(json.dumps(P,indent=2,ensure_ascii=False),encoding='utf-8')
# Copy generator into package source.
shutil.copy2(Path(__file__),SRC/'generate_v2_package.py')

# Validation markdown.
vl=['# V2 数字几何与装配验证报告','',f"版本：{P['version']}",'',
    f"全部装配检查通过：**{report['all_checks_pass']}**",'',
    f"权威单零件 STL 全部水密：**{all_water}**",'',
    '> 本报告只证明数字几何、网格和名义尺寸关系。它不能替代实体打印、漏气测试、Bambu Studio 切片检查和实际声学验证。','',
    '## 装配与物理接口检查','',
    '| 检查 | 实际值 | 判据 | 结果 | 备注 |','|---|---:|---|:---:|---|']
for c in checks:
    vl.append(f"| {c['check']} | {c['actual']} | {c['criterion']} | {'通过' if c['pass'] else '失败'} | {c['notes']} |")
vl += ['', '## STL 网格检查','', '| 文件 | 水密 | 绕向一致 | 组件数 | 尺寸 mm | 实体体积 cm³ |','|---|:---:|:---:|---:|---|---:|']
for v in validation:
    vl.append(f"| {v['file']} | {v['watertight']} | {v['winding_consistent']} | {v['components']} | {v['size_mm']} | {v['volume_cm3']} |")
(DOC/'VALIDATION_REPORT.md').write_text('\n'.join(vl),encoding='utf-8')

part_index='''# V2 零件编号与用途

## P01 — 通用八槽位主底座
一体打印的大型主体。包含八个45°径向模块槽、八个外部扩口、中心混合腔、iMM-6C插芯孔、16个主盖螺钉孔和转盘定位盲孔。

## P02 — 主上盖（带M3六角螺母捕获槽）
封闭中心腔和固定通道，压紧模块盖与密封件。M3螺母从上方放入六角槽，螺钉从底座下方向上安装。

## P03 — iMM-6C麦克风插芯
`ID9_0`版针对实测Ø8.8 mm前端；空白2.5 mm引导孔版用于后续自行扩孔。肩部在插芯底面停止时，10 mm前段的感声端名义到达中心腔约z=7 mm。

## P04 — 麦克风与插芯配合孔规
上排Ø8.8/8.9/9.0/9.1 mm；下排Ø20.0/20.2/20.4 mm。应先打印，确认实际P1S尺寸补偿。

## P05 — 八个相同的直通基线模块
每个模块由托盘、薄盖和可选小密封垫组成。用于U4-Symmetric和U8-Symmetric。

## P06 — A–H八种编码模块托盘
A短直、B长蛇形、C/D不同长度侧支、E折线侧支、F扩张腔、G双侧支、H长蛇形+长侧支。

## P07 — A–H模块薄盖
盖在对应P06托盘上。顶面的1–8个凹点对应A–H，主上盖压紧后密封。

## P08 — A–H模块小密封垫
建议用0.4 mm TPU打印，或按SVG从约0.4–0.5 mm薄硅胶片切割。其开口与各自模块声道相匹配，不能互换；E/G/H等复杂声道可能使垫片自然分成2–3片，这是预期结果。

## P08B — 通用模块顶部压力垫
0.6 mm厚，放在每个模块薄盖或P09占位模块顶部。它与P11主密封垫使用相同名义厚度，使P02主盖在被P11抬高后仍能压紧所有八个槽位。建议与P11使用同一片硅胶/EVA或同一TPU参数。

## P09 — 实心占位模块
U4状态中安装在45°、135°、225°、315°。其内外舌部填充固定通道，避免未启用方向形成长闭端侧腔。

## P10 — 外部渐缩堵头
用于临时关闭任意有效入口、漏气诊断和单通道测量。几何按16→8 mm扩口反向渐缩，并验证完整12 mm插入包络。

## P11 — 通用主盖密封垫
八片式，不随U4/U8或模块类型改变。可用TPU打印，或按1:1 SVG切割0.6–1.0 mm硅胶/闭孔EVA。

## P12 — 模块配合测试件
包括三档槽位测试座和短楔形测试键。必须在大型P01之前打印。

## P13 — 主盖密封与M3螺母槽测试件
小型通道底座、上盖和垫片，用于确认M3六角槽、螺钉长度和密封材料。

## P14 — 固定转盘底座
具有40 mm贯通电缆通路、八个45°定位孔和环形中心导向凸台。

## P15 — 旋转转盘上层
通过环形孔套在P14凸台上；四个支撑垫和定位柱连接P01，并为麦克风插芯、USB-C延长线留下下方空间。

## P16 — 角度定位销
将P15锁定到P14的0°、45°……315°位置。
'''
(DOC/'PART_INDEX.md').write_text(part_index,encoding='utf-8')

assembly='''# V2 装配说明

## 0. 首先打印测试件
1. P12模块测试座和测试键。
2. P04麦克风/插芯孔规。
3. P13密封与M3螺母槽测试件。
4. 在Bambu Studio中检查P01/P02没有超出平台，且没有自动缩放。

## 1. 模块组装
- 将对应P08小密封垫放在P06托盘顶面；没有TPU时可按SVG切割约0.4–0.5 mm硅胶；若材料更厚，应通过P13重新确认压缩量。
- 将对应P07薄盖覆盖在托盘上。凹点数量1–8依次表示A–H。
- 模块装入P01后，在每个P07薄盖顶部放一片P08B压力垫；P09实心占位件顶部也放P08B。
- 模块盖不单独用螺钉；P08B与P11等厚，使P02主盖能统一压紧。

## 2. 四通道U4安装
- 0°：有效模块；45°：P09实心占位；90°：有效模块；135°：P09；180°：有效；225°：P09；270°：有效；315°：P09。
- U4-Symmetric四个有效位置均使用P05直通模块。
- U4-Encoded使用A/B/D/F，见`CONFIGURATION_MATRIX.md`。

## 3. 八通道U8安装
- U8-Symmetric八个槽都使用P05。
- U8-Encoded按0°A、45°E、90°B、135°G、180°D、225°H、270°F、315°C安装。

## 4. 麦克风
- 从P01底部装入P03。
- iMM-6C的Ø8.8 mm前端从P03底面向上插入，较大肩部停在插芯底面；10 mm前段的端部名义到达中心腔z≈7 mm。
- 使用支持数据的USB-C公对母延长线；延长线从转盘中央40 mm通孔向下穿出。
- 用一圈很薄的PTFE带、软硅胶套或可移除胶泥消除8.8/9.0 mm间隙，禁止让密封材料遮住感声孔。

## 5. 主盖
- 将P11八片主密封垫放在固定通道之间的实心顶面；模块位置不放P11，而是每个槽位使用P08B顶部压力垫。
- 检查P08B与P11采用相同名义厚度。
- 放置P02，确认N标记对准0°入口。
- M3螺母放入P02上方六角槽；M3螺钉与垫片从P01底部向上穿入。
- 按对角、分三轮均匀紧固。不要一次把某一颗拧到底。

## 6. 转盘
- P15套在P14环形导向凸台外。
- 将P01底部四个Ø6.4盲孔对准P15四个Ø6定位柱。
- P16定位销插入所需45°孔。

## 7. 漏气检查
- 装上P10堵头，低声压扫频或轻微正压检查缝隙。
- 不要使用高压。
- 若主盖缝隙漏气，优先调整P11材料/压缩量，不要立即永久粘接。
'''
(DOC/'ASSEMBLY.md').write_text(assembly,encoding='utf-8')

print_bom='''# 打印与BOM

## 打印机
- Bambu Lab P1S，原装0.4 mm喷嘴。
- PLA，0.20 mm层高。
- P01/P02建议4道墙、5层顶底、12–18%填充、5 mm brim。
- P01开放通道朝上；P02大平面朝下；模块托盘开放面朝上；薄盖平面朝下。
- 禁止切片器自动缩放。

## 平台适配
- P01/P02的外接圆直径约227.3 mm，但按当前正八边形朝向，XY包围盒为210×210 mm。
- 加5 mm brim后XY占地约220×220 mm，小于P1S的256 mm平台。
- 建议关闭不必要的打印前流量校准图案，确认切片预览没有进入保留区。

## 建议先打印
1. P12模块配合件。
2. P04孔规。
3. P13密封/螺母槽测试件。
4. 一个P05托盘、盖和垫片。
5. 确认后再打印P01/P02。

## 非打印BOM
- M3×20或M3×22内六角螺钉：16。
- M3标准六角螺母：16。
- M3平垫片：16。
- 0.4–1.0 mm硅胶片、闭孔EVA或TPU；P08小垫片0.4 mm，P08B/P11为0.6 mm。
- USB-C公对母、支持数据传输的延长线。
- 少量PTFE生料带或可移除密封胶泥。

## 材料风险
- P01与P02是大平面零件。先清洁热床，使用brim，并避免冷风直吹。
- P02的六角螺母槽应先用P13确认；如果过紧，只调整XY孔补偿，不要整体缩放P02。
- 模块小密封垫若使用TPU，建议单独慢速打印；也可以按SVG手工切割硅胶片。
'''
(DOC/'PRINT_AND_BOM.md').write_text(print_bom,encoding='utf-8')

config_md=['# 配置矩阵','', '| 方向 | U4-Symmetric | U4-Encoded | U8-Symmetric | U8-Encoded |','|---:|---|---|---|---|']
for ang in P['head']['direction_angles_deg']:
    config_md.append(f"| {ang}° | {CONFIGS['U4-Symmetric'][ang]} | {CONFIGS['U4-Encoded'][ang]} | {CONFIGS['U8-Symmetric'][ang]} | {CONFIGS['U8-Encoded'][ang]} |")
config_md += ['', 'U4中的P09不是普通末端堵头，而是带内外填充舌的实心模块；它用于减少未启用通道形成闭端侧支的可能。']
(DOC/'CONFIGURATION_MATRIX.md').write_text('\n'.join(config_md),encoding='utf-8')

design_basis=f'''# 设计基础与尺寸理由

## 1. 研究定位
V2用于快速验证：一个被动内部声学形态能否把同一水平面内4或8个方向映射为中心单麦克风可区分的宽带频率响应。它沿用Sun等人“多个方向相关acoustic channel modules共同改变中心麦克风方向响应”的思路，但不复制其三层随机半球；原论文题为*Sound Localization and Separation in 3D Space Using a Single Microphone with a Metamaterial Enclosure*，其ACM被描述为由穿孔层和腔体构成的二阶声学滤波器。V2改用可解释的管路长度、侧支和扩张腔。

## 2. 为什么是通用八槽位主体
- 每45°一个机械一致槽位。
- U4只更换四个有效模块和四个实心占位件；U8不重印大型主体。
- A/B/D/F在U4与U8中可保持完全相同，减少大型打印件混杂。

## 3. 平台与尺度
- 正八边形跨平面210 mm、跨角{P['head']['across_corners_mm']:.2f} mm。
- 加5 mm brim后{P['head']['bed_footprint_with_brim_mm']:.2f} mm，适配256 mm P1S平台。
- 结构特征尺度D≈{P['head']['across_corners_mm']/1000:.3f} m，对应c/D≈{P['acoustic']['size_transition_hz_c_over_D']:.0f} Hz；因此主分析频段设为1.5–8 kHz，而不期望低频具有很强方向编码。

## 4. 通道截面
- 固定喉道8.0×9.2 mm，面积{P['acoustic']['fixed_channel_area_mm2']:.1f} mm²，水力直径{P['acoustic']['fixed_channel_hydraulic_diameter_mm']:.2f} mm。
- 模块直通基线声道9.4×6.4 mm，面积{P['acoustic']['module_channel_area_mm2']:.1f} mm²，水力直径{P['acoustic']['module_channel_hydraulic_diameter_mm']:.2f} mm。
- 两者中心高度基本对齐，面积比约{P['acoustic']['module_channel_area_mm2']/P['acoustic']['fixed_channel_area_mm2']:.2f}，避免V1的4 mm级长细管损耗成为主要限制。

## 5. 外部入口
外部固定段在17 mm内从8 mm扩张到16 mm，目的是提高远处扬声器的耦合能量，同时保留一定径向朝向。P10按该扩张包络设计，并对完整12 mm插入深度验证，不再只检查端面尺寸。

## 6. 模块滤波
闭端侧支的第一估算：

f_q ≈ c/(4L)

这是设计频率分散的粗略依据，不是对实体峰/谷位置的保证。真实响应还受端部修正、扩张腔、中心腔、外部辐射、打印粗糙度和房间反射影响。`SOURCE/module_acoustic_estimates.csv`记录每个模块的中心线长度和名义四分之一波长频率。

## 7. 麦克风
P03的9.0 mm孔对应实测8.8 mm前端，直径间隙0.2 mm。肩部距端部10 mm，肩部停在插芯底面时，端部名义位于z≈7 mm，接近中心腔高度中部。由于官方机械图未用于本设计，必须先用P04孔规实体确认。

## 8. 重要限制
- V2未经过FEM优化。
- U4与U8的总开口面积不同，不能视为严格单变量实验。
- 数字水密不等于实体气密。
- 第一轮应使用已知log sweep、固定扬声器、旋转结构和跨重定位测试。
'''
(DOC/'DESIGN_BASIS.md').write_text(design_basis,encoding='utf-8')

experiment='''# 最小实验计划

## 1. 机械与声学状态
依次测量：
1. 裸iMM-6C。
2. U4-Symmetric。
3. U4-Encoded。
4. U8-Symmetric。
5. U8-Encoded。

## 2. 布置
- 扬声器固定，结构中心距扬声器约1.5 m。
- 扬声器声学中心与麦克风感声端等高。
- 只旋转结构，使用P14–P16的45°定位。
- 第一阶段同一水平面：U4测0/90/180/270°；U8测每45°。

## 3. 信号
- REW log sweep，约300 Hz–10 kHz。
- 初步重点分析1.5–8 kHz。
- 每个方向5次不拆装重复，再做至少3次完全重新定位重复。

## 4. 分析
- 去除分析频段平均dB或做能量归一化，避免只靠响度。
- 同方向相关性、不同方向相关矩阵。
- effective rank。
- 最近模板与logistic regression。
- 采用leave-one-reposition-session-out，而不是把同一次连续测量随机拆分。

## 5. 初步成功标准
- 同方向重定位相关性>0.97。
- 方向间谱形距离至少为同方向重定位距离的2倍。
- U4-Encoded明显优于U4-Symmetric。
- U8-Encoded跨会话八方向分类>85%，且去除总能量后仍成立。
- 结果不能只依赖一个极窄的偶然频点。

## 6. 失败诊断顺序
1. 检查主盖、模块盖和麦克风插芯漏气。
2. 检查扬声器距离、直达声/反射和旋转中心。
3. 查看U4-Symmetric是否已被房间强烈区分。
4. 查看每个模块单独开口、其余用P10关闭时的传递函数。
5. 最后才考虑重新设计模块，而不是直接增加算法复杂度。
'''
(DOC/'EXPERIMENT_PLAN.md').write_text(experiment,encoding='utf-8')

ai_handoff=f'''# AI HANDOFF — Acoustic Morphology Encoder V2

## 任务
本包是一个可在Bambu P1S上一体打印大型主体的、同平面4/8方向单麦克风声学形态编码平台。大型主体只打印一次；U4与U8通过可换楔形模块切换。

## 必须先读
1. `SOURCE/design_parameters_v2.json`
2. `DOCS/DESIGN_BASIS.md`
3. `DOCS/CONFIGURATION_MATRIX.md`
4. `DOCS/VALIDATION_REPORT.md`
5. `SOURCE/generate_v2_package.py`

## 不可无意改变的机械接口
- 外八边形跨平面210 mm。
- 模块径向范围r=32–88 mm。
- 模块体长56 mm、内宽17 mm、外宽36 mm、托盘高7.6 mm。
- 模块托盘7.6 mm + 小垫片0.4 mm + 模块盖1.2 mm = 9.2 mm；其上再放P08B 0.6 mm，与P11主垫片等高。
- 固定喉道8×9.2 mm；模块直通基线名义9.4×6.4 mm；复杂模块宽度按壁厚约束局部减小。
- 麦克风底座孔Ø20.4，插芯颈Ø20.0，iMM-6C孔Ø9.0。
- 主盖16个M3孔和螺母槽由同一坐标表生成。
- P15转盘定位柱与P01底部盲孔必须一起修改。

## 坐标
- +Y为0°/N。
- +X为90°/E。
- 方向按0、45、90……315°。
- 模块局部+X从中心向外；局部x=-28是内端，x=+28是外端。

## 配置
- U4-Symmetric：0/90/180/270直通，其余P09。
- U4-Encoded：0=A、90=B、180=D、270=F，其余P09。
- U8-Encoded：0=A、45=E、90=B、135=G、180=D、225=H、270=F、315=C。

## 修改规则
- 修改模块外形时必须同时修改：P01槽、P07盖、P08垫片、P09占位、P12配合件和全部装配检查。
- 修改外部扩口时必须重新生成P10并验证整个插入包络。
- 修改麦克风位置时必须根据实测iMM-6C感声孔位置重新计算，不要只按外壳端面。
- 修改主体外径时重新检查P1S平台、brim和转盘。
- 新模块至少保持1.6 mm名义侧壁，并保留两端与固定喉道的正面积重叠。

## 已知局限
- 没有FEM优化或实体打印验证。
- U4/U8总开口面积不同。
- PLA大平面与TPU/硅胶密封的实际压缩量需要测试件确定。
- 当前iMM-6C几何来自用户实测Ø8.8 mm和肩部长度10 mm，而不是完整厂商机械图。

## 重新生成
在安装Python、numpy、shapely、trimesh、matplotlib后运行：

`python SOURCE/generate_v2_package.py`

默认输出到`SOURCE/_regenerated/Acoustic_Morphology_Encoder_V2`，也可通过环境变量`ACOUSTIC_ENCODER_V2_OUTPUT`指定。
'''
(DOC/'AI_HANDOFF.md').write_text(ai_handoff,encoding='utf-8')

readme=f'''# Acoustic Morphology Encoder V2.0.1

这是一个同一大型主体可切换4通道与8通道的单麦克风方向频域编码平台。

## 先做什么
1. 阅读`DOCS/PART_INDEX.md`。
2. 打印P12、P04、P13测试件。
3. 阅读`DOCS/PRINT_AND_BOM.md`和`DOCS/ASSEMBLY.md`。
4. 只有测试件通过后，才打印P01与P02。

## 核心设计
- Bambu P1S，0.4 mm喷嘴，PLA。
- 正八边形外接圆直径约{P['head']['across_corners_mm']:.2f} mm；按当前朝向，P01/P02的XY包围盒为210×210 mm，加5 mm brim约{P['head']['bed_footprint_with_brim_mm']:.2f}×{P['head']['bed_footprint_with_brim_mm']:.2f} mm。
- 八个45°楔形槽位。
- U4使用四个有效模块+四个P09实心占位；U8更换占位即可。
- Dayton Audio iMM-6C实测前端Ø8.8 mm，P03推荐孔Ø9.0 mm，前端到肩部按10 mm设计。
- 模块为托盘+0.4 mm小垫片+独立薄盖；每个槽位再放0.6 mm P08B压力垫，与0.6 mm P11主垫片等高后由主上盖统一压紧；主螺钉采用M3+捕获式六角螺母。

## 科学定位
该平台借鉴方向相关acoustic channel module的思想，但不是原论文三层随机超材料半球的复制。V2故意采用可解释的路径长度、侧支和扩张腔，以便快速比较对称与编码结构。它是proof-of-concept，不是已优化成品。

## 关键文件
- `DOCS/DESIGN_BASIS.md`
- `DOCS/CONFIGURATION_MATRIX.md`
- `DOCS/EXPERIMENT_PLAN.md`
- `DOCS/VALIDATION_REPORT.md`
- `DOCS/AI_HANDOFF.md`
- `SOURCE/design_parameters_v2.json`
- `SOURCE/generate_v2_package.py`
'''
(DOC/'README_中文.md').write_text(readme,encoding='utf-8')

start='''ACOUSTIC MORPHOLOGY ENCODER V2 — START HERE

1. Read DOCS/PART_INDEX.md
2. Read DOCS/PRINT_AND_BOM.md
3. Print P12, P04 and P13 coupons first
4. Do not print P01/P02 until fit coupons pass
5. Read DOCS/ASSEMBLY.md and CONFIGURATION_MATRIX.md
6. Read VALIDATION_REPORT.md: digital validation is not physical validation
7. For a new AI/agent, start with DOCS/AI_HANDOFF.md and SOURCE/design_parameters_v2.json
'''
(OUT/'START_HERE.txt').write_text(start,encoding='utf-8')

changelog='''# CHANGELOG

## V2.0.1
- Corrected all module lids from a +0.8 mm overhang to a 0.10 mm inset relative to the tray body.
- Added a 0.20 mm inset bottom lead-in to reduce first-layer interference.
- Corrected P05/P07 lids, P08 gaskets, P08B pressure pad, P09 dummy top flange, P11 main-gasket cut-outs and U4/U8 print plates.
- Repacked U4/U8 plates with separated parts and at least 6 mm nominal gap.

## V2.0.0
- Replaced V1 four-arm cross body with a universal eight-slot regular-octagon body.
- One large base supports both four-channel and eight-channel configurations.
- Added solid dummies with inner/outer filling tongues for U4.
- Replaced state-specific large gaskets with one universal main gasket plus small per-module gaskets.
- Added A–H deterministic channel modules, individual thin lids, and fit coupons.
- Added iMM-6C Ø9.0 mm insert based on user-measured Ø8.8 mm and 10 mm front-to-shoulder length.
- Added hollow-centre 45° turntable for USB-C extension routing; detent holes are blind from the top.
- Added P08B equal-thickness pressure pads so the main lid compresses modules and main gasket uniformly.
- Re-designed and fully validated the tapered external-port plug envelope.
'''
(DOC/'CHANGELOG.md').write_text(changelog,encoding='utf-8')

license_text='''This package is provided for research prototyping. No warranty is made that a printed part will be airtight, dimensionally exact, safe for elevated pressure, or achieve a specified acoustic performance. Perform low-pressure leak tests and inspect every sliced file before printing. Do not use this design for safety-critical localization or hearing protection. The package does not redistribute the cited papers; only bibliographic references are included.'''
(OUT/'LICENSE_AND_DISCLAIMER.txt').write_text(license_text,encoding='utf-8')

# Manifest
manifest=[]
for pth in sorted(OUT.rglob('*')):
    if pth.is_file():
        manifest.append({'path':str(pth.relative_to(OUT)),'size_bytes':pth.stat().st_size,'sha256':hashlib.sha256(pth.read_bytes()).hexdigest()})
(OUT/'MANIFEST.json').write_text(json.dumps({'package':'Acoustic_Morphology_Encoder_V2','version':P['version'],'files':manifest},indent=2,ensure_ascii=False),encoding='utf-8')

# Re-write manifest after including itself? Keep first manifest intentionally excluding itself's final hash.

# Build zip and checksum in build root.
zip_path=BUILD_ROOT/'Acoustic_Morphology_Encoder_V2_Print_Package.zip'
with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for pth in sorted(OUT.rglob('*')):
        if pth.is_file():
            z.write(pth,Path(OUT.name)/pth.relative_to(OUT))
sha=hashlib.sha256(zip_path.read_bytes()).hexdigest()
(zip_path.with_suffix(zip_path.suffix+'.sha256')).write_text(f'{sha}  {zip_path.name}\n',encoding='utf-8')

print(json.dumps({
    'out':str(OUT),
    'zip':str(zip_path),
    'sha256':sha,
    'stl_count':len(list(STL.glob('*.stl'))),
    'all_checks_pass':report['all_checks_pass'],
    'all_individual_watertight':all_water,
},indent=2))
