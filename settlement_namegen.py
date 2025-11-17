#!/usr/bin/env python3
"""
Settlement Name Generator

Library-first utility for generating settlement names (cities, towns, forts, ports, ruins)
using simple prefix/suffix syllables.

Usage (CLI):
    python settlement_namegen.py --type city --count 10 --seed 123

Usage (library):
    from settlement_namegen import SettlementNameGenerator
    gen = SettlementNameGenerator()
    name = gen.generate_name(kind="city")
"""

import json
import random
import argparse
from pathlib import Path


class SettlementNameGenerator:
    """
    Generates settlement-style names from syllable data.

    Data format (settlement_name_data.json):
    {
      "start": [...],
      "end": [...]
    }
    """

    def __init__(self, data_file: str = "settlement_name_data.json"):
        # Resolve relative path next to this file by default
        if not Path(data_file).is_absolute():
            data_path = Path(__file__).parent / data_file
        else:
            data_path = Path(data_file)

        with data_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        self.starts = list(data.get("start", []))
        self.ends = list(data.get("end", []))

        if not self.starts or not self.ends:
            raise ValueError(
                "SettlementNameGenerator: 'start' and 'end' lists must not be empty."
            )

    # ---------- Public API ----------

    def generate_name(self, kind: str = "generic", seed=None, rng=None) -> str:
        """
        Generate a settlement name.

        Args:
            kind: One of 'generic', 'city', 'town', 'village', 'fort', 'port', 'ruin', 'capital'.
                  This only lightly biases the suffix choice.
            seed: Optional integer seed for this call (if no rng is provided).
            rng:  Optional random.Random-like object. If provided, overrides seed/global RNG.

        Returns:
            Settlement name string.
        """
        # Priority: external rng → per-call seeded rng → global random
        local_rng = rng
        if local_rng is None:
            if seed is not None:
                local_rng = random.Random(seed)
            else:
                local_rng = random

        prefix = local_rng.choice(self.starts)
        suffix = self._pick_suffix_for_kind(kind, local_rng)

        raw = (prefix + suffix).replace("  ", " ").strip()

        # Clean capitalization, including multi-word pieces
        parts = raw.split()
        name = " ".join(p[:1].upper() + p[1:] for p in parts if p)

        return name

    # ---------- Internal helpers ----------

    def _pick_suffix_for_kind(self, kind: str, rng) -> str:
        """Very soft bias of suffixes based on settlement kind."""
        kind = (kind or "generic").lower()

        def available(candidates):
            return [s for s in candidates if s in self.ends]

        city_suffixes = available(
            [
                "burg",
                "bury",
                "ham",
                "haven",
                "hold",
                "holm",
                "keep",
                "march",
                "mere",
                "mill",
                "moor",
                "mouth",
                "port",
                "stead",
                "stone",
                "ton",
                "tower",
                "town",
                "vale",
                "view",
                "ville",
                "wall",
                "ward",
                "watch",
                "water",
                "wick",
                "market",
            ]
        )

        town_suffixes = available(
            [
                "bridge",
                "brook",
                "dale",
                "den",
                "field",
                "fields",
                "ford",
                "glen",
                "grove",
                "hill",
                "mill",
                "stead",
                "ton",
                "town",
                "well",
                "wick",
                "worth",
            ]
        )

        fort_suffixes = available(
            [
                "fort",
                "gate",
                "guard",
                "hold",
                "keep",
                "scar",
                "shield",
                "spire",
                "strong",
                "tower",
                "wall",
                "ward",
                "watch",
            ]
        )

        port_suffixes = available(
            [
                "port",
                "harbor",
                "haven",
                "mouth",
                "wharf",
                "water",
            ]
        )

        ruin_suffixes = available(
            [
                "barrow",
                "deep",
                "fall",
                "falls",
                "hollow",
                "scar",
                "shade",
                "thorn",
                "wold",
            ]
        )

        if kind in ("city", "capital"):
            pool = city_suffixes or self.ends
        elif kind in ("town", "village"):
            pool = town_suffixes or self.ends
        elif kind == "fort":
            pool = fort_suffixes or self.ends
        elif kind == "port":
            pool = port_suffixes or self.ends
        elif kind == "ruin":
            pool = ruin_suffixes or self.ends
        else:
            pool = self.ends

        return rng.choice(pool)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Settlement name generator (library-first)."
    )
    parser.add_argument(
        "--type",
        "-t",
        dest="kind",
        default="generic",
        help="Settlement kind: generic, city, town, village, fort, port, ruin, capital",
    )
    parser.add_argument(
        "--count",
        "-n",
        type=int,
        default=10,
        help="How many names to generate.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for deterministic output.",
    )
    parser.add_argument(
        "--data-file",
        type=str,
        default="settlement_name_data.json",
        help="Path to settlement name data JSON.",
    )

    args = parser.parse_args()

    if args.seed is not None:
        # Deterministic CLI sequences
        random.seed(args.seed)

    gen = SettlementNameGenerator(data_file=args.data_file)

    for _ in range(args.count):
        print(gen.generate_name(kind=args.kind))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
