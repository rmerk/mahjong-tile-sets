# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A collection of custom mahjong tile artwork organized as the "Minnesota theme." The repo contains tile images and HTML showcase pages that display them via base64-embedded `<img>` tags.

## Repository Structure

- `minnesota-theme/` — Tile artwork organized by suit:
  - `bams/` — 1-9 bam tiles + `bam-dragon.png` (Green Dragon)
  - `cracks/` — 1-9 crack tiles + `crack-dragon.png` (Red Dragon). Note: 7-crack is `.jpeg`, all others are `.png`
  - `dots/` — 1-9 dot tiles + `soap-dragon.png` (Soap Dragon)
  - `flowers/` — 1-8 flower tiles
  - `joker/` — `joker.png`
  - `winds/` — `north.png`, `south.png`, `east.png`, `west.png`
- `docs/index.html` — GitHub Pages showcase (served at the repo's GH Pages URL)
- `minnesota-theme-showcase.html` — Standalone showcase (same content, for local viewing)
- `TileSmith-Brand-Guidelines.pdf` — Brand reference document
- `tilesmith-brand-system.html`, `tilesmith-landing.html` — Brand/landing pages

## Updating Showcase Pages

After changing any tile images in `minnesota-theme/`, run the update-tile-showcase skill (`/update-tile-showcase`) to regenerate base64-embedded images in both HTML showcase files. The skill runs:

```bash
python3 ~/.claude/skills/update-tile-showcase/update-showcase.py /Users/rchoi/Personal/mahjong-tile-sets
```

Dragon tiles belong to their respective suits in the showcase (Green Dragon in Bams, Red Dragon in Cracks, Soap Dragon in Dots) — not in a separate Dragons section.

## HTML Showcase Structure

Both showcase HTML files share identical structure. Each suit is a `<section class="suit-section">` containing an `<h2>` header with a `<span class="tile-count">` and a `<div class="grid-container">` of `<div class="tile-card">` elements. Each tile-card contains a `<div class="tile-img-wrap">` with a base64 `<img>` and a `<div class="tile-label">`. Changes to one showcase file should be mirrored in the other.

## Tile Label to File Mapping

| Label | File |
|-------|------|
| `1-9 Bam` | `bams/{n}-bam.png` |
| `1-9 Crack` | `cracks/{n}-crack.png` (7 is `.jpeg`) |
| `1-9 Dot` | `dots/{n}-dot.png` |
| `Green Dragon` | `bams/bam-dragon.png` |
| `Red Dragon` | `cracks/crack-dragon.png` |
| `Soap Dragon` | `dots/soap-dragon.png` |
| `1-8 Flower` | `flowers/{n}-flower.png` |
| `Joker` | `joker/joker.png` |
| `North/South/East/West` | `winds/{name}.png` |
