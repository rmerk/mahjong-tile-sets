"""
Rebuild FaceSlab_{n}Bam_Relief meshes from repo SVGs using the same thickness as the
reference 1-bam relief: on the imported curve, set fill_mode + extrude (0 for a flat
fill), then convert to mesh, then Solidify (do not use curve extrude for thickness;
that leaves open boundaries).

Run inside Blender (Scripting workspace or MCP execute_blender_code), with
REPO_ROOT pointing at this repository clone.

Typical non-manifold cause for 2-9: Z-thickness was 0 (flat fills). Solidify
after flat conversion produces closed shells (nm_edges with >2 faces ~= 0).

Tile 3 SVG may still leave 2 non-manifold edges; inspect in Edit Mode or clean
the source SVG if needed.
"""
from __future__ import annotations

import os

import bpy
from mathutils import Vector

# Path to mahjong-tile-sets repo root (edit if needed)
REPO_ROOT = "/Users/rchoi/Personal/mahjong-tile-sets"
SVG_DIR = os.path.join(REPO_ROOT, "minnesota-theme", "bams", "svg")

# Match FaceSlab_1Bam_Relief world Z span (meters)
THICKNESS = 0.00067


def cleanup_empty_svg_collections() -> None:
    """Remove empty collections Blender creates when importing *-bam.svg files."""
    for col in list(bpy.data.collections):
        if "bam.svg" not in col.name.lower():
            continue
        if len(col.objects) > 0:
            continue
        bpy.data.collections.remove(col)


def cleanup_all_svg_import_leftovers() -> None:
    """Delete every object in SVG import collections and remove those collections."""
    for col in list(bpy.data.collections):
        if "bam.svg" not in col.name.lower():
            continue
        for obj in list(col.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(col)


def _relief_name(index: int) -> str:
    return f"FaceSlab_{index}Bam_Relief"


def _face_slab_name(index: int) -> str:
    """FaceSlab / FaceSlab.001 … for Bam_1 / Bam_2 …"""
    if index <= 1:
        return "FaceSlab"
    return f"FaceSlab.{(index - 1):03d}"


def world_bbox_center_xy(obj: bpy.types.Object) -> tuple[float, float]:
    mw = obj.matrix_world
    xs: list[float] = []
    ys: list[float] = []
    for corner in obj.bound_box:
        w = mw @ Vector(corner)
        xs.append(w.x)
        ys.append(w.y)
    return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)


def align_relief_xy_to_face_slab(relief: bpy.types.Object, face_slab: bpy.types.Object) -> None:
    """Shift relief location so world XY bbox center matches the tile FaceSlab (fixes post-SVG-rebuild drift)."""
    rx, ry = world_bbox_center_xy(relief)
    fx, fy = world_bbox_center_xy(face_slab)
    relief.location.x += fx - rx
    relief.location.y += fy - ry
    if bpy.context.view_layer:
        bpy.context.view_layer.update()


def rebuild_bam_relief_from_svg(index: int, thickness: float = THICKNESS) -> str:
    svg = os.path.join(SVG_DIR, f"{index}-bam.svg")
    if not os.path.isfile(svg):
        return f"{index}: missing {svg}"

    old = bpy.data.objects.get(_relief_name(index))
    if old is None or old.type != "MESH":
        return f"{index}: target {_relief_name(index)} not found"

    old_mesh = old.data
    mw = old.matrix_world.copy()

    names_before = {o.name for o in bpy.data.objects}
    bpy.ops.import_curve.svg(filepath=svg)
    new_names = [o.name for o in bpy.data.objects if o.name not in names_before]
    if not new_names:
        return f"{index}: SVG import produced no objects"

    bpy.ops.object.select_all(action="DESELECT")
    for nm in new_names:
        bpy.data.objects[nm].select_set(True)
    bpy.context.view_layer.objects.active = bpy.data.objects[new_names[0]]
    bpy.ops.object.join()

    cu = bpy.context.active_object
    cd = cu.data
    cd.fill_mode = "BOTH"
    cd.extrude = 0.0
    bpy.ops.object.convert(target="MESH")

    mesh_src = bpy.context.active_object
    sol = mesh_src.modifiers.new(name="SolidifyRelief", type="SOLIDIFY")
    sol.thickness = thickness
    sol.use_even_offset = True
    sol.offset = 0.0
    bpy.context.view_layer.objects.active = mesh_src
    bpy.ops.object.modifier_apply(modifier=sol.name)

    new_me = mesh_src.data.copy()
    old.data = new_me
    bpy.data.objects.remove(mesh_src, do_unlink=True)
    if old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)
    old.matrix_world = mw

    slab = bpy.data.objects.get(_face_slab_name(index))
    if slab is not None:
        align_relief_xy_to_face_slab(old, slab)

    cleanup_empty_svg_collections()

    return f"{index}: ok verts={len(old.data.vertices)}"


def align_all_bam_reliefs_to_face_slabs() -> list[str]:
    """Repair XY placement for FaceSlab_nBam_Relief without re-importing SVGs."""
    log: list[str] = []
    for index in range(1, 10):
        relief = bpy.data.objects.get(_relief_name(index))
        slab = bpy.data.objects.get(_face_slab_name(index))
        if relief is None:
            log.append(f"{index}: no {_relief_name(index)}")
            continue
        if slab is None:
            log.append(f"{index}: no {_face_slab_name(index)}")
            continue
        align_relief_xy_to_face_slab(relief, slab)
        log.append(f"{index}: aligned")
    return log


def ensure_bam_1_collection() -> None:
    """Mirror Bam_2..Bam_9: put tile-1 parts in collection Bam_1."""
    scene = bpy.context.scene
    name = "Bam_1"
    col1 = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if col1.name not in [c.name for c in scene.collection.children]:
        scene.collection.children.link(col1)

    inner = bpy.data.collections.get("Collection")
    tile1 = [
        "FaceSlab",
        "FaceSlab_1Bam_Relief",
        "BorderFrame",
        "Numeral_1",
        "LowerBody",
        "AccentStripe",
    ]
    for obj_name in tile1:
        obj = bpy.data.objects.get(obj_name)
        if obj is None:
            continue
        if inner is not None and inner in obj.users_collection:
            inner.objects.unlink(obj)
        if col1 not in obj.users_collection:
            col1.objects.link(obj)

    sc = scene.collection
    relief = bpy.data.objects.get("FaceSlab_1Bam_Relief")
    if relief is not None and sc in relief.users_collection:
        sc.objects.unlink(relief)


def main() -> None:
    cleanup_all_svg_import_leftovers()
    for i in range(2, 10):
        print(rebuild_bam_relief_from_svg(i))
    cleanup_all_svg_import_leftovers()
    ensure_bam_1_collection()
    print("Bam_1 collection updated.")


if __name__ == "__main__":
    main()
