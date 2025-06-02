import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class CarData:
    speed: float
    location: tuple
    fuel_level: float
    engine_temp: float
    tire_pressure: Dict[str, float]
    maintenance_needed: bool
    last_service_date: str
    total_mileage: float

class SmartCarSimulator:
    def __init__(self):
        self.cars: Dict[str, CarData] = {}
        self.running = False
    
    def add_car(self, car_id: str) -> None:
        """Add a new car to the simulation."""
        self.cars[car_id] = CarData(
            speed=0.0,
            location=(0.0, 0.0),
            fuel_level=100.0,
            engine_temp=90.0,
            tire_pressure={
                'front_left': 32.0,
                'front_right': 32.0,
                'rear_left': 32.0,
                'rear_right': 32.0
            },
            maintenance_needed=False,
            last_service_date='2024-01-01',
            total_mileage=0.0
        )
    
    def remove_car(self, car_id: str) -> None:
        """Remove a car from the simulation."""
        if car_id in self.cars:
            del self.cars[car_id]
    
    def get_car_data(self, car_id: str) -> Optional[CarData]:
        """Get current data for a specific car."""
        return self.cars.get(car_id)
    
    def update_car_data(self, car_id: str) -> None:
        """Update simulation data for a specific car."""
        if car_id not in self.cars:
            return
            
        car = self.cars[car_id]
        
        # Simulate speed changes
        car.speed += random.uniform(-5.0, 5.0)
        car.speed = max(0.0, min(120.0, car.speed))
        
        # Update location based on speed
        dx = random.uniform(-0.001, 0.001) * car.speed
        dy = random.uniform(-0.001, 0.001) * car.speed
        car.location = (
            car.location[0] + dx,
            car.location[1] + dy
        )
        
        # Decrease fuel level
        car.fuel_level -= random.uniform(0.0, 0.1)
        car.fuel_level = max(0.0, car.fuel_level)
        
        # Update engine temperature
        car.engine_temp += random.uniform(-1.0, 1.0)
        car.engine_temp = max(80.0, min(110.0, car.engine_temp))
        
        # Update tire pressure
        for tire in car.tire_pressure:
            car.tire_pressure[tire] += random.uniform(-0.1, 0.1)
            car.tire_pressure[tire] = max(25.0, min(35.0, car.tire_pressure[tire]))
        
        # Update mileage
        car.total_mileage += car.speed * 0.001  # Simplified mileage calculation
        
        # Check if maintenance is needed
        if car.total_mileage > 5000 and not car.maintenance_needed:
            car.maintenance_needed = True
    
    def start_simulation(self) -> None:
        """Start the simulation."""
        self.running = True
    
    def stop_simulation(self) -> None:
        """Stop the simulation."""
        self.running = False
    
    def is_running(self) -> bool:
        """Check if simulation is running."""
        return self.running
