"""
Prepare Bam tile Blender scenes for clean 3MF export to Bambu Studio.

Addresses:
- Duplicate / overlapping cream FaceSlab meshes (slicer warnings, Z-fighting).
- Ambiguous duplicate part names when multiple tiles are in one file (rename by column).
- Apply transforms + light mesh cleanup (merge by distance) before export.

Typical layout: tiles spaced ~0.045 m apart on X (see bam_numeral_placement_strategy.md).

Run inside Blender with your .blend open: Scripting → Run Script.

Adjust TILE_SPACING_M if your file uses a different grid pitch.
"""
from __future__ import annotations

import re
from typing import Iterable

import bpy
from mathutils import Vector

# World X distance between adjacent tile centers (meters)
TILE_SPACING_M = 0.045

# Cream face: FaceSlab / FaceSlab.001 / FaceSlab_Tile01 / FaceSlab.001_Tile02 — not *Bam_Relief*
_CREAM_SLAB_RE = re.compile(
    r"^FaceSlab(?:\.\d+)?(?:_Tile\d+)?(?:_\d+)?$"
)


def _is_cream_face_slab(obj: bpy.types.Object) -> bool:
    if obj.type != "MESH":
        return False
    if "Bam_Relief" in obj.name:
        return False
    return bool(_CREAM_SLAB_RE.match(obj.name))


def world_aabb(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    """World-space axis-aligned bounds (min, max)."""
    mw = obj.matrix_world
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for corner in obj.bound_box:
        w = mw @ Vector(corner)
        xs.append(w.x)
        ys.append(w.y)
        zs.append(w.z)
    return (
        Vector((min(xs), min(ys), min(zs))),
        Vector((max(xs), max(ys), max(zs))),
    )


def aabb_volume(lo: Vector, hi: Vector) -> float:
    d = hi - lo
    if d.x <= 0 or d.y <= 0 or d.z <= 0:
        return 0.0
    return d.x * d.y * d.z


def intersection_volume(
    a_lo: Vector, a_hi: Vector, b_lo: Vector, b_hi: Vector
) -> float:
    lo = Vector(
        (
            max(a_lo.x, b_lo.x),
            max(a_lo.y, b_lo.y),
            max(a_lo.z, b_lo.z),
        )
    )
    hi = Vector(
        (
            min(a_hi.x, b_hi.x),
            min(a_hi.y, b_hi.y),
            min(a_hi.z, b_hi.z),
        )
    )
    return aabb_volume(lo, hi)


def tile_index_for_object(obj: bpy.types.Object, x_min: float, spacing: float) -> int:
    lo, hi = world_aabb(obj)
    cx = (lo.x + hi.x) / 2.0
    if spacing <= 1e-9:
        return 0
    return int(round((cx - x_min) / spacing))


def _mesh_objects() -> list[bpy.types.Object]:
    return [o for o in bpy.data.objects if o.type == "MESH"]


def detect_tile_x_min(objs: Iterable[bpy.types.Object]) -> float:
    """Leftmost tile column from BorderFrame* and cream FaceSlab* (fallback: all meshes)."""
    candidates: list[bpy.types.Object] = []
    for o in objs:
        if o.type != "MESH":
            continue
        if o.name.startswith("BorderFrame") or _is_cream_face_slab(o):
            candidates.append(o)
    if not candidates:
        candidates = [o for o in objs if o.type == "MESH"]
    if not candidates:
        return 0.0
    return min(world_aabb(o)[0].x for o in candidates)


def remove_overlapping_cream_face_slabs(
    overlap_ratio: float = 0.85,
) -> list[str]:
    """
    Delete duplicate cream FaceSlab shells that heavily overlap in world AABB.

    Keeps the object with the lexicographically smaller name for determinism.
    """
    slabs = [o for o in bpy.data.objects if _is_cream_face_slab(o)]
    slabs.sort(key=lambda o: o.name)
    removed: list[str] = []
    to_delete: set[bpy.types.Object] = set()

    for i, a in enumerate(slabs):
        if a in to_delete:
            continue
        a_lo, a_hi = world_aabb(a)
        va = aabb_volume(a_lo, a_hi)
        if va <= 0:
            continue
        for b in slabs[i + 1 :]:
            if b in to_delete:
                continue
            b_lo, b_hi = world_aabb(b)
            vb = aabb_volume(b_lo, b_hi)
            inter = intersection_volume(a_lo, a_hi, b_lo, b_hi)
            smaller = min(va, vb)
            if smaller <= 0:
                continue
            if inter / smaller >= overlap_ratio:
                to_delete.add(b)
                removed.append(
                    f"removed duplicate cream slab '{b.name}' (overlap "
                    f"{inter / smaller:.2f} vs '{a.name}')"
                )

    for o in to_delete:
        bpy.data.objects.remove(o, do_unlink=True)

    return removed


def rename_tile_parts_for_unique_3mf(
    spacing: float = TILE_SPACING_M,
) -> list[str]:
    """
    Rename printable parts to include _TileNN suffix from world X column.

    Covers BorderFrame*, LowerBody*, AccentStripe*, cream FaceSlab*, Numeral_*.
    Skips relief meshes named FaceSlab_*Bam_Relief (already unique per rank).
    """
    meshes = _mesh_objects()
    if not meshes:
        return ["no mesh objects"]

    x_min = detect_tile_x_min(meshes)
    log: list[str] = []

    def should_rename(o: bpy.types.Object) -> bool:
        n = o.name
        if "Bam_Relief" in n:
            return False
        if n.startswith("BorderFrame"):
            return True
        if n.startswith("LowerBody"):
            return True
        if n.startswith("AccentStripe"):
            return True
        if n.startswith("Numeral_"):
            return True
        if _is_cream_face_slab(o):
            return True
        return False

    for o in meshes:
        if not should_rename(o):
            continue
        idx = tile_index_for_object(o, x_min, spacing) + 1  # 1-based
        stem = o.name
        if "_Tile" in stem:
            continue
        new_name = f"{stem}_Tile{idx:02d}"
        if new_name in bpy.data.objects and bpy.data.objects[new_name] is not o:
            # Blender requires unique names — bump suffix
            k = 0
            while f"{new_name}_{k}" in bpy.data.objects:
                k += 1
            new_name = f"{new_name}_{k}"
        log.append(f"{o.name} → {new_name}")
        o.name = new_name

    return log if log else ["no objects matched rename rules"]


def apply_all_transforms_meshes() -> list[str]:
    """Bake scale/rotation on all mesh objects (recommended before 3MF export)."""
    bpy.ops.object.select_all(action="DESELECT")
    meshes = _mesh_objects()
    for o in meshes:
        o.select_set(True)
    if not meshes:
        return ["no meshes"]
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.object.select_all(action="DESELECT")
    return [f"applied rotation+scale on {len(meshes)} mesh objects"]


def _merge_by_distance_edit(distance: float) -> None:
    """Prefer merge_by_distance; fall back to remove_doubles (older Blender / some builds)."""
    for kwargs in (
        {"threshold": distance},
        {"merge_threshold": distance},
    ):
        try:
            bpy.ops.mesh.merge_by_distance(**kwargs)
            return
        except (TypeError, AttributeError, RuntimeError):
            continue
    bpy.ops.mesh.remove_doubles(threshold=distance)


def merge_by_distance_all_meshes(distance: float = 1e-4) -> list[str]:
    """
    Merge by distance in edit mode per mesh (meters). Helps T-junctions; not a full
    manifold fix. Check remaining issues with Mesh → Clean Up or 3D Print Toolbox.
    """
    out: list[str] = []
    for o in _mesh_objects():
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        before = len(o.data.vertices)
        _merge_by_distance_edit(distance)
        bpy.ops.object.mode_set(mode="OBJECT")
        after = len(o.data.vertices)
        removed = before - after
        if removed:
            out.append(f"{o.name}: merged {removed} verts (threshold {distance})")
    return out if out else ["merge_by_distance: no doubles removed"]


def report_non_manifold_edges_bmesh() -> list[str]:
    """Approximate non-manifold edge count per mesh (bmesh edge.is_manifold)."""
    import bmesh

    out: list[str] = []
    for o in _mesh_objects():
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.edges.ensure_lookup_table()
        n = sum(1 for e in bm.edges if not e.is_manifold)
        bm.free()
        if n:
            out.append(f"{o.name}: {n} non-manifold edges (bmesh)")
    return out if out else ["non-manifold: no flagged edges (bmesh)"]


def report_cream_slabs() -> None:
    slabs = [o for o in bpy.data.objects if _is_cream_face_slab(o)]
    print(f"Cream FaceSlab meshes ({len(slabs)}):")
    for o in sorted(slabs, key=lambda x: x.name):
        lo, hi = world_aabb(o)
        print(
            f"  {o.name}: center_xy=({((lo.x+hi.x)/2)*1000:.2f}, {((lo.y+hi.y)/2)*1000:.2f}) mm "
            f"z_span={(hi.z-lo.z)*1000:.3f} mm verts={len(o.data.vertices)}"
        )


def main(
    *,
    dedupe_slabs: bool = True,
    rename_parts: bool = True,
    apply_transforms: bool = True,
    merge_doubles: bool = True,
    print_manifold_report: bool = True,
) -> None:
    print("=== prepare_bam_export_for_bambu ===")
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
    except RuntimeError:
        pass

    report_cream_slabs()
    if dedupe_slabs:
        removed = remove_overlapping_cream_face_slabs()
        for line in removed:
            print(line)
        if not removed:
            print("dedupe: no overlapping cream FaceSlabs removed")
    print("--- after dedupe ---")
    report_cream_slabs()

    if rename_parts:
        for line in rename_tile_parts_for_unique_3mf():
            print("rename:", line)

    if apply_transforms:
        for line in apply_all_transforms_meshes():
            print("transform:", line)

    if merge_doubles:
        for line in merge_by_distance_all_meshes():
            print("merge:", line)

    if print_manifold_report:
        print("--- non-manifold report (fix heavy cases in Edit Mode / SVG pipeline) ---")
        for line in report_non_manifold_edges_bmesh():
            print("manifold:", line)

    print("=== done — re-export 3MF; see docs/print-tuning-bambu-bam.md § 5 ===")


if __name__ == "__main__":
    main()