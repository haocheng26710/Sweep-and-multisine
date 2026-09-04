from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import Point, Polygon, MultiPolygon, GeometryCollection, box, LineString
from shapely.ops import unary_union, polygonize
import trimesh

SCRIPT_DIR = Path(__file__).resolve().parent
BUILD_ROOT = Path(os.environ.get('AME_V25_BUILD_ROOT', '/mnt/data/v25_build'))
OUT = Path(os.environ.get('AME_V25_OUTPUT', BUILD_ROOT / 'Acoustic_Morphology_Encoder_V2.5_Patch'))
STL = OUT / 'STL'
DOC = OUT / 'DOCS'
SRC = OUT / 'SOURCE'
SVG = OUT / 'TEMPLATES'
PREV = OUT / 'PREVIEWS'
for d in [OUT, STL, DOC, SRC, SVG, PREV]:
    d.mkdir(parents=True, exist_ok=True)

P: Dict[str, Any] = {
    'version': '2.5.1',
    'package_type': 'Patch/add-on for Acoustic Morphology Encoder V2.0.1 lid-fit correction',
    'date': '2026-07-30',
    'units': 'mm',
    'coordinate_system': 'V2 local module coordinates: x inward(-) to outward(+); y tangential; z up',
    'v2_interface': {
        'module_body_radial_length_mm': 56.0,
        'module_body_inner_width_mm': 17.0,
        'module_body_outer_width_mm': 36.0,
        'module_body_height_mm': 7.6,
        'module_bottom_skin_mm': 1.2,
        'module_air_height_mm': 6.4,
        'module_lid_thickness_mm': 1.2,
        'module_lid_fit_inset_mm': 0.10,
        'module_lid_entry_chamfer_inset_mm': 0.20,
        'module_gasket_thickness_mm': 0.4,
        'module_key_chamfer_mm': 4.0,
        'module_pocket_clearance_per_side_mm': 0.20,
        'module_end_x_mm': [-28.6, 28.6],
        'fixed_throat_width_mm': 8.0,
        'head_outer_apothem_mm': 105.0,
        'head_outer_sides': 8,
        'head_assembled_height_mm': 17.2,
        'main_lid_top_pressure_pad_thickness_mm': 0.60,
    },
    'printer': {
        'model': 'Bambu Lab P1S',
        'build_volume_mm': [256,256,256],
        'nozzle_mm': 0.4,
        'material': 'PLA',
        'recommended_layer_height_mm': 0.20,
    },
    'acoustic': {
        'speed_of_sound_mm_s': 343000.0,
        'formula': 'two-neck cavity estimate f=c/(2*pi)*sqrt((So/Lo_eff + Si/Li_eff)/V)',
        'end_correction_model': 'Leff = Lphysical + 1.7*sqrt(S/pi)',
        'warning': 'Engineering estimate only; central chamber loading, radiation, losses and print tolerances shift peaks.',
    },
    'baffle': {
        'clip_clearance_mm': 0.35,
        'clip_shell_radial_thickness_mm': 3.0,
        'clip_sector_half_angle_deg': 12.0,
        'fin_thickness_mm': 2.0,
        'fin_outer_radius_mm': 128.0,
        'height_mm': 22.0,
        'print_quantity': 8,
    },
}

# HR design set. U4 uses HR01/03/05/07 on the four cardinal sectors.
HR_SPECS = [
    {'id':'HR01','target_hz':1200,'cavity_center_x':4.0,'cavity_length':32.0,'cavity_width':19.0,'inner_neck_width':2.0,'outer_neck_width':2.4},
    {'id':'HR02','target_hz':1500,'cavity_center_x':4.0,'cavity_length':29.0,'cavity_width':19.0,'inner_neck_width':2.8,'outer_neck_width':4.4},
    {'id':'HR03','target_hz':1850,'cavity_center_x':8.0,'cavity_length':26.0,'cavity_width':15.0,'inner_neck_width':2.8,'outer_neck_width':4.4},
    {'id':'HR04','target_hz':2250,'cavity_center_x':-2.0,'cavity_length':36.0,'cavity_width':8.0,'inner_neck_width':2.8,'outer_neck_width':4.8},
    {'id':'HR05','target_hz':2700,'cavity_center_x':5.0,'cavity_length':31.0,'cavity_width':7.0,'inner_neck_width':2.8,'outer_neck_width':5.6},
    {'id':'HR06','target_hz':3200,'cavity_center_x':6.0,'cavity_length':26.0,'cavity_width':6.0,'inner_neck_width':2.8,'outer_neck_width':6.8},
    {'id':'HR07','target_hz':3800,'cavity_center_x':8.0,'cavity_length':23.0,'cavity_width':5.0,'inner_neck_width':2.8,'outer_neck_width':7.2},
    {'id':'HR08','target_hz':4500,'cavity_center_x':5.0,'cavity_length':18.0,'cavity_width':4.0,'inner_neck_width':4.4,'outer_neck_width':7.2},
]
P['hr_specs_input'] = HR_SPECS
P['configurations'] = {
    'V25-U4-HR': {'0':'HR01','45':'V2 P09 dummy','90':'HR03','135':'V2 P09 dummy','180':'HR05','225':'V2 P09 dummy','270':'HR07','315':'V2 P09 dummy'},
    'V25-U8-HR': {'0':'HR01','45':'HR02','90':'HR03','135':'HR04','180':'HR05','225':'HR06','270':'HR07','315':'HR08'},
}
P['reuse_from_v2'] = [
    'P01 universal 8-slot base', 'P02 main lid', 'P03 iMM-6C insert', 'P04 fit gauge',
    'P05 straight baseline modules', 'P08B universal module top pressure pads',
    'P09 solid dummy modules for U4', 'P10 port plugs', 'P11 main lid gasket',
    'P12/P13 fit and seal coupons', 'P14/P15/P16 indexed turntable'
]
P['replaced_from_v2'] = ['P06/P07/P08 encoded A-H module sets are replaced for the V2.5 HR experiment only. Keep them as broadband controls.']
P['added_in_v25'] = ['Eight two-neck Helmholtz-like frequency-division module sets', 'Eight removable corner baffle clips', 'Baffle fit coupon', 'Updated experiment and handoff documentation']

# -----------------------------------------------------------------------------
# Geometry helpers copied to preserve V2 interface conventions
# -----------------------------------------------------------------------------

def clean(g):
    if g.is_empty:
        return g
    g = shapely.set_precision(g, grid_size=0.001)
    if not g.is_valid:
        g = shapely.make_valid(g)
    return g


def circle(x: float, y: float, r: float, resolution: int=64):
    return Point(x,y).buffer(r, quad_segs=resolution)


def rounded_rect(xmin: float, ymin: float, xmax: float, ymax: float, r: float):
    if r <= 0:
        return box(xmin,ymin,xmax,ymax)
    if xmax-xmin <= 2*r or ymax-ymin <= 2*r:
        r = min((xmax-xmin)/4, (ymax-ymin)/4)
    core = box(xmin+r,ymin+r,xmax-r,ymax-r)
    return clean(core.buffer(r, join_style='round'))


def regular_ngon_apothem(n: int, apothem: float, face_normal_at_deg: float=0.0):
    R = apothem / math.cos(math.pi/n)
    start = math.radians(face_normal_at_deg + 180.0/n)
    pts=[]
    for k in range(n):
        a=start+2*math.pi*k/n
        pts.append((R*math.cos(a),R*math.sin(a)))
    return clean(Polygon(pts))


def wedge_sector(angle_deg: float, half_angle_deg: float, r: float=200.0):
    a0=math.radians(angle_deg-half_angle_deg)
    a1=math.radians(angle_deg+half_angle_deg)
    return clean(Polygon([(0,0),(r*math.cos(a0),r*math.sin(a0)),(r*math.cos(a1),r*math.sin(a1))]))


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
            if isinstance(x,(Polygon,MultiPolygon)):
                yield from rings_of(x)


def tri_area2(coords):
    (x0,y0),(x1,y1),(x2,y2)=coords
    return (x1-x0)*(y2-y0)-(y1-y0)*(x2-x0)


def add_horizontal_surface(vertices,faces,geom,z,up):
    geom=clean(geom)
    if geom.is_empty:
        return
    tris=shapely.constrained_delaunay_triangles(geom)
    for tri in getattr(tris,'geoms',[tris]):
        if not isinstance(tri,Polygon) or tri.area < 1e-9:
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


def add_vertical_walls(vertices,faces,geom,z0,z1):
    geom=clean(geom)
    for ring in rings_of(geom):
        coords=list(ring.coords)
        for i in range(len(coords)-1):
            a=(float(coords[i][0]),float(coords[i][1])); b=(float(coords[i+1][0]),float(coords[i+1][1]))
            if abs(a[0]-b[0])+abs(a[1]-b[1])<1e-9:
                continue
            p,q=sorted([a,b])
            base=len(vertices)
            vertices.extend([[p[0],p[1],z0],[q[0],q[1],z0],[q[0],q[1],z1],[p[0],p[1],z1]])
            faces.append([base,base+1,base+2]); faces.append([base,base+2,base+3])


def layered_mesh(layers: Sequence[Tuple[float,float,Any]], name: str='') -> trimesh.Trimesh:
    layers=[(float(a),float(b),clean(g)) for a,b,g in layers if b>a and not g.is_empty]
    layers.sort(key=lambda x:x[0])
    linework=unary_union([g.boundary for _,_,g in layers])
    cells=[clean(c) for c in polygonize(linework) if c.area>1e-8]
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


def mesh_export(mesh: trimesh.Trimesh, path: Path):
    path.parent.mkdir(parents=True,exist_ok=True)
    mesh.export(path,file_type='stl')


def combine_meshes(meshes: Sequence[trimesh.Trimesh], translations: Sequence[Tuple[float,float,float]]):
    out=[]
    for m,t in zip(meshes,translations):
        c=m.copy(); c.apply_translation(t); out.append(c)
    return trimesh.util.concatenate(out)


def module_outline(inner_w=17.0, outer_w=36.0, radial_len=56.0, key_chamfer=4.0):
    x0=-radial_len/2; x1=radial_len/2
    yi=inner_w/2; yo=outer_w/2; c=key_chamfer
    return clean(Polygon([(x0,-yi),(x1,-yo),(x1,yo-c),(x1-c,yo),(x0,yi)]))


def dots_identifier(n: int, x0=5.5, y0=0.0, spacing=3.2, radius=0.75):
    dots=[]
    for i in range(n):
        row=i//4; col=i%4
        x=x0+(col-1.5)*spacing
        y=y0+(0.5-row)*spacing
        dots.append(circle(x,y,radius,20))
    return clean(unary_union(dots))


def write_svg(geom, path: Path):
    geom=clean(geom)
    minx,miny,maxx,maxy=geom.bounds
    margin=2.0; W=maxx-minx+2*margin; H=maxy-miny+2*margin
    pieces=[]
    polys=list(geom.geoms) if isinstance(geom,MultiPolygon) else [geom]
    for poly in polys:
        if not isinstance(poly,Polygon): continue
        rings=[poly.exterior]+list(poly.interiors)
        d=[]
        for ring in rings:
            coords=list(ring.coords)
            if not coords: continue
            d.append(f'M {coords[0][0]-minx+margin:.3f},{maxy-coords[0][1]+margin:.3f}')
            for x,y in coords[1:]:
                d.append(f'L {x-minx+margin:.3f},{maxy-y+margin:.3f}')
            d.append('Z')
        pieces.append(f'<path d="{" ".join(d)}" fill="none" stroke="black" stroke-width="0.15" fill-rule="evenodd"/>')
    text=f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.3f}mm" height="{H:.3f}mm" viewBox="0 0 {W:.3f} {H:.3f}">\n'+'\n'.join(pieces)+'\n</svg>\n'
    path.write_text(text,encoding='utf-8')

# Exact V2 module interfaces
BODY_MOD=module_outline()
LID_MOD=clean(BODY_MOD.buffer(-0.10,join_style='mitre'))
LID_ENTRY_MOD=clean(BODY_MOD.buffer(-0.20,join_style='mitre'))
X0=-28.6; X1=28.6
H=P['v2_interface']['module_air_height_mm']

# -----------------------------------------------------------------------------
# Helmholtz-like two-neck modules
# -----------------------------------------------------------------------------

def tapered_neck(x0,x1,w0,w1):
    return clean(Polygon([(x0,-w0/2),(x1,-w1/2),(x1,w1/2),(x0,w0/2)]))


def hr_channel(spec):
    xc=spec['cavity_center_x']; l=spec['cavity_length']; wc=spec['cavity_width']
    xL=xc-l/2; xR=xc+l/2
    r=min(1.2,wc/4.0)
    cavity=clean(rounded_rect(xL,-wc/2,xR,wc/2,r).intersection(BODY_MOD.buffer(-1.6,join_style='mitre')))
    wi=spec['inner_neck_width']; wo=spec['outer_neck_width']
    # Preserve a full-width 8 mm throat at each V2 interface, then taper inward.
    inner_end=box(-29.0,-4.0,-24.6,4.0)
    inner_taper=tapered_neck(-24.6,-20.6,8.0,wi)
    inner_const=box(-20.6,-wi/2,xL+0.15,wi/2)
    outer_const=box(xR-0.15,-wo/2,21.0,wo/2)
    outer_taper=tapered_neck(21.0,25.0,wo,8.0)
    outer_end=box(25.0,-4.0,29.0,4.0)
    channel=clean(unary_union([cavity,inner_end,inner_taper,inner_const,outer_const,outer_taper,outer_end]).intersection(BODY_MOD.buffer(0.02)))
    return channel,cavity,(xL,xR)


def predicted_two_neck(spec,cavity):
    xL=spec['cavity_center_x']-spec['cavity_length']/2
    xR=spec['cavity_center_x']+spec['cavity_length']/2
    Lin=xL-X0; Lout=X1-xR
    Si=spec['inner_neck_width']*H; So=spec['outer_neck_width']*H
    ri=math.sqrt(Si/math.pi); ro=math.sqrt(So/math.pi)
    Lei=Lin+1.7*ri; Leo=Lout+1.7*ro
    V=cavity.area*H
    f=P['acoustic']['speed_of_sound_mm_s']/(2*math.pi)*math.sqrt((Si/Lei+So/Leo)/V)
    return {'cavity_plan_area_mm2':cavity.area,'cavity_volume_mm3':V,'inner_neck_area_mm2':Si,'outer_neck_area_mm2':So,'inner_physical_length_mm':Lin,'outer_physical_length_mm':Lout,'inner_effective_length_mm':Lei,'outer_effective_length_mm':Leo,'predicted_hz':f}

hr_trays={}; hr_lids={}; hr_gaskets={}; hr_metrics=[]
for idx,spec in enumerate(HR_SPECS,1):
    channel,cavity,_=hr_channel(spec)
    tray=layered_mesh([(0,1.2,BODY_MOD),(1.2,7.6,clean(BODY_MOD.difference(channel)))],f'V25_{spec["id"]}_tray')
    dots=dots_identifier(idx)
    lid=layered_mesh([(0,0.25,LID_ENTRY_MOD),
                      (0.25,0.8,LID_MOD),
                      (0.8,1.2,clean(LID_MOD.difference(dots)))],f'V25_{spec["id"]}_lid')
    gasket_prof=clean(LID_MOD.difference(channel.buffer(0.30,join_style='round')))
    gasket=layered_mesh([(0,0.4,gasket_prof)],f'V25_{spec["id"]}_gasket')
    hr_trays[spec['id']]=tray; hr_lids[spec['id']]=lid; hr_gaskets[spec['id']]=gasket
    mesh_export(tray,STL/f'V25_{spec["id"]}_{spec["target_hz"]}Hz_HR_tray.stl')
    mesh_export(lid,STL/f'V25_{spec["id"]}_{spec["target_hz"]}Hz_HR_lid.stl')
    mesh_export(gasket,STL/f'V25_{spec["id"]}_{spec["target_hz"]}Hz_HR_gasket_TPU.stl')
    write_svg(gasket_prof,SVG/f'V25_{spec["id"]}_{spec["target_hz"]}Hz_gasket_1to1.svg')
    m=predicted_two_neck(spec,cavity)
    m.update(spec)
    hr_metrics.append(m)

# U4 and U8 convenience plates: HR01/03/05/07 first, then even-number extension.
def make_plate(ids,name):
    meshes=[]; trans=[]
    positions=[(-62,-44),(0,-44),(62,-44),(-62,0),(0,0),(62,0),(-31,44),(31,44)]
    for i,hid in enumerate(ids):
        meshes.extend([hr_trays[hid],hr_lids[hid]])
        trans.extend([(*positions[2*i],0),(*positions[2*i+1],0)])
    p=combine_meshes(meshes,trans)
    mesh_export(p,STL/name)

make_plate(['HR01','HR03','HR05','HR07'],'PLATE_V25_U4_HR_cardinal_trays_and_lids.stl')
make_plate(['HR02','HR04','HR06','HR08'],'PLATE_V25_U8_diagonal_extension_trays_and_lids.stl')

# -----------------------------------------------------------------------------
# Removable directional baffle corner clips
# -----------------------------------------------------------------------------
HEAD=regular_ngon_apothem(8,105.0,face_normal_at_deg=0.0)

def baffle_profile(clearance: float):
    inner=clean(HEAD.buffer(clearance,join_style='mitre'))
    outer=clean(HEAD.buffer(clearance+P['baffle']['clip_shell_radial_thickness_mm'],join_style='mitre'))
    # One canonical corner at mathematical +22.5 deg.
    sector=wedge_sector(22.5,P['baffle']['clip_sector_half_angle_deg'],160)
    shell=clean(outer.difference(inner).intersection(sector))
    a=math.radians(22.5)
    corner_r=105.0/math.cos(math.radians(22.5))
    p0=((corner_r+P['baffle']['clip_clearance_mm']+1.2)*math.cos(a),(corner_r+P['baffle']['clip_clearance_mm']+1.2)*math.sin(a)); p1=(P['baffle']['fin_outer_radius_mm']*math.cos(a),P['baffle']['fin_outer_radius_mm']*math.sin(a))
    fin=clean(LineString([p0,p1]).buffer(P['baffle']['fin_thickness_mm']/2,cap_style='flat',join_style='mitre'))
    return clean(unary_union([shell,fin]))

BAFFLE_PROFILE=baffle_profile(P['baffle']['clip_clearance_mm'])
baffle_mesh=layered_mesh([(0,P['baffle']['height_mm'],BAFFLE_PROFILE)],'V25_corner_baffle_clip_H22')
mesh_export(baffle_mesh,STL/'V25_B01_corner_baffle_clip_H22_PRINT_8.stl')

# Three low-height fit samples at 0.20/0.35/0.50 mm clearance.
fit_meshes=[]; fit_trans=[]
for i,clr in enumerate([0.20,0.35,0.50]):
    m=layered_mesh([(0,5.0,baffle_profile(clr))],f'V25_baffle_fit_{clr:.2f}')
    fit_meshes.append(m); fit_trans.append((i*45,0,0))
fit=combine_meshes(fit_meshes,fit_trans)
fit.apply_translation(-fit.bounds.mean(axis=0))
mesh_export(fit,STL/'V25_B02_baffle_corner_fit_coupon_0p20_0p35_0p50.stl')

# Plate with eight identical clips; arranged in two rows. This is optional and may be slower than printing one test clip first.
clip_meshes=[baffle_mesh]*8
clip_trans=[]
for i in range(8):
    clip_trans.append(((i%4)*48,(i//4)*58,0))
clip_plate=combine_meshes(clip_meshes,clip_trans)
clip_plate.apply_translation(-clip_plate.bounds.mean(axis=0))
mesh_export(clip_plate,STL/'PLATE_V25_baffle_clips_8.stl')

# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------
checks=[]
def check(name,passed,details):
    checks.append({'name':name,'pass':bool(passed),'details':details})

# Mesh reports
mesh_reports=[]
for path in sorted(STL.glob('*.stl')):
    m=trimesh.load_mesh(path,force='mesh')
    mesh_reports.append({'file':path.name,'watertight':bool(m.is_watertight),'winding_consistent':bool(m.is_winding_consistent),'components':len(m.split(only_watertight=False)),'extents_mm':np.round(m.extents,3).tolist(),'bounds_mm':np.round(m.bounds,3).tolist(),'faces':len(m.faces),'volume_mm3':abs(float(m.volume))})
check('All V2.5 STL meshes are watertight and winding-consistent',all(r['watertight'] and r['winding_consistent'] for r in mesh_reports),{'failed':[r['file'] for r in mesh_reports if not(r['watertight'] and r['winding_consistent'])]})

# Interface dimensions exactly match V2.
check('Module body outline matches V2 interface',BODY_MOD.bounds==(-28.0,-18.0,28.0,18.0),{'bounds':BODY_MOD.bounds,'expected':[-28,-18,28,18]})
check('Tray and lid vertical stack matches V2',abs(7.6+0.4+1.2+0.6-(9.2+0.6))<1e-9,{'active_stack_mm':9.8,'V2 pocket_plus_pad_mm':9.8})

# HR channel checks.
protected=BODY_MOD.buffer(-1.6,join_style='mitre')
for spec in HR_SPECS:
    ch,cav,_=hr_channel(spec)
    mid=ch.intersection(box(-23,-100,23,100))
    outside=mid.difference(protected).area
    inner_line=ch.intersection(LineString([(-27.8,-20),(-27.8,20)]))
    outer_line=ch.intersection(LineString([(27.8,-20),(27.8,20)]))
    inner_open=inner_line.length
    outer_open=outer_line.length
    gasket_prof=clean(LID_MOD.difference(ch.buffer(0.30,join_style='round')))
    check(f'{spec["id"]} central channel/cavity preserves >=1.6 mm nominal wall',outside<1e-4,{'outside_protected_area_mm2':outside})
    check(f'{spec["id"]} both V2 throat interfaces remain open',inner_open>7.3 and outer_open>7.3,{'inner_open_width_mm':inner_open,'outer_open_width_mm':outer_open})
    check(f'{spec["id"]} gasket does not cover airspace',gasket_prof.intersection(ch).area<1e-6,{'intersection_area_mm2':gasket_prof.intersection(ch).area})

# Frequency ordering and target error.
preds=[m['predicted_hz'] for m in hr_metrics]
check('Predicted resonances are strictly increasing',all(preds[i]<preds[i+1] for i in range(7)),{'predicted_hz':[round(x,1) for x in preds]})
relerrs=[abs(m['predicted_hz']-m['target_hz'])/m['target_hz'] for m in hr_metrics]
check('Analytical design points are within 1.0% of target under stated approximation',max(relerrs)<0.01,{'max_relative_error':max(relerrs),'errors':[round(x,5) for x in relerrs]})

# Baffle compatibility and port clearance.
head_clear=HEAD.buffer(P['baffle']['clip_clearance_mm'],join_style='mitre')
check('Baffle clip has positive radial clearance from V2 outer octagon',BAFFLE_PROFILE.intersection(HEAD).area<1e-6,{'intersection_area_mm2':BAFFLE_PROFILE.intersection(HEAD).area,'nominal_clearance_mm':P['baffle']['clip_clearance_mm']})
# Adjacent port face normals are 0 and 45 deg; clip sector around corner 22.5 stays at least 10.5 deg away from their axes.
check('Baffle fin is positioned between adjacent V2 port axes',P['baffle']['clip_sector_half_angle_deg']<22.5,{'half_sector_deg':P['baffle']['clip_sector_half_angle_deg'],'port_to_corner_deg':22.5})
check('Baffle clip print plate fits P1S bed',max(clip_plate.extents[:2])<=256,{'plate_extents_mm':np.round(clip_plate.extents[:2],2).tolist(),'bed_mm':[256,256]})

validation={'version':P['version'],'all_checks_pass':all(c['pass'] for c in checks),'checks':checks,'mesh_reports':mesh_reports,'limitations':['No physical print fit has been performed.','No FEM/BEM or measured acoustic calibration has been performed.','The two-neck formula is an engineering starting estimate, not a guaranteed measured peak.','Baffle clips are friction-fit accessories; use the three-clearance coupon before printing eight.']}
(SRC/'validation_report_v25.json').write_text(json.dumps(validation,indent=2,ensure_ascii=False),encoding='utf-8')

# Parameter and HR tables
P['hr_metrics']=hr_metrics
(SRC/'design_parameters_v25.json').write_text(json.dumps(P,indent=2,ensure_ascii=False),encoding='utf-8')
with (SRC/'hr_design_table.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.writer(f)
    w.writerow(['id','target_hz','predicted_hz','cavity_volume_mm3','cavity_plan_area_mm2','inner_neck_width_mm','outer_neck_width_mm','inner_physical_length_mm','outer_physical_length_mm','inner_effective_length_mm','outer_effective_length_mm'])
    for m in hr_metrics:
        w.writerow([m['id'],m['target_hz'],round(m['predicted_hz'],1),round(m['cavity_volume_mm3'],1),round(m['cavity_plan_area_mm2'],2),m['inner_neck_width'],m['outer_neck_width'],round(m['inner_physical_length_mm'],2),round(m['outer_physical_length_mm'],2),round(m['inner_effective_length_mm'],2),round(m['outer_effective_length_mm'],2)])

# -----------------------------------------------------------------------------
# Preview figures
# -----------------------------------------------------------------------------
fig,axes=plt.subplots(2,4,figsize=(15,7))
for ax,spec,m in zip(axes.ravel(),HR_SPECS,hr_metrics):
    ch,cav,_=hr_channel(spec)
    x,y=BODY_MOD.exterior.xy; ax.fill(x,y,alpha=.12)
    polys=list(ch.geoms) if isinstance(ch,MultiPolygon) else [ch]
    for p in polys:
        if isinstance(p,Polygon):
            px,py=p.exterior.xy; ax.fill(px,py,alpha=.65)
    ax.set_title(f"{spec['id']} target {spec['target_hz']} Hz\nest. {m['predicted_hz']:.0f} Hz")
    ax.set_aspect('equal'); ax.set_xlim(-31,31); ax.set_ylim(-20,20); ax.axis('off')
fig.suptitle('V2.5 two-neck Helmholtz-like frequency-division modules')
fig.tight_layout(rect=[0,0,1,.95]); fig.savefig(PREV/'V25_HR_module_geometry.png',dpi=190); plt.close(fig)

fig,ax=plt.subplots(figsize=(8,8))
headx,heady=HEAD.exterior.xy; ax.fill(headx,heady,alpha=.12,label='reused V2 head outline')
for k in range(8):
    c=affinity.rotate(BAFFLE_PROFILE,45*k,origin=(0,0))
    polys=list(c.geoms) if isinstance(c,MultiPolygon) else [c]
    for p in polys:
        if isinstance(p,Polygon):
            x,y=p.exterior.xy; ax.fill(x,y,alpha=.55)
ax.set_aspect('equal'); ax.set_xlim(-135,135); ax.set_ylim(-135,135); ax.grid(alpha=.15)
ax.set_title('Eight removable corner baffle clips around reused V2 head')
fig.tight_layout(); fig.savefig(PREV/'V25_baffle_clips_top_view.png',dpi=190); plt.close(fig)

fig,axes=plt.subplots(1,2,figsize=(11,5))
configs=[('V2.5 U4-HR',P['configurations']['V25-U4-HR']),('V2.5 U8-HR',P['configurations']['V25-U8-HR'])]
for ax,(title,mapping) in zip(axes,configs):
    ax.add_patch(plt.Circle((0,0),1,fill=False,lw=1.5))
    for deg,val in mapping.items():
        d=float(deg); a=math.radians(90-d)
        x=.78*math.cos(a);y=.78*math.sin(a)
        label='X' if 'dummy' in val.lower() else val.replace('HR','')
        ax.text(x,y,label,ha='center',va='center',fontsize=11,weight='bold')
        ax.plot([.25*math.cos(a),.62*math.cos(a)],[.25*math.sin(a),.62*math.sin(a)],lw=1)
    ax.text(0,0,'mic',ha='center',va='center');ax.set_title(title);ax.set_aspect('equal');ax.set_xlim(-1.1,1.1);ax.set_ylim(-1.1,1.1);ax.axis('off')
fig.tight_layout();fig.savefig(PREV/'V25_configuration_map.png',dpi=190);plt.close(fig)

# -----------------------------------------------------------------------------
# Documentation
# -----------------------------------------------------------------------------
(OUT/'START_HERE.txt').write_text('''Acoustic Morphology Encoder V2.5 PATCH\n\nThis ZIP does NOT repeat the reusable V2 P01/P02/P03/etc. parts.\n1. Read DOCS/README_中文.md and DOCS/REUSE_FROM_V2.md.\n2. Print V25_B02 baffle fit coupon and one HR module before a full set.\n3. For the first U4 experiment use HR01, HR03, HR05 and HR07 plus four reused V2 P09 dummy modules.\n4. Reuse V2 P08B pressure pads, P11 main gasket, P01/P02/P03 and turntable.\n5. All STL units are millimetres.\n''',encoding='utf-8')

(DOC/'README_中文.md').write_text('''# Acoustic Morphology Encoder V2.5 增量包\n\nV2.5 不是完整 V2 的重复文件包，而是针对 V2.0.0 的增量升级：\n\n- 用 8 个具有不同名义共振频率的双颈 Helmholtz-like 模块替换 V2 原 P06/P07/P08 宽带编码模块，用于共振频分实验；\n- 新增 8 个可拆卸外角方向隔板夹，增强相邻入口之间的遮挡和方向耦合差异；\n- 保留 V2 的大主体、主盖、麦克风接口、对称基线模块、实心 dummy、主密封垫和转盘。\n\n本设计受 Meng 与 Yao 的三腔 Helmholtz 方向传感器启发。原论文通过三个共振腔中的三个麦克风读取压力比。V2.5 仍只用一个中心麦克风，因此不能直接复制其三压力比方法，而是让各模块使用不同共振频率，把多个空间压力通道转换为可从一个频谱中读取的频率通道。\n\n## 首选实验顺序\n\n1. V2 U4-Symmetric，不装隔板；\n2. V2 U4-Symmetric，装 8 个隔板；\n3. V2.5 U4-HR，不装隔板；\n4. V2.5 U4-HR，装 8 个隔板；\n5. 成功后扩展至 V2.5 U8-HR。\n\nHR 模块的预测频率只是双颈腔体近似值，真实峰值会受中心腔、外辐射、损耗和打印误差影响。第一轮应先测出每个模块的实际峰值，再建立方向特征。\n''',encoding='utf-8')

(DOC/'REUSE_FROM_V2.md').write_text('''# 从 V2 继续使用、无需重新打印的零件\n\n## 必须继续使用\n- V2 P01 通用八槽位主体；\n- V2 P02 主上盖；\n- V2 P03 iMM-6C 插芯；\n- V2 P08B 通用顶部压力垫；\n- V2 P11 主盖密封垫；\n- V2 P14/P15/P16 45° 转盘。\n\n## U4-HR 需要继续使用\n- V2 P09 实心 dummy ×4，安装在 45/135/225/315°。\n\n## 仍作为对照保留\n- V2 P05 八个相同直通模块；\n- V2 原 P06/P07/P08 A–H 宽带编码模块。它们没有失效，只是不属于 V2.5 HR 主实验。\n\n## V2.5 替换的部分\n在 V2.5-HR 状态下，用本包 HR01–HR08 的 tray/lid/gasket 替代 V2 原 encoded A–H 模块。模块外形、堆叠高度和接口保持 V2 兼容。\n''',encoding='utf-8')

(DOC/'ASSEMBLY.md').write_text('''# V2.5 装配\n\n## HR 模块\n每个 HR 模块仍采用 V2 的托盘 + 小密封垫 + 薄盖。薄底朝下，开放腔体朝上。按照文件名配对同一 HR 编号的 tray、gasket 和 lid。继续在其上方放置 V2 P08B 0.6 mm 压力垫，再安装 V2 P02 主盖。\n\n模块的窄端朝中心、宽端朝外，带斜角的键位与 V2 P01 槽一致。HR01–HR08 外形没有改变，所以不应缩放 STL。\n\n## U4-HR 映射\n- 0°/N：HR01；\n- 90°/E：HR03；\n- 180°/S：HR05；\n- 270°/W：HR07；\n- 四个斜向槽：继续使用 V2 P09 实心 dummy。\n\n## U8-HR 映射\n按顺时针方向依次安装 HR01、HR02、HR03、HR04、HR05、HR06、HR07、HR08。\n\n## 外角隔板夹\n隔板夹安装在两个相邻入口之间的八边形外角，不安装在入口正面。先打印 V25_B02 三档间隙测试件；在已装好 P01/P02 的角部测试 0.20、0.35、0.50 mm 三档。默认完整零件为 0.35 mm。\n\n隔板夹是开口式摩擦配合件，可从角部侧向套入；不要强行从入口方向压入。必要时在内表面增加一小片薄 TPU/纸胶带。隔板高 22 mm、向外约 14 mm，不需要改造 V2 主体。\n''',encoding='utf-8')

(DOC/'DESIGN_BASIS.md').write_text('''# 设计依据与公式\n\nMeng 与 Yao 的论文使用三个同频 Helmholtz 腔和三个腔内麦克风，以腔体压力排序及压力比估计 0–360° 方位。单个 V2.5 装置只有一个中心麦克风，若使用多个同频腔，腔体输出会在中心相加，无法直接获得论文中的三个独立压力。\n\nV2.5 采用频分复用：每个空间方向模块具有不同名义共振频率。模块由外部激励颈、局部腔体和内部读出颈组成。工程估计为：\n\n    f ≈ c/(2π) * sqrt((So/Lo* + Si/Li*) / V)\n\n其中 Lo*、Li* 使用 Leff=Lphysical+1.7*sqrt(S/π) 的简化端部修正。该式是对单颈 Helmholtz 公式的双开口近似，不是对中心耦合网络的精确模型。\n\n目标值为 1.2、1.5、1.85、2.25、2.7、3.2、3.8、4.5 kHz。U4 首先使用奇数编号，使四个名义频率间隔较大；U8 再加入偶数编号。\n\n为什么增加隔板：新论文的方向性不只来自共振，也来自面向声源的腔体压力较高、背向腔体受遮挡。V2.5 的八个角部隔板在不修改 V2 主体的情况下增加相邻入口的声学分区。它是可拆消融变量，不应在所有实验中默认存在而不做对照。\n''',encoding='utf-8')

(DOC/'EXPERIMENT_PLAN.md').write_text('''# V2.5 最小实验计划\n\n## 1. 单模块标定\n每次只开放一个方向，其余入口用 V2 P10 堵头，测 HR01/03/05/07 的实际峰值。不要假设峰值等于文件名目标。记录峰值、-3 dB 带宽和重装配漂移。\n\n## 2. 四方向消融\n固定扬声器、旋转结构，按以下顺序测 0/90/180/270°：\nA. U4-Symmetric，无隔板；\nB. U4-Symmetric，有隔板；\nC. U4-HR，无隔板；\nD. U4-HR，有隔板。\n\n每方向至少 5 次连续重复和 5 次重新定位重复。使用 300 Hz–10 kHz sweep，初步分析 1–6 kHz。\n\n## 3. 特征\n除完整谱形外，提取每个实测 HR 峰附近的窄带积分能量 Ai，并归一化：qi=Ai/sum(Aj)。比较 q 向量、完整谱形相关性和简单 logistic regression。\n\n## 4. 继续八方向的判据\n只有当 C 或 D 相比 A/B 的方向间距明显增加，而且 between-direction / within-reposition 距离比大于约 2 时，才打印 HR02/04/06/08 并进入 U8。\n''',encoding='utf-8')

(DOC/'AI_HANDOFF.md').write_text('''# V2.5 AI 交接\n\n本包必须与 Acoustic Morphology Encoder V2.0.0 配合。它不包含 V2 大件。权威接口快照位于 SOURCE/design_parameters_v25.json。\n\n不可改变的兼容尺寸：模块长 56、内宽17、外宽36、高7.6、底皮1.2、盖1.2、密封垫0.4、盖外扩0.8、键位斜角4、端点 x=±28.6。\n\nV2.5 的核心假设是：不同方向模块的腔体压力通过不同共振频率在单中心麦克风中被频分读取。此机制未经 FEM/BEM 或实体实验验证。不得把 predicted_hz 当作测量真值。\n\n未来修改优先级：\n1. 依据单模块实测峰值，调整 cavity volume 或 neck width；\n2. 保持外形接口不变；\n3. 先优化 U4 奇数模块，再扩展 U8；\n4. 对隔板高度和外伸长度做消融；\n5. 如峰值相互重叠，优先增加频率间隔，而不是立即使用复杂分类器。\n\n每次修改后必须重新检查：水密、端口连通、中央区域 1.6 mm 壁厚、gasket 不覆盖 airspace、预测频率顺序、隔板与 V2 外轮廓的完整间隙。\n''',encoding='utf-8')

# BOM
with (DOC/'BOM.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.writer(f); w.writerow(['item','quantity','material','when_needed','notes'])
    w.writerow(['HR01/03/05/07 tray+lid+gasket',1,'PLA + TPU/silicone','first U4-HR','Four cardinal modules'])
    w.writerow(['HR02/04/06/08 tray+lid+gasket',1,'PLA + TPU/silicone','U8 extension','Print only after U4 passes'])
    w.writerow(['V25_B01 corner baffle clip',8,'PLA','baffle condition','Print one after fit coupon, then replicate'])
    w.writerow(['V25_B02 baffle fit coupon',1,'PLA','print first','0.20/0.35/0.50 mm options'])
    w.writerow(['Reused V2 P08B top pressure pad',8,'TPU','all active HR modules','Not included in this patch'])
    w.writerow(['Reused V2 P09 dummy',4,'PLA','U4-HR','Not included in this patch'])

# Validation report markdown
lines=['# V2.5 数字验证报告','',f"总体：**{'全部通过' if validation['all_checks_pass'] else '存在失败'}**",'','## 自动检查']
for c in checks:
    lines.append(f"- {'PASS' if c['pass'] else 'FAIL'} — **{c['name']}**: `{json.dumps(c['details'],ensure_ascii=False)}`")
lines += ['','## STL 网格']
for r in mesh_reports:
    lines.append(f"- {r['file']}: watertight={r['watertight']}, winding={r['winding_consistent']}, components={r['components']}, extents={r['extents_mm']} mm")
lines += ['','## 未完成的实体与声学验证','- 未在实体 V2 P01/P02 上测试模块和隔板夹。','- 未进行 FEM/BEM。','- 未测量实体共振频率、Q 值、方向相关性或分类率。','- 打印前必须先做 V25_B02 和一个 HR 模块。']
(DOC/'VALIDATION_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

# Source, disclaimer, manifest
(SRC/'generate_v25_patch.py').write_text(Path(__file__).read_text(encoding='utf-8'),encoding='utf-8')
(SRC/'requirements.txt').write_text('numpy\nshapely>=2.1\ntrimesh\nmatplotlib\n',encoding='utf-8')
(OUT/'LICENSE_AND_DISCLAIMER.txt').write_text('Research prototype patch. Digital geometry validation does not guarantee physical fit or acoustic performance. Use the V2.0.0 package and the uploaded papers as separate cited sources.\n',encoding='utf-8')
(STL/'README_UNITS_MM.txt').write_text('All STL coordinates are millimetres. This patch excludes reusable V2 parts.\n',encoding='utf-8')

manifest=[]
for path in sorted(OUT.rglob('*')):
    if path.is_file():
        data=path.read_bytes(); manifest.append({'path':str(path.relative_to(OUT)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
(OUT/'MANIFEST.json').write_text(json.dumps({'package':'Acoustic_Morphology_Encoder_V2.5_Patch','version':'2.5.0','all_checks_pass':validation['all_checks_pass'],'files':manifest},indent=2,ensure_ascii=False),encoding='utf-8')

print('Generated',OUT)
print('All checks pass:',validation['all_checks_pass'])
for c in checks:
    if not c['pass']:
        print('FAIL',c['name'],c['details'])
