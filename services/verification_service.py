# services/verification_service.py
from typing import Dict, Optional
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from models.vehicle import Vehicle
from services.blockchain_service import BlockchainService
from services.did_services import DIDService

class VehicleVerificationService:
    def __init__(self, blockchain_service: BlockchainService, did_service: DIDService):
        self.blockchain_service = blockchain_service
        self.did_service = did_service

    def generate_verification_challenge(self, vehicle: Vehicle) -> str:
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        challenge = private_key.sign(
            vehicle.vin.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return challenge.hex()

    def verify_vehicle(self, vehicle: Vehicle, verification_data: Dict) -> bool:
        blockchain_verified = self.blockchain_service.verify_vehicle(vehicle.vin)
        did_verified = self.did_service.verify_vehicle_did(vehicle.entity_did)
        credential_verified = self._validate_credential(vehicle)
        maintenance_check = self._check_maintenance_history(vehicle)

        return (
            blockchain_verified and 
            did_verified and 
            credential_verified and 
            maintenance_check
        )

    def _validate_credential(self, vehicle: Vehicle) -> bool:
        credential = self.did_service.verify_credential(vehicle.credential_id)
        if not credential:
            return False
        return (
            credential.get('credentialSubject', {}).get('vin') == vehicle.vin and
            credential.get('credentialSubject', {}).get('type') == 'VehicleRegistrationCredential'
        )

    def _check_maintenance_history(self, vehicle: Vehicle) -> bool:
        # Implement maintenance history check logic
        # For now, return True as a placeholder
        return True

    def generate_vehicle_passport(self, vehicle: Vehicle) -> Dict:
        return {
            "vehicle_id": vehicle.id,
            "vin": vehicle.vin,
            "verification_status": self.verify_vehicle(vehicle, {}),
            "maintenance_records": vehicle.get_maintenance_records(),
        }