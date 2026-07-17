# BAM numeral placement — bbox verification and chosen strategy

## Todo: verify-bboxes (Blender world space)

Report file: [`bam_numeral_bbox_report.txt`](bam_numeral_bbox_report.txt) (regenerate via Blender MCP / `execute_blender_code`).

### Tile 1

| Object | World bbox (x / y / z min–max, m) |
|--------|-----------------------------------|
| Numeral_1 | x [0.00267, 0.00396] y [0.02666, 0.02935] z [0.01229, 0.01299] |
| BorderFrame | x [0.00000, 0.02300] y [0.00000, 0.03200] z [0.01220, 0.01300] |
| FaceSlab_1Bam_Relief | x [0.00535, 0.01765] y [0.00585, 0.02615] z [0.01216, 0.01283] |
| FaceSlab | x [0.00150, 0.02150] y [0.00150, 0.03050] z [0.01204, 0.01224] |

The numeral sits in the **upper-left** of the tile face (high y, low x), **above** the top of the relief mesh in y. The relief sits **inside** the BorderFrame / FaceSlab footprint.

### Tile 2

| Object | World bbox (x / y / z min–max, m) |
|--------|-----------------------------------|
| Numeral_2 | x [0.04767, 0.04896] y [0.02666, 0.02935] z [0.01229, 0.01299] |
| BorderFrame.001 | x [0.04500, 0.06800] y [0.00000, 0.03200] z [0.01220, 0.01300] |
| FaceSlab_2Bam_Relief | x [0.08578, 0.14702] y [0.02565, 0.09674] z [0.01219, 0.01286] |
| FaceSlab.001 | x [0.04650, 0.06650] y [0.00150, 0.03050] z [0.01204, 0.01224] |

**Numeral_2** is shifted by **+0.045 m** in x vs Numeral_1 — consistent with **BorderFrame.001** (+0.045 vs BorderFrame). So the **numeral uses the same local placement** relative to the duplicated tile kit as tile 1.

**FaceSlab_2Bam_Relief** is the outlier: its x extent **[0.086, 0.147]** lies **mostly to the right of** BorderFrame.001 **[0.045, 0.068]**. There is **almost no horizontal overlap** between the relief and the tile frame. The digit still sits in the **nominal numeral band** of the frame, but the **fish art is drawn elsewhere in world space**, so the rank no longer reads as “inside” the composition like 1-bam.

### Interpretation

1. **Separate Numeral_* meshes** + **shared offset** vs tile kit is **not** the primary bug for tile 2 in this file: the numeral tracks the frame duplicate correctly.
2. **Misalignment of relief mesh vs tile** after SVG replace (or pre-existing) is the dominant issue: **preserving `matrix_world` while swapping mesh data** can leave art **off-tile** if the new mesh’s **bounding box / origin** differs from the old SVG mesh.
3. Mixed **viewBoxes** across `n-bam.svg` (see plan) still makes **per-tile** centering necessary even after a one-time fix.

## Todo: choose-strategy

**Chosen approach (ordered):**

1. **Primary — align relief to tile (Blender)**  
   After each `FaceSlab_nBam_Relief` rebuild from SVG, **translate** (or set origin-to-geometry then parent) so the relief’s world bbox **fits the FaceSlab.n / BorderFrame.n opening** in XY (match 1-bam overlap pattern). Optionally bake into [`blender_rebuild_bam_relief_from_svg.py`](blender_rebuild_bam_relief_from_svg.py).

2. **Secondary — normalize SVG artboards (Inkscape)**  
   Long term, use a **common viewBox** and **centered content** for all `*-bam.svg` so imports are predictable without heavy per-file nudging.

3. **Tertiary — per-tile Numeral_n tweaks**  
   Only if, after (1)–(2), a digit still sits on busy artwork; small per-object location edits.

**Not chosen first:** baking numerals into every SVG (heavy art change) unless you want to drop `Numeral_*` objects entirely.

## Relief ↔ tile alignment (restores “working” layout after SVG rebuild)

Rebuilding relief from SVG changes mesh bounds; keeping the old `matrix_world` often leaves fish art **off the FaceSlab**. [`blender_rebuild_bam_relief_from_svg.py`](blender_rebuild_bam_relief_from_svg.py) now **re-centers XY** each `FaceSlab_nBam_Relief` to its `FaceSlab` / `FaceSlab.00(n-1)` after assigning the new mesh.

To fix an already-open file **without** re-importing SVGs, open [`blender_rebuild_bam_relief_from_svg.py`](blender_rebuild_bam_relief_from_svg.py) in Blender’s **Text Editor**, run it once, then in the same editor run:

```python
align_all_bam_reliefs_to_face_slabs()
```

## Regenerating the bbox report

Open your tile `.blend`, then run in Blender (Scripting) or MCP `execute_blender_code` the snippet that writes `scripts/bam_numeral_bbox_report.txt` (same logic as in the implementation session).
