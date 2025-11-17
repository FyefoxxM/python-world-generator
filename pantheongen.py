#!/usr/bin/env python3
"""
pantheongen.py

Generate a pantheon of deities for the world.

Input:
    - history_sim.v1 (preferred)
      or settlements.v1 + realms.v1
Output:
    - pantheon.v1

Follows library-first, CLI-second pattern.
"""

import argparse
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------- Helpers ----------


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_realms(path: Path) -> Dict[str, Any]:
    data = load_json(path)
    if data.get("schema") != "realms.v1":
        raise ValueError("Expected realms.v1 schema")
    return data


def load_settlements(path: Path) -> Dict[str, Any]:
    data = load_json(path)
    if data.get("schema") != "settlements.v1":
        raise ValueError("Expected settlements.v1 schema")
    return data


def load_history(path: Path) -> Dict[str, Any]:
    data = load_json(path)
    if data.get("schema") != "history_sim.v1":
        raise ValueError("Expected history_sim.v1 schema")
    return data


# ---------- Core ----------


class PantheonGenerator:
    def __init__(self, seed: Optional[int] = None, deity_data_path: Optional[Path] = None):
        self.seed = seed if seed is not None else random.randint(0, 999999)
        self.rng = random.Random(self.seed)

        if deity_data_path is None:
            deity_data_path = Path(__file__).parent / "deity_data.json"

        try:
            with deity_data_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {
                "domains": ["war", "wisdom", "nature", "death", "forge", "sea", "harvest", "trickery"],
                "symbols": ["sword", "owl", "tree", "skull", "hammer", "wave", "wheat", "mask"],
                "epithets": ["the Unyielding", "the Wise", "the Wild", "the Eternal"],
                "alignments": ["lawful_good", "neutral_good", "chaotic_good", "true_neutral"],
            }

        self.domains = data["domains"]
        self.symbols = data["symbols"]
        self.epithets = data["epithets"]
        self.alignments = data["alignments"]

    # ---------- Generation ----------

    def generate(self, world_data: Dict[str, Any]) -> Dict[str, Any]:
        realms = []
        settlements = []
        if world_data.get("schema") == "history_sim.v1":
            realms = [r for r in world_data.get("realms", [])]
        elif world_data.get("schema") == "realms.v1":
            realms = world_data.get("realms", [])
        if "settlements" in world_data:
            settlements = world_data["settlements"]

        deity_count = self.rng.randint(5, 8)
        deities = [self._make_deity(i, realms, settlements) for i in range(deity_count)]

        # Ensure every realm has at least one favored deity
        if realms:
            self._ensure_realm_coverage(deities, realms, settlements)

        myths = []
        for d in deities:
            for _ in range(self.rng.randint(2, 3)):
                myths.append(self._make_myth(d))

        pantheon = {
            "schema": "pantheon.v1",
            "seed": self.seed,
            "pantheon_name": self._pantheon_name(),
            "deities": deities,
            "myths": myths,
        }

        return pantheon

    # ---------- Internals ----------

    def _make_deity(self, index: int, realms: List[Dict[str, Any]], settlements: List[Dict[str, Any]]) -> Dict[str, Any]:
        domain = self.rng.choice(self.domains)
        symbol = self.symbols[self.domains.index(domain)] if domain in self.domains else self.rng.choice(self.symbols)
        epithet = self.rng.choice(self.epithets)
        alignment = self.rng.choice(self.alignments)

        name_root = domain.capitalize()
        name = f"{name_root} {epithet}"

        favored_realms = []
        if realms:
            realm_sample = self.rng.sample(realms, k=min(len(realms), self.rng.randint(1, 2)))
            favored_realms = [r["id"] for r in realm_sample]

        deity = {
            "id": f"deity_{index:03d}",
            "name": name,
            "title": f"God of {domain.capitalize()}",
            "domain": domain,
            "symbol": symbol,
            "alignment": alignment,
            "favored_by": favored_realms,
            "temples": [],
        }

        deity["temples"] = self._place_temples(favored_realms, settlements)
        return deity

    def _place_temples(self, favored_realms: List[int], settlements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Place temples in major settlements (capitals or cities) of favored realms."""
        temples = []
        
        for rid in favored_realms:
            # Find settlements in this realm
            realm_settlements = [s for s in settlements if s.get("realm") == rid]
            
            if not realm_settlements:
                # No settlements in this realm, create placeholder
                temples.append({
                    "settlement_id": f"settlement_{rid:03d}",
                    "importance": "major"
                })
                continue
            
            # Prefer capitals, then cities, then any settlement
            capital = next((s for s in realm_settlements if s.get("is_capital")), None)
            if capital:
                # Find index of this settlement in the full list for ID
                settlement_index = settlements.index(capital)
                temples.append({
                    "settlement_id": f"settlement_{settlement_index:03d}",
                    "importance": "major"
                })
            else:
                # Use first city if available, otherwise first settlement
                city = next((s for s in realm_settlements if s.get("type") == "city"), realm_settlements[0])
                settlement_index = settlements.index(city)
                temples.append({
                    "settlement_id": f"settlement_{settlement_index:03d}",
                    "importance": "major"
                })
        
        return temples

    def _ensure_realm_coverage(self, deities: List[Dict[str, Any]], realms: List[Dict[str, Any]], settlements: List[Dict[str, Any]]):
        """Ensure each realm is favored by at least one deity."""
        realm_ids = {r["id"] for r in realms}
        covered = {rid for d in deities for rid in d["favored_by"]}
        uncovered = realm_ids - covered
        
        # Assign uncovered realms to random deities
        for rid in uncovered:
            deity = self.rng.choice(deities)
            if rid not in deity["favored_by"]:
                deity["favored_by"].append(rid)
                
                # Add temple in this realm
                realm_settlements = [s for s in settlements if s.get("realm") == rid]
                if realm_settlements:
                    capital = next((s for s in realm_settlements if s.get("is_capital")), realm_settlements[0])
                    settlement_index = settlements.index(capital)
                    deity["temples"].append({
                        "settlement_id": f"settlement_{settlement_index:03d}",
                        "importance": "major"
                    })
                else:
                    # Fallback if no settlements
                    deity["temples"].append({
                        "settlement_id": f"settlement_{rid:03d}",
                        "importance": "major"
                    })

    def _make_myth(self, deity: Dict[str, Any]) -> Dict[str, Any]:
        verbs = ["Forging", "Birth", "Fall", "Rise", "Dream", "Wrath", "Blessing", "Trial"]
        nouns = ["Blade", "World", "Sun", "Moon", "Storm", "Harvest", "Forge", "Sea"]
        title = f"The {self.rng.choice(verbs)} of the {self.rng.choice(nouns)}"
        summary = f"How {deity['name']} shaped the fate of mortals through {deity['domain']}."
        return {"title": title, "deities": [deity["id"]], "summary": summary}

    def _pantheon_name(self) -> str:
        roots = ["Thornborn", "Ironveil", "Silverwake", "Dawnforged", "Ashen Covenant", "Twilight Host"]
        return f"The {self.rng.choice(roots)} Pantheon"


# ---------- CLI ----------


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a pantheon of deities (pantheon.v1).")
    parser.add_argument("--history", type=Path, help="Path to history_sim.v1 JSON")
    parser.add_argument("--realms", type=Path, help="Path to realms.v1 JSON")
    parser.add_argument("--settlements", type=Path, help="Path to settlements.v1 JSON")
    parser.add_argument("--deity-data", type=Path, help="Optional path to deity_data.json")
    parser.add_argument("--seed", type=int, help="Random seed")
    parser.add_argument("--output", type=Path, required=True, help="Output JSON path")
    args = parser.parse_args()

    if args.history:
        data = load_history(args.history)
    elif args.realms:
        data = load_realms(args.realms)
        if args.settlements:
            data["settlements"] = load_settlements(args.settlements).get("settlements", [])
    else:
        raise SystemExit("Must provide either --history or --realms")

    gen = PantheonGenerator(seed=args.seed, deity_data_path=args.deity_data)
    result = gen.generate(data)

    with args.output.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Generated pantheon.v1 (seed={result['seed']}) with {len(result['deities'])} deities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())