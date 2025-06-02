import time
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
import random
import math

@dataclass
class Position:
    x: float
    y: float

@dataclass
class Entity:
    did: str
    type: str
    position: Position
    data: Dict[str, Any]

class SimulationService:
    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.road_length = 800  # pixels
        self.interaction_radius = 100  # pixels

    def add_entity(self, did: str, entity_type: str, position: Position, data: Dict[str, Any] = None):
        """Add an entity to the simulation."""
        self.entities[did] = Entity(
            did=did,
            type=entity_type,
            position=position,
            data=data or {}
        )

    def update_position(self, did: str, new_position: Position):
        """Update an entity's position."""
        if did in self.entities:
            self.entities[did].position = new_position

    def get_nearby_entities(self, did: str) -> List[Entity]:
        """Get entities within interaction radius."""
        if did not in self.entities:
            return []

        entity = self.entities[did]
        nearby = []

        for other_did, other in self.entities.items():
            if other_did != did:
                distance = self._calculate_distance(entity.position, other.position)
                if distance <= self.interaction_radius:
                    nearby.append(other)

        return nearby

    def _calculate_distance(self, pos1: Position, pos2: Position) -> float:
        """Calculate distance between two positions."""
        return math.sqrt((pos1.x - pos2.x)**2 + (pos1.y - pos2.y)**2)

    def generate_sensor_data(self, entity_type: str) -> Dict[str, Any]:
        """Generate simulated sensor data based on entity type."""
        if entity_type == "Vehicle":
            return {
                "speed": random.uniform(0, 120),  # km/h
                "heading": random.uniform(0, 360),  # degrees
                "acceleration": random.uniform(-5, 5),  # m/s^2
                "temperature": random.uniform(15, 35),  # Celsius
                "fuel_level": random.uniform(0, 100),  # percentage
                "tire_pressure": {
                    f"tire_{i}": random.uniform(28, 35) for i in range(4)
                }
            }
        elif entity_type == "Roadside Unit":
            return {
                "traffic_density": random.uniform(0, 1),
                "weather": {
                    "temperature": random.uniform(15, 35),
                    "humidity": random.uniform(30, 90),
                    "precipitation": random.uniform(0, 100)
                },
                "road_condition": random.choice([
                    "clear", "wet", "icy", "snow-covered"
                ])
            }
        return {}

    def simulate_movement(self, did: str, speed: float = 1.0) -> Position:
        """Simulate entity movement along the road."""
        if did not in self.entities:
            return None

        entity = self.entities[did]
        new_x = (entity.position.x + speed) % self.road_length
        new_position = Position(new_x, entity.position.y)
        self.update_position(did, new_position)
        return new_position

    def get_entity_status(self, did: str) -> Dict[str, Any]:
        """Get current status of an entity."""
        if did not in self.entities:
            return None

        entity = self.entities[did]
        nearby = self.get_nearby_entities(did)
        
        return {
            "position": {
                "x": entity.position.x,
                "y": entity.position.y
            },
            "type": entity.type,
            "data": entity.data,
            "nearby_entities": [
                {
                    "did": e.did,
                    "type": e.type,
                    "distance": self._calculate_distance(entity.position, e.position)
                }
                for e in nearby
            ]
        }

    def reset_simulation(self):
        """Reset the simulation state."""
        self.entities.clear()
