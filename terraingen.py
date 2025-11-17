#!/usr/bin/env python3
"""
Terrain Generator - Realistic procedural terrain generation
Generates elevation, moisture, rivers, and biomes for fantasy worlds
"""

import random
import json
import argparse
from dataclasses import dataclass, asdict
from typing import List, Tuple, Optional, Dict
from collections import deque


@dataclass
class Tile:
    """Single map tile"""
    x: int
    y: int
    elevation: float
    moisture: float
    biome: str
    water: bool
    river: bool = False
    river_size: int = 0
    terrain_feature: Optional[str] = None


@dataclass
class River:
    """River path from source to mouth"""
    id: str
    source: Tuple[int, int]
    mouth: Tuple[int, int]
    path: List[Tuple[int, int]]
    length: int


class SimplexNoise:
    """Simplified 2D simplex noise implementation"""
    
    def __init__(self, seed: int):
        self.seed = seed
        self.perm = list(range(256))
        random.Random(seed).shuffle(self.perm)
        self.perm = self.perm * 2
        
    def noise2d(self, x: float, y: float) -> float:
        """Generate 2D simplex noise value between -1 and 1"""
        # Simplified noise - using pseudo-random grid interpolation
        xi = int(x) & 255
        yi = int(y) & 255
        xf = x - int(x)
        yf = y - int(y)
        
        # Fade curves
        u = self._fade(xf)
        v = self._fade(yf)
        
        # Hash coordinates
        aa = self.perm[self.perm[xi] + yi]
        ab = self.perm[self.perm[xi] + yi + 1]
        ba = self.perm[self.perm[xi + 1] + yi]
        bb = self.perm[self.perm[xi + 1] + yi + 1]
        
        # Interpolate
        x1 = self._lerp(self._grad(aa, xf, yf), self._grad(ba, xf - 1, yf), u)
        x2 = self._lerp(self._grad(ab, xf, yf - 1), self._grad(bb, xf - 1, yf - 1), u)
        
        return self._lerp(x1, x2, v)
    
    def _fade(self, t: float) -> float:
        """Fade function for smooth interpolation"""
        return t * t * t * (t * (t * 6 - 15) + 10)
    
    def _lerp(self, a: float, b: float, t: float) -> float:
        """Linear interpolation"""
        return a + t * (b - a)
    
    def _grad(self, hash_val: int, x: float, y: float) -> float:
        """Gradient function"""
        h = hash_val & 3
        u = x if h < 2 else y
        v = y if h < 2 else x
        return (u if (h & 1) == 0 else -u) + (v if (h & 2) == 0 else -v)


class TerrainGenerator:
    """Generate realistic terrain with elevation, moisture, rivers, and biomes"""
    
    def __init__(
        self,
        width: int,
        height: int,
        seed: int,
        mode: str = 'continent',
        octaves: int = 5,
        persistence: float = 0.5,
        lacunarity: float = 2.0,
        scale: float = 100.0,
        river_count: int = 8,
        prevailing_wind: str = 'west'
    ):
        if width < 50 or height < 50:
            raise ValueError("Map size must be at least 50x50 for realistic noise generation")
        
        self.width = width
        self.height = height
        self.seed = seed
        self.mode = mode
        self.octaves = octaves
        self.persistence = persistence
        self.lacunarity = lacunarity
        self.scale = scale
        self.river_count = river_count
        self.prevailing_wind = prevailing_wind
        
        self.rng = random.Random(seed)
        self.noise = SimplexNoise(seed)
        self.tiles: List[List[Tile]] = []
        self.rivers: List[River] = []
        
    def generate(self) -> Dict:
        """Generate complete terrain"""
        print(f"Generating {self.width}x{self.height} terrain (seed: {self.seed})...")
        
        # Step 1: Generate elevation
        print("  - Generating elevation...")
        self._generate_elevation()
        
        # Step 2: Generate rivers
        print(f"  - Generating {self.river_count} rivers...")
        self._generate_rivers()
        
        # Step 3: Calculate moisture
        print("  - Calculating moisture...")
        self._calculate_moisture()
        
        # Step 4: Assign biomes
        print("  - Assigning biomes...")
        self._assign_biomes()
        
        # Step 5: Identify features
        print("  - Identifying terrain features...")
        features = self._identify_features()
        
        return self._to_dict(features)
    
    def _generate_elevation(self):
        """Generate elevation using multi-octave simplex noise with domain warping"""
        self.tiles = [[None for _ in range(self.width)] for _ in range(self.height)]
        
        # Generate base noise
        for y in range(self.height):
            for x in range(self.width):
                # Multi-octave noise
                elevation = 0.0
                amplitude = 1.0
                frequency = 1.0
                max_value = 0.0
                
                for _ in range(self.octaves):
                    sample_x = x / self.scale * frequency
                    sample_y = y / self.scale * frequency
                    
                    noise_val = self.noise.noise2d(sample_x, sample_y)
                    elevation += noise_val * amplitude
                    
                    max_value += amplitude
                    amplitude *= self.persistence
                    frequency *= self.lacunarity
                
                # Normalize to 0-1
                elevation = (elevation / max_value + 1) / 2
                
                # Domain warping for more organic look
                warp_x = x + self.noise.noise2d(x * 0.03, y * 0.03) * 10
                warp_y = y + self.noise.noise2d(x * 0.03 + 100, y * 0.03 + 100) * 10
                warp_sample_x = warp_x / self.scale
                warp_sample_y = warp_y / self.scale
                warp_noise = self.noise.noise2d(warp_sample_x, warp_sample_y)
                elevation = elevation * 0.6 + ((warp_noise + 1) / 2) * 0.4
                
                # Apply mode-specific shaping BEFORE clamping
                elevation = self._apply_mode_shaping(x, y, elevation)
                
                # Expand range to allow for full 0-1 span after shaping
                if self.mode != 'none':
                    # Boost and remap to ensure we can hit high values
                    elevation = elevation * 1.5
                
                # Clamp
                elevation = max(0.0, min(1.0, elevation))
                
                # Placeholder tile
                self.tiles[y][x] = Tile(
                    x=x,
                    y=y,
                    elevation=elevation,
                    moisture=0.0,
                    biome='',
                    water=elevation < 0.4
                )
    
    def _apply_mode_shaping(self, x: int, y: int, elevation: float) -> float:
        """Apply mode-specific shaping to elevation"""
        if self.mode == 'continent':
            # Radial falloff from center - gentler curve to preserve elevation range
            center_x = self.width / 2
            center_y = self.height / 2
            dx = (x - center_x) / (self.width * 0.8)  # Scale to allow center peaks
            dy = (y - center_y) / (self.height * 0.8)
            distance = (dx * dx + dy * dy) ** 0.5
            # Smoother falloff curve
            falloff = max(0, 1 - distance * distance * 0.8)
            # Blend with original elevation to preserve variation
            return elevation * 0.3 + (elevation * falloff) * 0.7
        
        elif self.mode == 'archipelago':
            # Multiple island centers with falloff
            island_count = 5 + self.rng.randint(0, 3)
            max_influence = 0.0
            for _ in range(island_count):
                island_x = self.rng.random() * self.width
                island_y = self.rng.random() * self.height
                dx = (x - island_x) / self.width
                dy = (y - island_y) / self.height
                distance = (dx * dx + dy * dy) ** 0.5
                influence = max(0, 1 - distance * 3)
                max_influence = max(max_influence, influence)
            return elevation * max_influence
        
        elif self.mode == 'highlands':
            # Elevated base with valleys
            base = 0.5
            return base + elevation * 0.5
        
        else:  # No shaping
            return elevation
    
    def _generate_rivers(self):
        """Generate rivers from high elevation to ocean"""
        # Find potential river sources (high elevation, not water)
        sources = []
        for y in range(self.height):
            for x in range(self.width):
                tile = self.tiles[y][x]
                if tile.elevation > 0.7 and not tile.water:
                    sources.append((x, y))
        
        # Select random sources
        if len(sources) < self.river_count:
            actual_river_count = len(sources)
        else:
            actual_river_count = self.river_count
        
        selected_sources = self.rng.sample(sources, actual_river_count)
        
        # Trace each river downhill
        for idx, (start_x, start_y) in enumerate(selected_sources):
            path = self._trace_river_path(start_x, start_y)
            if len(path) > 10:  # Only keep rivers that are long enough
                river = River(
                    id=f"river_{idx:03d}",
                    source=(start_x, start_y),
                    mouth=path[-1],
                    path=path,
                    length=len(path)
                )
                self.rivers.append(river)
                
                # Mark tiles as river
                for x, y in path:
                    self.tiles[y][x].river = True
    
    def _trace_river_path(self, start_x: int, start_y: int) -> List[Tuple[int, int]]:
        """Trace river path downhill from source"""
        path = [(start_x, start_y)]
        current_x, current_y = start_x, start_y
        visited = set(path)
        
        max_iterations = self.width * self.height
        iterations = 0
        
        while iterations < max_iterations:
            iterations += 1
            current_tile = self.tiles[current_y][current_x]
            
            # Stop if we hit water
            if current_tile.water:
                break
            
            # Find lowest neighbor
            neighbors = self._get_neighbors(current_x, current_y)
            lowest = None
            lowest_elevation = current_tile.elevation
            
            for nx, ny in neighbors:
                if (nx, ny) in visited:
                    continue
                neighbor_tile = self.tiles[ny][nx]
                if neighbor_tile.elevation < lowest_elevation:
                    lowest_elevation = neighbor_tile.elevation
                    lowest = (nx, ny)
            
            # No lower neighbor found, stop
            if lowest is None:
                break
            
            current_x, current_y = lowest
            path.append(lowest)
            visited.add(lowest)
        
        return path
    
    def _get_neighbors(self, x: int, y: int) -> List[Tuple[int, int]]:
        """Get valid neighbor coordinates (4-directional)"""
        neighbors = []
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                neighbors.append((nx, ny))
        return neighbors
    
    def _calculate_moisture(self):
        """Calculate moisture based on water proximity, elevation, and rain shadows"""
        for y in range(self.height):
            for x in range(self.width):
                tile = self.tiles[y][x]
                
                # Base: Distance from water (ocean or river)
                water_distance = self._distance_to_water(x, y)
                water_moisture = max(0, 1 - water_distance / 30)
                
                # Modifier: Elevation (orographic lift - mountains are wetter initially)
                elevation_moisture = tile.elevation * 0.3
                
                # Modifier: Rain shadow
                rain_shadow = self._calculate_rain_shadow(x, y)
                
                # Combine
                moisture = water_moisture + elevation_moisture - rain_shadow
                moisture = max(0.0, min(1.0, moisture))
                
                tile.moisture = moisture
    
    def _distance_to_water(self, x: int, y: int) -> float:
        """Calculate Manhattan distance to nearest water or river"""
        min_distance = float('inf')
        
        # Check nearby tiles (optimization: don't check entire map)
        search_radius = 40
        for dy in range(-search_radius, search_radius + 1):
            for dx in range(-search_radius, search_radius + 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    tile = self.tiles[ny][nx]
                    if tile.water or tile.river:
                        distance = abs(dx) + abs(dy)
                        min_distance = min(min_distance, distance)
        
        return min_distance if min_distance != float('inf') else search_radius
    
    def _calculate_rain_shadow(self, x: int, y: int) -> float:
        """Calculate rain shadow effect from mountains blocking prevailing wind"""
        wind_direction = {'west': (-1, 0), 'east': (1, 0), 'north': (0, -1), 'south': (0, 1)}
        dx, dy = wind_direction.get(self.prevailing_wind, (-1, 0))
        
        # Check if there's a mountain range upwind
        check_distance = 15
        max_blocking = 0.0
        
        for i in range(1, check_distance):
            check_x = x + dx * i
            check_y = y + dy * i
            
            if 0 <= check_x < self.width and 0 <= check_y < self.height:
                tile = self.tiles[check_y][check_x]
                if tile.elevation > 0.7:  # Mountain
                    blocking = (tile.elevation - 0.7) * 0.5
                    max_blocking = max(max_blocking, blocking)
        
        return max_blocking
    
    def _assign_biomes(self):
        """Assign biomes based on elevation and moisture"""
        biome_rules = self._load_biome_rules()
        
        for y in range(self.height):
            for x in range(self.width):
                tile = self.tiles[y][x]
                
                # Determine biome
                tile.biome = self._determine_biome(tile.elevation, tile.moisture, biome_rules)
    
    def _load_biome_rules(self) -> Dict:
        """Load or define biome assignment rules"""
        return {
            'deep_ocean': {'elevation': [0.0, 0.3]},
            'ocean': {'elevation': [0.3, 0.38]},
            'beach': {'elevation': [0.38, 0.42]},
            'desert': {'elevation': [0.42, 0.7], 'moisture': [0.0, 0.25]},
            'grassland': {'elevation': [0.42, 0.7], 'moisture': [0.25, 0.6]},
            'temperate_forest': {'elevation': [0.42, 0.7], 'moisture': [0.6, 1.0]},
            'wetlands': {'elevation': [0.42, 0.5], 'moisture': [0.7, 1.0]},
            'highland': {'elevation': [0.7, 0.78]},
            'mountain': {'elevation': [0.78, 1.0]}
        }
    
    def _determine_biome(self, elevation: float, moisture: float, rules: Dict) -> str:
        """Determine biome from elevation and moisture"""
        # Check rules in priority order
        priority = ['deep_ocean', 'ocean', 'beach', 'mountain', 'highland', 
                   'wetlands', 'temperate_forest', 'grassland', 'desert']
        
        for biome in priority:
            rule = rules[biome]
            elev_range = rule.get('elevation', [0, 1])
            moist_range = rule.get('moisture', [0, 1])
            
            if (elev_range[0] <= elevation < elev_range[1] and
                moist_range[0] <= moisture <= moist_range[1]):
                return biome
        
        return 'grassland'  # Default
    
    def _identify_features(self) -> Dict:
        """Identify notable terrain features"""
        features = {
            'mountain_ranges': [],
            'lakes': []
        }
        
        # Find mountain ranges (clusters of mountain tiles)
        # Simplified for now - just find high elevation clusters
        
        return features
    
    def _to_dict(self, features: Dict) -> Dict:
        """Convert terrain to dictionary for JSON export"""
        tiles_list = []
        for y in range(self.height):
            for x in range(self.width):
                tile = self.tiles[y][x]
                tiles_list.append({
                    'x': tile.x,
                    'y': tile.y,
                    'elevation': round(tile.elevation, 3),
                    'moisture': round(tile.moisture, 3),
                    'biome': tile.biome,
                    'water': tile.water,
                    'river': tile.river
                })
        
        rivers_list = []
        for river in self.rivers:
            rivers_list.append({
                'id': river.id,
                'source': list(river.source),
                'mouth': list(river.mouth),
                'length': river.length
            })
        
        return {
            'schema': 'terrain.v1',
            'seed': self.seed,
            'width': self.width,
            'height': self.height,
            'mode': self.mode,
            'generation_params': {
                'octaves': self.octaves,
                'persistence': self.persistence,
                'lacunarity': self.lacunarity,
                'scale': self.scale,
                'river_count': self.river_count,
                'prevailing_wind': self.prevailing_wind
            },
            'tiles': tiles_list,
            'rivers': rivers_list,
            'features': features
        }
    
    def get_average_elevation(self) -> float:
        """Calculate average elevation of land tiles"""
        land_tiles = [tile for row in self.tiles for tile in row if not tile.water]
        if not land_tiles:
            return 0.0
        return sum(tile.elevation for tile in land_tiles) / len(land_tiles)


def generate_ascii_map(terrain: Dict) -> str:
    """Generate ASCII representation of terrain"""
    width = terrain['width']
    height = terrain['height']
    
    # Create 2D array
    grid = [['?' for _ in range(width)] for _ in range(height)]
    
    for tile in terrain['tiles']:
        x, y = tile['x'], tile['y']
        biome = tile['biome']
        
        char = '?'
        if tile['water']:
            char = '~'
        elif tile['river']:
            char = 'â‰ˆ'
        elif biome == 'mountain':
            char = '^'
        elif biome == 'highland':
            char = 'n'
        elif biome == 'temperate_forest':
            char = 'â™£'
        elif biome == 'grassland':
            char = '.'
        elif biome == 'desert':
            char = 'Ã·'
        elif biome == 'beach':
            char = 'Â·'
        elif biome == 'wetlands':
            char = 'â‰‹'
        
        grid[y][x] = char
    
    return '\n'.join(''.join(row) for row in grid)


def main():
    parser = argparse.ArgumentParser(
        description='Generate realistic procedural terrain for fantasy worlds'
    )
    parser.add_argument('--width', type=int, default=80,
                       help='Map width (minimum 50)')
    parser.add_argument('--height', type=int, default=60,
                       help='Map height (minimum 50)')
    parser.add_argument('--seed', type=int, default=None,
                       help='Random seed for deterministic generation')
    parser.add_argument('--mode', choices=['continent', 'archipelago', 'highlands', 'none'],
                       default='continent', help='Generation mode')
    parser.add_argument('--octaves', type=int, default=5,
                       help='Noise octaves (detail level)')
    parser.add_argument('--scale', type=float, default=100.0,
                       help='Noise scale (larger = broader features)')
    parser.add_argument('--rivers', type=int, default=8,
                       help='Number of rivers to generate')
    parser.add_argument('--wind', choices=['west', 'east', 'north', 'south'],
                       default='west', help='Prevailing wind direction')
    parser.add_argument('--output', type=str, required=True,
                       help='Output JSON file path')
    parser.add_argument('--ascii', action='store_true',
                       help='Print ASCII map preview')
    
    args = parser.parse_args()
    
    # Generate seed if not provided
    if args.seed is None:
        args.seed = random.randint(0, 999999)
    
    # Generate terrain
    try:
        generator = TerrainGenerator(
            width=args.width,
            height=args.height,
            seed=args.seed,
            mode=args.mode,
            octaves=args.octaves,
            scale=args.scale,
            river_count=args.rivers,
            prevailing_wind=args.wind
        )
        
        terrain = generator.generate()
        
        # Save to file
        with open(args.output, 'w') as f:
            json.dump(terrain, f, indent=2)
        
        print(f"\nâœ“ Terrain saved to {args.output}")
        print(f"  Seed: {args.seed}")
        print(f"  Size: {args.width}x{args.height}")
        print(f"  Rivers: {len(terrain['rivers'])}")
        print(f"  Average land elevation: {generator.get_average_elevation():.3f}")
        
        if args.ascii:
            print(f"\nASCII Preview:")
            print(generate_ascii_map(terrain))
    
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())