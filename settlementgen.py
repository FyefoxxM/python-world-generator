#!/usr/bin/env python3
"""
settlementgen.py

Starting settlement placer for the worldgen toolkit.

Design:
- Library-first, CLI-second.
- Uses:
    - terrain.v1 (from terraingen.py)
    - realms.v1  (from realmgen.py) [optional but recommended]
    - SettlementNameGenerator (from settlement_namegen.py)
- Places ONLY initial population centers (cities, towns, optional villages).
  Later history/POI passes are free to add/modify.

Output schema (settlements.v1):

{
  "schema": "settlements.v1",
  "seed": 123,
  "settlements": [
    {
      "name": "Dawnport",
      "type": "city",        # city | town | village
      "x": 42,
      "y": 27,
      "realm": 2,            # or null if no realms
      "biome": "grassland",
      "is_capital": true,
      "is_port": true
    }
  ]
}
"""

import argparse
import json
import random
import sys
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Optional name generator
try:
    from settlement_namegen import SettlementNameGenerator
except ImportError:
    SettlementNameGenerator = None
    
#Optional Realm Painter import
try:
    from realmgen import RealmPainter
except ImportError:
    RealmPainter = None

# ---------- Helpers to load inputs ----------

def load_terrain(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("schema") != "terrain.v1":
        raise ValueError("Expected terrain.v1 for terrain input")
    return data


def load_realms(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("schema") != "realms.v1":
        raise ValueError("Expected realms.v1 for realms input")
    return data


# ---------- Core placement engine ----------

class SettlementPlacer:
    def __init__(self, seed: Optional[int] = None):
        self.seed = seed if seed is not None else random.randint(0, 999999)
        self.rng = random.Random(self.seed)
        self.namegen = SettlementNameGenerator() if SettlementNameGenerator else None

    # Public entrypoint for other scripts
    def generate(
        self,
        terrain: Dict,
        realms: Optional[Dict] = None,
        cities_per_realm: int = 1,
        towns_per_realm: int = 3,
        villages_per_realm: int = 0,
    ) -> Dict:
        width = terrain["width"]
        height = terrain["height"]
        tiles = terrain["tiles"]

        # Index terrain tiles by (x,y)
        grid = {(t["x"], t["y"]): t for t in tiles}

        # Realms mapping: (x,y) -> realm_id or None
        realm_tiles, realms_meta = self._prepare_realms(width, height, realms)

        # Precompute distance fields
        dist_water = self._distance_field(width, height, grid, lambda t: bool(t.get("water")))
        dist_river = self._distance_field(width, height, grid, lambda t: bool(t.get("river")))

        settlements: List[Dict] = []

        # Placement parameters (tuned for "realistic-ish", tweak as needed)
        min_city_spacing = 18
        min_town_spacing = 8
        min_village_spacing = 4

        # Process per realm (or single pseudo-realm)
        for realm_id, meta in realms_meta.items():
            land_tiles = [
                (x, y) for (x, y), t in grid.items()
                if not t.get("water")
                and (realm_tiles.get((x, y)) == realm_id if realms_meta else True)
            ]
            if not land_tiles:
                continue

            # 1) Capital city
            capital_site = self._pick_capital_site(
                grid, dist_water, dist_river, land_tiles, meta.get("capital")
            )
            if capital_site:
                sx, sy = capital_site
                settlements.append(
                    self._make_settlement(
                        x=sx,
                        y=sy,
                        kind="city",
                        biome=grid[(sx, sy)]["biome"],
                        realm=realm_id,
                        is_capital=True,
                        is_port=self._is_port_tile(grid, sx, sy),
                    )
                )

            # Convenience list for spacing checks
            def too_close(x: int, y: int, min_dist: int, types: Tuple[str, ...]) -> bool:
                for s in settlements:
                    if s["type"] in types:
                        dx = s["x"] - x
                        dy = s["y"] - y
                        if abs(dx) + abs(dy) < min_dist:
                            return True
                return False

            # Candidate ranking helpers
            city_candidates = self._rank_candidates(
                land_tiles, grid, dist_water, dist_river, score_kind="city"
            )
            town_candidates = self._rank_candidates(
                land_tiles, grid, dist_water, dist_river, score_kind="town"
            )
            village_candidates = self._rank_candidates(
                land_tiles, grid, dist_water, dist_river, score_kind="village"
            )

            # 2) Extra cities
            target_cities = max(1, cities_per_realm)
            placed_cities = 1 if capital_site else 0
            for (x, y), _score in city_candidates:
                if placed_cities >= target_cities:
                    break
                if too_close(x, y, min_city_spacing, ("city",)):
                    continue
                if (x, y) == capital_site:
                    continue
                settlements.append(
                    self._make_settlement(
                        x=x,
                        y=y,
                        kind="city",
                        biome=grid[(x, y)]["biome"],
                        realm=realm_id,
                        is_capital=False,
                        is_port=self._is_port_tile(grid, x, y),
                    )
                )
                placed_cities += 1

            # 3) Towns
            placed_towns = 0
            for (x, y), _score in town_candidates:
                if placed_towns >= towns_per_realm:
                    break
                if too_close(x, y, min_town_spacing, ("city", "town")):
                    continue
                settlements.append(
                    self._make_settlement(
                        x=x,
                        y=y,
                        kind="town",
                        biome=grid[(x, y)]["biome"],
                        realm=realm_id,
                        is_capital=False,
                        is_port=self._is_port_tile(grid, x, y),
                    )
                )
                placed_towns += 1

            # 4) Villages (optional, light sprinkling)
            placed_villages = 0
            for (x, y), _score in village_candidates:
                if placed_villages >= villages_per_realm:
                    break
                if too_close(x, y, min_village_spacing, ("city", "town", "village")):
                    continue
                settlements.append(
                    self._make_settlement(
                        x=x,
                        y=y,
                        kind="village",
                        biome=grid[(x, y)]["biome"],
                        realm=realm_id,
                        is_capital=False,
                        is_port=False,  # small ports can come later via history/POI pass
                    )
                )
                placed_villages += 1

        return {
            "schema": "settlements.v1",
            "seed": self.seed,
            "settlements": settlements,
        }

    # ---------- Internals ----------

    def _prepare_realms(self, width: int, height: int, realms: Optional[Dict]):
        if not realms:
            # Single pseudo-realm: id = None, no capitals
            meta = {None: {"id": None, "name": None, "capital": None}}
            tiles = {}
            return tiles, meta

        tiles = {}
        for t in realms.get("tiles", []):
            tiles[(t["x"], t["y"])] = t.get("realm")

        meta = {}
        for r in realms.get("realms", []):
            meta[r["id"]] = {
                "id": r["id"],
                "name": r.get("name"),
                "capital": tuple(r.get("capital")) if r.get("capital") else None,
            }

        return tiles, meta

    def _distance_field(
        self,
        width: int,
        height: int,
        grid: Dict[Tuple[int, int], Dict],
        is_source,
        max_dist: int = 9999,
    ) -> Dict[Tuple[int, int], int]:
        # BFS from all source tiles
        q = deque()
        dist = {(x, y): max_dist for x in range(width) for y in range(height)}

        for (x, y), t in grid.items():
            if is_source(t):
                dist[(x, y)] = 0
                q.append((x, y))

        while q:
            x, y = q.popleft()
            d = dist[(x, y)]
            nd = d + 1
            if nd >= max_dist:
                continue
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < width and 0 <= ny < height:
                    if nd < dist[(nx, ny)]:
                        dist[(nx, ny)] = nd
                        q.append((nx, ny))

        return dist

    def _pick_capital_site(
        self,
        grid: Dict[Tuple[int, int], Dict],
        dist_water: Dict[Tuple[int, int], int],
        dist_river: Dict[Tuple[int, int], int],
        land_tiles: List[Tuple[int, int]],
        preferred_capital: Optional[Tuple[int, int]],
        search_radius: int = 5,
    ) -> Optional[Tuple[int, int]]:
        # Try near provided capital coord first
        candidates: List[Tuple[int, int]] = []

        def score_tile(x: int, y: int) -> float:
            t = grid[(x, y)]
            if t.get("water"):
                return -1e9
            biome = t.get("biome", "")
            biome_score = {
                "grassland": 3.0,
                "temperate_forest": 2.5,
                "wetlands": 1.5,
                "beach": 1.5,
                "highland": 1.0,
            }.get(biome, 0.5)
            w = dist_water.get((x, y), 99)
            r = dist_river.get((x, y), 99)
            water_bonus = max(0, 4 - min(w, r))  # closer is better
            return biome_score + water_bonus

        if preferred_capital:
            cx, cy = preferred_capital
            for dx in range(-search_radius, search_radius + 1):
                for dy in range(-search_radius, search_radius + 1):
                    x, y = cx + dx, cy + dy
                    if (x, y) in grid and (x, y) in land_tiles:
                        s = score_tile(x, y)
                        if s > 0:
                            candidates.append(((x, y), s))

        if candidates:
            candidates.sort(key=lambda item: item[1], reverse=True)
            return candidates[0][0]

        # Fallback: best land tile overall
        best = None
        best_score = -1e9
        for (x, y) in land_tiles:
            s = score_tile(x, y)
            if s > best_score:
                best_score = s
                best = (x, y)
        return best

    def _rank_candidates(
        self,
        coords: List[Tuple[int, int]],
        grid: Dict[Tuple[int, int], Dict],
        dist_water: Dict[Tuple[int, int], int],
        dist_river: Dict[Tuple[int, int], int],
        score_kind: str,
    ) -> List[Tuple[Tuple[int, int], float]]:
        # Basic suitability scoring; tuned differently per type
        scores: List[Tuple[Tuple[int, int], float]] = []
        for (x, y) in coords:
            t = grid[(x, y)]
            if t.get("water"):
                continue
            biome = t.get("biome", "")
            w = dist_water.get((x, y), 99)
            r = dist_river.get((x, y), 99)
            near_water = min(w, r)

            if score_kind == "city":
                biome_score = {
                    "grassland": 3.0,
                    "temperate_forest": 2.5,
                    "beach": 2.0,
                }.get(biome, 0.0)
                if biome_score <= 0:
                    continue
                score = biome_score + max(0, 4 - near_water)
            elif score_kind == "town":
                biome_score = {
                    "grassland": 2.5,
                    "temperate_forest": 2.0,
                    "wetlands": 1.5,
                    "highland": 1.0,
                    "beach": 2.0,
                }.get(biome, 0.5)
                score = biome_score + max(0, 5 - near_water)
            else:  # village
                biome_score = {
                    "grassland": 2.0,
                    "temperate_forest": 1.8,
                    "wetlands": 1.5,
                    "highland": 1.0,
                }.get(biome, 0.5)
                score = biome_score + max(0, 6 - near_water)

            if score > 0:
                scores.append(((x, y), score))

        # Sort high to low, add light randomness for variation
        self.rng.shuffle(scores)
        scores.sort(key=lambda item: item[1], reverse=True)
        return scores

    def _is_port_tile(self, grid: Dict[Tuple[int, int], Dict], x: int, y: int) -> bool:
        t = grid[(x, y)]
        if t.get("water"):
            return False
        biome = t.get("biome", "")
        if biome not in ("beach", "grassland", "temperate_forest"):
            return False
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            nt = grid.get((nx, ny))
            if nt and nt.get("water"):
                return True
        return False

    def _make_settlement(
        self,
        x: int,
        y: int,
        kind: str,
        biome: str,
        realm: Optional[int],
        is_capital: bool,
        is_port: bool,
    ) -> Dict:
        name = self._generate_name(kind="capital" if is_capital else ("port" if is_port else kind))
        return {
            "name": name,
            "type": kind,
            "x": x,
            "y": y,
            "realm": realm,
            "biome": biome,
            "is_capital": bool(is_capital),
            "is_port": bool(is_port),
        }

    def _generate_name(self, kind: str) -> str:
        if self.namegen:
            return self.namegen.generate_name(kind=kind, rng=self.rng)
        # Fallback: simple, so tool never dies if import fails
        base = {
            "city": "City",
            "town": "Town",
            "village": "Village",
            "port": "Port",
            "capital": "Capital",
        }.get(kind, "Hold")
        suffix = self.rng.randint(1, 9999)
        return f"{base} {suffix}"


# Convenience function for other scripts
def generate_settlements(
    terrain: Dict,
    realms: Optional[Dict] = None,
    seed: Optional[int] = None,
    cities_per_realm: int = 1,
    towns_per_realm: int = 3,
    villages_per_realm: int = 0,
) -> Dict:
    placer = SettlementPlacer(seed=seed)
    return placer.generate(
        terrain=terrain,
        realms=realms,
        cities_per_realm=cities_per_realm,
        towns_per_realm=towns_per_realm,
        villages_per_realm=villages_per_realm,
    )


# ---------- CLI ----------

def main() -> int:
    parser = argparse.ArgumentParser(description="Place starting settlements on terrain/realms.")
    parser.add_argument("--terrain", type=Path, required=True, help="Path to terrain.v1 JSON")
    parser.add_argument("--realms", type=Path, help="Path to realms.v1 JSON (optional)")
    parser.add_argument("--seed", type=int, default=None, help="Seed for deterministic placement")
    parser.add_argument("--cities-per-realm", type=int, default=1, help="Extra cities per realm (besides capital)")
    parser.add_argument("--towns-per-realm", type=int, default=3, help="Towns per realm")
    parser.add_argument("--villages-per-realm", type=int, default=0, help="Villages per realm")
    parser.add_argument("--output", type=Path, help="Write settlements.v1 JSON to this path")
    parser.add_argument("--ascii", action="store_true", help="Print ASCII overlay preview")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors in ASCII view")
    args = parser.parse_args()

    terrain = load_terrain(args.terrain)

    # Handle realms input:
    if args.realms:
        # If a realms file path was provided...
        if args.realms.exists():
            # ...and it exists, load it normally.
            realms = load_realms(args.realms)
        else:
            # ...and it does NOT exist, try to auto-generate using realmgen.RealmPainter
            if RealmPainter is not None:
                print(f"[settlementgen] {args.realms} not found. Generating realms on the fly using seed {args.seed}.")
                painter = RealmPainter(seed=args.seed)
                # Default to 6 realms; tweak if you want this configurable.
                realms = painter.from_terrain(terrain, realm_count=6)
            else:
                print(f"[settlementgen] {args.realms} not found and realmgen not available. Proceeding WITHOUT realms.", file=sys.stderr)
                realms = None
    else:
        # No --realms provided: single pseudo-realm case handled in _prepare_realms
        realms = None


    placer = SettlementPlacer(seed=args.seed)
    data = placer.generate(
        terrain=terrain,
        realms=realms,
        cities_per_realm=args.cities_per_realm,
        towns_per_realm=args.towns_per_realm,
        villages_per_realm=args.villages_per_realm,
    )

    if args.ascii:
        _print_ascii_preview(terrain, data, use_color=not args.no_color)

    text = json.dumps(data, indent=2)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"Wrote settlements to {args.output}")
    else:
        print(text)

    return 0


def _print_ascii_preview(terrain: Dict, settlements_data: Dict, use_color: bool = True) -> None:
    width = terrain["width"]
    height = terrain["height"]
    grid = {(t["x"], t["y"]): t for t in terrain["tiles"]}
    settlements = settlements_data["settlements"]

    # Quick lookup
    s_at = {(s["x"], s["y"]): s for s in settlements}

    # Colors (simple)
    reset = "\033[0m"
    city_c = "\033[91m" if use_color else ""
    town_c = "\033[93m" if use_color else ""
    vill_c = "\033[92m" if use_color else ""
    water_c = "\033[94m" if use_color else ""

    for y in range(height):
        row = []
        for x in range(width):
            s = s_at.get((x, y))
            t = grid.get((x, y), {})
            ch = " "
            if t.get("water"):
                ch = "~"
                cell = f"{water_c}{ch}{reset}" if use_color else ch
            elif s:
                if s["type"] == "city":
                    cell = f"{city_c}C{reset}" if use_color else "C"
                elif s["type"] == "town":
                    cell = f"{town_c}t{reset}" if use_color else "t"
                else:
                    cell = f"{vill_c}v{reset}" if use_color else "v"
            else:
                biome = t.get("biome", "")
                ch = "." if biome in ("grassland", "temperate_forest") else ","
                cell = ch
            row.append(cell)
        print("".join(row))
    print()


if __name__ == "__main__":
    raise SystemExit(main())