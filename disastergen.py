#!/usr/bin/env python3
"""
disastergen.py

Generate macro-level disaster events for a world.

- Input:
    - terrain.v1
- Output:
    - disasters.v1
"""

import json
import argparse
import random
from pathlib import Path
from typing import Any, Dict, List, Optional


DISASTER_TYPES = [
    "plague",
    "famine",
    "earthquake",
    "flood",
    "storm",
    "wildfire",
    "arcane_catastrophe",
]


def load_terrain(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("schema") != "terrain.v1":
        raise ValueError("Expected terrain.v1")
    return data


class DisasterGenerator:
    def __init__(
        self, 
        seed: Optional[int] = None, 
        years: int = 400, 
        count: int = 20,
        rules_path: Optional[Path] = None
    ):
        self.seed = seed if seed is not None else random.randint(0, 999999)
        self.years = years
        self.count = count
        self.rng = random.Random(self.seed)
        
        # Load disaster rules
        if rules_path is None:
            rules_path = Path(__file__).parent / "disaster_rules.json"
        
        try:
            with rules_path.open("r", encoding="utf-8") as f:
                rules = json.load(f)
            self.disaster_types = rules.get("disaster_types", DISASTER_TYPES)
            self.biome_suitability = rules.get("biome_suitability", {})
        except FileNotFoundError:
            # Fallback to hardcoded if file not found
            self.disaster_types = DISASTER_TYPES
            self.biome_suitability = {}

    def generate(self, terrain: Dict[str, Any]) -> Dict[str, Any]:
        tiles = terrain.get("tiles", [])
        if not tiles:
            raise ValueError("No tiles in terrain")

        land = [t for t in tiles if not t.get("water")]
        rivers = [t for t in tiles if t.get("river")]
        coasts = [t for t in tiles if self._is_coast(t, tiles)]

        events: List[Dict[str, Any]] = []

        for _ in range(self.count):
            year = self.rng.randint(0, max(0, self.years - 1))
            dtype = self.rng.choice(self.disaster_types)

            # Pick suitable tiles based on disaster type and biome rules
            if dtype == "plague":
                suitable = self._filter_suitable_tiles(land, dtype)
                pos = self._pick(suitable) if suitable else self._pick(land)
                radius = self.rng.randint(4, 10)
                note = "Plague sweeps through populated routes."
            elif dtype == "famine":
                suitable = self._filter_suitable_tiles(land, dtype)
                pos = self._pick(suitable) if suitable else self._pick(land)
                radius = self.rng.randint(5, 12)
                note = "Harvests fail across key farmlands."
            elif dtype == "earthquake":
                suitable = self._filter_suitable_tiles(land, dtype)
                pos = self._pick(suitable) if suitable else self._pick(land)
                radius = self.rng.randint(2, 6)
                note = "Earthquakes shatter cities and roads."
            elif dtype == "flood":
                # Floods need lowlands near water
                suitable = self._filter_suitable_tiles(land, dtype, all_tiles=tiles)
                pos = self._pick(suitable) if suitable else self._pick(coasts or land)
                radius = self.rng.randint(3, 8)
                note = "Rivers or coasts overflow; lowlands drown."
            elif dtype == "storm":
                # Storms prefer coasts but can hit anywhere
                base = coasts if coasts else land
                suitable = self._filter_suitable_tiles(base, dtype)
                pos = self._pick(suitable) if suitable else self._pick(base)
                radius = self.rng.randint(4, 10)
                note = "A great storm ravages the region."
            elif dtype == "wildfire":
                # Wildfires need vegetation
                suitable = self._filter_suitable_tiles(land, dtype)
                pos = self._pick(suitable) if suitable else self._pick(land)
                radius = self.rng.randint(3, 7)
                note = "Wildfires sweep forests and plains."
            else:  # arcane_catastrophe
                suitable = self._filter_suitable_tiles(land, dtype)
                pos = self._pick(suitable) if suitable else self._pick(land)
                radius = self.rng.randint(2, 5)
                note = "Arcane forces devastate the landscape."

            if not pos:
                continue

            events.append(
                {
                    "year": year,
                    "type": dtype,
                    "severity": self.rng.randint(1, 5),
                    "x": pos["x"],
                    "y": pos["y"],
                    "radius": radius,
                    "note": note,
                }
            )

        events.sort(key=lambda e: e["year"])

        return {
            "schema": "disasters.v1",
            "seed": self.seed,
            "years": self.years,
            "events": events,
        }

    # ----- internals -----

    def _pick(self, tiles: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not tiles:
            return None
        return self.rng.choice(tiles)

    def _is_coast(self, tile: Dict[str, Any], tiles: List[Dict[str, Any]]) -> bool:
        if tile.get("water"):
            return False
        x, y = tile["x"], tile["y"]
        lookup = {(t["x"], t["y"]): t for t in tiles}
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = lookup.get((x + dx, y + dy))
            if n and n.get("water"):
                return True
        return False

    def _has_water_neighbor(self, tile: Dict[str, Any], tiles: List[Dict[str, Any]]) -> bool:
        """Check if tile is adjacent to water (for floods)."""
        x, y = tile["x"], tile["y"]
        lookup = {(t["x"], t["y"]): t for t in tiles}
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = lookup.get((x + dx, y + dy))
            if n and (n.get("water") or n.get("river")):
                return True
        return False

    def _is_biome_suitable(self, tile: Dict[str, Any], disaster_type: str) -> bool:
        """Check if disaster type can occur in this biome."""
        if not self.biome_suitability:
            return True  # No rules loaded, allow everything
        
        rules = self.biome_suitability.get(disaster_type, {})
        if not rules:
            return True  # No rules for this disaster type
        
        biome = tile.get("biome", "unknown")
        suitable = rules.get("suitable", [])
        unsuitable = rules.get("unsuitable", [])
        
        # Check unsuitable first
        if unsuitable and biome in unsuitable:
            return False
        
        # Check suitable (if "all", accept everything not in unsuitable)
        if suitable and "all" not in suitable and biome not in suitable:
            return False
        
        # Check elevation constraints for floods
        if disaster_type == "flood":
            elevation_max = rules.get("elevation_max")
            if elevation_max is not None:
                if tile.get("elevation", 1.0) > elevation_max:
                    return False
        
        return True

    def _filter_suitable_tiles(
        self, 
        tiles: List[Dict[str, Any]], 
        disaster_type: str,
        all_tiles: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Filter tiles to only those suitable for this disaster type."""
        suitable = []
        
        for tile in tiles:
            if not self._is_biome_suitable(tile, disaster_type):
                continue
            
            # Special case: flood needs water neighbor
            if disaster_type == "flood":
                rules = self.biome_suitability.get("flood", {})
                if rules.get("requires_water_neighbor") and all_tiles:
                    if not self._has_water_neighbor(tile, all_tiles):
                        continue
            
            suitable.append(tile)
        
        return suitable


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate disasters for a world (disasters.v1)."
    )
    parser.add_argument(
        "--terrain",
        "-t",
        required=True,
        help="Path to terrain.v1 JSON",
    )
    parser.add_argument(
        "--years",
        "-y",
        type=int,
        default=400,
        help="Timespan in years (default: 400)",
    )
    parser.add_argument(
        "--count",
        "-c",
        type=int,
        default=20,
        help="Number of disasters to generate (default: 20)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for deterministic generation.",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output JSON path for disasters.v1",
    )

    args = parser.parse_args()

    terrain = load_terrain(Path(args.terrain))
    gen = DisasterGenerator(seed=args.seed, years=args.years, count=args.count)
    out = gen.generate(terrain)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())