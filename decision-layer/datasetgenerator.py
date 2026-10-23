import json
import uuid
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum

class RequestType(Enum):
    LEGITIMATE = "legitimate"
    EMERGENCY = "emergency"
    POLICY_VIOLATION = "policy_violation"
    INSIDER_ATTACK = "insider_attack"
    UNAUTHORIZED = "unauthorized"

class SensorData:
    """Simulates vehicle sensor data"""
    @staticmethod
    def normal_data():
        return {
            "speed": random.randint(20, 80),
            "location": {"latitude": 34.0522, "longitude": -118.2437},
            "temperature": random.randint(80, 95),
            "fuel": f"{random.randint(30, 90)}%",
            "battery": f"{random.randint(60, 95)}%",
            "brake_status": "functional",
            "tire_pressure": [32, 32, 31, 33],
            "engine_rpm": random.randint(1000, 3000),
            "airbag_status": "not_deployed",
            "collision_detected": False,
            "acceleration": {"x": 0.5, "y": 0.2, "z": 9.8}
        }
    
    @staticmethod
    def accident_data():
        return {
            "speed": 0,
            "location": {"latitude": 34.0522, "longitude": -118.2437},
            "temperature": random.randint(100, 120),
            "fuel": f"{random.randint(10, 40)}%",
            "battery": f"{random.randint(20, 60)}%",
            "brake_status": "emergency_engaged",
            "tire_pressure": [28, 0, 30, 32],  # Flat tire
            "engine_rpm": 0,
            "airbag_status": "deployed",
            "collision_detected": True,
            "acceleration": {"x": -15.5, "y": -2.3, "z": 8.2},
            "impact_force": 8.5,
            "emergency_alert": True
        }

@dataclass
class TestScenario:
    scenario_id: int
    scenario_type: str
    sender_type: str
    sender_did: str
    recipient_type: str
    recipient_did: str
    requested_data: List[str]
    is_emergency: bool
    has_consent: bool
    policy_allows: bool
    sensor_data: Dict[str, Any]
    context: str
    expected_decision: str  # "approve" or "deny"
    expected_reason: str
    timestamp: str
    
    def to_dict(self):
        return asdict(self)

class AdvancedDatasetGenerator:
    def __init__(self):
        self.scenarios = []
        self.entity_types = {
            "INDIVIDUAL": ["did:ssi:individual:user1", "did:ssi:individual:user2"],
            "MECHANIC": ["did:ssi:mechanic:shop1", "did:ssi:mechanic:shop2"],
            "INSURANCE_PROVIDER": ["did:ssi:insurance:company1"],
            "EMERGENCY_SERVICE": ["did:ssi:emergency:911", "did:ssi:emergency:ambulance"],
            "ROADSIDE_UNIT": ["did:ssi:rsu:highway1", "did:ssi:rsu:city1"],
            "CAR": ["did:ssi:car:vehicle1", "did:ssi:car:vehicle2"]
        }
        
        # Define consent matrix
        self.consent_matrix = {
            "MECHANIC": {
                "allowed_data": ["battery", "fuel", "tire_pressure", "brake_status", "temperature"],
                "forbidden_data": ["location", "speed", "user_behavior", "trip_history"]
            },
            "INSURANCE_PROVIDER": {
                "allowed_data": ["speed", "trip_history", "mileage"],
                "forbidden_data": ["location", "user_behavior", "real_time_tracking"]
            },
            "EMERGENCY_SERVICE": {
                "allowed_data": ["location", "speed", "sensor_data", "collision_data"],
                "forbidden_data": []
            }
        }

    def generate_legitimate_request(self, scenario_id: int) -> TestScenario:
        """Generate legitimate requests where policy allows and requester has consent"""
        sender_type = random.choice(["MECHANIC", "INSURANCE_PROVIDER"])
        allowed_data = self.consent_matrix[sender_type]["allowed_data"]
        
        return TestScenario(
            scenario_id=scenario_id,
            scenario_type=RequestType.LEGITIMATE.value,
            sender_type=sender_type,
            sender_did=random.choice(self.entity_types[sender_type]),
            recipient_type="INDIVIDUAL",
            recipient_did=random.choice(self.entity_types["INDIVIDUAL"]),
            requested_data=[random.choice(allowed_data)],
            is_emergency=False,
            has_consent=True,
            policy_allows=True,
            sensor_data=SensorData.normal_data(),
            context=f"{sender_type} requesting authorized data for legitimate service",
            expected_decision="approve",
            expected_reason=f"Request from authorized {sender_type} with valid consent for the requested data type",
            timestamp=datetime.now().isoformat()
        )

    def generate_emergency_request(self, scenario_id: int) -> TestScenario:
        """Generate emergency requests where policy should be overridden"""
        return TestScenario(
            scenario_id=scenario_id,
            scenario_type=RequestType.EMERGENCY.value,
            sender_type="EMERGENCY_SERVICE",
            sender_did=random.choice(self.entity_types["EMERGENCY_SERVICE"]),
            recipient_type="INDIVIDUAL",
            recipient_did=random.choice(self.entity_types["INDIVIDUAL"]),
            requested_data=["location", "sensor_data", "collision_data"],
            is_emergency=True,
            has_consent=False,
            policy_allows=False,
            sensor_data=SensorData.accident_data(),
            context="Vehicle collision detected, emergency services requesting critical data",
            expected_decision="approve",
            expected_reason="Emergency override: Accident detected with airbag deployment and collision sensors triggered. Policy override justified to save lives.",
            timestamp=datetime.now().isoformat()
        )

    def generate_insider_attack(self, scenario_id: int) -> TestScenario:
        """Generate insider attack where authorized entity requests unauthorized data"""
        sender_type = random.choice(["MECHANIC", "INSURANCE_PROVIDER"])
        forbidden_data = self.consent_matrix[sender_type]["forbidden_data"]
        
        return TestScenario(
            scenario_id=scenario_id,
            scenario_type=RequestType.INSIDER_ATTACK.value,
            sender_type=sender_type,
            sender_did=random.choice(self.entity_types[sender_type]),
            recipient_type="INDIVIDUAL",
            recipient_did=random.choice(self.entity_types["INDIVIDUAL"]),
            requested_data=[random.choice(forbidden_data)],
            is_emergency=False,
            has_consent=True,  # Has consent for their role, but not for this data
            policy_allows=False,
            sensor_data=SensorData.normal_data(),
            context=f"{sender_type} attempting to access data outside their authorized scope during service",
            expected_decision="deny",
            expected_reason=f"Insider attack detected: {sender_type} has valid credentials but is requesting data ({forbidden_data[0]}) outside their authorized scope. This violates the principle of minimal necessary disclosure.",
            timestamp=datetime.now().isoformat()
        )

    def generate_policy_violation(self, scenario_id: int) -> TestScenario:
        """Generate requests that violate policy without emergency justification"""
        sender_type = random.choice(["INDIVIDUAL", "CAR"])
        
        return TestScenario(
            scenario_id=scenario_id,
            scenario_type=RequestType.POLICY_VIOLATION.value,
            sender_type=sender_type,
            sender_did=random.choice(self.entity_types[sender_type]),
            recipient_type="INDIVIDUAL",
            recipient_did=random.choice(self.entity_types["INDIVIDUAL"]),
            requested_data=["location", "speed", "user_behavior"],
            is_emergency=False,
            has_consent=False,
            policy_allows=False,
            sensor_data=SensorData.normal_data(),
            context=f"Unauthorized {sender_type} requesting sensitive data without consent or justification",
            expected_decision="deny",
            expected_reason=f"Request denied: {sender_type} lacks authorization and consent for sensitive data. No emergency justification provided.",
            timestamp=datetime.now().isoformat()
        )

    def generate_false_emergency(self, scenario_id: int) -> TestScenario:
        """Generate false emergency claims (no actual accident in sensor data)"""
        return TestScenario(
            scenario_id=scenario_id,
            scenario_type=RequestType.POLICY_VIOLATION.value,
            sender_type="INSURANCE_PROVIDER",
            sender_did=random.choice(self.entity_types["INSURANCE_PROVIDER"]),
            recipient_type="INDIVIDUAL",
            recipient_did=random.choice(self.entity_types["INDIVIDUAL"]),
            requested_data=["location", "sensor_data"],
            is_emergency=True,  # Claims emergency
            has_consent=False,
            policy_allows=False,
            sensor_data=SensorData.normal_data(),  # But no accident detected
            context="Insurance provider claiming emergency but sensor data shows normal operation",
            expected_decision="deny",
            expected_reason="False emergency claim detected: Request marked as emergency but sensor data shows no collision, normal airbag status, and normal vehicle operation. Potential fraudulent access attempt.",
            timestamp=datetime.now().isoformat()
        )

    def generate_mechanic_scope_creep(self, scenario_id: int) -> TestScenario:
        """Mechanic with battery consent trying to access location during repair"""
        return TestScenario(
            scenario_id=scenario_id,
            scenario_type=RequestType.INSIDER_ATTACK.value,
            sender_type="MECHANIC",
            sender_did=random.choice(self.entity_types["MECHANIC"]),
            recipient_type="INDIVIDUAL",
            recipient_did=random.choice(self.entity_types["INDIVIDUAL"]),
            requested_data=["location", "user_behavior", "trip_history"],
            is_emergency=False,
            has_consent=True,  # Has consent for mechanical repairs
            policy_allows=False,
            sensor_data=SensorData.normal_data(),
            context="Mechanic repairing battery but requesting location and behavioral data",
            expected_decision="deny",
            expected_reason="Scope creep attack: Mechanic has valid consent for battery repair but is requesting location, user behavior, and trip history which are outside repair scope. This violates selective disclosure and represents potential surveillance or data harvesting.",
            timestamp=datetime.now().isoformat()
        )

    def generate_dataset(self, num_scenarios: int = 100) -> List[Dict]:
        """Generate balanced dataset with various scenario types"""
        self.scenarios = []
        
        # Distribution of scenario types
        distribution = {
            "legitimate": int(num_scenarios * 0.30),
            "emergency": int(num_scenarios * 0.15),
            "insider_attack": int(num_scenarios * 0.25),
            "policy_violation": int(num_scenarios * 0.20),
            "false_emergency": int(num_scenarios * 0.10)
        }
        
        scenario_id = 1
        
        # Generate legitimate requests
        for _ in range(distribution["legitimate"]):
            self.scenarios.append(self.generate_legitimate_request(scenario_id))
            scenario_id += 1
        
        # Generate emergency requests
        for _ in range(distribution["emergency"]):
            self.scenarios.append(self.generate_emergency_request(scenario_id))
            scenario_id += 1
        
        # Generate insider attacks
        for _ in range(distribution["insider_attack"]):
            if random.random() < 0.5:
                self.scenarios.append(self.generate_insider_attack(scenario_id))
            else:
                self.scenarios.append(self.generate_mechanic_scope_creep(scenario_id))
            scenario_id += 1
        
        # Generate policy violations
        for _ in range(distribution["policy_violation"]):
            self.scenarios.append(self.generate_policy_violation(scenario_id))
            scenario_id += 1
        
        # Generate false emergencies
        for _ in range(distribution["false_emergency"]):
            self.scenarios.append(self.generate_false_emergency(scenario_id))
            scenario_id += 1
        
        # Shuffle scenarios
        random.shuffle(self.scenarios)
        
        return [s.to_dict() for s in self.scenarios]

    def save_dataset(self, filename: str = "ssi_iov_test_dataset.json"):
        """Save dataset to JSON file"""
        dataset = {
            "metadata": {
                "total_scenarios": len(self.scenarios),
                "generation_timestamp": datetime.now().isoformat(),
                "scenario_distribution": self._get_distribution(),
                "expected_metrics": self._calculate_expected_metrics()
            },
            "scenarios": [s.to_dict() for s in self.scenarios]
        }
        
        with open(filename, 'w') as f:
            json.dump(dataset, f, indent=2)
        
        print(f"\n{'='*60}")
        print(f"Dataset Generated: {filename}")
        print(f"{'='*60}")
        print(f"Total Scenarios: {len(self.scenarios)}")
        print("\nScenario Distribution:")
        for scenario_type, count in self._get_distribution().items():
            print(f"  {scenario_type}: {count}")
        print("\nExpected Metrics:")
        metrics = self._calculate_expected_metrics()
        for metric, value in metrics.items():
            print(f"  {metric}: {value}")
        print(f"{'='*60}\n")
        
        return dataset

    def _get_distribution(self) -> Dict[str, int]:
        """Calculate distribution of scenario types"""
        distribution = {}
        for scenario in self.scenarios:
            scenario_type = scenario.scenario_type
            distribution[scenario_type] = distribution.get(scenario_type, 0) + 1
        return distribution

    def _calculate_expected_metrics(self) -> Dict[str, Any]:
        """Calculate expected evaluation metrics"""
        total = len(self.scenarios)
        expected_approvals = sum(1 for s in self.scenarios if s.expected_decision == "approve")
        expected_denials = total - expected_approvals
        emergency_overrides = sum(1 for s in self.scenarios if s.is_emergency and s.expected_decision == "approve")
        insider_attacks = sum(1 for s in self.scenarios if s.scenario_type == RequestType.INSIDER_ATTACK.value)
        
        return {
            "expected_approval_rate": f"{(expected_approvals/total)*100:.1f}%",
            "expected_denial_rate": f"{(expected_denials/total)*100:.1f}%",
            "expected_emergency_overrides": emergency_overrides,
            "expected_insider_attack_detections": insider_attacks,
            "expected_policy_compliance_rate": f"{((total - insider_attacks)/total)*100:.1f}%"
        }

def main():
    """Generate and save the test dataset"""
    generator = AdvancedDatasetGenerator()
    
    # Generate dataset with 100 scenarios
    generator.generate_dataset(num_scenarios=100)
    
    # Save to file
    dataset = generator.save_dataset("ssi_iov_test_dataset.json")
    
    # Print sample scenarios
    print("\nSample Scenarios:")
    print("="*60)
    for i, scenario in enumerate(dataset["scenarios"][:3], 1):
        print(f"\nScenario {i}:")
        print(f"  Type: {scenario['scenario_type']}")
        print(f"  Sender: {scenario['sender_type']}")
        print(f"  Requested: {scenario['requested_data']}")
        print(f"  Emergency: {scenario['is_emergency']}")
        print(f"  Expected: {scenario['expected_decision']}")
        print(f"  Reason: {scenario['expected_reason'][:100]}...")

if __name__ == "__main__":
    main()