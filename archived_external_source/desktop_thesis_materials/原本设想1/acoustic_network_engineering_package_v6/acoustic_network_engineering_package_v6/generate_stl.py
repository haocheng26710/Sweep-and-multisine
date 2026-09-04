import os, json, math, zipfile, shutil
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon, Point, LineString, MultiPolygon, box
from shapely.ops import unary_union
from scipy.spatial import Delaunay
import trimesh

OUT = Path('/mnt/data/acoustic_network_engineering_package_v6')
MODELS = OUT / 'models'
W = 160.0
H = 140.0
BOTTOM_THICKNESS = 2.0
WALL_HEIGHT = 5.0
BASE_TOTAL_HEIGHT = BOTTOM_THICKNESS + WALL_HEIGHT
COVER_THICKNESS = 2.5
MAIN_CHANNEL_WIDTH = 4.4
BRIDGE_CHANNEL_WIDTH = 2.2
SCREW_DIAM = 3.2
SCREW_R = SCREW_DIAM/2
# Each duct is a single non-self-intersecting serpentine: right -> down -> left -> down -> right -> short neck.
LANES = {
    'A': {'ys': (104.0, 97.0, 90.0), 'xR': 110.0, 'xL': 42.0, 'xOut': 124.0, 'ch_pt': (137.25, 74.0)},
    'B': {'ys': (82.0, 75.0, 68.0), 'xR': 116.0, 'xL': 40.0, 'xOut': 125.0, 'ch_pt': (131.14, 68.0)},
    'C': {'ys': (60.0, 53.0, 46.0), 'xR': 116.0, 'xL': 40.0, 'xOut': 125.0, 'ch_pt': (131.14, 52.0)},
    'D': {'ys': (38.0, 31.0, 24.0), 'xR': 112.0, 'xL': 42.0, 'xOut': 124.0, 'ch_pt': (137.25, 46.0)},
}
CHAMBER_C=(145.0,60.0)
CHAMBER_R=16.0
MIC_PORT_WIDTH=4.4
SCREW_HOLES = [(12,10),(46,10),(80,10),(114,10),(148,10),
               (12,130),(46,130),(80,130),(114,130),(148,130)]
# Bridges connect a late/final segment of one duct to an early/first segment of the next duct. This avoids crossing the next duct's folded return leg.
BRIDGES={
    'AB': {'from':'A','to':'B','x':80.0,'from_pass':'final','to_pass':'first'},
    'BC': {'from':'B','to':'C','x':80.0,'from_pass':'final','to_pass':'first'},
    'CD': {'from':'C','to':'D','x':80.0,'from_pass':'final','to_pass':'first'},
}
STATES={
    'S0_no_bridges': [],
    'S1_AB': ['AB'],
    'S2_AB_CD': ['AB','CD'],
    'Smax_chain_AB_BC_CD': ['AB','BC','CD'],
}


def ensure_dirs():
    if OUT.exists(): shutil.rmtree(OUT)
    MODELS.mkdir(parents=True)

def path_points(lane):
    p=LANES[lane]
    y0,y1,y2=p['ys']; xR=p['xR']; xL=p['xL']; xOut=p['xOut']
    # This is a simple S/serpentine, not a branch: the two vertical turns are at the outer ends and never cross an existing leg.
    return [(0,y0),(xR,y0),(xR,y1),(xL,y1),(xL,y2),(xOut,y2),p['ch_pt']]

def path_length(pts):
    return sum(math.hypot(x1-x0,y1-y0) for (x0,y0),(x1,y1) in zip(pts[:-1],pts[1:]))

def point_on_pass(lane, pass_name, x):
    y0,y1,y2=LANES[lane]['ys']
    if pass_name=='first': return (x,y0)
    if pass_name=='return': return (x,y1)
    if pass_name=='final': return (x,y2)
    raise ValueError(pass_name)

def channel_shapes(open_bridges):
    regions=[]
    for lane in LANES:
        regions.append(LineString(path_points(lane)).buffer(MAIN_CHANNEL_WIDTH/2, cap_style=2, join_style=1, resolution=20))
    chamber=Point(*CHAMBER_C).buffer(CHAMBER_R, resolution=64)
    mic=LineString([(CHAMBER_C[0],CHAMBER_C[1]),(W,CHAMBER_C[1])]).buffer(MIC_PORT_WIDTH/2, cap_style=2, join_style=1, resolution=20)
    regions += [chamber,mic]
    for b in open_bridges:
        info=BRIDGES[b]
        p0=point_on_pass(info['from'],info['from_pass'],info['x'])
        p1=point_on_pass(info['to'],info['to_pass'],info['x'])
        regions.append(LineString([p0,p1]).buffer(BRIDGE_CHANNEL_WIDTH/2, cap_style=1, join_style=1, resolution=24))
    return unary_union(regions).intersection(box(0,0,W,H)).buffer(0)

def bridge_shapes(open_bridges):
    regs=[]
    for b in open_bridges:
        info=BRIDGES[b]
        p0=point_on_pass(info['from'],info['from_pass'],info['x'])
        p1=point_on_pass(info['to'],info['to_pass'],info['x'])
        regs.append(LineString([p0,p1]).buffer(BRIDGE_CHANNEL_WIDTH/2, cap_style=1, join_style=1, resolution=24))
    return unary_union(regs) if regs else Polygon()

def screw_poly():
    return unary_union([Point(x,y).buffer(SCREW_R, resolution=24) for x,y in SCREW_HOLES])

def extrude_geom_trimesh(g, height):
    if g.is_empty:
        return trimesh.Trimesh(vertices=np.zeros((0,3)), faces=np.zeros((0,3), dtype=int), process=False)
    if isinstance(g, MultiPolygon):
        meshes=[extrude_geom_trimesh(p, height) for p in g.geoms if p.area > 1e-6]
        return trimesh.util.concatenate(meshes) if meshes else trimesh.Trimesh(vertices=np.zeros((0,3)), faces=np.zeros((0,3), dtype=int), process=False)
    return trimesh.creation.extrude_polygon(g.buffer(0), height=height)

def make_base_mesh(open_bridges):
    rect=box(0,0,W,H)
    screw=screw_poly()
    ch=channel_shapes(open_bridges).difference(screw).buffer(0)
    bottom=rect.difference(screw).buffer(0)
    walls=rect.difference(unary_union([ch,screw])).buffer(0)
    bottom_mesh=extrude_geom_trimesh(bottom, BOTTOM_THICKNESS)
    wall_mesh=extrude_geom_trimesh(walls, WALL_HEIGHT)
    wall_mesh.apply_translation([0,0,BOTTOM_THICKNESS])
    mesh=trimesh.util.concatenate([bottom_mesh, wall_mesh])
    trimesh.repair.fix_normals(mesh)
    return mesh

def make_cover_mesh():
    region=box(0,0,W,H).difference(screw_poly()).buffer(0)
    mesh=extrude_geom_trimesh(region, COVER_THICKNESS)
    trimesh.repair.fix_normals(mesh)
    return mesh

def make_tube_adapter_test():
    meshes=[]
    meshes.append(trimesh.creation.box(extents=[70,14,3], transform=trimesh.transformations.translation_matrix([35,7,1.5])))
    xs=[14,35,56]; radii=[2.05,2.10,2.15]
    for x,r in zip(xs,radii):
        cyl=trimesh.creation.cylinder(radius=r,height=16,sections=64)
        cyl.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2,[0,1,0]))
        cyl.apply_transform(trimesh.transformations.translation_matrix([x,17,7]))
        meshes.append(cyl)
    return trimesh.util.concatenate(meshes)

def export_mesh(mesh,path):
    mesh.export(str(path))
    return {'file':path.name,'vertices':int(len(mesh.vertices)),'faces':int(len(mesh.faces)),'watertight':bool(mesh.is_watertight),'bounds':np.round(mesh.bounds,3).tolist()}

def poly_to_path(poly, scale=5, yflip=True):
    def one(p):
        coords=list(p.exterior.coords)
        if not coords: return ''
        parts=[]
        for i,(x,y) in enumerate(coords):
            yy=H-y if yflip else y
            parts.append(('M' if i==0 else 'L')+f'{x*scale:.2f},{yy*scale:.2f}')
        parts.append('Z')
        return ' '.join(parts)
    if poly.is_empty: return ''
    if isinstance(poly, MultiPolygon): return ' '.join(one(g) for g in poly.geoms)
    return one(poly)

def centerline_svg(scale=5):
    colors={'A':'#1f77ff','B':'#1ca34a','C':'#b000ff','D':'#d99a00'}
    lines=[]
    for lane in LANES:
        pts=path_points(lane)
        s=' '.join(f'{x*scale:.2f},{(H-y)*scale:.2f}' for x,y in pts)
        lines.append(f'<polyline points="{s}" fill="none" stroke="{colors[lane]}" stroke-width="2" opacity="0.9"/>')
        x0,y0=pts[0]
        lines.append(f'<text x="{(x0+2)*scale}" y="{(H-y0-3)*scale}" font-size="14" fill="{colors[lane]}">{lane}</text>')
    return '\n'.join(lines)

def screw_svg(scale=5):
    return '\n'.join([f'<circle cx="{x*scale:.2f}" cy="{(H-y)*scale:.2f}" r="{SCREW_R*scale:.2f}" fill="#111" opacity="0.35" />' for x,y in SCREW_HOLES])

def write_index():
    state_options=''.join([f'<option value="{s}">{s}</option>' for s in STATES])
    channel_paths={s:poly_to_path(channel_shapes(bs),5) for s,bs in STATES.items()}
    bridge_paths={s:poly_to_path(bridge_shapes(bs),5) for s,bs in STATES.items()}
    files={
        'S0_no_bridges':'core_base_S0_no_bridges.stl',
        'S1_AB':'core_base_S1_AB.stl',
        'S2_AB_CD':'core_base_S2_AB_CD.stl',
        'Smax_chain_AB_BC_CD':'core_base_Smax_chain_AB_BC_CD.stl',
        'cover':'core_cover_common.stl',
        'adapter':'tube_adapter_gauge.stl'
    }
    js_data=json.dumps({'channels':channel_paths,'bridges':bridge_paths,'files':files},ensure_ascii=False)
    index=f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>V6 四端口声学网络工程图</title>
<style>body{{margin:0;font-family:Arial,"Microsoft YaHei",sans-serif;background:#eef3fa;color:#111}}#layout{{display:flex;height:100vh}}#side{{width:360px;background:#fff;border-right:1px solid #ddd;padding:18px;box-sizing:border-box;overflow:auto}}#main{{flex:1;display:flex;align-items:center;justify-content:center;overflow:auto}}svg{{background:#f8fbff;border:1px solid #ccd;box-shadow:0 2px 10px #0001}}select,button{{width:100%;padding:10px;border-radius:8px;border:1px solid #bbb;margin:8px 0;font-size:14px}}button.primary{{background:#2563eb;color:white;border:0}}.note{{font-size:12px;line-height:1.5;background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:10px;margin-top:12px}}.small{{font-size:12px;color:#444;line-height:1.5}}label{{font-size:13px;display:block;margin:7px 0}}</style></head><body><div id="layout"><aside id="side"><h2>V6 四端口声学网络</h2><div class="small">V6 修正 V5：每条主管为单一 S 形蛇形路径，无自交/三叉戟；桥连接 final→first，避免穿过下一管道的折返段。</div><b>底板状态</b><select id="state">{state_options}</select><button class="primary" id="dlbase">下载当前底板 STL</button><button id="dlcover">下载共用盖板 STL</button><button id="dladapter">下载软管接口试套件 STL</button><label><input type="checkbox" id="showLine" checked> 显示彩色中心线</label><label><input type="checkbox" id="showScrew" checked> 显示螺丝孔</label><div class="note">深绿色为真实开槽 footprint；红色为当前状态打开的桥槽。底板路径现在是连续 S 形折返，不再在输入端形成三通/三叉戟。</div><pre id="info" class="small"></pre></aside><main id="main"><svg id="svg" width="900" height="800" viewBox="-20 -20 {W*5+40} {H*5+40}" xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0" width="{W*5}" height="{H*5}" fill="#dce9f9" stroke="#333" stroke-width="2"/><path id="channels" d="" fill="#188a4d" opacity="0.78" stroke="#0b5d30" stroke-width="1.5"/><path id="bridges" d="" fill="#e3342f" opacity="0.85" stroke="#9b1111" stroke-width="1"/><g id="centerlines">{centerline_svg(5)}</g><g id="screws">{screw_svg(5)}</g><circle cx="{CHAMBER_C[0]*5}" cy="{(H-CHAMBER_C[1])*5}" r="{CHAMBER_R*5}" fill="none" stroke="#111" stroke-width="1.5" stroke-dasharray="5 4" opacity="0.6"/><text x="{(CHAMBER_C[0]-18)*5}" y="{(H-CHAMBER_C[1]+3)*5}" font-size="12" fill="#111">mixing chamber</text></svg></main></div><script>
const DATA={js_data};
const state=document.getElementById('state');
const ch=document.getElementById('channels');
const br=document.getElementById('bridges');
const info=document.getElementById('info');
function downloadFile(file){{ const a=document.createElement('a'); a.href='models/'+file; a.download=file; document.body.appendChild(a); a.click(); a.remove(); }}
function upd(){{
  const s=state.value;
  ch.setAttribute('d', DATA.channels[s] || '');
  br.setAttribute('d', DATA.bridges[s] || '');
  info.textContent = `状态: ${{s}}\n底板尺寸: {W} × {H} × {BASE_TOTAL_HEIGHT} mm\n共用盖板: {W} × {H} × {COVER_THICKNESS} mm\n主通道: nominal 4 mm, 建模槽宽 {MAIN_CHANNEL_WIDTH} mm\n桥管: nominal 2 mm, 建模槽宽 {BRIDGE_CHANNEL_WIDTH} mm`;
}}
state.addEventListener('change', upd);
document.getElementById('showLine').addEventListener('change', e => document.getElementById('centerlines').style.display = e.target.checked ? 'block' : 'none');
document.getElementById('showScrew').addEventListener('change', e => document.getElementById('screws').style.display = e.target.checked ? 'block' : 'none');
document.getElementById('dlbase').addEventListener('click', () => downloadFile(DATA.files[state.value]));
document.getElementById('dlcover').addEventListener('click', () => downloadFile(DATA.files.cover));
document.getElementById('dladapter').addEventListener('click', () => downloadFile(DATA.files.adapter));
upd();
</script></body></html>'''
    (OUT/'index.html').write_text(index,encoding='utf-8')
    (OUT/'model_data.js').write_text('const V6_MODEL_DATA = '+js_data+';\n',encoding='utf-8')
    (OUT/'viewer.js').write_text('// V6 viewer is embedded in index.html for local-file reliability.\n',encoding='utf-8')

def write_docs(checks):
    lengths={l:round(path_length(path_points(l)),2) for l in LANES}
    bridge_lengths={b: round(math.hypot(point_on_pass(v['from'],v['from_pass'],v['x'])[0]-point_on_pass(v['to'],v['to_pass'],v['x'])[0], point_on_pass(v['from'],v['from_pass'],v['x'])[1]-point_on_pass(v['to'],v['to_pass'],v['x'])[1]),2) for b,v in BRIDGES.items()}
    txt=[]
    txt += ['V6 四端口交叉耦合内部声学网络 — 机制验证样机','']
    txt += ['相对 V5 的关键修正：','- 修复 index.html 的 JavaScript 字符串换行错误，状态切换和 STL 下载按钮现在应可工作。','- 每条主管改为单一非自交 S 形蛇形路径：right -> down -> left -> down -> right -> chamber。','- 取消 V5 中同一管道竖向折返穿过输入直管造成的三叉/三通形态。','- 桥管改为连接上一管 final pass 到下一管 first pass，避免桥槽穿过下一管的 return pass。','']
    txt += [f'底板尺寸：{W} × {H} × {BASE_TOTAL_HEIGHT} mm',f'盖板尺寸：{W} × {H} × {COVER_THICKNESS} mm','主通道：nominal 4 mm；建模为 4.4 mm 圆角槽，由共用平盖板密封。','桥槽：nominal 2 mm；建模宽度 2.2 mm。','']
    txt += ['中心线长度：']
    for k,v in lengths.items(): txt.append(f'- {k}: {v} mm')
    txt += ['','桥槽长度：']
    for k,v in bridge_lengths.items(): txt.append(f'- {k}: {v} mm')
    txt += ['','桥状态：','- S0_no_bridges: 无桥','- S1_AB: AB','- S2_AB_CD: AB + CD','- Smax_chain_AB_BC_CD: AB + BC + CD','']
    txt += ['仿真说明：','- 圆角槽 + 共用平盖板不是严格圆管；一维仿真请使用等效截面积/水力直径，并加入经验损耗。','- 因四个状态共用同一主管几何，相对比较桥槽引入后的相关性/有效秩变化仍然有效。','- mixing chamber 是不可避免的单麦克风汇总点，但 V6 避免了长总线 collector 和主管自交。','']
    txt += ['网格检查：']
    for k,v in checks.items(): txt.append(f'- {k}: {v}')
    (OUT/'model_params.txt').write_text('\n'.join(txt),encoding='utf-8')
    sim={'version':'V6','units':'mm','purpose':'2.5D mechanism validation coupon for internal cross-coupled acoustic duct network','frequency_range_hz':[0,8000],'dimensions':{'W':W,'H':H,'base_height':BASE_TOTAL_HEIGHT,'cover_thickness':COVER_THICKNESS},'main_channel':{'nominal_diameter_mm':4.0,'modeled_slot_width_mm':MAIN_CHANNEL_WIDTH,'note':'rounded slot sealed with common flat cover; not ideal circle'},'bridge_channel':{'nominal_diameter_mm':2.0,'modeled_slot_width_mm':BRIDGE_CHANNEL_WIDTH},'ports':{'inputs':['A','B','C','D'],'output':'mic_port'},'centerlines':{k:path_points(k) for k in LANES},'centerline_lengths_mm':{k:round(path_length(path_points(k)),3) for k in LANES},'mixing_chamber':{'center':CHAMBER_C,'radius_mm':CHAMBER_R},'mic_port':{'from':CHAMBER_C,'to':[W,CHAMBER_C[1]],'width_mm':MIC_PORT_WIDTH},'bridges':{k:{**v,'p0':point_on_pass(v['from'],v['from_pass'],v['x']),'p1':point_on_pass(v['to'],v['to_pass'],v['x'])} for k,v in BRIDGES.items()},'states':STATES,'screw_holes':{'diameter_mm':SCREW_DIAM,'centers_mm':SCREW_HOLES}}
    (OUT/'sim_params.json').write_text(json.dumps(sim,indent=2,ensure_ascii=False),encoding='utf-8')
    readme='''V6 工程包说明
================

V6 是机制验证样机，不是最终声学产品。

推荐打印顺序
------------
1. 先打印 core_base_S0_no_bridges.stl 和 core_cover_common.stl。
2. 确认密封、软管连接、耳机和 iMM-6C 测量流程。
3. 再打印 S1/S2/Smax 底板。

重要设计修正
------------
- 每条主管现在是单一 S 形蛇形路径，不是三叉/三通。
- S0 中除 mixing chamber 外没有内部桥槽。
- Smax 为链式 AB+BC+CD。
- 桥槽不穿过下一根管的折返段。

打印建议
--------
- Bambu Lab P1S, PLA, 0.4 mm 喷嘴。
- 层高 0.16–0.20 mm。
- 底板和盖板平放打印。
- 共用盖板与底板之间建议使用薄硅胶片、真空脂或薄密封垫。
- 4 mm 内径塑料软管可先用 tube_adapter_gauge.stl 测试套合松紧。

实验建议
--------
- 麦克风固定在右侧输出口。
- 入耳式耳机通过短 4 mm 内径软管依次连接 A/B/C/D。
- 未激励端口全部用一致方式封堵。
- 建议 log chirp 或白噪声，分析 500–8000 Hz。
- 主要比较 S0/S1/S2/Smax 的传递函数相关性矩阵、有效秩、重复性分离比和能量归一化分类准确率。
'''
    (OUT/'README.txt').write_text(readme,encoding='utf-8')
    notes='''Codex Notes for V6
==================

generate_stl.py regenerates the entire package.

Most important geometry functions:
- path_points(lane): four main duct centerlines. Each path is a simple non-self-intersecting serpentine.
- channel_shapes(open_bridges): union of main ducts, compact mixing chamber, mic port, and selected bridges.
- BRIDGES: chain topology AB, BC, CD. Bridges connect final pass of upper duct to first pass of next duct.
- STATES: S0/S1/S2/Smax.

Key design idea:
V6 corrects the V5 self-intersection/trident issue. Do not reintroduce vertical connectors that cross an existing leg of the same duct.
'''
    (OUT/'codex_notes.txt').write_text(notes,encoding='utf-8')

def copy_self():
    (OUT/'generate_stl.py').write_text(Path(__file__).read_text(encoding='utf-8'),encoding='utf-8')

def main():
    ensure_dirs()
    checks={}
    for st,brs in STATES.items():
        mesh=make_base_mesh(brs)
        fname=f'core_base_{st}.stl'
        checks[fname]=export_mesh(mesh,MODELS/fname)
    checks['core_cover_common.stl']=export_mesh(make_cover_mesh(),MODELS/'core_cover_common.stl')
    checks['tube_adapter_gauge.stl']=export_mesh(make_tube_adapter_test(),MODELS/'tube_adapter_gauge.stl')
    write_index(); write_docs(checks); copy_self()
    zip_path=Path('/mnt/data/acoustic_network_engineering_package_v6.zip')
    if zip_path.exists(): zip_path.unlink()
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
        for p in OUT.rglob('*'):
            z.write(p,p.relative_to(OUT.parent))
    print(zip_path)
    print('lengths', {l:round(path_length(path_points(l)),2) for l in LANES})
    print('checks', checks)

if __name__=='__main__': main()
