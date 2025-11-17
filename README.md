# RPG World Generator

Complete procedural world generation toolkit for tabletop RPGs. Generates realistic geography, political territories, settlements, disasters, dynasties, and pantheons.

**Part of the 30-for-30 challenge: Day 13**

## Features

- **Terrain Generation**: Elevation, moisture, rivers, and biomes using simplex noise
- **Political Realms**: Territory painting with realistic borders
- **Strategic Settlements**: Cities, towns, and forts placed based on geography
- **Historical Events**: 400 years of disasters, wars, and cultural shifts
- **Dynasties**: Ruling families with succession and lineage
- **Pantheons**: Gods, domains, temples, and religious influence

All generation is deterministic - use seeds to reproduce exact worlds.

## Installation

```bash
git clone https://github.com/yourusername/rpg-worldgen.git
cd rpg-worldgen
```

Requires Python 3.10+. No external dependencies.

## Library Usage

Import and use generators programmatically:

```python
import terraingen
import realmgen
import settlementgen

# Generate terrain
terrain_gen = terraingen.TerrainGenerator(width=60, height=50, seed=12345)
terrain = terrain_gen.generate()

# Paint realms
realm_painter = realmgen.RealmPainter(seed=67890)
world = realm_painter.from_terrain(terrain, realm_count=5)

# Place settlements
settlement_placer = settlementgen.SettlementPlacer(seed=11111)
world = settlement_placer.generate(terrain=world, realms=world)
```

Each generator returns standardized JSON with versioned schemas (`terrain.v1`, `realms.v1`, etc).

## CLI Usage

### Quick World Generation

```bash
python worldgen.py --output world.json --ansi
```

Generates a complete world with random seed, saves to JSON, displays colored map.

### Full Control

```bash
python worldgen.py \
  --width 60 \
  --height 50 \
  --seed 42 \
  --years 400 \
  --disasters 20 \
  --output world.json \
  --ansi
```

### Individual Generators

Each generator works standalone:

```bash
# Terrain only
python terraingen.py --width 60 --height 50 --seed 123 --output terrain.json --ascii

# Realms (requires terrain.json)
python realmgen.py --input terrain.json --seed 456 --output realms.json

# Settlements (requires realms.json)
python settlementgen.py --input realms.json --seed 789 --output settlements.json

# View with colors
python biomeview.py --input terrain.json --legend
```

## Output Format

`worldgen.py` produces a single JSON file containing:

```json
{
  "schema": "terrain.v1",
  "master_seed": 42,
  "component_seeds": {
    "terrain": 123456,
    "realms": 234567,
    "settlements": 345678,
    "disasters": 456789,
    "dynasties": 567890,
    "pantheon": 678901
  },
  "width": 60,
  "height": 50,
  "tiles": [...],
  "realms": [...],
  "settlements": [...],
  "disasters": [...],
  "dynasties": [...],
  "pantheon": {...}
}
```

All data in one file, ready to import into your game or world-building tool.

## Architecture

**Week 2 Patterns:**
1. Seed-based deterministic generation
2. Standardized JSON schemas with version tags
3. Human-editable configuration files
4. Library-first design (CLI wraps importable functions)

**Pipeline:**
```
terrain → realms → settlements → disasters → dynasties → pantheon
```

Each stage reads the previous stage's output and adds new data.


## Data Files

All generator behavior is controlled by human-editable JSON:

- `disaster_rules.json` - Disaster types and biome compatibility
- `race_lifespans.json` - Race lifespans for dynasty generation
- `settlement_name_data.json` - Name components for settlement generation
- `name_data.json` - Character names for NPCs
- `npc_*.json` - NPC traits, occupations, hooks, secrets

Edit these to customize generation without touching code.

## Project Structure

```
rpg-worldgen/
├── worldgen.py              # Main integration CLI
├── terraingen.py            # Terrain generator
├── realmgen.py              # Realm painter
├── settlementgen.py         # Settlement placer
├── disastergen.py           # Disaster generator
├── dynastygen.py            # Dynasty generator
├── pantheongen.py           # Pantheon creator
├── biomeview.py             # ASCII/ANSI visualization
├── historysim.py            # Historical simulation
├── settlement_namegen.py    # Settlement name generation
├── *_data.json              # Configuration files
├── test_*.py                # Unit tests
└── run_tests.py             # Test runner
```

## Examples

Generate world and view it:
```bash
python worldgen.py --seed 42 --output world.json --ansi
```

Reproduce exact world:
```bash
python worldgen.py --seed 42 --output world2.json
# world.json and world2.json are identical
```

Custom size and history:
```bash
python worldgen.py --width 100 --height 80 --years 800 --output big_world.json
```

## License

MIT License - Free for commercial and personal use.

## Credits

Part of the **30-for-30 Challenge**: Building 30 small tools in 30 days.

Day 13: World Generator Integration
