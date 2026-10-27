#!/usr/bin/env python3
"""
Convertit le metrics.json de msdf-atlas-gen en CSV importable
comme Data Table Unreal.

Prerequis : atlas genere avec -uniformcell (le bloc "grid" doit
etre present dans le JSON).

Sortie : Name,GlyphIndex
  Name       = code point decimal (Row Name)
  GlyphIndex = index de cellule, lu ligne par ligne depuis le
               coin superieur gauche de l'atlas

Usage :
    python msdf_json_to_ue_csv.py metrics.json charset.csv
"""

import csv
import json
import math
import sys


def cell_index(glyph, grid, atlas_height):
    """Index de cellule a partir du centre du quad.

    Les atlasBounds portent un decalage d'un demi-pixel et peuvent
    deborder legerement de l'image ; passer par le centre de la
    cellule evite les erreurs d'arrondi aux bords.
    yOrigin vaut "bottom" : l'axe Y est inverse par rapport a Unreal.
    """
    b = glyph["atlasBounds"]
    center_x = (b["left"] + b["right"]) / 2
    center_y_from_bottom = (b["bottom"] + b["top"]) / 2
    center_y_from_top = atlas_height - center_y_from_bottom

    col = math.floor(center_x / grid["cellWidth"])
    row = math.floor(center_y_from_top / grid["cellHeight"])
    return row * grid["columns"] + col


def main(json_path, csv_path):
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    atlas = data["atlas"]
    if "grid" not in atlas:
        sys.exit(
            "Pas de bloc 'grid' dans le JSON : l'atlas n'a pas ete genere "
            "avec -uniformcell. Les cellules ne sont pas regulieres, "
            "l'index de cellule n'a pas de sens."
        )

    grid = atlas["grid"]
    capacity = grid["columns"] * grid["rows"]

    rows = []
    skipped = []
    for glyph in data["glyphs"]:
        cp = glyph["unicode"]
        if "atlasBounds" not in glyph:
            # Glyphe sans forme : espace, espace insecable.
            skipped.append(cp)
            continue
        idx = cell_index(glyph, grid, atlas["height"])
        if not 0 <= idx < capacity:
            sys.exit(f"Index hors grille pour U+{cp:04X} : {idx}")
        rows.append((cp, idx))

    rows.sort(key=lambda r: r[0])

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Name", "GlyphIndex"])
        for cp, idx in rows:
            w.writerow([cp, idx])

    # Verification : un index de cellule ne doit jamais etre partage.
    used = [idx for _, idx in rows]
    if len(set(used)) != len(used):
        print("ATTENTION : des glyphes partagent le meme index de cellule.")

    print(f"{len(rows)} glyphes ecrits dans {csv_path}")
    print(f"Grille : {grid['columns']}x{grid['rows']} = {capacity} cellules")
    if skipped:
        shown = ", ".join(f"U+{c:04X}" for c in skipped[:10])
        print(f"{len(skipped)} glyphe(s) sans forme ignore(s) : {shown}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage : python msdf_json_to_ue_csv.py <metrics.json> <sortie.csv>")
    main(sys.argv[1], sys.argv[2])