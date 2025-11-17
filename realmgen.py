#!/usr/bin/env python3
"""
Realm Painter (realmgen.py)

Assigns political realms to an existing terrain.v1 map.

Design:
- Library first, CLI second.
- Uses existing terrain.v1 JSON from terraingen.py.
- Deterministic via --seed.
- Output is flat, boring, human-editable.

Output schema (realms.v1):

{
  "schema": "realms.v1",
  "seed": int,
  "width": int,
  "height": int,
  "realm_count": int,
  "realms": [
    {
      "id": int,
      "name": str,
      "capital": [x, y]
    }
  ],
  "tiles": [
    {"x": int, "y": int, "realm": int or null}
  ]
}
"""

import json
import argparse
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Optional: passthrough to your existing terrain generator
try:
    from terraingen import TerrainGenerator
except ImportError:
    TerrainGenerator = None


class RealmPainter:
    def __init__(self, seed: Optional[int] = None):
        self.random = random.Random(seed)
        self.seed = seed if seed is not None else self.random.randint(0, 999999)
        # Simple fallback names; you can swap in realm_names.json later.
        self.default_names = [
            "Aldoria", "Kethran", "Velmoor", "Thessalia",
            "Orwyn", "Myrr", "Drakovar", "Selene Vale",
            "Norcrest", "Ilyrion"
        ]

    # ---------- Public API ----------

    def from_terrain(self, terrain: Dict, realm_count: int = 6) -> Dict:
        """Generate realms.v1 dict from terrain.v1 dict."""
        width = terrain.get("width")
        height = terrain.get("height")
        tiles = terrain.get("tiles", [])
        if not width or not height or not tiles:
            raise ValueError("Invalid terrain: missing width/height/tiles")

        land_tiles = [(t["x"], t["y"]) for t in tiles if not t.get("water", False)]
        if not land_tiles:
            # All water = no realms
            return {
                "schema": "realms.v1",
                "seed": self.seed,
                "width": width,
                "height": height,
                "realm_count": 0,
                "realms": [],
                "tiles": [{"x": t["x"], "y": t["y"], "realm": None} for t in tiles],
            }

        realm_count = max(1, min(realm_count, len(land_tiles)))

        capitals = self._pick_capitals(land_tiles, realm_count)
        realms = self._build_realms(capitals)
        assignments = self._assign_tiles(tiles, capitals)

        return {
            "schema": "realms.v1",
            "seed": self.seed,
            "width": width,
            "height": height,
            "realm_count": len(realms),
            "realms": realms,
            "tiles": assignments,
        }

    # ---------- Internal helpers ----------

    def _pick_capitals(
        self,
        land_tiles: List[Tuple[int, int]],
        realm_count: int
    ) -> List[Tuple[int, int]]:
        """Pick capital tiles using a simple max-distance heuristic."""
        capitals: List[Tuple[int, int]] = []
        capitals.append(self.random.choice(land_tiles))

        while len(capitals) < realm_count:
            best_tile = None
            best_dist = -1
            for x, y in land_tiles:
                if (x, y) in capitals:
                    continue
                d = min(abs(x - cx) + abs(y - cy) for cx, cy in capitals)
                if d > best_dist:
                    best_dist = d
                    best_tile = (x, y)
            if not best_tile:
                break
            capitals.append(best_tile)

        return capitals

    def _build_realms(self, capitals: List[Tuple[int, int]]) -> List[Dict]:
        realms: List[Dict] = []
        for i, (x, y) in enumerate(capitals):
            realms.append({
                "id": i,
                "name": self._realm_name(i),
                "capital": [x, y],
            })
        return realms

    def _realm_name(self, index: int) -> str:
        if index < len(self.default_names):
            return self.default_names[index]
        return f"Realm {index + 1}"

    def _assign_tiles(
        self,
        tiles: List[Dict],
        capitals: List[Tuple[int, int]],
    ) -> List[Dict]:
        """Assign each non-water tile to nearest capital (Manhattan)."""
        assignments: List[Dict] = []
        caps = capitals

        for t in tiles:
            x, y = t["x"], t["y"]
            if t.get("water", False):
                realm_id = None
            else:
                best_id = 0
                best_dist = 10**9
                for rid, (cx, cy) in enumerate(caps):
                    d = abs(x - cx) + abs(y - cy)
                    if d < best_dist:
                        best_dist = d
                        best_id = rid
                realm_id = best_id

            assignments.append({"x": x, "y": y, "realm": realm_id})

        return assignments


# ---------- Helpers ----------

def _load_terrain(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("schema") != "terrain.v1":
        raise ValueError("Expected terrain.v1 schema")
    return data


def _maybe_generate_terrain(
    width: int,
    height: int,
    seed: int,
    mode: str = "continent",
) -> Dict:
    """Optional passthrough: use existing TerrainGenerator."""
    if not TerrainGenerator:
        raise SystemExit("terraingen.py not available; use --input terrain.json instead.")
    gen = TerrainGenerator(width=width, height=height, seed=seed, mode=mode)
    return gen.generate()


def _realms_to_ascii(realm_data: Dict, use_color: bool = True) -> str:
    """Tiny ASCII visualization for sanity-checking realms."""
    width = realm_data["width"]
    height = realm_data["height"]
    tiles = realm_data["tiles"]

    glyphs = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    grid = [[" " for _ in range(width)] for _ in range(height)]

    colors = [
        "\033[91m", "\033[92m", "\033[93m", "\033[94m",
        "\033[95m", "\033[96m", "\033[90m"
    ]
    reset = "\033[0m"

    for t in tiles:
        x, y, rid = t["x"], t["y"], t["realm"]
        if rid is None:
            ch = "~"
            cell = ch
        else:
            ch = glyphs[rid % len(glyphs)]
            if use_color:
                color = colors[rid % len(colors)]
                cell = f"{color}{ch}{reset}"
            else:
                cell = ch
        grid[y][x] = cell

    return "\n".join("".join(row) for row in grid)


# ---------- CLI ----------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Paint political realms onto terrain.v1 maps.")
    parser.add_argument("--input", type=Path, help="Input terrain JSON (terrain.v1).")
    parser.add_argument("--output", type=Path, help="Output realms JSON.")
    parser.add_argument("--realms", type=int, default=6, help="Number of realms.")
    parser.add_argument("--seed", type=int, help="Random seed for realm placement.")
    parser.add_argument("--width", type=int, help="With --generate: terrain width.")
    parser.add_argument("--height", type=int, help="With --generate: terrain height.")
    parser.add_argument("--mode", type=str, default="continent", help="With --generate: terrain mode.")
    parser.add_argument("--generate", action="store_true",
                        help="Use terraingen.TerrainGenerator instead of --input.")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors in ASCII preview.")
    args = parser.parse_args(argv)

    # Source terrain: either load or generate via existing tool
    if args.generate:
        if args.width is None or args.height is None or args.seed is None:
            raise SystemExit("--generate requires --width, --height, and --seed.")
        terrain = _maybe_generate_terrain(args.width, args.height, args.seed, mode=args.mode)
    else:
        if not args.input:
            raise SystemExit("Provide --input terrain.json or use --generate.")
        terrain = _load_terrain(args.input)

    painter = RealmPainter(seed=args.seed)
    realms = painter.from_terrain(terrain, realm_count=args.realms)

    # ASCII preview
    print(_realms_to_ascii(realms, use_color=not args.no_color))
    print()

    # JSON output
    text = json.dumps(realms, indent=2)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"Wrote realms JSON to {args.output}")
    #else:
        #print(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())