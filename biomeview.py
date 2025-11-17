#!/usr/bin/env python3
"""
Biome Viewer - ASCII/ANSI visualization for terrain.v1 files.

Library-first:
    from biomeview import render_biome_map, load_terrain, generate_terrain

    # 1) Load existing terrain.json
    data = load_terrain("terrain.json")
    print(render_biome_map(data, use_color=True, legend=True))

    # 2) Or generate terrain via terraingen.TerrainGenerator and visualize directly
    data = generate_terrain(
        width=80,
        height=60,
        seed=42,
        mode="continent",
        octaves=5,
        scale=100.0,
        rivers=8,
        wind="west",
    )
    print(render_biome_map(data, use_color=True, legend=True))

CLI:
    # View an existing file
    python biomeview.py --input terrain.json --legend

    # Generate via terraingen and view (no file written)
    python biomeview.py --generate --seed 42 --width 80 --height 60 --mode continent --legend

    # Generate AND save JSON, then view
    python biomeview.py --generate --seed 42 --output terrain.json --legend

Notes:
- Expects schema: terrain.v1 (as produced by terraingen.TerrainGenerator)
- Uses `width`, `height`, and `tiles` (with x,y,biome,water,river).
"""

import json
import argparse
import sys
from typing import Dict, Any, List, Optional

# Simple ANSI helpers (no external deps)
RESET = "\033[0m"

COLOR_CODES = {
    "black": "30",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "white": "37",
    "bright_black": "90",
    "bright_red": "91",
    "bright_green": "92",
    "bright_yellow": "93",
    "bright_blue": "94",
    "bright_magenta": "95",
    "bright_cyan": "96",
    "bright_white": "97",
}


def color(text: str, fg: str) -> str:
    code = COLOR_CODES.get(fg)
    if not code:
        return text
    return f"\033[{code}m{text}{RESET}"


# Biome -> (char, color)
# Keep it boring & editable.
BIOME_STYLES = {
    "ocean":            {"ch": "~", "color": "blue"},
    "deep_ocean":       {"ch": "~", "color": "bright_blue"},
    "beach":            {"ch": ".", "color": "yellow"},
    "grassland":        {"ch": ",", "color": "green"},
    "temperate_forest": {"ch": "^", "color": "bright_green"},
    "wetlands":         {"ch": ";", "color": "cyan"},
    "desert":           {"ch": ":", "color": "bright_yellow"},
    "highland":         {"ch": "^", "color": "white"},
    "mountain":         {"ch": "M", "color": "bright_white"},
}

# Overlay priorities:
# river > water(ocean/lake/coast) > biome
RIVER_STYLE = {"ch": "=", "color": "bright_blue"}
WATER_STYLE = {"ch": "~", "color": "blue"}


def load_terrain(path: str) -> Dict[str, Any]:
    """Load terrain.v1 JSON from disk."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("schema") != "terrain.v1":
        raise ValueError(f"Unsupported schema {data.get('schema')}, expected terrain.v1")

    if "width" not in data or "height" not in data or "tiles" not in data:
        raise ValueError("terrain JSON missing required keys: width, height, tiles")

    return data


def build_grid(data: Dict[str, Any]) -> List[List[Dict[str, Any]]]:
    """Convert flat tiles list into [y][x] grid for quick lookup."""
    w = data["width"]
    h = data["height"]
    grid: List[List[Optional[Dict[str, Any]]]] = [[None for _ in range(w)] for _ in range(h)]

    for t in data["tiles"]:
        x = t.get("x")
        y = t.get("y")
        if x is None or y is None:
            continue
        if 0 <= x < w and 0 <= y < h:
            grid[y][x] = t

    # Fill gaps with dummy tiles so rendering never explodes
    for y in range(h):
        for x in range(w):
            if grid[y][x] is None:
                grid[y][x] = {
                    "x": x,
                    "y": y,
                    "biome": "unknown",
                    "water": False,
                    "river": False,
                }

    return grid


def tile_style(tile: Dict[str, Any]) -> Dict[str, str]:
    """Decide which glyph/color to use for a tile."""
    biome = tile.get("biome", "unknown")
    is_water = bool(tile.get("water"))
    is_river = bool(tile.get("river"))

    if is_river:
        return RIVER_STYLE

    if is_water:
        return WATER_STYLE

    style = BIOME_STYLES.get(biome)
    if style:
        return style

    # Fallback for unknown biomes
    return {"ch": "?", "color": "magenta"}


def render_biome_map(
    data: Dict[str, Any],
    use_color: bool = True,
    char_width: int = 1,
    legend: bool = False,
) -> str:
    """
    Render the biome map as a string.

    char_width: repeat each character horizontally to scale map.
    legend: append a legend block at the bottom.
    """
    grid = build_grid(data)
    h = data["height"]
    w = data["width"]

    lines: List[str] = []

    for y in range(h):
        row_chars: List[str] = []
        for x in range(w):
            style = tile_style(grid[y][x])
            ch = style["ch"]
            cell = color(ch, style["color"]) if use_color else ch
            row_chars.append(cell * char_width)
        lines.append("".join(row_chars))

    if legend:
        lines.append("")
        lines.append("Legend:")
        seen = set()
        for biome, style in BIOME_STYLES.items():
            if biome in seen:
                continue
            ch = style["ch"]
            glyph = color(ch, style["color"]) if use_color else ch
            lines.append(f"  {glyph}  {biome}")
            seen.add(biome)

        water_glyph = color(WATER_STYLE["ch"], WATER_STYLE["color"]) if use_color else WATER_STYLE["ch"]
        river_glyph = color(RIVER_STYLE["ch"], RIVER_STYLE["color"]) if use_color else RIVER_STYLE["ch"]
        lines.append(f"  {water_glyph}  water/ocean")
        lines.append(f"  {river_glyph}  river")

    return "\n".join(lines)


# ---------- Passthrough to existing terrain generator ----------

def generate_terrain(
    width: int = 80,
    height: int = 60,
    seed: Optional[int] = None,
    mode: str = "continent",
    octaves: int = 5,
    scale: float = 100.0,
    rivers: int = 8,
    wind: str = "west",
) -> Dict[str, Any]:
    """
    Thin wrapper around terraingen.TerrainGenerator.

    Keeps terraingen as the single source of truth.
    Raises ImportError if terraingen is not available.
    """
    from terraingen import TerrainGenerator  # type: ignore

    if seed is None:
        import random as _random
        seed = _random.randint(0, 999_999)

    gen = TerrainGenerator(
        width=width,
        height=height,
        seed=seed,
        mode=mode,
        octaves=octaves,
        scale=scale,
        river_count=rivers,
        prevailing_wind=wind,
    )
    return gen.generate()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Visualize biomes from a terrain.v1 file, or generate via terraingen and preview."
    )

    # Source options
    parser.add_argument(
        "--input", "-i",
        help="Path to existing terrain.json (terrain.v1). Omit when using --generate."
    )
    parser.add_argument(
        "--generate", "-g",
        action="store_true",
        help="Use terraingen.TerrainGenerator to create a map on the fly."
    )

    # Shared viz options
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors (plain ASCII)."
    )
    parser.add_argument(
        "--legend",
        action="store_true",
        help="Show biome legend."
    )
    parser.add_argument(
        "--char-width",
        type=int,
        default=1,
        help="Horizontal scale factor for each tile (default: 1)."
    )

    # Generation passthrough options (match terraingen defaults)
    parser.add_argument("--width", type=int, default=80, help="Generated map width.")
    parser.add_argument("--height", type=int, default=60, help="Generated map height.")
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for deterministic generation (passthrough to terraingen)."
    )
    parser.add_argument(
        "--mode",
        choices=["continent", "archipelago", "highlands", "none"],
        default="continent",
        help="Generation mode (for --generate)."
    )
    parser.add_argument(
        "--octaves",
        type=int,
        default=5,
        help="Noise octaves (for --generate)."
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=100.0,
        help="Noise scale (for --generate)."
    )
    parser.add_argument(
        "--rivers",
        type=int,
        default=8,
        help="Number of rivers (for --generate)."
    )
    parser.add_argument(
        "--wind",
        choices=["west", "east", "north", "south"],
        default="west",
        help="Prevailing wind direction (for --generate)."
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional path to save generated terrain JSON when using --generate."
    )

    args = parser.parse_args()

    # Decide data source
    if args.generate:
        try:
            data = generate_terrain(
                width=args.width,
                height=args.height,
                seed=args.seed,
                mode=args.mode,
                octaves=args.octaves,
                scale=args.scale,
                rivers=args.rivers,
                wind=args.wind,
            )
        except ImportError:
            print(
                "Error: terraingen module not found. Place biomeview.py next to terraingen.py or adjust PYTHONPATH.",
                file=sys.stderr,
            )
            return 1

        # Optionally save out the generated JSON for reuse
        if args.output:
            try:
                with open(args.output, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                print(f"Saved generated terrain to {args.output}")
            except Exception as e:
                print(f"Warning: could not save output JSON: {e}", file=sys.stderr)

    else:
        if not args.input:
            print("Error: either provide --input terrain.json or use --generate.", file=sys.stderr)
            return 1
        try:
            data = load_terrain(args.input)
        except Exception as e:
            print(f"Error loading terrain: {e}", file=sys.stderr)
            return 1

    use_color = not args.no_color and sys.stdout.isatty()
    output = render_biome_map(
        data,
        use_color=use_color,
        char_width=max(1, args.char_width),
        legend=args.legend,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())