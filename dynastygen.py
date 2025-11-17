#!/usr/bin/env python3
"""
dynastygen.py

Generate dynasties / ruling houses for realms.

- Input:
    - realms.v1 (required)
    - history_sim.v1 (optional; to align with simulated rulers)
- Output:
    - dynasties.v1

Design:
- Library-first.
- Deterministic via --seed.
- Uses existing NameGenerator from namegen.py when available.
- Flat, human-editable JSON.
"""

import json
import argparse
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from namegen import NameGenerator  # must match your existing file
except ImportError:
    NameGenerator = None  # type: ignore


RACES = ["human", "elf", "dwarf", "orc"]


# ---------- IO ----------

def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_realms(path: Path) -> Dict[str, Any]:
    data = load_json(path)
    if data.get("schema") != "realms.v1":
        raise ValueError("Expected realms.v1")
    return data


def load_history(path: Path) -> Dict[str, Any]:
    data = load_json(path)
    if data.get("schema") != "history_sim.v1":
        raise ValueError("Expected history_sim.v1")
    return data


# ---------- Core ----------

class DynastyGenerator:
    """
    Build dynasties from realms (+ optional history_sim rulers).

    Usage (library):
        gen = DynastyGenerator(seed=123)
        dyn = gen.generate(realms_data, history_data_optional)
    """

    def __init__(self, seed: Optional[int] = None, race_lifespans_path: Optional[Path] = None):
        self.seed = seed if seed is not None else random.randint(0, 999999)
        self.rng = random.Random(self.seed)
        self.name_gen = NameGenerator() if NameGenerator else None
        
        # Load race lifespan data
        if race_lifespans_path is None:
            # Look for race_lifespans.json in same directory as this file
            race_lifespans_path = Path(__file__).parent / "race_lifespans.json"
        
        try:
            self.race_lifespans = load_json(race_lifespans_path)
        except FileNotFoundError:
            # Fallback to hardcoded defaults if file not found
            self.race_lifespans = {
                "human": {"min_reign": 20, "max_reign": 50},
                "elf": {"min_reign": 80, "max_reign": 200},
                "dwarf": {"min_reign": 50, "max_reign": 150},
                "orc": {"min_reign": 15, "max_reign": 40},
                "default": {"min_reign": 20, "max_reign": 50},
            }

    def generate(
        self,
        realms: Dict[str, Any],
        history: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        realms_list = realms.get("realms", [])
        history_by_realm: Dict[int, Dict[str, Any]] = {}

        if history:
            for hr in history.get("realms", []):
                history_by_realm[hr["id"]] = hr

        dynasties: List[Dict[str, Any]] = []
        did = 0

        for r in realms_list:
            rid = r["id"]
            rname = r.get("name", f"Realm {rid}")
            race = self._pick_race_for_realm(rname)

            rulers = history_by_realm.get(rid, {}).get("rulers", [])
            dynasty_name = self._dynasty_name(rname, race)

            members, founder = self._build_members(rulers, race)

            dynasties.append(
                {
                    "id": did,
                    "realm_id": rid,
                    "realm_name": rname,
                    "name": dynasty_name,
                    "race": race,
                    "founder": founder,
                    "members": members,
                }
            )
            did += 1

        return {
            "schema": "dynasties.v1",
            "seed": self.seed,
            "dynasties": dynasties,
        }

    # ----- internals -----

    def _pick_race_for_realm(self, realm_name: str) -> str:
        h = sum(ord(c) for c in realm_name)
        return RACES[h % len(RACES)]

    def _dynasty_name(self, realm_name: str, race: str) -> str:
        base = self._person_name(race)
        # Use last token as house name to avoid spaces from human names
        surname = base.split()[-1]
        return f"House {surname}"

    def _ruler_lifespan(self, race: str) -> int:
        """Get appropriate reign length for a race."""
        race_key = race.lower()
        lifespan_data = self.race_lifespans.get(race_key, self.race_lifespans.get("default", {}))
        min_reign = lifespan_data.get("min_reign", 20)
        max_reign = lifespan_data.get("max_reign", 50)
        return self.rng.randint(min_reign, max_reign)

    def _build_members(
        self,
        rulers: List[Dict[str, Any]],
        race: str,
    ):
        members: List[Dict[str, Any]] = []

        # If we have rulers from history_sim, mirror them as a linear tree
        if rulers:
            first = rulers[0]
            founder_name = first.get("name", self._person_name(race))
            founder = {
                "name": founder_name,
                "race": race,
                "year": first.get("start_year", 0),
            }

            prev_id = None
            mid = 0
            for r in rulers:
                m = {
                    "id": mid,
                    "name": r.get("name", self._person_name(race)),
                    "role": "monarch",
                    "year_start": r.get("start_year", 0),
                    "year_end": r.get("end_year", r.get("start_year", 0)),
                }
                if prev_id is not None:
                    m["parent_id"] = prev_id
                members.append(m)
                prev_id = mid
                mid += 1

            return members, founder

        # Otherwise, synthesize a short line
        founder_name = self._person_name(race)
        founder = {
            "name": founder_name,
            "race": race,
            "year": 0,
        }

        prev_id = None
        year = 0
        length = self.rng.randint(2, 4)
        for mid in range(length):
            span = self._ruler_lifespan(race)
            name = founder_name if mid == 0 else self._person_name(race)
            m = {
                "id": mid,
                "name": name,
                "role": "monarch",
                "year_start": year,
                "year_end": year + span,
            }
            if prev_id is not None:
                m["parent_id"] = prev_id
            members.append(m)
            prev_id = mid
            year += span

        return members, founder

    def _person_name(self, race: str) -> str:
        """Use NameGenerator if possible; otherwise fallback."""
        race = race.lower()
        if self.name_gen:
            # Prefer the existing API without guessing:
            if hasattr(self.name_gen, "generate_name"):
                return str(self.name_gen.generate_name(race))
            # Fallback to specific race methods if present
            method_map = {
                "human": "generate_human_name",
                "elf": "generate_elf_name",
                "dwarf": "generate_dwarf_name",
                "orc": "generate_orc_name",
            }
            m = method_map.get(race)
            if m and hasattr(self.name_gen, m):
                return str(getattr(self.name_gen, m)())
        # Very small deterministic fallback so we never crash
        starts = ["Al", "Bel", "Cor", "Dan", "Ela", "Fen", "Gal", "Hal", "Is", "Jar"]
        ends = ["ric", "dor", "en", "iel", "as", "or", "eth", "an", "os", "yn"]
        return self.rng.choice(starts) + self.rng.choice(ends)


# ---------- CLI ----------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate dynasties for realms (dynasties.v1)."
    )
    parser.add_argument(
        "--realms",
        "-r",
        required=True,
        help="Path to realms.v1 JSON",
    )
    parser.add_argument(
        "--history",
        dest="history",
        required=False,
        help="Optional path to history_sim.v1 JSON (to align with rulers).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for deterministic dynasty generation.",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output JSON path for dynasties.v1",
    )

    args = parser.parse_args()

    realms = load_realms(Path(args.realms))
    history = load_history(Path(args.history)) if args.history else None

    gen = DynastyGenerator(seed=args.seed)
    data = gen.generate(realms, history)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())