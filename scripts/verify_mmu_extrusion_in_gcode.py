#!/usr/bin/env python3
"""
Scan exported multi-tool G-code for tool changes (T0, T1, ...) and extrusion (E) deltas.

Usage:
  python3 scripts/verify_mmu_extrusion_in_gcode.py path/to/print.gcode [tool_index]

If tool_index is omitted, summarizes all tools seen. If provided (e.g. 1 for T1),
reports whether that tool has any positive E extrusion after its Tn line.

Example:
  python3 scripts/verify_mmu_extrusion_in_gcode.py ~/Downloads/tile.gcode 1
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path


TOOL_RE = re.compile(r"^T(\d+)\s*$")
# G0/G1 ... E-1.234 or E12.34
E_RE = re.compile(r"\bE([-+]?\d*\.?\d+)\b")


def parse_args() -> tuple[Path, int | None]:
    if len(sys.argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(2)
    path = Path(sys.argv[1]).expanduser()
    tool_filter: int | None = None
    if len(sys.argv) >= 3:
        tool_filter = int(sys.argv[2])
    return path, tool_filter


def main() -> None:
    path, tool_filter = parse_args()
    if not path.is_file():
        print(f"Not a file: {path}", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(errors="replace").splitlines()

    current_tool = 0
    extrusion_by_tool: dict[int, float] = defaultdict(float)
    lines_with_e_by_tool: dict[int, int] = defaultdict(int)
    last_e: dict[int, float] = {}

    for line in text:
        line = line.split(";", 1)[0].strip()
        if not line:
            continue
        m = TOOL_RE.match(line)
        if m:
            current_tool = int(m.group(1))
            last_e.setdefault(current_tool, 0.0)
            continue
        if not (line.startswith("G0") or line.startswith("G1")):
            continue
        em = E_RE.search(line)
        if not em:
            continue
        e_val = float(em.group(1))
        prev = last_e.get(current_tool, 0.0)
        delta = e_val - prev
        last_e[current_tool] = e_val
        if delta > 1e-9:
            extrusion_by_tool[current_tool] += delta
            lines_with_e_by_tool[current_tool] += 1

    print(f"File: {path}")
    print("Total positive extrusion (mm of filament, approximate) by tool:")
    for t in sorted(extrusion_by_tool.keys()):
        total = extrusion_by_tool[t]
        nlines = lines_with_e_by_tool[t]
        print(f"  T{t}: sum(E deltas)={total:.4f}  ({nlines} extruding moves)")

    if tool_filter is not None:
        ext = extrusion_by_tool.get(tool_filter, 0.0)
        ok = ext > 0 and lines_with_e_by_tool.get(tool_filter, 0) > 0
        print()
        if ok:
            print(f"OK: T{tool_filter} has extrusion in this G-code.")
        else:
            print(
                f"PROBLEM: T{tool_filter} has no positive extrusion in this G-code — "
                "slicer did not generate face/tool moves, or wrong file."
            )
            sys.exit(1)


if __name__ == "__main__":
    main()
