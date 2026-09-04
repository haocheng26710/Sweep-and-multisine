#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate corrected V2 parts for the existing dual-tube base modules 01-04.

The generator deliberately leaves base modules 01-04 unchanged.
All units are millimetres.

Parts:
05 compact T-node interface, compatible with existing base mounting holes
06 low-profile flush plug, compatible with 05
11 dual far-end seat, bolts to existing base module D holes
12 dual sealed cap, mates with 11
13 dual independent 2x(1-to-4) lossy manifold, mates with 11

Meshes are generated from analytic voxel CSG and marching cubes.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Sequence, Tuple

import numpy as np
import trimesh
from skimage import measure

OUT = Path('/mnt/data/dual_tube_acoustic_network_v2_corrected')
STL = OUT / 'STL'
PREV = OUT / 'PREVIEWS'
STL.mkdir(parents=True, exist_ok=True)
PREV.mkdir(parents=True, exist_ok=True)

PARAM = {
    'existing_base_tube_axis_y_mm': [-8.0, 8.0],
    'existing_base_tube_axis_z_mm': 10.0,
    'existing_base_node_mount_holes_relative_to_tube_axis_mm': [[-8.0, -9.0], [8.0, -9.0]],
    'existing_base_far_mount_holes_global_module_D_mm': [[88.0, -21.0], [88.0, 21.0]],
    'main_tube_id_mm': 4.0,
    'main_tube_od_assumed_mm': 7.0,
    'main_socket_diameter_mm': 7.2,
    'bridge_tube_id_mm': 2.0,
    'bridge_tube_od_assumed_mm': 4.0,
    'bridge_socket_diameter_mm': 4.2,
    'tube_center_spacing_mm': 16.0,
    'bridge_cut_length_mm': 12.0,
    'node_body_inner_outer_width_mm': 10.0,
    'node_face_gap_when_installed_mm': 6.0,
    'node_bridge_socket_depth_each_side_mm': 3.0,
    'plug_axial_protrusion_each_side_mm': 0.8,
    'plug_to_plug_remaining_clearance_mm': 4.4,
    'far_end_seat_extension_mm': 6.0,
    'far_end_tube_socket_depth_to_shoulder_mm': 5.2,
    'far_end_printed_throat_length_mm': 0.8,
    'corrected_main_acoustic_length_mm': 406.0,
    'corrected_last_soft_tube_cut_length_mm': 79.2,
    'far_end_mating_face_width_mm': 40.0,
    'far_end_mating_face_height_mm': 28.0,
    'far_end_mating_bolt_centres_mm': [[-16.0, 5.0], [-16.0, 23.0], [16.0, 5.0], [16.0, 23.0]],
    'o_ring_recommendation': 'optional 8 mm ID x 1.5 mm section; otherwise thin silicone grease or sheet gasket',
    'tail_count_each_main': 4,
    'tail_socket_diameter_mm': 4.2,
    'tail_acoustic_id_mm': 2.0,
}


class VoxelCSG:
    def __init__(self, bounds: Sequence[Sequence[float]], pitch: float):
        self.bounds = np.asarray(bounds, dtype=float)
        self.pitch = float(pitch)
        lo, hi = self.bounds
        self.shape = tuple((np.ceil((hi - lo) / self.pitch).astype(int) + 1).tolist())
        self.grid = np.zeros(self.shape, dtype=bool)
        self.coords = [lo[i] + np.arange(self.shape[i], dtype=np.float32) * self.pitch for i in range(3)]

    def _ranges(self, lo, hi):
        lo = np.asarray(lo, float); hi = np.asarray(hi, float)
        idx0 = np.floor((lo - self.bounds[0]) / self.pitch).astype(int) - 1
        idx1 = np.ceil((hi - self.bounds[0]) / self.pitch).astype(int) + 2
        idx0 = np.maximum(idx0, 0)
        idx1 = np.minimum(idx1, np.asarray(self.shape))
        return tuple(slice(int(a), int(b)) for a, b in zip(idx0, idx1))

    def _apply_mask(self, sl, mask, add=True):
        if add:
            self.grid[sl] |= mask
        else:
            self.grid[sl] &= ~mask

    def box(self, lo, hi, add=True):
        lo = np.asarray(lo,float); hi=np.asarray(hi,float)
        sl=self._ranges(lo,hi)
        xs,ys,zs=[self.coords[i][sl[i]] for i in range(3)]
        mask=((xs[:,None,None]>=lo[0])&(xs[:,None,None]<=hi[0])&
              (ys[None,:,None]>=lo[1])&(ys[None,:,None]<=hi[1])&
              (zs[None,None,:]>=lo[2])&(zs[None,None,:]<=hi[2]))
        self._apply_mask(sl,mask,add)

    def cylinder(self, center, radius, length, axis='z', add=True):
        center=np.asarray(center,float); radius=float(radius); length=float(length)
        ax={'x':0,'y':1,'z':2}[axis]
        lo=center-radius; hi=center+radius
        lo[ax]=center[ax]-length/2; hi[ax]=center[ax]+length/2
        sl=self._ranges(lo,hi)
        coords=[self.coords[i][sl[i]] for i in range(3)]
        A=coords[ax]
        others=[i for i in range(3) if i!=ax]
        U=coords[others[0]]; V=coords[others[1]]
        axial=(A>=center[ax]-length/2)&(A<=center[ax]+length/2)
        radial=(U[:,None]-center[others[0]])**2+(V[None,:]-center[others[1]])**2 <= radius**2
        if ax==0:
            mask=axial[:,None,None]&radial[None,:,:]
        elif ax==1:
            mask=radial[:,None,:]&axial[None,:,None]
        else:
            mask=radial[:,:,None]&axial[None,None,:]
        self._apply_mask(sl,mask,add)

    def annular_cylinder(self, center, r_inner, r_outer, length, axis='x', add=False):
        center=np.asarray(center,float); ax={'x':0,'y':1,'z':2}[axis]
        lo=center-r_outer; hi=center+r_outer
        lo[ax]=center[ax]-length/2; hi[ax]=center[ax]+length/2
        sl=self._ranges(lo,hi)
        coords=[self.coords[i][sl[i]] for i in range(3)]
        A=coords[ax]
        others=[i for i in range(3) if i!=ax]
        U=coords[others[0]]; V=coords[others[1]]
        axial=(A>=center[ax]-length/2)&(A<=center[ax]+length/2)
        rr=(U[:,None]-center[others[0]])**2+(V[None,:]-center[others[1]])**2
        radial=(rr>=r_inner**2)&(rr<=r_outer**2)
        if ax==0: mask=axial[:,None,None]&radial[None,:,:]
        elif ax==1: mask=radial[:,None,:]&axial[None,:,None]
        else: mask=radial[:,:,None]&axial[None,None,:]
        self._apply_mask(sl,mask,add)

    def sphere(self, center, radius, add=True):
        center=np.asarray(center,float); radius=float(radius)
        sl=self._ranges(center-radius,center+radius)
        xs,ys,zs=[self.coords[i][sl[i]] for i in range(3)]
        mask=((xs[:,None,None]-center[0])**2+(ys[None,:,None]-center[1])**2+
              (zs[None,None,:]-center[2])**2<=radius**2)
        self._apply_mask(sl,mask,add)

    def cone_z(self, z0, z1, r0, r1, center_xy=(0,0), add=True):
        lo=np.array([center_xy[0]-max(r0,r1), center_xy[1]-max(r0,r1), min(z0,z1)])
        hi=np.array([center_xy[0]+max(r0,r1), center_xy[1]+max(r0,r1), max(z0,z1)])
        sl=self._ranges(lo,hi)
        xs,ys,zs=[self.coords[i][sl[i]] for i in range(3)]
        t=(zs-z0)/(z1-z0)
        rz=r0+(r1-r0)*t
        valid=(t>=0)&(t<=1)
        rr=(xs[:,None]-center_xy[0])**2+(ys[None,:]-center_xy[1])**2
        mask=rr[:,:,None] <= rz[None,None,:]**2
        mask &= valid[None,None,:]
        self._apply_mask(sl,mask,add)

    def cylinder_between(self, p0, p1, radius, add=True):
        p0=np.asarray(p0,float); p1=np.asarray(p1,float); radius=float(radius)
        lo=np.minimum(p0,p1)-radius; hi=np.maximum(p0,p1)+radius
        sl=self._ranges(lo,hi)
        xs,ys,zs=[self.coords[i][sl[i]] for i in range(3)]
        X,Y,Z=np.meshgrid(xs,ys,zs,indexing='ij',sparse=False)
        v=p1-p0; vv=float(np.dot(v,v))
        t=((X-p0[0])*v[0]+(Y-p0[1])*v[1]+(Z-p0[2])*v[2])/vv
        tc=np.clip(t,0.0,1.0)
        dx=X-(p0[0]+tc*v[0]); dy=Y-(p0[1]+tc*v[1]); dz=Z-(p0[2]+tc*v[2])
        mask=(dx*dx+dy*dy+dz*dz)<=radius**2
        self._apply_mask(sl,mask,add)

    def to_mesh(self, name: str, simplify_target: int | None = None, step_size: int = 2):
        # Pad one empty voxel to guarantee a closed surface.
        vol=np.pad(self.grid,1,constant_values=False)
        verts,faces,normals,_=measure.marching_cubes(vol.astype(np.uint8), level=0.5,
                                                      spacing=(self.pitch,self.pitch,self.pitch),
                                                      allow_degenerate=False, step_size=step_size)
        verts += self.bounds[0] - self.pitch
        mesh=trimesh.Trimesh(vertices=verts, faces=faces, process=True)
        mesh.remove_unreferenced_vertices(); mesh.merge_vertices(); mesh.fix_normals()
        if simplify_target and len(mesh.faces)>simplify_target:
            try:
                mesh=mesh.simplify_quadric_decimation(face_count=simplify_target)
                mesh.process(validate=True)
            except Exception:
                pass
        path=STL/name
        mesh.export(path)
        return mesh,path


def make_part05():
    v=VoxelCSG([[-14.5,-13.0,-0.5],[14.5,5.6,12.5]],0.05)
    v.box([-14,-5,0],[14,5,12],True)
    v.box([-10,-12.6,0],[10,-4.5,3],True)
    # Main tube sockets and 4 mm central acoustic passage.
    v.cylinder([-9.95,0,6],3.6,8.2,'x',False)
    v.cylinder([ 9.95,0,6],3.6,8.2,'x',False)
    v.cylinder([0,0,6],2.0,12.4,'x',False)
    # Compact 3.0 mm-deep bridge OD socket plus 2 mm bore.
    v.cylinder([0,3.50,6],2.10,3.20,'y',False)
    v.cylinder([0,2.50,6],1.00,5.40,'y',False)
    # Existing base mounting holes, unchanged.
    for x in (-8,8):
        v.cylinder([x,-9,1.5],1.70,5.0,'z',False)
    return v.to_mesh('05_T_node_interface_V2_compact.stl',180000)


def make_part06():
    v=VoxelCSG([[-4.0,-4.0,-0.3],[7.5,4.0,4.2]],0.04)
    v.cylinder([0,0,0.4],3.50,0.80,'z',True)
    v.cone_z(0.80,3.75,2.06,2.00,(0,0),True)
    # Radial pull tab lies in the flange plane; rotate tab upward during installation.
    v.box([3.0,-1.5,0.0],[7.0,1.5,0.8],True)
    return v.to_mesh('06_node_low_profile_flush_plug_V2.stl',70000)


def make_part11():
    v=VoxelCSG([[-16.5,-25.5,-0.5],[6.5,25.5,28.5]],0.08)
    # Dual mating body, beyond the x=400 end of base module D.
    v.box([0,-20,0],[6,20,28],True)
    # Mounting arms align with existing base D holes at global x=388, y=+-21.
    v.box([-16,-25,4],[0.3,-17,7],True)
    v.box([-16,17,4],[0.3,25,7],True)
    # Reinforcing webs outside the existing rails.
    v.box([-4,-22,4],[2,-16.5,12],True)
    v.box([-4,16.5,4],[2,22,12],True)
    # Main-tube sockets and repeatable shoulders. Axes exactly match base y=+-8, z=10.
    for y in (-8,8):
        v.cylinder([2.5,y,10],3.60,5.40,'x',False)  # rear to shoulder x=5.2
        v.cylinder([5.65,y,10],2.00,1.20,'x',False) # 0.8 mm printed throat to front face
        # Optional O-ring groove on mating face.
        v.annular_cylinder([5.55,y,10],3.70,5.40,0.90,'x',False)
    # Mating flange holes.
    for y in (-16,16):
        for z in (5,23):
            v.cylinder([3,y,z],1.70,7.0,'x',False)
    # Mount to base D common holes: local x=-12 corresponds global x=388.
    for y in (-21,21):
        v.cylinder([-12,y,5.5],1.70,5.0,'z',False)
    return v.to_mesh('11_dual_far_end_seat_V2_base01-04_compatible.stl',280000)


def make_part12():
    v=VoxelCSG([[-0.5,-20.5,-0.5],[4.5,20.5,28.5]],0.08)
    v.box([0,-20,0],[4,20,28],True)
    for y in (-16,16):
        for z in (5,23):
            v.cylinder([2,y,z],1.70,5.0,'x',False)
    return v.to_mesh('12_dual_far_end_sealed_cap_V2.stl',140000)


def make_part13():
    v=VoxelCSG([[-0.5,-20.5,-0.5],[20.5,20.5,28.5]],0.08)
    v.box([0,-20,0],[20,20,28],True)
    # Four common M3 mating holes.
    for y in (-16,16):
        for z in (5,23):
            v.cylinder([10,y,z],1.70,21.0,'x',False)

    groups={
        -8.0:[(-12.0,7.0),(-12.0,15.0),(-4.0,7.0),(-4.0,15.0)],
         8.0:[(4.0,7.0),(4.0,15.0),(12.0,7.0),(12.0,15.0)],
    }
    for inlet_y, endpoints in groups.items():
        branch=np.array([7.0,inlet_y,10.0])
        # 4 mm inlet from rear face to branch point.
        v.cylinder([3.55,inlet_y,10],2.00,7.30,'x',False)
        v.sphere(branch,2.35,False)
        for ey,ez in endpoints:
            shoulder=np.array([16.05,ey,ez])
            v.cylinder_between(branch,shoulder,1.00,False)
            # 4.2 mm OD socket, 4 mm insertion from front face.
            v.cylinder([18.05,ey,ez],2.10,4.30,'x',False)
    return v.to_mesh('13_dual_lossy_2x1to4_manifold_V2.stl',420000)


def main():
    meshes=[]
    for fn in (make_part05,make_part06,make_part11,make_part12,make_part13):
        mesh,path=fn(); meshes.append((mesh,path))
        print(path.name, mesh.is_watertight, mesh.is_volume, len(mesh.faces), mesh.bounds.tolist())
    records=[]
    for mesh,path in meshes:
        records.append({
            'file':str(path.relative_to(OUT)),
            'watertight':bool(mesh.is_watertight),
            'is_volume':bool(mesh.is_volume),
            'volume_mm3':float(mesh.volume),
            'bounds_mm':np.round(mesh.bounds,3).tolist(),
            'extents_mm':np.round(mesh.extents,3).tolist(),
            'faces':int(len(mesh.faces)),
            'vertices':int(len(mesh.vertices)),
        })
        if not mesh.is_watertight or not mesh.is_volume:
            raise RuntimeError(f'Invalid mesh: {path}')
    (OUT/'V2_parameters.json').write_text(json.dumps(PARAM,indent=2,ensure_ascii=False),encoding='utf-8')
    (OUT/'V2_mesh_validation.json').write_text(json.dumps(records,indent=2,ensure_ascii=False),encoding='utf-8')

if __name__=='__main__':
    main()
