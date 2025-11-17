#!/usr/bin/env python3
"""
World Generator - Complete RPG world generation pipeline
Runs terrain → realms → settlements → disasters → dynasties → pantheon
"""

import random
import json
import argparse
from typing import Dict

import terraingen
import realmgen
import settlementgen
import disastergen
import dynastygen
import pantheongen
from biomeview import render_biome_map


def derive_seeds(master_seed: int) -> Dict[str, int]:
    """Derive all component seeds from master seed"""
    rng = random.Random(master_seed)
    return {
        'terrain': rng.randint(0, 999999),
        'realms': rng.randint(0, 999999),
        'settlements': rng.randint(0, 999999),
        'disasters': rng.randint(0, 999999),
        'dynasties': rng.randint(0, 999999),
        'pantheon': rng.randint(0, 999999)
    }


def generate_world(
    width: int,
    height: int,
    master_seed: int,
    years: int = 400,
    disaster_count: int = 20
) -> Dict:
    """Run complete world generation pipeline"""
    
    print(f"\nGenerating world (master seed: {master_seed})...\n")
    
    # Derive component seeds
    seeds = derive_seeds(master_seed)
    print(f"Component seeds: {seeds}\n")
    
        # Step 1: Terrain
    print("1. Generating terrain...")
    terrain_gen = terraingen.TerrainGenerator(
        width=width,
        height=height,
        seed=seeds['terrain'],
        mode='continent'
    )
    terrain = terrain_gen.generate()

    # Step 2: Realms (separate dict)
    print("2. Painting realms...")
    realm_painter = realmgen.RealmPainter(seed=seeds['realms'])
    realms = realm_painter.from_terrain(terrain, realm_count=5)

    # Step 3: Settlements (needs BOTH terrain and realms)
    print("3. Placing settlements...")
    settlement_placer = settlementgen.SettlementPlacer(seed=seeds['settlements'])
    settlements = settlement_placer.generate(
        terrain=terrain,  # Original terrain with biome data
        realms=realms,    # Realm assignments
        cities_per_realm=1,
        towns_per_realm=3
    )

    # Step 4: Disasters (needs terrain)
    print("4. Generating disasters...")
    disaster_gen = disastergen.DisasterGenerator(
        seed=seeds['disasters'],
        years=years,
        count=disaster_count
    )
    disasters = disaster_gen.generate(terrain)

    # Step 5: Dynasties (needs realms)
    print("5. Generating dynasties...")
    dynasty_gen = dynastygen.DynastyGenerator(seed=seeds['dynasties'])
    dynasties = dynasty_gen.generate(realms, None)

    # Step 6: Pantheon (needs settlements)
    print("6. Creating pantheon...")
    pantheon_gen = pantheongen.PantheonGenerator(seed=seeds['pantheon'])
    pantheon = pantheon_gen.generate(settlements)

    # Merge all data
    world = {
        'schema': 'world.v1',
        'master_seed': master_seed,
        'component_seeds': seeds,
        'years_simulated': years,
        'width': terrain['width'],
        'height': terrain['height'],
        'generation_params': terrain['generation_params'],
        'tiles': terrain['tiles'],
        'rivers': terrain['rivers'],
        'features': terrain['features'],
        'realms': realms['realms'],
        'settlements': settlements['settlements'],
        'disasters': disasters['events'],
        'dynasties': dynasties['dynasties'],
        'pantheon': {
            'name': pantheon.get('pantheon_name', 'The Pantheon'),
            'deities': pantheon.get('deities', []),
            'myths': pantheon.get('myths', [])
        }
    }

    return world


def main():
    parser = argparse.ArgumentParser(
        description='Generate complete RPG world with geography, politics, history, and culture'
    )
    parser.add_argument('--width', type=int, default=60,
                       help='Map width')
    parser.add_argument('--height', type=int, default=50,
                       help='Map height')
    parser.add_argument('--seed', type=int, default=None,
                       help='Master seed for deterministic generation')
    parser.add_argument('--years', type=int, default=400,
                       help='Years of history to simulate')
    parser.add_argument('--disasters', type=int, default=20,
                       help='Number of disasters to generate')
    parser.add_argument('--output', type=str, required=True,
                       help='Output JSON file path')
    parser.add_argument('--ascii', action='store_true',
                       help='Display ASCII map preview')
    parser.add_argument('--ansi', action='store_true',
                       help='Display ANSI color map preview')
    
    args = parser.parse_args()
    
    # Generate master seed if not provided
    if args.seed is None:
        args.seed = random.randint(0, 999999)
    
    try:
        # Generate world
        world = generate_world(
            width=args.width,
            height=args.height,
            master_seed=args.seed,
            years=args.years,
            disaster_count=args.disasters
        )
        
        # Save to file
        with open(args.output, 'w') as f:
            json.dump(world, f, indent=2)
        
        print(f"\n✓ World saved to {args.output}")
        print(f"\nWorld Summary:")
        print(f"  Master Seed: {args.seed}")
        print(f"  Size: {args.width}x{args.height}")
        print(f"  Realms: {len(world.get('realms', []))}")
        print(f"  Settlements: {len(world.get('settlements', []))}")
        print(f"  Disasters: {len(world.get('disasters', []))}")
        print(f"  Dynasties: {len(world.get('dynasties', []))}")
        print(f"  Deities: {len(world.get('pantheon', {}).get('deities', []))}")
        
        # Display map if requested
        if args.ascii or args.ansi:
            print("\nMap Preview:")
            map_display = render_biome_map(
                world,
                use_color=args.ansi,
                legend=True
            )
            print(map_display)
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())