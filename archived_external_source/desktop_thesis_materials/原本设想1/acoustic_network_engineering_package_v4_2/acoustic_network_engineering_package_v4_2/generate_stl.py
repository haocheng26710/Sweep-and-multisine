import os, json, math, zipfile, shutil
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon, Point, LineString, MultiPolygon, box
from shapely.ops import unary_union
from scipy.spatial import Delaunay
import trimesh

# ----------------- Parameters -----------------
OUT = Path(__file__).resolve().parent
MODELS = OUT / 'models'
W = 160.0
H = 125.0
BOTTOM_THICKNESS = 2.0
WALL_HEIGHT = 5.0
BASE_TOTAL_HEIGHT = BOTTOM_THICKNESS + WALL_HEIGHT
COVER_THICKNESS = 2.5
MAIN_CHANNEL_WIDTH = 4.4  # modeled rounded-slot width; nominal 4 mm
BRIDGE_CHANNEL_WIDTH = 2.2  # modeled rounded-slot bridge; nominal 2 mm
SCREW_DIAM = 3.2
SCREW_R = SCREW_DIAM / 2.0
EDGE_MARGIN = 6.0
# Lane center y positions (top to bottom)
LANES = {'A': 96.0, 'B': 74.0, 'C': 52.0, 'D': 30.0}
START_X = 0.0
X1 = 115.0
X2 = 45.0
X3 = 138.0
DY1 = 6.0
DY2 = -6.0
COLLECTOR_X = 142.0
COLLECTOR_W = 5.0
CHAMBER_C = (150.0, 63.0)
CHAMBER_R = 7.0
MIC_PORT_Y = 63.0
MIC_PORT_WIDTH = 4.4
# Screw holes around perimeter; avoid channels
SCREW_HOLES = [(12, 10), (50, 10), (92, 10), (135, 10),
               (12, 116), (50, 116), (92, 116), (135, 116)]
# Bridge geometry chosen for clean 2.5D no-crossing chain topology.
# Path positions are approximate centerline distances from input.
BRIDGES = {
    'AB': {'from':'A', 'to':'B', 'x':88.0, 'from_pass':'first', 'to_pass':'return', 'from_s':83.0, 'to_s':143.0},
    'BC': {'from':'B', 'to':'C', 'x':80.0, 'from_pass':'final', 'to_pass':'return', 'from_s':233.0, 'to_s':151.0},
    'CD': {'from':'C', 'to':'D', 'x':88.0, 'from_pass':'first', 'to_pass':'return', 'from_s':83.0, 'to_s':143.0},
}
STATES = {
    'S0_no_bridges': [],
    'S1_AB': ['AB'],
    'S2_AB_CD': ['AB', 'CD'],
    'Smax_chain_AB_BC_CD': ['AB', 'BC', 'CD'],
}
# ----------------- Geometry helpers -----------------
def ensure_dirs():
    if OUT.exists():
        shutil.rmtree(OUT)
    MODELS.mkdir(parents=True)

def path_points(y):
    # Serpentine centerline: left input -> first long pass -> offset pass -> final pass to collector
    return [(START_X, y), (X1, y), (X1, y+DY1), (X2, y+DY1), (X2, y+DY2), (X3, y+DY2), (COLLECTOR_X, y+DY2)]

def path_length(points):
    total=0
    for (x0,y0),(x1,y1) in zip(points[:-1], points[1:]):
        total += math.hypot(x1-x0, y1-y0)
    return total

def point_on_pass(lane, pass_name, x):
    y = LANES[lane]
    if pass_name == 'first':
        return (x, y)
    if pass_name == 'return':
        return (x, y+DY1)
    if pass_name == 'final':
        return (x, y+DY2)
    raise ValueError(pass_name)

def channel_shapes(open_bridges):
    lines=[]
    # Main channels
    for lane,y in LANES.items():
        lines.append(LineString(path_points(y)).buffer(MAIN_CHANNEL_WIDTH/2.0, cap_style=2, join_style=1, resolution=16))
    # Collector and chamber and mic port. Collector connects all four channel exits.
    collector = LineString([(COLLECTOR_X, LANES['D']+DY2), (COLLECTOR_X, LANES['A']+DY2)]).buffer(COLLECTOR_W/2, cap_style=1, join_style=1, resolution=16)
    chamber = Point(*CHAMBER_C).buffer(CHAMBER_R, resolution=32)
    mic = LineString([(CHAMBER_C[0], MIC_PORT_Y), (W, MIC_PORT_Y)]).buffer(MIC_PORT_WIDTH/2, cap_style=2, join_style=1, resolution=16)
    lines += [collector, chamber, mic]
    # Bridges
    for b in open_bridges:
        info=BRIDGES[b]
        p0=point_on_pass(info['from'], info['from_pass'], info['x'])
        p1=point_on_pass(info['to'], info['to_pass'], info['x'])
        lines.append(LineString([p0,p1]).buffer(BRIDGE_CHANNEL_WIDTH/2, cap_style=1, join_style=1, resolution=16))
    return unary_union(lines)

def ring_points(poly):
    pts = list(poly.exterior.coords)[:-1]
    for interior in poly.interiors:
        pts += list(interior.coords)[:-1]
    return pts

def add_grid_points(poly, spacing=8.0):
    minx,miny,maxx,maxy = poly.bounds
    pts=[]
    xs=np.arange(minx+spacing/2, maxx, spacing)
    ys=np.arange(miny+spacing/2, maxy, spacing)
    for x in xs:
        for y in ys:
            p=Point(float(x),float(y))
            if poly.contains(p):
                pts.append((float(x),float(y)))
    return pts

def triangulate_poly(poly):
    # Returns vertices2d and triangle indices whose centroids lie inside polygon
    # Add boundary and internal grid points.
    pts = ring_points(poly) + add_grid_points(poly, spacing=6.0)
    # Remove duplicates rounded
    seen={}
    uniq=[]
    for x,y in pts:
        key=(round(x,4),round(y,4))
        if key not in seen:
            seen[key]=len(uniq)
            uniq.append((float(x),float(y)))
    pts_arr=np.array(uniq)
    if len(pts_arr) < 3:
        return pts_arr, np.zeros((0,3), dtype=int)
    tri=Delaunay(pts_arr)
    triangles=[]
    for simplex in tri.simplices:
        coords=pts_arr[simplex]
        cx,cy=coords.mean(axis=0)
        # use representative point centroid
        if poly.contains(Point(float(cx),float(cy))):
            triangles.append(simplex.tolist())
    return pts_arr, np.array(triangles, dtype=int)

def extrude_polygon_mesh(poly, z0, z1):
    if poly.is_empty:
        return trimesh.Trimesh(vertices=np.zeros((0,3)), faces=np.zeros((0,3), dtype=int), process=False)
    if isinstance(poly, MultiPolygon):
        meshes=[extrude_polygon_mesh(p, z0, z1) for p in poly.geoms if not p.is_empty and p.area > 1e-6]
        return trimesh.util.concatenate(meshes) if meshes else trimesh.Trimesh(vertices=np.zeros((0,3)), faces=np.zeros((0,3), dtype=int), process=False)
    poly = poly.buffer(0)
    vertices=[]
    faces=[]
    pts2d, tris = triangulate_poly(poly)
    n=len(pts2d)
    # bottom and top vertices
    for x,y in pts2d:
        vertices.append([x,y,z0])
    for x,y in pts2d:
        vertices.append([x,y,z1])
    # Top faces oriented upward; bottom downward
    for tri in tris:
        faces.append([int(tri[0]+n), int(tri[1]+n), int(tri[2]+n)])
        faces.append([int(tri[2]), int(tri[1]), int(tri[0])])
    # Boundary side faces for exterior and interior rings
    def add_side(coords, exterior=True):
        # coords closed maybe; ensure not duplicate
        coords=list(coords)
        if coords[0] == coords[-1]:
            coords=coords[:-1]
        idx_bottom=[]; idx_top=[]
        for x,y in coords:
            vertices.append([x,y,z0]); idx_bottom.append(len(vertices)-1)
            vertices.append([x,y,z1]); idx_top.append(len(vertices)-1)
        m=len(coords)
        for i in range(m):
            j=(i+1)%m
            b0=idx_bottom[i]; b1=idx_bottom[j]; t0=idx_top[i]; t1=idx_top[j]
            if exterior:
                faces.append([b0,b1,t1]); faces.append([b0,t1,t0])
            else:
                # holes have opposite orientation
                faces.append([b1,b0,t0]); faces.append([b1,t0,t1])
    add_side(poly.exterior.coords, exterior=True)
    for interior in poly.interiors:
        add_side(interior.coords, exterior=False)
    mesh=trimesh.Trimesh(vertices=np.array(vertices), faces=np.array(faces), process=True)
    return mesh

def circle_poly(x,y,r,res=32):
    return Point(x,y).buffer(r, resolution=res)

def make_screw_holes():
    return unary_union([circle_poly(x,y,SCREW_R,24) for x,y in SCREW_HOLES])

def surface_mesh_for_region(region, z, upward=True):
    # Create a flat triangulated surface for a Polygon/MultiPolygon at height z.
    if region.is_empty:
        return trimesh.Trimesh(vertices=np.zeros((0,3)), faces=np.zeros((0,3), dtype=int), process=False)
    if isinstance(region, MultiPolygon):
        meshes=[surface_mesh_for_region(p, z, upward) for p in region.geoms if not p.is_empty and p.area > 1e-6]
        return trimesh.util.concatenate(meshes) if meshes else trimesh.Trimesh(vertices=np.zeros((0,3)), faces=np.zeros((0,3), dtype=int), process=False)
    vertices=[]; faces=[]
    pts2d, tris = triangulate_poly(region.buffer(0))
    for x,y in pts2d:
        vertices.append([x,y,z])
    for tri in tris:
        if upward:
            faces.append([int(tri[0]), int(tri[1]), int(tri[2])])
        else:
            faces.append([int(tri[2]), int(tri[1]), int(tri[0])])
    return trimesh.Trimesh(vertices=np.array(vertices), faces=np.array(faces), process=False)

def side_mesh_for_region(region, z0, z1):
    # Vertical side walls along all region boundaries.
    if region.is_empty:
        return trimesh.Trimesh(vertices=np.zeros((0,3)), faces=np.zeros((0,3), dtype=int), process=False)
    if isinstance(region, MultiPolygon):
        meshes=[side_mesh_for_region(p, z0, z1) for p in region.geoms if not p.is_empty and p.area > 1e-6]
        return trimesh.util.concatenate(meshes) if meshes else trimesh.Trimesh(vertices=np.zeros((0,3)), faces=np.zeros((0,3), dtype=int), process=False)
    vertices=[]; faces=[]
    def add_ring(coords, reverse=False):
        coords=list(coords)
        if coords[0] == coords[-1]: coords=coords[:-1]
        n=len(coords)
        ids=[]
        for x,y in coords:
            vertices.append([x,y,z0]); b=len(vertices)-1
            vertices.append([x,y,z1]); t=len(vertices)-1
            ids.append((b,t))
        for i in range(n):
            j=(i+1)%n
            b0,t0=ids[i]; b1,t1=ids[j]
            if not reverse:
                faces.append([b0,b1,t1]); faces.append([b0,t1,t0])
            else:
                faces.append([b1,b0,t0]); faces.append([b1,t0,t1])
    add_ring(region.exterior.coords, reverse=False)
    for interior in region.interiors:
        add_ring(interior.coords, reverse=True)
    return trimesh.Trimesh(vertices=np.array(vertices), faces=np.array(faces), process=False)

def make_base_mesh(open_bridges):
    # A unified stepped open-channel solid: full bottom slab plus raised walls around channels.
    rect=box(0,0,W,H)
    screw=make_screw_holes()
    channels=channel_shapes(open_bridges).intersection(rect).difference(screw).buffer(0)
    bottom_region = rect.difference(screw).buffer(0)
    wall_region = rect.difference(unary_union([channels, screw])).buffer(0)
    parts=[]
    # bottom slab: bottom face and vertical outer/screw sides from z=0 to z=bottom thickness
    parts.append(surface_mesh_for_region(bottom_region, 0, upward=False))
    parts.append(side_mesh_for_region(bottom_region, 0, BOTTOM_THICKNESS))
    # exposed channel floors at z=bottom thickness
    parts.append(surface_mesh_for_region(channels, BOTTOM_THICKNESS, upward=True))
    # raised wall top and all wall sides from channel floor to wall top
    parts.append(surface_mesh_for_region(wall_region, BASE_TOTAL_HEIGHT, upward=True))
    parts.append(side_mesh_for_region(wall_region, BOTTOM_THICKNESS, BASE_TOTAL_HEIGHT))
    mesh=trimesh.util.concatenate(parts)
    mesh.merge_vertices()
    trimesh.repair.fix_normals(mesh)
    return mesh

def make_cover_mesh():
    rect=box(0,0,W,H)
    screw=make_screw_holes()
    region=rect.difference(screw).buffer(0)
    return extrude_polygon_mesh(region, 0, COVER_THICKNESS)

def make_nozzle_adapter_mesh():
    # Optional simple test nozzles: five 4.2 mm OD short cylinders on a small plate.
    meshes=[]
    # base plate
    meshes.append(trimesh.creation.box(extents=[75, 12, 3], transform=trimesh.transformations.translation_matrix([37.5, 6, 1.5])))
    xs=[8,22,36,50,64]
    for x in xs:
        # outer cylinder, axis along X? Easier vertical cylinders, but this is just sizing gauge / optional adapter.
        cyl=trimesh.creation.cylinder(radius=2.1, height=12, sections=48)
        cyl.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [0,1,0]))
        cyl.apply_transform(trimesh.transformations.translation_matrix([x, 13, 6]))
        meshes.append(cyl)
    return trimesh.util.concatenate(meshes)

def export_mesh(mesh, path):
    # Ensure reasonable normals, export binary STL
    mesh.export(str(path))
    return {
        'file': str(path.name),
        'vertices': int(len(mesh.vertices)),
        'faces': int(len(mesh.faces)),
        'watertight': bool(mesh.is_watertight),
        'bounds': mesh.bounds.round(3).tolist(),
    }

def mesh_data_for_viewer(mesh, color, opacity=1.0, offset=(0,0,0)):
    v=(mesh.vertices + np.array(offset)).astype(float)
    f=mesh.faces.astype(int)
    # To reduce JS size, keep faces and vertices separate.
    return {'vertices': np.round(v,3).tolist(), 'faces': f.tolist(), 'color': color, 'opacity': opacity}

# Feature centerlines for viewer in 3D (z above base)
def centerline_data():
    z=BASE_TOTAL_HEIGHT+0.25
    main=[]
    colors={'A':'#1f77ff','B':'#1ca34a','C':'#b000ff','D':'#d99a00'}
    for lane,y in LANES.items():
        pts=[[x,y,z] for x,y in path_points(y)]
        main.append({'name':lane, 'points':pts, 'color':colors[lane], 'width':3})
    bridge_lines=[]
    for name,info in BRIDGES.items():
        p0=point_on_pass(info['from'], info['from_pass'], info['x'])
        p1=point_on_pass(info['to'], info['to_pass'], info['x'])
        bridge_lines.append({'name':name, 'points':[[p0[0],p0[1],z+1.0],[p1[0],p1[1],z+1.0]], 'color':'#e3342f', 'width':5})
    collector=[{'name':'collector', 'points':[[COLLECTOR_X, LANES['D']+DY2,z],[COLLECTOR_X, LANES['A']+DY2,z]], 'color':'#444444','width':2},
               {'name':'mic_port', 'points':[[CHAMBER_C[0],MIC_PORT_Y,z],[W,MIC_PORT_Y,z]], 'color':'#444444','width':2}]
    return {'main':main, 'bridges':bridge_lines, 'collector':collector}

def write_viewer(model_entries, file_manifest):
    # Create index.html, viewer.js, model_data.js
    index = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<title>V4 4端口交叉耦合声学网络</title>
<style>
body{margin:0;font-family:Arial,"Microsoft YaHei",sans-serif;background:#f3f6fb;color:#111;}
#layout{display:flex;height:100vh;width:100vw;}
#sidebar{width:330px;background:#fff;border-right:1px solid #ddd;padding:18px;box-sizing:border-box;overflow:auto;}
#viewerWrap{flex:1;position:relative;background:#eef2f8;}
canvas{width:100%;height:100%;display:block;}
h2{margin:0 0 8px 0;font-size:20px}.small{font-size:12px;color:#444;line-height:1.45}.field{margin-top:16px}select,button{width:100%;padding:10px;margin-top:8px;border-radius:8px;border:1px solid #ccc;background:white;font-size:14px}button.primary{background:#2563eb;color:white;border:none}button.secondary{background:#f1f5f9}.info{background:#f3f4f6;padding:12px;border-radius:8px;margin-top:12px;font-size:12px;white-space:pre-wrap}.legend{font-size:12px;line-height:1.45;margin-top:12px}.sw{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}.row{margin:5px 0}.checks label{display:block;font-size:13px;margin:8px 0}.note{font-size:12px;background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:10px;margin-top:12px}.topBtns{display:grid;grid-template-columns:1fr 1fr;gap:8px}</style>
</head>
<body>
<div id="layout">
  <aside id="sidebar">
    <h2>V4 四端口声学网络查看器</h2>
    <div class="small">左键拖动旋转模型。V4 为机制验证样机：四条主管分道、集成 mixing chamber、固定桥状态底板。</div>
    <div class="field"><b>显示模式</b><select id="modeSelect"></select></div>
    <button id="downloadBtn" class="primary">下载 STL</button>
    <div class="topBtns"><button id="topBtn" class="secondary">顶视图</button><button id="isoBtn" class="secondary">斜视图</button></div>
    <div class="checks">
      <label><input type="checkbox" id="showEdges" checked> 显示 STL 边线</label>
      <label><input type="checkbox" id="showCenter" checked> 显示内部中心线</label>
      <label><input type="checkbox" id="showTransparentCover" checked> 盖板半透明</label>
    </div>
    <div id="info" class="info"></div>
    <div class="legend"><b>颜色说明</b>
      <div class="row"><span class="sw" style="background:#88aee0"></span>核心底板</div>
      <div class="row"><span class="sw" style="background:#aaaaaa"></span>共用盖板</div>
      <div class="row"><span class="sw" style="background:#d8a73e"></span>软管接口示意/测试件</div>
      <div class="row"><span class="sw" style="background:#e3342f"></span>桥管中心线</div>
    </div>
    <div class="note">注意：网页显示为预览与检查用途。打印前请在切片软件中再次检查 STL 尺寸、层高、支撑和孔径。</div>
  </aside>
  <main id="viewerWrap"><canvas id="glcanvas"></canvas></main>
</div>
<script src="model_data.js"></script>
<script src="viewer.js"></script>
</body>
</html>
'''
    (OUT/'index.html').write_text(index, encoding='utf-8')
    data = {
        'models': model_entries,
        'features': centerline_data(),
        'files': file_manifest,
        'params': {'W':W,'H':H,'base_height':BASE_TOTAL_HEIGHT,'cover_thickness':COVER_THICKNESS}
    }
    (OUT/'model_data.js').write_text('const MODEL_DATA = '+json.dumps(data, ensure_ascii=False)+';\n', encoding='utf-8')
    viewer = r'''const canvas = document.getElementById('glcanvas');
const gl = canvas.getContext('webgl', {antialias:true});
if(!gl){ alert('WebGL不可用，请检查浏览器或硬件加速设置。'); }
let rotX = -0.85, rotY = 0.0, dragging=false, lastX=0, lastY=0;
let mode='assembly_Smax';
const select = document.getElementById('modeSelect');
const infoBox = document.getElementById('info');
const downloadBtn = document.getElementById('downloadBtn');
const showEdgesEl=document.getElementById('showEdges');
const showCenterEl=document.getElementById('showCenter');
const showTransparentCoverEl=document.getElementById('showTransparentCover');
const MODES = [
  ['assembly_Smax','完整装配：Smax 链式互连'],
  ['S0_base','S0 底板：无桥'],
  ['S1_base','S1 底板：AB'],
  ['S2_base','S2 底板：AB + CD'],
  ['Smax_base','Smax 底板：AB + BC + CD'],
  ['cover','共用盖板'],
  ['adapter','软管接口测试件']
];
for(const [v,t] of MODES){ const o=document.createElement('option'); o.value=v; o.textContent=t; select.appendChild(o); }
select.value=mode; select.addEventListener('change',()=>{mode=select.value; updateInfo(); draw();});
document.getElementById('topBtn').onclick=()=>{rotX=-Math.PI/2; rotY=0; draw();};
document.getElementById('isoBtn').onclick=()=>{rotX=-0.85; rotY=0.0; draw();};
showEdgesEl.onchange=draw; showCenterEl.onchange=draw; showTransparentCoverEl.onchange=draw;
canvas.addEventListener('mousedown',e=>{dragging=true; lastX=e.clientX; lastY=e.clientY;});
window.addEventListener('mouseup',()=>dragging=false);
window.addEventListener('mousemove',e=>{ if(!dragging) return; const dx=e.clientX-lastX, dy=e.clientY-lastY; lastX=e.clientX; lastY=e.clientY; rotY += dx*0.01; rotX += dy*0.01; draw(); });
window.addEventListener('resize',()=>{resize(); draw();});
function resize(){ const dpr=window.devicePixelRatio||1; const w=canvas.clientWidth*dpr, h=canvas.clientHeight*dpr; if(canvas.width!==w||canvas.height!==h){ canvas.width=w; canvas.height=h; gl.viewport(0,0,w,h); } }
function mat4Identity(){return [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1];}
function mat4Mul(a,b){let r=new Array(16).fill(0); for(let c=0;c<4;c++)for(let row=0;row<4;row++)for(let k=0;k<4;k++)r[c*4+row]+=a[k*4+row]*b[c*4+k]; return r;}
function translate(x,y,z){let m=mat4Identity(); m[12]=x; m[13]=y; m[14]=z; return m;}
function scale(s){let m=mat4Identity(); m[0]=m[5]=m[10]=s; return m;}
function rotXmat(a){let c=Math.cos(a),s=Math.sin(a),m=mat4Identity(); m[5]=c;m[6]=s;m[9]=-s;m[10]=c; return m;}
function rotYmat(a){let c=Math.cos(a),s=Math.sin(a),m=mat4Identity(); m[0]=c;m[2]=-s;m[8]=s;m[10]=c; return m;}
function perspective(fovy,aspect,near,far){let f=1/Math.tan(fovy/2),nf=1/(near-far);return [f/aspect,0,0,0, 0,f,0,0, 0,0,(far+near)*nf,-1, 0,0,2*far*near*nf,0];}
function rgb(hex,alpha){hex=hex.replace('#','');return [parseInt(hex.slice(0,2),16)/255,parseInt(hex.slice(2,4),16)/255,parseInt(hex.slice(4,6),16)/255,alpha];}
const vs=`attribute vec3 aPos; uniform mat4 uMVP; void main(){ gl_Position=uMVP*vec4(aPos,1.0); }`;
const fs=`precision mediump float; uniform vec4 uColor; void main(){ gl_FragColor=uColor; }`;
function shader(type,src){let s=gl.createShader(type); gl.shaderSource(s,src); gl.compileShader(s); if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)) console.error(gl.getShaderInfoLog(s)); return s;}
const prog=gl.createProgram(); gl.attachShader(prog,shader(gl.VERTEX_SHADER,vs)); gl.attachShader(prog,shader(gl.FRAGMENT_SHADER,fs)); gl.linkProgram(prog); gl.useProgram(prog);
const locPos=gl.getAttribLocation(prog,'aPos'), locMVP=gl.getUniformLocation(prog,'uMVP'), locColor=gl.getUniformLocation(prog,'uColor');
function getMVP(){ let M=mat4Identity(); M=mat4Mul(translate(-80,-62.5,-4),M); M=mat4Mul(rotXmat(rotX),M); M=mat4Mul(rotYmat(rotY),M); M=mat4Mul(scale(0.016),M); M=mat4Mul(translate(0,0,-4.2),M); let P=perspective(45*Math.PI/180,canvas.width/canvas.height,0.1,100); return mat4Mul(P,M); }
function meshBuffers(mesh){ if(mesh._buf) return mesh._buf; const verts=new Float32Array(mesh.vertices.flat()); const inds=new Uint32Array(mesh.faces.flat()); const vbuf=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER,vbuf); gl.bufferData(gl.ARRAY_BUFFER,verts,gl.STATIC_DRAW); const ibuf=gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,ibuf); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,inds,gl.STATIC_DRAW); mesh._buf={vbuf,ibuf,count:inds.length}; return mesh._buf; }
function edgeBuffers(mesh){ if(mesh._ebuf) return mesh._ebuf; const edges=[]; const seen=new Set(); for(const f of mesh.faces){ for(let i=0;i<3;i++){ let a=f[i], b=f[(i+1)%3]; let k=a<b?`${a}_${b}`:`${b}_${a}`; if(!seen.has(k)){seen.add(k); edges.push(a,b);} } } const inds=new Uint32Array(edges); const ibuf=gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,ibuf); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,inds,gl.STATIC_DRAW); mesh._ebuf={ibuf,count:inds.length}; return mesh._ebuf; }
function drawMesh(mesh, color, opacityOverride=null){ const b=meshBuffers(mesh); gl.bindBuffer(gl.ARRAY_BUFFER,b.vbuf); gl.vertexAttribPointer(locPos,3,gl.FLOAT,false,0,0); gl.enableVertexAttribArray(locPos); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,b.ibuf); const a = opacityOverride===null ? mesh.opacity : opacityOverride; gl.uniform4fv(locColor, rgb(color||mesh.color,a)); gl.drawElements(gl.TRIANGLES,b.count,gl.UNSIGNED_INT,0); if(showEdgesEl.checked){ const eb=edgeBuffers(mesh); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,eb.ibuf); gl.uniform4fv(locColor,[0.1,0.13,0.16,0.35]); gl.drawElements(gl.LINES,eb.count,gl.UNSIGNED_INT,0); } }
function lineBuffer(points){ const verts=new Float32Array(points.flat()); const buf=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER,buf); gl.bufferData(gl.ARRAY_BUFFER,verts,gl.STATIC_DRAW); return {buf,count:points.length}; }
function drawLine(points,color,width=3){ const b=lineBuffer(points); gl.bindBuffer(gl.ARRAY_BUFFER,b.buf); gl.vertexAttribPointer(locPos,3,gl.FLOAT,false,0,0); gl.enableVertexAttribArray(locPos); gl.uniform4fv(locColor,rgb(color,1)); gl.lineWidth(width); gl.drawArrays(gl.LINE_STRIP,0,b.count); }
function visibleKeys(){ if(mode==='assembly_Smax') return ['Smax_base','cover','adapter']; if(mode==='S0_base') return ['S0_base','cover']; if(mode==='S1_base') return ['S1_base','cover']; if(mode==='S2_base') return ['S2_base','cover']; if(mode==='Smax_base') return ['Smax_base','cover']; if(mode==='cover') return ['cover']; if(mode==='adapter') return ['adapter']; return []; }
function draw(){ resize(); gl.clearColor(0.93,0.96,1,1); gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT); gl.enable(gl.DEPTH_TEST); gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA); gl.uniformMatrix4fv(locMVP,false,new Float32Array(getMVP())); let keys=visibleKeys(); for(const k of keys){ let mesh=MODEL_DATA.models[k]; let alpha=mesh.opacity; if(k==='cover' && showTransparentCoverEl.checked) alpha=0.35; let col=mesh.color; if(k===mode) col='#ff7a1a'; drawMesh(mesh,col,alpha); } if(showCenterEl.checked){ for(const l of MODEL_DATA.features.main) drawLine(l.points,l.color,3); for(const l of MODEL_DATA.features.collector) drawLine(l.points,l.color,2); const active = mode==='S0_base'?[]: mode==='S1_base'?['AB']: mode==='S2_base'?['AB','CD']: ['AB','BC','CD']; for(const l of MODEL_DATA.features.bridges){ if(mode==='assembly_Smax' || mode==='Smax_base' || active.includes(l.name)) drawLine(l.points,l.color,5); } } }
function updateInfo(){ const labels={assembly_Smax:'完整装配预览。显示 Smax 链式互连状态，盖板默认半透明。此项不提供整体 STL。',S0_base:'S0 底板：无桥管，四条主管独立汇入 mixing chamber。',S1_base:'S1 底板：仅 AB 桥打开。',S2_base:'S2 底板：AB 与 CD 桥打开。',Smax_base:'Smax 底板：链式 AB + BC + CD 打开。',cover:'共用实心盖板：用于所有底板状态。',adapter:'软管接口测试件：用于试套 4 mm 内径软管，可按需修改。'}; infoBox.textContent=labels[mode]+'\n\n尺寸：底板约 160 × 125 × 7 mm；盖板 160 × 125 × 2.5 mm。主通道为圆角槽，名义 4 mm。'; const file=MODEL_DATA.files[mode]; if(file){ downloadBtn.style.display='block'; downloadBtn.textContent='下载：'+file; downloadBtn.onclick=()=>{ window.location.href='models/'+file; }; } else { downloadBtn.style.display='none'; } }
updateInfo(); draw();
'''
    (OUT/'viewer.js').write_text(viewer, encoding='utf-8')


def write_docs(mesh_checks):
    # Compute lengths
    lengths={lane:round(path_length(path_points(y)),2) for lane,y in LANES.items()}
    params = []
    params.append('V4 四端口交叉耦合内部声学网络 — 初版机制验证样机')
    params.append('')
    params.append('设计检查与保守修正：')
    params.append('- 选择 2.5D 机制验证 coupon，而非真正三维 stacked 结构。')
    params.append('- 放弃 V3 的堵塞件和独立软管式 mic manifold，改为一体化 mixing chamber。')
    params.append('- Smax 采用链式互连 AB + BC + CD，避免 2.5D 平面内强行连接 DA 导致交叉。')
    params.append('- 采用共用实心盖板 + 底板圆角槽，减少打印件数量；代价是截面不是精确圆管。')
    params.append('- 150×150 mm 目标下，最终底板约 160×125 mm；仍远小于 Bambu Lab P1S 256×256 mm 平台。')
    params.append('')
    params.append('总体尺寸：')
    params.append(f'- 底板外形：{W} × {H} × {BASE_TOTAL_HEIGHT} mm')
    params.append(f'- 共用盖板：{W} × {H} × {COVER_THICKNESS} mm')
    params.append('- 主通道截面：名义 4.0 mm；建模为 4.4 mm 宽圆角槽，槽深约 5 mm，由共用平盖板密封。')
    params.append('- 桥管截面：名义 2.0 mm；建模为 2.2 mm 宽圆角槽。')
    params.append('')
    params.append('路径长度：')
    for lane,L in lengths.items(): params.append(f'- {lane}: {L} mm')
    params.append('')
    params.append('桥管状态：')
    params.append('- S0_no_bridges: 无桥')
    params.append('- S1_AB: AB')
    params.append('- S2_AB_CD: AB + CD')
    params.append('- Smax_chain_AB_BC_CD: AB + BC + CD')
    params.append('')
    params.append('桥管位置（按中心线累计距离近似）：')
    for name,info in BRIDGES.items():
        params.append(f'- {name}: {info["from"]}@{info["from_s"]} mm <-> {info["to"]}@{info["to_s"]} mm；物理 x={info["x"]} mm')
    params.append('')
    params.append('软管与传感器：')
    params.append('- 输入端口和麦克风端均按 4 mm 内径常见塑料软管连接思路预留。')
    params.append('- 扬声器：普通入耳式耳机，例如水月雨竹 2；麦克风：iMM-6C。二者外形未被直接建模。')
    params.append('')
    params.append('仿真影响说明：')
    params.append('- 使用共用平盖板的圆角槽会使截面不同于理想圆管；一维声学仿真中应使用等效截面积或等效水力直径，而不是严格 4 mm 圆管。')
    params.append('- 由于 S0/S1/S2/Smax 共用相同主管截面，比较“桥管是否提高可分性”的相对趋势仍然有意义。')
    params.append('- 第一轮仿真建议先用相同损耗模型和等效截面，重点比较传递函数相关性、有效秩和插入损耗，而不是精确预测每个峰谷。')
    params.append('')
    params.append('网格检查：')
    for k,v in mesh_checks.items():
        params.append(f'- {k}: {v}')
    (OUT/'model_params.txt').write_text('\n'.join(params), encoding='utf-8')

    sim={
        'version':'V4',
        'purpose':'Initial 4-port internal cross-coupled duct network coupon for transfer-function separability tests.',
        'units':'mm',
        'acoustic_frequency_range_hz':[0,8000],
        'main_channel':{
            'nominal_diameter_mm':4.0,
            'modeled_slot_width_mm':MAIN_CHANNEL_WIDTH,
            'slot_depth_mm':WALL_HEIGHT,
            'cross_section_note':'Rounded slot sealed by a common flat cover; not a perfect circular tube. Use equivalent area/hydraulic diameter for 1D simulation.'
        },
        'bridge_channel':{
            'nominal_diameter_mm':2.0,
            'modeled_slot_width_mm':BRIDGE_CHANNEL_WIDTH,
            'bridge_note':'Bridges are integrated into state-specific bases as rounded slots; Smax is chain topology AB+BC+CD.'
        },
        'dimensions_mm':{'width':W,'height':H,'base_total_height':BASE_TOTAL_HEIGHT,'cover_thickness':COVER_THICKNESS},
        'ports':{'inputs':['A','B','C','D'],'output':'mic_mixing_chamber'},
        'centerlines':{lane:path_points(y) for lane,y in LANES.items()},
        'centerline_lengths_mm':{lane:round(path_length(path_points(y)),3) for lane,y in LANES.items()},
        'collector':{'x':COLLECTOR_X,'from_y':LANES['D']+DY2,'to_y':LANES['A']+DY2,'width_mm':COLLECTOR_W},
        'mixing_chamber':{'center':CHAMBER_C,'radius_mm':CHAMBER_R},
        'mic_port':{'from':CHAMBER_C,'to':[W,MIC_PORT_Y],'width_mm':MIC_PORT_WIDTH},
        'bridges':BRIDGES,
        'states':STATES,
        'screw_holes':{'diameter_mm':SCREW_DIAM,'centers_mm':SCREW_HOLES},
        'recommended_measurement_states':['S0_no_bridges','S1_AB','S2_AB_CD','Smax_chain_AB_BC_CD'],
        'recommended_features':['normalized log magnitude 500-8000 Hz','complex transfer function if phase stable','impulse response for qualitative echo analysis'],
    }
    (OUT/'sim_params.json').write_text(json.dumps(sim, indent=2, ensure_ascii=False), encoding='utf-8')

    readme = '''V4 工程包说明
================

目标
----
该模型是“4端口可重构/多状态交叉耦合内部声学网络”的初期机制验证样机。它不是最终精密产品。

打开网页查看器
--------------
解压后双击 index.html。鼠标左键拖动旋转模型。可以选择 S0/S1/S2/Smax 底板、共用盖板和软管接口测试件，并下载对应 STL。

打印建议
--------
- 材料：PLA。
- 喷嘴：0.4 mm。
- 建议层高：0.16–0.20 mm。
- 建议外墙：4 道以上。
- 底板和盖板均平放打印。
- 盖板与底板之间可使用薄硅胶片、真空脂或薄密封垫以改善气密性。
- 螺丝孔为 3.2 mm，适合 M3 级别紧固件；请根据实际打印收缩微调。

模块
----
- core_base_S0_no_bridges.stl：无桥底板。
- core_base_S1_AB.stl：仅 AB 桥。
- core_base_S2_AB_CD.stl：AB + CD 桥。
- core_base_Smax_chain_AB_BC_CD.stl：链式 AB + BC + CD 桥。
- core_cover_common.stl：所有状态共用盖板。
- tube_adapter_test.stl：4 mm 内径软管试套/接口测试件，可选打印。

实验建议
--------
1. 先打印 S0 和共用盖板，检查密封、端口连接和频扫测量流程。
2. 再打印 S1、S2、Smax 底板。
3. 麦克风固定在右侧汇总口，扬声器通过短 4 mm 内径软管依次接 A/B/C/D。
4. 未激励端口应使用一致的硬封堵方式。
5. 推荐使用 log chirp 或白噪声，分析 500–8000 Hz 频段。
6. 主要比较 S0/S1/S2/Smax 的传递函数相关性矩阵、有效秩、重复性和能量归一化分类准确率。

重要限制
--------
- V4 使用共用平盖板的圆角槽截面，不是严格圆管。
- 该模型未经过真实声学仿真和打印验证。
- 尺寸和桥管参数是初版实验参数，适合快速验证规律，不代表最终结构。
'''
    (OUT/'README.txt').write_text(readme, encoding='utf-8')

    notes = '''Codex Notes for V4
==================

Code entry point:
- generate_stl.py regenerates all STL, model_data.js, sim_params.json and documentation.

Important parameters:
- W, H: base plate footprint.
- MAIN_CHANNEL_WIDTH: modeled slot width for nominal 4 mm channels.
- BRIDGE_CHANNEL_WIDTH: modeled slot width for nominal 2 mm bridges.
- LANES: A/B/C/D lane y positions.
- path_points(y): defines the shared serpentine path used by all four ducts.
- BRIDGES: bridge topology and approximate path-length coordinates.
- STATES: which bridges are open in each base state.

Design philosophy:
- Four base states share the exact same main duct layout.
- Bridge topology is integrated into the state-specific base STL, not controlled by plugs.
- A single common flat cover is used to reduce printing workload.
- The cross-section is a rounded slot rather than an ideal circular tube; sim_params.json records this.

For simulation:
- Treat each path segment between vertices and bridge junctions as 1D acoustic graph edges.
- Use equivalent area/hydraulic diameter for the rounded slot.
- For first-pass modeling, keep the same loss model for all states and compare relative changes in correlation/effective rank.

Potential future changes:
- Add a DA bridge only if a stacked or multi-layer design is adopted.
- Replace common cover with matching half-round covers if circular cross-section becomes important.
- Add export of centerline graph in GraphML/CSV for direct simulation.
'''
    (OUT/'codex_notes.txt').write_text(notes, encoding='utf-8')


def copy_generator_script():
    # Copy this script into package as generate_stl.py, but replace output path with local relative output if run later.
    txt=Path('/mnt/data/generate_v4.py').read_text(encoding='utf-8')
    txt=txt.replace("OUT = Path(__file__).resolve().parent", "OUT = Path(__file__).resolve().parent")
    (OUT/'generate_stl.py').write_text(txt, encoding='utf-8')


def main():
    ensure_dirs()
    mesh_checks={}
    base_meshes={}
    for state, open_bridges in STATES.items():
        mesh=make_base_mesh(open_bridges)
        fname=f'core_base_{state}.stl'
        check=export_mesh(mesh, MODELS/fname)
        mesh_checks[fname]=check
        base_meshes[state]=mesh
    cover=make_cover_mesh()
    mesh_checks['core_cover_common.stl']=export_mesh(cover, MODELS/'core_cover_common.stl')
    adapter=make_nozzle_adapter_mesh()
    mesh_checks['tube_adapter_test.stl']=export_mesh(adapter, MODELS/'tube_adapter_test.stl')
    # Viewer entries: use STL meshes with offsets. Cover offset upward for assembly but can show alone too.
    model_entries={
        'S0_base': mesh_data_for_viewer(base_meshes['S0_no_bridges'], '#88aee0', 0.95),
        'S1_base': mesh_data_for_viewer(base_meshes['S1_AB'], '#88aee0', 0.95),
        'S2_base': mesh_data_for_viewer(base_meshes['S2_AB_CD'], '#88aee0', 0.95),
        'Smax_base': mesh_data_for_viewer(base_meshes['Smax_chain_AB_BC_CD'], '#88aee0', 0.95),
        'cover': mesh_data_for_viewer(cover, '#aaaaaa', 0.65, offset=(0,0,BASE_TOTAL_HEIGHT+1.0)),
        'adapter': mesh_data_for_viewer(adapter, '#d8a73e', 0.9, offset=(83, 108, 10)),
    }
    file_manifest={
        'S0_base':'core_base_S0_no_bridges.stl',
        'S1_base':'core_base_S1_AB.stl',
        'S2_base':'core_base_S2_AB_CD.stl',
        'Smax_base':'core_base_Smax_chain_AB_BC_CD.stl',
        'cover':'core_cover_common.stl',
        'adapter':'tube_adapter_test.stl'
    }
    write_viewer(model_entries, file_manifest)
    write_docs(mesh_checks)
    copy_generator_script()
    # zip package
    zip_path=Path('/mnt/data/acoustic_network_engineering_package_v4.zip')
    if zip_path.exists(): zip_path.unlink()
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in OUT.rglob('*'):
            z.write(p, p.relative_to(OUT.parent))
    print('Created', zip_path)
    print(json.dumps(mesh_checks, indent=2))

if __name__=='__main__':
    main()
