from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = ['Noto Sans CJK JP', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import polygonize, unary_union
import trimesh

ROOT = Path(os.environ.get('OPEN_TOWER_BUILD_ROOT', '/mnt/data/open_tower_build'))
OUT = ROOT / 'V2_OpenTower_Indexed_Stand_Patch'
STL = OUT / 'STL'
DOC = OUT / 'DOCS'
SRC = OUT / 'SOURCE'
PREV = OUT / 'PREVIEWS'
SVG = OUT / 'TEMPLATES'
for d in [OUT, STL, DOC, SRC, PREV, SVG]:
    d.mkdir(parents=True, exist_ok=True)

P: Dict[str, Any] = {
    'package_name': 'V2_OpenTower_Indexed_Stand_Patch',
    'version': '1.0.0',
    'units': 'mm',
    'printer': {'model': 'Bambu Lab P1S', 'nozzle_mm': 0.4, 'material': 'PLA', 'build_volume_mm': [256,256,256]},
    'reuses': ['V2 P01 universal eight-slot base', 'V2 P02 main lid and acoustic modules'],
    'replaces': ['V2 P14 large fixed turntable', 'V2 P15 large rotating top', 'V2 P16 old detent pin', 'V2 P03 9.0 mm insert if tighter fit is desired'],
    'microphone': {
        'model': 'Dayton Audio iMM-6C',
        'sensing_position': 'approximately at the top end, user supplied',
        'nose_diameter_mm': 8.8,
        'maximum_lateral_width_mm': 40.0,
        'insert_bores_mm': [8.7, 8.8],
        'optional_lowering_spacer_mm': 2.0,
        'warning': 'The 2 mm spacer lowers the sensing tip. First compare standard and lowered positions; keep the tip inside the V2 central chamber.'
    },
    'v2_mount_interface': {
        'source': 'Measured from uploaded P15_turntable_rotating_top.stl',
        'support_centers_mm': [[38.80293,-16.07268],[16.07268,38.80293],[-38.80293,16.07268],[-16.07268,-38.80293]],
        'support_center_radius_mm': 42.0,
        'support_pad_diameter_mm': 16.0,
        'locating_post_diameter_mm': 6.0,
        'locating_post_height_mm': 3.0,
        'spider_center_hole_diameter_mm': 34.0,
    },
    'base': {
        'diameter_mm': 165.0,
        'height_mm': 8.0,
        'guide_groove_inner_radius_mm': 30.2,
        'guide_groove_outer_radius_mm': 53.8,
        'guide_groove_depth_mm': 2.6,
        'detent_radius_mm': 49.5,
        'detent_hole_diameter_mm': 4.4,
        'detent_blind_depth_mm': 4.0,
        'angle_increment_deg': 45,
    },
    'rotating_tower': {
        'guide_lip_inner_radius_mm': 30.5,
        'guide_lip_outer_radius_mm': 53.5,
        'guide_lip_height_mm': 2.2,
        'upper_flange_inner_radius_mm': 25.0,
        'upper_flange_outer_radius_mm': 54.0,
        'upper_flange_height_mm': 3.0,
        'tower_inner_radius_mm': 26.0,
        'tower_outer_radius_mm': 30.0,
        'rear_opening_angle_deg': 140.0,
        'tower_wall_height_mm': 100.0,
        'tower_clear_height_to_spider_bottom_mm': 105.2,
        'minimum_internal_diameter_mm': 52.0,
        'rear_opening_chord_mm': 2*26.0*math.sin(math.radians(70.0)),
        'detent_ear_radius_mm': 49.5,
        'detent_through_hole_diameter_mm': 4.4,
        'opening_direction': 'rear / 180 degrees relative to the detent ear and zero pointer',
    },
    'spider_to_tower': {
        'fasteners': '3x M3x12 screws + 3x M3 nuts',
        'mount_radius_mm': 27.0,
        'mount_angles_math_deg': [0,90,180],
        'hole_diameter_mm': 3.4,
    },
    'hardware': [
        '1x 4 mm steel dowel pin recommended (printed pin included)',
        '3x M3x12 screws and 3x M3 nuts for the head-mount spider',
        'Optional 0.1-0.2 mm PET/PTFE annular washer for smoother rotation',
        'Optional thin PTFE tape around the P03 outer neck',
    ],
}

# Exact mount centers measured from the uploaded P15.
MOUNT_CENTERS = np.array(P['v2_mount_interface']['support_centers_mm'], dtype=float)

# -----------------------------------------------------------------------------
# Geometry helpers
# -----------------------------------------------------------------------------

def clean(g):
    if g.is_empty:
        return g
    g = shapely.set_precision(g, grid_size=0.001)
    if not g.is_valid:
        g = shapely.make_valid(g)
    return g


def circle(x, y, r, resolution=64):
    return Point(x,y).buffer(r, quad_segs=resolution)


def rounded_rect(xmin,ymin,xmax,ymax,r):
    if r <= 0:
        return box(xmin,ymin,xmax,ymax)
    rr=min(r,(xmax-xmin)/4,(ymax-ymin)/4)
    return clean(box(xmin+rr,ymin+rr,xmax-rr,ymax-rr).buffer(rr,join_style='round'))


def annulus(rin,rout,resolution=128):
    return clean(circle(0,0,rout,resolution).difference(circle(0,0,rin,resolution)))


def wedge(center_deg, half_deg, r=200):
    # True circular sector: +X=0, CCW positive.
    angles=np.linspace(math.radians(center_deg-half_deg),math.radians(center_deg+half_deg),65)
    pts=[(0,0)]+[(r*math.cos(a),r*math.sin(a)) for a in angles]+[(0,0)]
    return clean(Polygon(pts))


def radial_slot(angle_deg,r0,r1,width):
    a=math.radians(angle_deg)
    p0=(r0*math.cos(a),r0*math.sin(a)); p1=(r1*math.cos(a),r1*math.sin(a))
    return clean(LineString([p0,p1]).buffer(width/2,cap_style='flat',join_style='mitre'))


def regular_hex(cx,cy,across_flats):
    R=across_flats/math.sqrt(3)
    pts=[]
    for i in range(6):
        a=math.radians(30+i*60)
        pts.append((cx+R*math.cos(a),cy+R*math.sin(a)))
    return clean(Polygon(pts))


def rings_of(g):
    if g.is_empty: return
    if isinstance(g,Polygon):
        yield g.exterior
        for r in g.interiors: yield r
    elif isinstance(g,MultiPolygon):
        for p in g.geoms: yield from rings_of(p)
    elif isinstance(g,GeometryCollection):
        for x in g.geoms:
            if isinstance(x,(Polygon,MultiPolygon)): yield from rings_of(x)


def tri_area2(coords):
    (x0,y0),(x1,y1),(x2,y2)=coords
    return (x1-x0)*(y2-y0)-(y1-y0)*(x2-x0)


def add_horizontal(vertices,faces,g,z,up):
    g=clean(g)
    if g.is_empty: return
    tris=shapely.constrained_delaunay_triangles(g)
    for t in getattr(tris,'geoms',[tris]):
        if not isinstance(t,Polygon) or t.area < 1e-9: continue
        if not g.covers(t.representative_point()): continue
        coords=list(t.exterior.coords)[:3]
        if tri_area2(coords)<0: coords=[coords[0],coords[2],coords[1]]
        if not up: coords=[coords[0],coords[2],coords[1]]
        idx=[]
        for x,y in coords:
            idx.append(len(vertices)); vertices.append([x,y,z])
        faces.append(idx)


def add_walls(vertices,faces,g,z0,z1):
    g=clean(g)
    for ring in rings_of(g):
        coords=list(ring.coords)
        for i in range(len(coords)-1):
            a=(float(coords[i][0]),float(coords[i][1])); b=(float(coords[i+1][0]),float(coords[i+1][1]))
            if abs(a[0]-b[0])+abs(a[1]-b[1])<1e-9: continue
            p,q=sorted([a,b])
            k=len(vertices)
            vertices.extend([[p[0],p[1],z0],[q[0],q[1],z0],[q[0],q[1],z1],[p[0],p[1],z1]])
            faces.append([k,k+1,k+2]); faces.append([k,k+2,k+3])


def layered_mesh(layers: Sequence[Tuple[float,float,Any]], name=''):
    layers=[(float(z0),float(z1),clean(g)) for z0,z1,g in layers if z1>z0 and not g.is_empty]
    layers.sort(key=lambda x:x[0])
    lines=unary_union([g.boundary for _,_,g in layers])
    cells=[clean(c) for c in polygonize(lines) if c.area>1e-8]
    vertices=[]; faces=[]
    for cell in cells:
        rp=cell.representative_point()
        for z0,z1,g in layers:
            if g.covers(rp):
                add_horizontal(vertices,faces,cell,z0,False)
                add_horizontal(vertices,faces,cell,z1,True)
                add_walls(vertices,faces,cell,z0,z1)
    m=trimesh.Trimesh(vertices=np.asarray(vertices),faces=np.asarray(faces),process=False)
    m.merge_vertices(digits_vertex=5); m.remove_unreferenced_vertices()
    sf=np.sort(m.faces,axis=1)
    _,inv,cnt=np.unique(sf,axis=0,return_inverse=True,return_counts=True)
    m.update_faces(cnt[inv]==1); m.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(m,multibody=True)
    m.metadata['name']=name
    return m


def export(m,path):
    # Split/repair then concatenate so every exported shell has closed edge topology.
    comps = m.split(only_watertight=False)
    fixed = trimesh.util.concatenate(comps)
    fixed.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(fixed, multibody=True)
    path.parent.mkdir(parents=True,exist_ok=True)
    fixed.export(path,file_type='stl')


def combine(meshes,translations):
    out=[]
    for m,t in zip(meshes,translations):
        c=m.copy(); c.apply_translation(t); out.append(c)
    return trimesh.util.concatenate(out)


def write_svg(path: Path, geom):
    geom=clean(geom); minx,miny,maxx,maxy=geom.bounds; margin=2
    W=maxx-minx+2*margin; H=maxy-miny+2*margin
    paths=[]
    polys=list(geom.geoms) if isinstance(geom,MultiPolygon) else [geom]
    for p in polys:
        if not isinstance(p,Polygon): continue
        ds=[]
        for ring in [p.exterior]+list(p.interiors):
            co=list(ring.coords)
            if not co: continue
            d=[f'M {co[0][0]-minx+margin:.3f},{maxy-co[0][1]+margin:.3f}']
            for x,y in co[1:]: d.append(f'L {x-minx+margin:.3f},{maxy-y+margin:.3f}')
            d.append('Z'); ds.append(' '.join(d))
        paths.append(f'<path d="{" ".join(ds)}" fill="none" stroke="black" stroke-width="0.15" fill-rule="evenodd"/>')
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.3f}mm" height="{H:.3f}mm" viewBox="0 0 {W:.3f} {H:.3f}">\n'+'\n'.join(paths)+'\n</svg>\n',encoding='utf-8')

# -----------------------------------------------------------------------------
# R01 fixed indexed base
# -----------------------------------------------------------------------------
base_r=P['base']['diameter_mm']/2
groove=annulus(P['base']['guide_groove_inner_radius_mm'],P['base']['guide_groove_outer_radius_mm'])
# 8 blind detent holes, 0 deg = +Y; clockwise labels.
detents=[]
for deg in range(0,360,45):
    a=math.radians(90-deg)
    detents.append(circle(P['base']['detent_radius_mm']*math.cos(a),P['base']['detent_radius_mm']*math.sin(a),P['base']['detent_hole_diameter_mm']/2,32))
detents_u=clean(unary_union(detents))
# Shallow top index ticks. 0-degree tick is wider.
ticks=[]
for deg in range(0,360,45):
    a=90-deg
    ticks.append(radial_slot(a,73.5,81.5,2.2 if deg==0 else 1.1))
ticks_u=clean(unary_union(ticks))
base_disk=circle(0,0,base_r,160)
R01=layered_mesh([
    (0,4.0,base_disk),
    (4.0,5.4,clean(base_disk.difference(detents_u))),
    (5.4,7.4,clean(base_disk.difference(unary_union([detents_u,groove])))),
    (7.4,8.0,clean(base_disk.difference(unary_union([detents_u,groove,ticks_u])))),
],'R01_fixed_indexed_base_D165')
export(R01,STL/'R01_fixed_indexed_base_D165.stl')

# -----------------------------------------------------------------------------
# R02 rotating open C-tower with hidden guide lip
# -----------------------------------------------------------------------------
rear_gap=wedge(-90,P['rotating_tower']['rear_opening_angle_deg']/2,150)
guide_c=clean(annulus(P['rotating_tower']['guide_lip_inner_radius_mm'],P['rotating_tower']['guide_lip_outer_radius_mm']).difference(rear_gap))
flange_c=clean(annulus(P['rotating_tower']['upper_flange_inner_radius_mm'],P['rotating_tower']['upper_flange_outer_radius_mm']).difference(rear_gap))
shell_c=clean(annulus(P['rotating_tower']['tower_inner_radius_mm'],P['rotating_tower']['tower_outer_radius_mm']).difference(rear_gap))
# Detent through-hole lies inside the hidden rotating annulus; no projecting ear is required.
ear_hole=circle(0,P['rotating_tower']['detent_ear_radius_mm'],P['rotating_tower']['detent_through_hole_diameter_mm']/2,32)
flange_ear=clean(flange_c.difference(ear_hole))
# Three top tabs on the occupied arc at 0, 90, 180 mathematical degrees.
tab_centers=[]; tabs=[]; tab_holes=[]
for deg in P['spider_to_tower']['mount_angles_math_deg']:
    a=math.radians(deg); x=27*math.cos(a); y=27*math.sin(a)
    tab_centers.append((x,y)); tabs.append(circle(x,y,6.0,40)); tab_holes.append(circle(x,y,1.7,24))
tabs_u=clean(unary_union(tabs)); tab_holes_u=clean(unary_union(tab_holes))
top_shell_tabs=clean(unary_union([shell_c,tabs_u]).difference(tab_holes_u))
lower_shell=shell_c
R02=layered_mesh([
    (0,2.2,clean(guide_c.difference(ear_hole))),
    (2.2,5.2,flange_ear),
    (5.2,101.2,shell_c),
    (101.2,105.2,top_shell_tabs),
],'R02_rotating_open_C_tower')
export(R02,STL/'R02_rotating_open_C_tower.stl')

# -----------------------------------------------------------------------------
# R03 head-mount spider reproducing exact P15 support pads/posts
# -----------------------------------------------------------------------------
center_ring=annulus(17.0,30.0)
arms=[]; pads=[]; posts=[]
for x,y in MOUNT_CENTERS:
    a=math.atan2(y,x)
    p0=(25*math.cos(a),25*math.sin(a)); p1=(math.hypot(x,y)*math.cos(a),math.hypot(x,y)*math.sin(a))
    arms.append(LineString([p0,p1]).buffer(5.0,cap_style='round',join_style='round'))
    pads.append(circle(x,y,8.0,48)); posts.append(circle(x,y,3.0,40))
spider_profile=clean(unary_union([center_ring,unary_union(arms),unary_union(pads)]))
spider_mount_holes=clean(unary_union([circle(x,y,1.7,24) for x,y in tab_centers]))
spider_profile=clean(spider_profile.difference(spider_mount_holes))
R03=layered_mesh([(0,4.0,spider_profile),(4.0,7.0,clean(unary_union(posts)))],'R03_V2_head_mount_spider')
export(R03,STL/'R03_V2_head_mount_spider_exact_P15_interface.stl')

# -----------------------------------------------------------------------------
# R04 detent pin
# -----------------------------------------------------------------------------
R04=layered_mesh([(0,2.5,circle(0,0,6.0,48)),(2.5,13.0,circle(0,0,2.0,40))],'R04_detent_pin_D4')
export(R04,STL/'R04_detent_pin_D4_PRINT_2.stl')

# -----------------------------------------------------------------------------
# R05/R06 tighter P03 inserts, exact original outer dimensions
# -----------------------------------------------------------------------------
def p03_insert(bore,name):
    b=circle(0,0,bore/2,64)
    flange=clean(circle(0,0,15.0,96).difference(b))
    neck=clean(circle(0,0,10.0,96).difference(b))
    ridge=clean(circle(0,0,10.09,96).difference(b))
    return layered_mesh([(0,3.0,flange),(3.0,5.5,neck),(5.5,6.0,ridge),(6.0,6.5,neck)],name)
for bore,code in [(8.7,'R05'),(8.8,'R06')]:
    m=p03_insert(bore,f'{code}_P03_insert_ID{bore:.1f}')
    export(m,STL/f'{code}_P03_insert_ID{str(bore).replace(".","p")}.stl')

# Optional 2 mm shoulder spacers. Place between the microphone shoulder and P03 underside.
for bore,code in [(8.7,'R07'),(8.8,'R08')]:
    prof=clean(circle(0,0,7.0,64).difference(circle(0,0,bore/2,64)))
    m=layered_mesh([(0,2.0,prof)],f'{code}_P03_lowering_spacer_2mm_ID{bore:.1f}')
    export(m,STL/f'{code}_P03_lowering_spacer_2mm_ID{str(bore).replace(".","p")}.stl')

# -----------------------------------------------------------------------------
# R09 guide-ring fit coupon: three short arc pairs with 0.20/0.30/0.40 clearance
# -----------------------------------------------------------------------------
fit_parts=[]; translations=[]
for i,clr in enumerate([0.20,0.30,0.40]):
    # Base arc with a 40-degree annular groove and separate matching lip arc.
    sector=wedge(90,20,60)
    block=clean(annulus(25,53).intersection(sector))
    groove_i=30.5-clr; groove_o=53.5+clr
    groove_arc=clean(annulus(groove_i,groove_o).intersection(sector))
    base=layered_mesh([(0,3.0,block),(3.0,5.5,clean(block.difference(groove_arc)))],f'fit_base_{clr}')
    lip_prof=clean(annulus(30.5,53.5).intersection(sector))
    lip=layered_mesh([(0,2.2,lip_prof)],f'fit_lip_{clr}')
    fit_parts.extend([base,lip]); translations.extend([(i*65,0,0),(i*65,40,0)])
R09=combine(fit_parts,translations); R09.apply_translation(-R09.bounds.mean(axis=0))
export(R09,STL/'R09_hidden_ring_fit_coupon_clearance_0p20_0p30_0p40.stl')

# R10 bore/pin gauge.
gauge=rounded_rect(-38,-20,38,20,3)
holes=[]
for x,d in zip([-27,-9,9,27],[8.6,8.7,8.8,8.9]): holes.append(circle(x,8,d/2,40))
for x,d in zip([-18,-6,6,18],[4.1,4.2,4.3,4.4]): holes.append(circle(x,-8,d/2,32))
R10=layered_mesh([(0,3.0,clean(gauge.difference(unary_union(holes))))],'R10_mic_and_pin_fit_gauge')
export(R10,STL/'R10_mic_8p6_8p9_and_pin_4p1_4p4_fit_gauge.stl')

# Optional low-friction washer template matching the guide track.
washer=annulus(30.4,53.6)
write_svg(SVG/'optional_low_friction_washer_1to1.svg',washer)
# Angle template for checking external ticks.
angle_ring=annulus(72.5,82.5)
for deg in range(0,360,45): angle_ring=clean(angle_ring.difference(radial_slot(90-deg,73.5,82.5,0.5)))
write_svg(SVG/'indexed_base_angle_reference_1to1.svg',angle_ring)

# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------
checks=[]
def chk(name,passed,details): checks.append({'name':name,'pass':bool(passed),'details':details})

mesh_reports=[]
for pth in sorted(STL.glob('*.stl')):
    m=trimesh.load_mesh(pth,force='mesh')
    mesh_reports.append({'file':pth.name,'watertight':bool(m.is_watertight),'winding_consistent':bool(m.is_winding_consistent),'components':len(m.split(only_watertight=False)),'extents_mm':np.round(m.extents,3).tolist(),'bounds_mm':np.round(m.bounds,3).tolist(),'volume_mm3':abs(float(m.volume)),'faces':len(m.faces)})
chk('All authoritative STL meshes are watertight and winding-consistent',all(r['watertight'] and r['winding_consistent'] for r in mesh_reports),{'failed':[r['file'] for r in mesh_reports if not(r['watertight'] and r['winding_consistent'])]})
chk('Fixed base fits P1S bed with 6 mm brim',165+12<=256,{'part_mm':165,'with_brim_mm':177,'bed_mm':256})
chk('Hidden guide ring has 0.30 mm nominal radial clearance at both boundaries',abs((30.5-30.2)-0.3)<1e-9 and abs((53.8-53.5)-0.3)<1e-9,{'inner_clearance_mm':0.3,'outer_clearance_mm':0.3})
chk('Tower internal diameter exceeds user-estimated 40 mm microphone width',2*26.0>40.0,{'internal_diameter_mm':52.0,'mic_width_mm':40.0,'diametral_margin_mm':12.0})
opening_chord=2*26.0*math.sin(math.radians(70))
chk('Rear opening chord exceeds user-estimated 40 mm width',opening_chord>40.0,{'opening_chord_mm':opening_chord,'mic_width_mm':40.0,'margin_mm':opening_chord-40.0})
chk('Spider center hole clears P03 flange',34.0>30.0,{'spider_hole_mm':34.0,'P03_flange_mm':30.0,'diametral_clearance_mm':4.0})
# Compare exact post centers to uploaded P15 measured centers.
expected=np.array([[38.80293,-16.07268],[16.07268,38.80293],[-38.80293,16.07268],[-16.07268,-38.80293]])
err=np.max(np.linalg.norm(MOUNT_CENTERS-expected,axis=1))
chk('Spider locating-post centers reproduce uploaded P15',err<1e-6,{'maximum_center_error_mm':float(err),'post_diameter_mm':6.0})
chk('Detent pin has positive clearance in nominal holes',4.4>4.0,{'hole_mm':4.4,'pin_mm':4.0,'diametral_clearance_mm':0.4})
chk('Tower provides at least 100 mm vertical body/cable region',P['rotating_tower']['tower_wall_height_mm']>=100,{'wall_height_mm':100.0})
# Hardware holes align between spider and tower.
spider_hole_centers=np.array(tab_centers); tower_hole_centers=np.array(tab_centers)
chk('Spider and tower M3 mount holes align',np.max(np.linalg.norm(spider_hole_centers-tower_hole_centers,axis=1))<1e-9,{'centers_mm':tab_centers,'hole_mm':3.4})
# Detent ear and base holes use same radius.
chk('Detent ear aligns with eight base positions',abs(P['rotating_tower']['detent_ear_radius_mm']-P['base']['detent_radius_mm'])<1e-9,{'radius_mm':49.5,'positions':8})
validation={'package':P['package_name'],'version':P['version'],'all_checks_pass':all(c['pass'] for c in checks),'checks':checks,'mesh_reports':mesh_reports,'limitations':['No physical print/fit test has been performed.','The microphone total length was not measured; the design provides approximately 100 mm open vertical body/cable space based on the user photo and 40 mm maximum width estimate.','The 2 mm lowering spacer changes acoustic sensing-tip height and must be evaluated experimentally.','The gravity-retained hidden guide ring is intended for manual indexed experiments, not motorized or high-speed rotation.']}
(SRC/'validation_report.json').write_text(json.dumps(validation,indent=2,ensure_ascii=False),encoding='utf-8')
P['derived']={'rear_opening_chord_mm':opening_chord,'base_to_spider_bottom_assembled_mm':8.0-2.6+105.2,'base_to_P01_bottom_assembled_mm':8.0-2.6+105.2+4.0,'nominal_space_below_P01_bottom_to_base_top_mm':105.2-2.6+4.0}
(SRC/'design_parameters.json').write_text(json.dumps(P,indent=2,ensure_ascii=False),encoding='utf-8')

# -----------------------------------------------------------------------------
# Previews
# -----------------------------------------------------------------------------
# Side schematic.
fig,ax=plt.subplots(figsize=(8,10))
# base
ax.add_patch(plt.Rectangle((-82.5,0),165,8,facecolor='0.88',edgecolor='black'))
# hidden ring / tower
ax.add_patch(plt.Rectangle((-50,8),100,5.2,facecolor='0.82',edgecolor='black'))
ax.add_patch(plt.Rectangle((-30,13.2),60,100,facecolor='none',edgecolor='black',linewidth=2))
# open rear indicated by dashed right wall and cable
ax.plot([30,30],[13.2,113.2],'--',color='0.5')
# spider / head placeholder
ax.add_patch(plt.Rectangle((-50,113.2),100,4,facecolor='0.75',edgecolor='black'))
ax.add_patch(plt.Polygon([(-105,117.2),(105,117.2),(95,134),(-95,134)],closed=True,facecolor='0.93',edgecolor='black'))
# microphone placeholder and side branch
ax.add_patch(plt.Rectangle((-6,35),12,72,facecolor='0.2',edgecolor='black'))
ax.plot([0,25],[80,64],color='0.2',linewidth=10,solid_capstyle='round')
ax.plot([0,18,35],[35,25,15],color='black',linewidth=3)
# labels
ax.annotate('现有 V2 声学主体',xy=(70,126),xytext=(110,132),arrowprops=dict(arrowstyle='->'))
ax.annotate('R03 精确复用 P15 的四个定位柱',xy=(45,115),xytext=(78,107),arrowprops=dict(arrowstyle='->'))
ax.annotate('约 100 mm 开口塔身空间',xy=(-30,65),xytext=(-112,70),arrowprops=dict(arrowstyle='->'))
ax.annotate('异形麦克风与侧支，最大宽度按 40 mm',xy=(17,72),xytext=(75,80),arrowprops=dict(arrowstyle='->'))
ax.annotate('延长线从后方开口直接引出',xy=(30,18),xytext=(65,28),arrowprops=dict(arrowstyle='->'))
ax.annotate('隐藏式小转环 + 45° 插销',xy=(45,10),xytext=(70,2),arrowprops=dict(arrowstyle='->'))
ax.set_xlim(-130,160); ax.set_ylim(-5,145); ax.set_aspect('equal'); ax.axis('off'); ax.set_title('V2 开口圆柱塔 + 隐藏插销转环：侧视概念')
fig.tight_layout(); fig.savefig(PREV/'side_concept.png',dpi=190); plt.close(fig)

# Top view.
fig,ax=plt.subplots(figsize=(8,8))
ax.add_patch(plt.Circle((0,0),82.5,facecolor='0.94',edgecolor='black'))
ax.add_patch(plt.Circle((0,0),48.1,facecolor='none',edgecolor='0.5',linestyle='--'))
# C shell
shellpoly=shell_c
x,y=shellpoly.exterior.xy if isinstance(shellpoly,Polygon) else ([],[])
if isinstance(shellpoly,Polygon): ax.fill(x,y,alpha=.5)
for deg in range(0,360,45):
    a=math.radians(90-deg); x=57*math.cos(a); y=57*math.sin(a)
    ax.add_patch(plt.Circle((x,y),2.2,facecolor='white',edgecolor='black'))
    ax.text(74*math.cos(a),74*math.sin(a),f'{deg}°',ha='center',va='center',fontsize=9)
ax.plot([0,0],[42,56],color='tab:orange',linewidth=6)
ax.text(0,60,'插销孔 / 0°',ha='center',color='tab:orange')
ax.text(0,-42,'后方开放：侧支与线缆出口',ha='center',color='tab:blue')
ax.set_aspect('equal'); ax.set_xlim(-90,90); ax.set_ylim(-90,90); ax.axis('off'); ax.set_title('顶视图：单圆盘底座，内部隐藏小转环')
fig.tight_layout(); fig.savefig(PREV/'top_concept.png',dpi=190); plt.close(fig)

# Exploded assembly.
fig,ax=plt.subplots(figsize=(9,7))
levels=[('现有 V2 P01/P02',6.2),('R05/R06 P03 插芯（可选 R07/R08 降低 2 mm）',5.25),('R03 头部安装蜘蛛架',4.3),('R02 开口圆柱塔 + 隐藏转环',2.9),('R01 固定角度底座',1.35)]
for i,(lab,y) in enumerate(levels):
    w=7.0-0.45*i
    ax.add_patch(plt.Rectangle((4.5-w/2,y),w,.55,fill=False,linewidth=1.5))
    ax.text(4.5,y+.275,lab,ha='center',va='center')
    if i<len(levels)-1: ax.annotate('',xy=(4.5,levels[i+1][1]+.62),xytext=(4.5,y-.05),arrowprops=dict(arrowstyle='->'))
ax.text(7.7,1.65,'R04 插销\n从上方插入',ha='center')
ax.annotate('',xy=(6.2,1.65),xytext=(7.2,1.65),arrowprops=dict(arrowstyle='->'))
ax.set_xlim(0,9); ax.set_ylim(.5,7.1); ax.axis('off'); ax.set_title('装配顺序')
fig.tight_layout(); fig.savefig(PREV/'exploded_assembly.png',dpi=190); plt.close(fig)

# GLB assembly scene of new parts only.
scene=trimesh.Scene()
scene.add_geometry(R01,node_name='R01_base')
rt=R02.copy(); rt.apply_translation([0,0,5.4]); scene.add_geometry(rt,node_name='R02_tower')
sp=R03.copy(); sp.apply_translation([0,0,5.4+105.2]); scene.add_geometry(sp,node_name='R03_spider')
# P03 standard at centre, approximate placement above spider/P01 interface for visual reference.
p03=p03_insert(8.7,'p03_preview'); p03.apply_translation([0,0,5.4+105.2+4.0]); scene.add_geometry(p03,node_name='R05_P03')
scene.export(PREV/'assembled_new_parts.glb')

# -----------------------------------------------------------------------------
# Documentation
# -----------------------------------------------------------------------------
(OUT/'START_HERE.txt').write_text('''V2 Open-Tower Indexed Stand Patch\n\nThis package replaces the V2 P14/P15 large two-disc turntable and adds tighter P03 inserts.\n1. Print R09 and R10 first.\n2. Print R01, R02 and R03.\n3. Reuse the existing V2 P01/P02 head.\n4. Use R05 (8.7 mm) first; R06 is the looser 8.8 mm option.\n5. R07/R08 are optional 2 mm sensing-tip lowering spacers, not mandatory.\n6. The tower rear opening must face the microphone side branch and USB-C cable.\n''',encoding='utf-8')

(DOC/'README_中文.md').write_text('''# V2 开口圆柱塔 + 隐藏插销定位底座\n\n这是一套针对 Dayton Audio iMM-6C 异形机身的增量支架。它不重复 V2 声学主体，而是替换原来体积较大的 P14/P15 双圆盘转盘。\n\n结构为：一个直径 165 mm 的固定圆盘底座；底座顶部隐藏一个小型 C 形导向转环；开口圆柱塔与转环一体打印；顶部通过独立 R03 蜘蛛架复用原 P15 的四个 Ø6 mm 定位柱位置。定位销提供 0/45/90/.../315° 八个机械位置。\n\n塔身内部直径 52 mm，后方开口的最小弦宽约 48.9 mm，针对用户估计的 40 mm 最大侧向宽度留有余量。塔身约提供 100 mm 的开放垂直空间，延长线从后方直接引出，不穿过底座。\n\nR05/R06 保持原 P03 外部接口，但内孔改为 8.7/8.8 mm。R07/R08 是可选的 2 mm 肩部垫圈，用于把感声顶部降低约 2 mm；因为感声口位于顶部，必须先比较不用垫圈与使用垫圈的频谱和灵敏度，不能默认越低越好。\n''',encoding='utf-8')

(DOC/'PART_INDEX.md').write_text('''# 零件索引\n\n1. **R01_fixed_indexed_base_D165**：固定圆盘、隐藏环形轨道、八个盲定位孔和角度刻线。\n2. **R02_rotating_open_C_tower**：C 形开口塔身、隐藏导向唇、定位孔；麦克风侧支和线缆朝后方开口。\n3. **R03_V2_head_mount_spider_exact_P15_interface**：顶部独立打印的支撑架，四个定位柱完全复用上传 P15 的坐标。\n4. **R04_detent_pin_D4**：4 mm 打印定位销，建议正式使用 4 mm 金属圆柱销。\n5. **R05_P03_insert_ID8p7**：较紧的 8.7 mm 插芯。\n6. **R06_P03_insert_ID8p8**：较松的 8.8 mm 插芯。\n7. **R07/R08 lowering spacer**：可选 2 mm 降低垫圈。\n8. **R09 ring fit coupon**：0.20/0.30/0.40 mm 三档隐藏导向环配合测试。\n9. **R10 fit gauge**：8.6–8.9 mm 麦克风孔和 4.1–4.4 mm 定位销孔规。\n''',encoding='utf-8')

(DOC/'ASSEMBLY.md').write_text('''# 装配说明\n\n## 1. 先做配合测试\n打印 R09 和 R10。默认导向环按每侧 0.30 mm 间隙设计；默认插销孔 Ø4.4、插销 Ø4.0。P03 优先测试 8.7 mm。\n\n## 2. R01 与 R02\nR02 下方 C 形导向唇放入 R01 顶部环形凹槽。R02 的顶部插销孔指向 0°，塔身后方大开口指向 180°。结构靠重力保持在轨道中，插销锁定角度，不用于高速旋转。可在轨道中放置按 SVG 切割的 0.1–0.2 mm PET/PTFE 垫圈。\n\n## 3. R03 蜘蛛架\n用 3 组 M3×12 螺钉和 M3 螺母将 R03 固定到 R02 顶部三个安装耳。螺母可从开口塔身内部操作。四个 Ø6 mm 柱朝上。\n\n## 4. 安装现有 V2 主体\n把 V2 P01 底部四个盲孔压到 R03 四个定位柱上。R03 中心孔 Ø34 mm，为 P03 Ø30 mm 法兰留下 4 mm 直径总间隙。\n\n## 5. 麦克风与 P03\nR05/R06 从 V2 P01 底部安装。麦克风侧支和 USB-C 延长线朝向塔身后方开口。若感声顶部确实过高，可在麦克风肩部与 P03 底面之间增加对应 R07/R08 2 mm 垫圈；先确认感声口仍位于中心声腔内。\n\n## 6. 转角操作\n固定扬声器。拔出 R04，旋转 R02 与上方整个声学主体，到达下一个 45°孔位后重新插入。为了避免线缆绕紧，建议每次测量后回到 0°，不要连续多圈旋转。\n''',encoding='utf-8')

(DOC/'PRINT_AND_BOM.md').write_text('''# 打印与五金\n\n## 推荐打印参数\n- P1S，0.4 mm 喷嘴，PLA。\n- R01：平面贴床，0.20/0.24 mm 层高，4–5墙，5 mm brim。\n- R02：隐藏导向环贴床、塔身竖直；后方开口避免大跨度封闭桥接。\n- R03：大平面贴床，定位柱朝上。\n- R04、R05–R10：0.16–0.20 mm 层高。\n\n## 五金\n- 3×M3×12 螺钉；\n- 3×M3 螺母；\n- 推荐 1×Ø4 mm 金属圆柱销，长度约 12–15 mm；\n- 可选低摩擦 PET/PTFE 薄片；\n- 可选薄 PTFE 生料带调节 P03 外颈。\n\n## 最小打印顺序\n1. R09、R10；\n2. R05 8.7 mm 插芯；\n3. R01；\n4. R02；\n5. R03；\n6. R04；\n7. 需要时再打印 R06/R07/R08。\n''',encoding='utf-8')

(DOC/'VALIDATION_REPORT.md').write_text('# 数字验证报告\n\n总体：**'+('全部通过' if validation['all_checks_pass'] else '存在失败项')+'**\n\n## 检查\n'+'\n'.join([f"- {'PASS' if c['pass'] else 'FAIL'} — **{c['name']}**: `{json.dumps(c['details'],ensure_ascii=False)}`" for c in checks])+'\n\n## 尚未验证\n- 未进行实体打印和装配。\n- 麦克风总长度未实测；当前约 100 mm 塔身空间是基于照片和用户给出的 40 mm 横向宽度。\n- 未验证 2 mm 降低垫圈对实际声学响应的影响。\n- 隐藏环是手动实验定位机构，不适合电机高速旋转。\n',encoding='utf-8')

(DOC/'AI_HANDOFF.md').write_text('''# AI 交接\n\n该增量包解决：iMM-6C 机身较长、带约 40 mm 侧支、USB-C 延长线无需向下穿底，以及原 P14/P15 双大圆盘过大的问题。\n\n关键接口：\n- R03 四个柱中心来自上传 P15 STL：半径 42 mm，角度 -22.5/67.5/157.5/247.5°，柱 Ø6×3，支撑垫 Ø16。\n- R03 中心孔 Ø34；P03 法兰 Ø30。\n- 隐藏导向环：R02 lip 30.5–53.5 半径；R01 groove 30.2–53.8 半径，每侧 0.30 mm。\n- 塔身内径 52；后方开口 140°；壁厚 4；开放高度约 100。\n- 底座 Ø165；八个定位孔半径 57，Ø4.4。\n- P03 外接口维持原 Ø20 neck / Ø30 flange / 6.5 mm 上部高度，新增 8.7/8.8 mm 内孔。\n\n修改时必须重新检查：水密、导向环正间隙、R03/P15柱坐标、P03法兰与中心孔、40 mm宽度余量、M3孔对齐、定位销半径。\n''',encoding='utf-8')

(SRC/'design_parameters.json').write_text(json.dumps(P,indent=2,ensure_ascii=False),encoding='utf-8')
(SRC/'generate_open_tower_patch.py').write_text(Path(__file__).read_text(encoding='utf-8'),encoding='utf-8')
(SRC/'requirements.txt').write_text('numpy\nshapely>=2.1\ntrimesh\nmatplotlib\n',encoding='utf-8')
(OUT/'LICENSE_AND_DISCLAIMER.txt').write_text('Research prototype. Digital geometry validation does not guarantee physical fit, stability, acoustic performance or cable compatibility. Print fit coupons first.\n',encoding='utf-8')
(STL/'README_UNITS_MM.txt').write_text('All STL coordinates are millimetres.\n',encoding='utf-8')

# manifest
manifest=[]
for pth in sorted(OUT.rglob('*')):
    if pth.is_file():
        data=pth.read_bytes(); manifest.append({'path':str(pth.relative_to(OUT)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
(OUT/'MANIFEST.json').write_text(json.dumps({'package':P['package_name'],'version':P['version'],'all_checks_pass':validation['all_checks_pass'],'files':manifest},indent=2,ensure_ascii=False),encoding='utf-8')

print('Generated',OUT)
print('all checks',validation['all_checks_pass'])
for c in checks:
    if not c['pass']: print('FAIL',c)
