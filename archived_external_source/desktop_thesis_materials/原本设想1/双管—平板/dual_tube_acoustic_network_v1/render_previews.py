from pathlib import Path
import numpy as np
import trimesh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

ROOT=Path(__file__).resolve().parent
STL=ROOT/'STL'
OUT=ROOT/'PREVIEWS'
OUT.mkdir(exist_ok=True)

def render(path, out):
    m=trimesh.load(path, force='mesh')
    # simplify for display if huge
    faces=m.triangles
    fig=plt.figure(figsize=(8,6), dpi=150)
    ax=fig.add_subplot(111, projection='3d')
    coll=Poly3DCollection(faces, linewidths=0.05, alpha=1.0)
    coll.set_edgecolor((0.15,0.15,0.15,0.35))
    coll.set_facecolor((0.75,0.80,0.85,1.0))
    ax.add_collection3d(coll)
    b=m.bounds
    c=b.mean(axis=0); e=(b[1]-b[0]); r=max(e)/2*1.15
    ax.set_xlim(c[0]-r,c[0]+r); ax.set_ylim(c[1]-r,c[1]+r); ax.set_zlim(c[2]-r,c[2]+r)
    ax.set_box_aspect([1,1,1])
    ax.view_init(elev=25, azim=-55)
    ax.set_axis_off()
    ax.set_title(path.stem, fontsize=9)
    plt.tight_layout()
    fig.savefig(out, bbox_inches='tight', pad_inches=0.05)
    plt.close(fig)

for p in sorted(STL.glob('*.stl')):
    render(p, OUT/(p.stem+'.png'))
print('rendered', len(list(STL.glob('*.stl'))))
