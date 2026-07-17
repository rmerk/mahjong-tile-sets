# Bambu Studio / AMS — Bam tile print tuning

Use this checklist when the **white face** shows diagonal gaps / infill bleed-through, or **black relief / numeral** stringing, blobs, or smear into white. See also [`scripts/bam_numeral_placement_strategy.md`](../scripts/bam_numeral_placement_strategy.md) for modeled Z extents.

**Blender note:** Tile 1 objects may live in the default `Collection` until you run `ensure_bam_1_collection()` in [`scripts/blender_rebuild_bam_relief_from_svg.py`](../scripts/blender_rebuild_bam_relief_from_svg.py). Collection membership does **not** affect print quality.

**3MF / Bambu import issues** (non-manifold count, duplicate `FaceSlab` parts, assembly wider than the bed): see **§ 5** at the end of this page.

## 1 — Scale and G-code verification

### Expected geometry (1 Blender unit = 1 m)

| Part | Approx. world Z span |
|------|----------------------|
| `FaceSlab` (cream face) | ~0.2 mm |
| `FaceSlab_*Bam_Relief` | ~0.67 mm (`THICKNESS` in rebuild script) |

A **~0.2 mm** face is only about **two** layers at 0.1 mm layer height, so the slicer must use enough **top solid layers** (see section 3) or you should **thicken** the slab in Blender (see [`scripts/blender_thicken_bam_face_slabs.py`](../scripts/blender_thicken_bam_face_slabs.py)).

### In Bambu Studio

1. Import your tile (STL/3MF from Blender).
2. Select the model and check **Scale** on the plate: confirm the **printed size** matches your intent (e.g. standard mahjong face ~21–23 mm wide if that is your design).
3. Use the **measure** or part dimensions readout to sanity-check **overall height** and that the cream region is not accidentally scaled to a fraction of a millimeter.

### MMU extrusion sanity check

After slicing, export **G-code** and run:

```bash
python3 scripts/verify_mmu_extrusion_in_gcode.py path/to/your_tile.gcode
```

Optional: verify a single AMS slot (example: tool `1` = second filament):

```bash
python3 scripts/verify_mmu_extrusion_in_gcode.py path/to/your_tile.gcode 1
```

Every color that should print must show **non-zero** positive E deltas. If a tool has **no extrusion** after its `Tn` line, fix object/part painting or process assignment in the slicer—not the printer.

A tiny synthetic example that should pass is in [`scripts/fixtures/sample_mmu_tile.gcode`](../scripts/fixtures/sample_mmu_tile.gcode) (for script smoke tests).

## 2 — Black (relief + numeral): AMS and ooze

- **Flush volumes** (Project / filament settings / multi-material): increase **white → black** and **black → white** until color bleed and weak black perimeters improve. This is the main lever for “black dragging into white.”
- **Nozzle temperature**: after mechanical checks, try **slightly lower** black print temperature in small steps to reduce ooze (respect filament manufacturer min).
- **Retraction / wipe**: use your printer profile’s **wipe** / **retraction** recommendations; for AMS, ensure **load/unload** tuning is not leaving excess pressure before small features.
- **Slow small features**: reduce **outer wall** or **small perimeter** speed so tiny black segments are not rushed (reduces blobbing and uneven lines).
- **Minimize tool hops**: for one tile, avoid many separate black bodies if you can merge mesh islands without breaking painting (fewer travels = less stringing).

## 3 — White face: solid top and flow

- **Top shell layers** / **top surface layer count**: raise until the **layer preview** shows a **solid** top over the cream face (often **4+** layers at 0.08–0.12 mm when the modeled cap is very thin).
- **Line width**: align with nozzle (e.g. 0.4 mm nozzle → ~0.42 mm default or Arachne-equivalent); too-narrow effective width can leave **gaps** between top skin passes.
- **Overlap**: if available, slightly increase **infill / top layer overlap** to help skins bond.
- **Infill under the face**: if the body is hollow with sparse infill, increase **infill percentage** or add **solid infill** under the face so top layers have support.

## 4 — Blender: thicken `FaceSlab` (optional)

If slicer tuning is not enough, run in Blender (with your tile `.blend` open):

```text
Scripting workspace → Run script → scripts/blender_thicken_bam_face_slabs.py
```

The script extends each `FaceSlab` / `FaceSlab.xxx` mesh **downward** in world Z so the **top** of the slab stays aligned (relief and border unchanged on the visible face). Default target minimum thickness is **0.5 mm** (edit `MIN_THICKNESS_M` in the script if needed). Re-export to Bambu Studio and re-slice.

Relief height is controlled by `THICKNESS` in [`scripts/blender_rebuild_bam_relief_from_svg.py`](../scripts/blender_rebuild_bam_relief_from_svg.py); change that only if black details are too shallow to slice—not as the first fix for stringing.

## 5 — 3MF export checklist (Bambu Studio)

Use this when Bambu reports **non-manifold edges**, **duplicate `FaceSlab` parts**, **plate overhang / out of bounds** (e.g. nine tiles in one row ≈ 383 mm long), or **multi-part at multiple heights**.

### Blender (before export)

1. **Optional automated prep:** In Blender, run [`scripts/blender_prepare_bam_export_for_bambu.py`](../scripts/blender_prepare_bam_export_for_bambu.py) (Scripting → Run Script). It will:
   - Remove **heavily overlapping** cream `FaceSlab` / `FaceSlab.xxx` duplicates (same tile, stacked shells).
   - Rename `BorderFrame*`, `LowerBody*`, `AccentStripe*`, cream `FaceSlab*`, `Numeral_*` to include `_TileNN` from world X columns (default spacing **0.045 m** — edit `TILE_SPACING_M` if your layout differs).
   - **Apply rotation + scale** on all meshes.
   - **Merge by distance** (light cleanup) and print a **non-manifold edge count** per mesh (heavy fixes: Edit Mode, or re-run [`scripts/blender_rebuild_bam_relief_from_svg.py`](../scripts/blender_rebuild_bam_relief_from_svg.py) for reliefs; external repair if needed).
2. **Manual pass:** Delete any leftover duplicate slabs per tile (wireframe / X-Ray helps). Ensure **one** cream face slab per tile.
3. Export **3MF** (or STL per part if you prefer). Prefer **one plate’s worth of tiles** per file if you want to avoid assemblies longer than your bed (e.g. nine tiles in a row).

### Bambu Studio (after import)

1. **“Multi-part object detected”** → choose **Yes** (one object, multiple parts) so parts stay grouped for AMS painting.
2. **Scale / units:** Confirm per-tile width/height match intent (~21–23 mm face width if your Blender scene was meters ×1000). Fix in Blender scene scale or Bambu **uniform scale** once, then re-export.
3. **Bed fit:** If the assembly is wider than your plate (common for 9×1 rows), **split** across plates, **arrange** in a grid, or export **fewer tiles** per 3MF.
4. **Object warnings:** Re-open the object list — you should see **unique** part names (e.g. `FaceSlab_Tile03`), not multiple indistinguishable `FaceSlab` rows.
5. **Filament painting:** Assign cream / black / accent to the correct **parts** after geometry is clean (single default color usually means nothing is painted yet).
6. Re-slice and confirm the **non-manifold** count in Bambu’s object check is gone or acceptable.
7. **Triangle count:** After cleanup, if the slicer is sluggish, consider **Decimate** only on internal or non-visible meshes. Prioritize **manifold** watertight geometry over reducing poly count.

The committed [`minnesota-theme/blank_tile_standard.3mf`](../minnesota-theme/blank_tile_standard.3mf) is a **single-tile** example with uniquely named components. Multi-tile exports (e.g. `blank_tile_standard-8`) need the cleanup above so names and shells stay unique per tile.
