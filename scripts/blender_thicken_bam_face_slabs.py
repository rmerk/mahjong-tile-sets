"""
Thicken Bam tile FaceSlab meshes for more reliable FDM top surfaces.

The cream face (`FaceSlab`, `FaceSlab.001`, …) is only ~0.2 mm in world Z in the
documented bbox; a few solid slicer layers may not fully close. This script
finds each slab's world-Z extent and, if below MIN_THICKNESS_M, moves only the
bottom vertices down in world space so the top surface stays fixed.

Run inside Blender: open your tile .blend, then Run Script on this file.

Adjust MIN_THICKNESS_M if you want a different minimum (meters; 0.0005 = 0.5 mm).
"""
from __future__ import annotations

import re

import bpy
import bmesh
from mathutils import Vector

# Minimum world-space thickness for each FaceSlab (meters)
MIN_THICKNESS_M = 0.0005

# Cream slabs only (not reliefs); allow Blender .001 or export names _TileNN
_FACE_SLAB_RE = re.compile(r"^FaceSlab(?:\.\d+)?(?:_Tile\d+)?(?:_\d+)?$")


def _is_face_slab_name(name: str) -> bool:
    return bool(_FACE_SLAB_RE.match(name))


def thicken_face_slab_mesh(obj: bpy.types.Object, min_thickness: float) -> str:
    if obj.type != "MESH":
        return f"{obj.name}: skip (not mesh)"
    me = obj.data
    mw = obj.matrix_world.copy()
    mw_inv = mw.inverted()

    zs: list[float] = []
    for v in me.vertices:
        zs.append((mw @ v.co).z)
    if not zs:
        return f"{obj.name}: no vertices"
    z_lo = min(zs)
    z_hi = max(zs)
    current = z_hi - z_lo
    if current >= min_thickness - 1e-9:
        return f"{obj.name}: ok thickness={current * 1000:.4f} mm (no change)"

    delta = min_thickness - current
    eps = max(1e-6, current * 0.02)

    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()

    n_moved = 0
    for v in bm.verts:
        wco = mw @ v.co
        if wco.z <= z_lo + eps:
            wco.z -= delta
            v.co = mw_inv @ wco
            n_moved += 1

    bm.to_mesh(me)
    me.update()
    bm.free()

    new_t = z_hi - (z_lo - delta)
    return (
        f"{obj.name}: thickened {current * 1000:.4f} mm → {new_t * 1000:.4f} mm "
        f"({n_moved} bottom verts, Δ={delta * 1000:.4f} mm down)"
    )


def main() -> None:
    reports: list[str] = []
    for obj in bpy.data.objects:
        if not _is_face_slab_name(obj.name):
            continue
        reports.append(thicken_face_slab_mesh(obj, MIN_THICKNESS_M))
    if not reports:
        print("No objects named FaceSlab or FaceSlab.xxx found.")
        return
    for line in reports:
        print(line)


if __name__ == "__main__":
    main()
