import hashlib
import base64
import json
import uuid
import os
from datetime import datetime
from typing import Dict, Optional, Tuple, List
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from services.blockchain_service import BlockchainService, UserType
from services.address_manager import AddressManager

class DIDDocument:
    def __init__(self, did: str, public_key: bytes, created: datetime = None):
        self.did = did
        self.info = []
        self.public_key = public_key
        self.created = created or datetime.utcnow()
        self.authentication = []
        self.service_endpoints = []
        self.type = []
        self.controller = None
        self.verificationMethod = []
        self.credentials = []

    def to_dict(self) -> Dict:
        """Convert DID Document to dictionary format following W3C spec"""
        # Create the verification method for the public key
        key_id = f"{self.did}#keys-1"
        verification_method = {
            "id": key_id,
            "type": "RsaVerificationKey2018",
            "controller": self.did,
            "publicKeyPem": self.public_key.decode('utf-8')
        }
        
        # Base DID Document structure
        doc = {
            "@context": [
                "https://www.w3.org/2018/credentials/v1",
                "https://www.w3.org/ns/did/v1",
                "https://w3id.org/security/v1"
            ],
            "id": self.did,
            "type":self.type,
            "info": self.info,
            "created": self.created.isoformat(),
            "verificationMethod": [verification_method],
            "authentication": [key_id],
            "assertionMethod": [key_id],
            "credentials": self.credentials,
            "service": self.service_endpoints
        }
        
        # Add controller if present
        if self.controller:
            doc["controller"] = self.controller
            
        return doc

class DIDWallet:
    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or "did_wallet"
        os.makedirs(self.storage_path, exist_ok=True)

    def store_keys(self, did: str, private_key: bytes, public_key: bytes):
        """Store keys securely"""
        did_folder = os.path.join(self.storage_path, did.replace(":", "_"))
        os.makedirs(did_folder, exist_ok=True)

        # Store private key (in practice, this should be encrypted)
        with open(os.path.join(did_folder, "private.pem"), "wb") as f:
            f.write(private_key)

        # Store public key
        with open(os.path.join(did_folder, "public.pem"), "wb") as f:
            f.write(public_key)

    def get_keys(self, did: str) -> Tuple[bytes, bytes]:
        """Retrieve keys for a DID"""
        did_folder = os.path.join(self.storage_path, did.replace(":", "_"))
        
        with open(os.path.join(did_folder, "private.pem"), "rb") as f:
            private_key = f.read()
        
        with open(os.path.join(did_folder, "public.pem"), "rb") as f:
            public_key = f.read()
        
        return private_key, public_key

class DIDService:
    DID_METHOD = "ssi"
    
    def __init__(self, blockchain_service: BlockchainService = None):
        self.blockchain_service = blockchain_service or BlockchainService()
        self.address_manager = AddressManager(blockchain_service=self.blockchain_service)
        self.wallet = DIDWallet()

    def _generate_key_pair(self) -> Tuple[bytes, bytes]:
        """Generate RSA key pair"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return private_pem, public_pem


    def create_user_dids(self):
        """
        Create both entity and wallet DIDs for a user
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Tuple[str, str]: (entity_did, wallet_did)
        """
        try:
            # Generate UUIDs for both DIDs
            entity_uuid = str(uuid.uuid4())
            wallet_uuid = str(uuid.uuid4())
            
            # Create DIDs
            entity_did = f"did:{self.DID_METHOD}:entity:{entity_uuid}"
            wallet_did = f"did:{self.DID_METHOD}:wallet:{wallet_uuid}"

            print(f"Created entity DID: {entity_did}")
            print(f"Created wallet DID: {wallet_did}")
            
            return entity_did, wallet_did
            
        except Exception as e:
            print(f"Error creating user DIDs: {e}")
            return None, None

    def get_user_vehicles(self, did: str) -> List[Dict]:
        """Get all vehicles owned by a user."""
        try:
            vehicle_doc = self.blockchain_service.get_did_document(did)
            detailed_vehicles = []
            if vehicle_doc:
                if isinstance(vehicle_doc, str):
                    vehicle_doc = json.loads(vehicle_doc)

                # Get vehicle info from the vehicle's DID document
                vehicle_info = None
                for info in vehicle_doc.get('info', []):
                    # Assuming you want to match by owner_did and some vehicle id
                        vehicle_info = info
                        break
                print(f"info od fhrbtrw snd sm: {vehicle_info}")
                if vehicle_info:
                    detailed_vehicles.append({
                        'name': f"{vehicle_info.get('make', '')} {vehicle_info.get('model', '')}",
                        'did': vehicle_doc.get('id'),  # Assuming this is the vehicle DID
                        'wallet_did': vehicle_info.get('wallet_did', ''),  # Ensure wallet_did is accessible
                        'vin': vehicle_info.get('vin',''),
                        'make': vehicle_info.get('make',''),
                        'model': vehicle_info.get('model',''),
                        'year': vehicle_info.get('year',''),
                        'color': vehicle_info.get('color',''),
                        'status': vehicle_info.get('status',''),
                        'owner_did': vehicle_info.get('owner_did',''),
                        'acquired_date': vehicle_info.get('acquired_date', '')  # Ensure acquired_date is accessible
                    })

            return detailed_vehicles


        except Exception as e:
            print(f"Error getting user vehicles: {e}")
            return []

    def verify_signature(self, did: str, message: bytes, signature: bytes) -> bool:
        """Verify a signature using the DID's public key"""
        try:
            _, public_key_pem = self.wallet.get_keys(did)
            public_key = serialization.load_pem_public_key(public_key_pem)
            
            public_key.verify(
                signature,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False

    def sign_message(self, did: str, message: bytes) -> bytes:
        """Sign a message using the DID's private key"""
        private_key_pem, _ = self.wallet.get_keys(did)
        private_key = serialization.load_pem_private_key(
            private_key_pem,
            password=None
        )
        
        signature = private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return signature

    def get_did_document(self, did: str) -> Optional[Dict]:
        """
        Retrieve a DID document from the blockchain
        
        Args:
            did: The DID to retrieve the document for
            
        Returns:
            Optional[Dict]: The DID document if found, None otherwise
        """
        try:
            # Get the DID document from blockchain
            did_doc = self.blockchain_service.get_did_document(did)
            if did_doc:
                # Verify the document structure
                if '@context' not in did_doc:
                    did_doc['@context'] = ['https://www.w3.org/ns/did/v1']
                
                # Add verification method if not present
                if 'verificationMethod' not in did_doc:
                    try:
                        # Get public key from wallet
                        _, public_key = self.wallet.get_keys(did)
                        key_id = f"{did}#keys-1"
                        verification_method = {
                            "id": key_id,
                            "type": "RsaVerificationKey2018",
                            "controller": did,
                            "publicKeyPem": public_key.decode('utf-8')
                        }
                        did_doc['verificationMethod'] = [verification_method]
                        did_doc['authentication'] = [key_id]
                        did_doc['assertionMethod'] = [key_id]
                    except Exception as e:
                        print(f"Error adding verification method: {e}")
                
                return did_doc
            
            return None
            
        except Exception as e:
            print(f"Error retrieving DID document: {e}")
            return None

    def create_credential(self, issuer_did: str, subject_did: str, claims: Dict) -> Optional[Dict]:
        """Create a verifiable credential."""
        try:
            # Get the issuer's blockchain address
            address_info = self.address_manager.get_address(issuer_did)
            if not address_info:
                raise Exception("No blockchain address found for issuer")
            address, private_key = address_info
            
            # Create blockchain service with issuer's address
            blockchain_service = BlockchainService(account=address, private_key=private_key)

            # Generate a unique credential ID
            credential_id = f"did:{self.DID_METHOD}:credential:{str(uuid.uuid4())}"
            
            # Get issuer's keys for signing
            private_key_pem, _ = self.wallet.get_keys(issuer_did)
            
            # Create the credential
            credential = {
                "@context": [
                    "https://www.w3.org/2018/credentials/v1",
                    "https://www.w3.org/2018/credentials/examples/v1"
                ],
                "id": credential_id,
                "type": ["VerifiableCredential"] + ([claims["type"]] if "type" in claims else []),
                "issuer": issuer_did,
                "issuanceDate": datetime.utcnow().isoformat(),
                "credentialSubject": {
                    "id": subject_did,
                    **claims
                }
            }
            
            # Sign the credential
            credential_bytes = json.dumps(credential).encode()
            signature = self.sign_message(issuer_did, credential_bytes)
            
            # Add the proof
            credential["proof"] = {
                "type": "RsaSignature2018",
                "created": datetime.utcnow().isoformat(),
                "verificationMethod": f"{issuer_did}#keys-1",
                "signatureValue": base64.b64encode(signature).decode()
            }
            
            # Store the credential on the blockchain using issuer's address
            status = blockchain_service.store_did_document(
                credential_id, 
                json.dumps(credential)
            )
            
            if not status:
                raise Exception("Failed to store credential on blockchain")
            
            return credential
            
        except Exception as e:
            print(f"Error creating credential: {e}")
            return None

    def verify_credential(self, credential_id: str) -> Optional[Dict]:
        """Verify a credential by retrieving it from the blockchain."""
        credential_data = self.blockchain_service.get_credential(credential_id)
        if credential_data:
            return json.loads(credential_data)
        return None

    def verify_user_did(self, did: str) -> bool:
        """Verify if a user DID exists on the blockchain."""
        return bool(self.blockchain_service.get_user_by_did(did))

    def verify_vehicle_did(self, did: str) -> bool:
        """Verify if a vehicle DID exists on the blockchain."""
        return bool(self.blockchain_service.get_vehicle_by_did(did))

    def create_did(self, user_type: str, name: str) -> Optional[Dict]:
        """
        Create a new DID for a user
        
        Args:
            user_type: Type of user (individual, mechanic, etc.)
            name: Name of the user
            
        Returns:
            Optional[Dict]: DID document if successful, None otherwise
        """
        try:
            # Get a unique blockchain address for the user
            try:
                entity_did, wallet_did = self.create_user_dids()
                address_info = self.address_manager.get_address(entity_did)
            except Exception as e:
                print(f"Failed to get blockchain address: {e}")
                return None
                
            if not address_info:
                print("No available blockchain addresses")
                return None
                
            address, private_key = address_info
            print(f"Got address {address} with private key {private_key}")
            
            # Create a new blockchain service instance with the user's address
            blockchain_service = BlockchainService(account=address, private_key=private_key)

            # Store the blockchain service instance for DID document storage
            self.blockchain_service = blockchain_service

            # Generate separate key pairs for both DIDs
            entity_private_key, entity_public_key = self._generate_key_pair()
            wallet_private_key, wallet_public_key = self._generate_key_pair()
            
            
            # Create DID documents
            entity_doc = DIDDocument(entity_did, entity_public_key)
            wallet_doc = DIDDocument(wallet_did, wallet_public_key)
          
            
            # First register the user with both DIDs
            print(f"Registering user with name: {name}, type: {user_type}, entity_did: {entity_did}, wallet_did: {wallet_did}")
            success, message = blockchain_service.register_user(
                name, 
                user_type,
                entity_did,
                wallet_did
            )
            
            if not success:
                print(f"Failed to register user: {message}")
                # Release the address back to the pool
                self.address_manager.release_address(entity_did)
                return None
                
            print("User registered successfully!")
            
            # Store both key pairs in wallet
            self.wallet.store_keys(entity_did, entity_private_key, entity_public_key)
            self.wallet.store_keys(wallet_did, wallet_private_key, wallet_public_key)
           
            # Link the DIDs by adding controller relationships
            entity_doc.service_endpoints.append({
                "id": f"{wallet_did}#wallet",
                "@type": ["ServiceEndpoint"],
                "serviceEndpoint": f"https://api.example.org/wallet/{wallet_did}",
                "controller": entity_did
            })
            entity_doc.type.append("Person")
            entity_doc.type.append("VerifiableCredential")
            
            entity_str = json.dumps(entity_doc.to_dict())
            status = self.blockchain_service.store_did_document(entity_did, entity_str)

            if not status:
                self.address_manager.release_address(entity_did)
                return None

            wallet_doc.service_endpoints.append({
                "id": f"{entity_did}#entity",
                "type": ["WalletService"],
                "controller": entity_did,
                "serviceEndpoint": f"https://api.example.org/wallet/{entity_did}"
            })
            wallet_doc.type.append("VerifiableCredential")
            wallet_doc.type.append("Wallet")
            
            wallet_str = json.dumps(wallet_doc.to_dict())
            
            # Store on blockchain
            status = self.blockchain_service.store_did_document(wallet_did, wallet_str)
            if not status:
                self.address_manager.release_address(entity_did)
                return None
                
            return {
                'entity_did': entity_did,
                'wallet_did': wallet_did,
                'entity_did_document': entity_doc.to_dict(),
                'wallet_did_document': wallet_doc.to_dict()
            }
            
        except Exception as e:
            print(f"Error creating DID: {e}")
            # Release the address back to the pool if we have a user_id
            if 'user_id' in locals():
                self.address_manager.release_address(entity_did)
            return None
        
    def register_vehicle(self, car_did_document: Dict, owner_did: str) -> Dict:
        """Register a vehicle with its DIDs and update the owner's document."""
        try:
            vehicle_did, wallet_did = self.create_user_dids()
            # Extract necessary information from the car DID document
            vin = car_did_document.get('vin','')
            make = car_did_document.get('make','')
            model = car_did_document.get('model','')
            year = car_did_document.get('year','')
            color = car_did_document.get('color','')
            status = car_did_document.get('status','')
            owner = car_did_document.get('owner', {})
            service_history = car_did_document.get('serviceHistory', [])
            c = car_did_document.get('type', ["VerifiableCredential", "Car"])
         

            self.set_account_address(vehicle_did)
            # Generate separate key pairs for both DIDs
            entity_private_key, entity_public_key = self._generate_key_pair()
            wallet_private_key, wallet_public_key = self._generate_key_pair()

            # Create DID documents for vehicle and wallet
            vehicle_doc = DIDDocument(vehicle_did, entity_public_key)
            wallet_doc = DIDDocument(wallet_did, wallet_public_key)

            # Register vehicle in the blockchain using the CAR type from the enum
            success, message = self.blockchain_service.register_user(
                make + " " + model,  # vehicle name
                "CAR",  # Use the string name for UserType.CAR
                vehicle_did,
                wallet_did
            )
            
            if not success:
                print(f"Failed to register car: {message}")
                self.address_manager.release_address(vehicle_did)
                return None
                
            print("Car registered successfully!")

            # Store keys in wallet
            vehicle_doc.info.extend([
                {
                    "id": f"{vehicle_did}#vehicle_{vin}",
                    "manufacturer": owner.get('name',''),  # Store manufacturer name
                    "owner_did": owner_did,  # Store owner's DID
                    "status": status,
                    "vin": vin,
                    "make": make,
                    "model": model,
                    "year": year,
                    "color": color
                },
                {
                    "id": f"{wallet_did}#wallet",
                    "type": "WalletLink",
                    "serviceEndpoint": wallet_did
                }
            ])

            # Add vehicle type
            vehicle_doc.type.extend(c)

            # Store the vehicle DID document
            vehicle_str = json.dumps(vehicle_doc.to_dict())
            status = self.blockchain_service.store_did_document(vehicle_did, vehicle_str)
            if not status:
                print("Failed to store vehicle DID document")
                self.address_manager.release_address(vehicle_did)
                return None

            # Store wallet DID document
            wallet_doc.service_endpoints.append({
                "id": f"{wallet_did}#entity",
                "type": "EntityLink",
                "serviceEndpoint": vehicle_did,
                "service_history": service_history
            })
            wallet_doc.type.extend(["VerifiableCredential", "VehicleWallet"])

            wallet_str = json.dumps(wallet_doc.to_dict())
            status = self.blockchain_service.store_did_document(wallet_did, wallet_str)
            if not status:
                print("Failed to store wallet DID document")
                self.address_manager.release_address(vehicle_did)
                return None

            # Store keys in wallet
            self.wallet.store_keys(vehicle_did, entity_private_key, entity_public_key)
            self.wallet.store_keys(wallet_did, wallet_private_key, wallet_public_key)
            
            data = {
                    "id": f"{vehicle_did}#vehicle_{vin}",
                    "type": "OwnedVehicle",
                    "vehicle_did": vehicle_did,
                    "wallet_did": wallet_did,
                    "acquired_date": datetime.utcnow().isoformat()
                }

            # Get owner's DID document to update it with vehicle information
            update = self.update_did_document(owner_did,None,data)

            return {
                "vehicle_did": vehicle_did,
                "wallet_did": wallet_did,
                "vehicle_doc": vehicle_doc.to_dict(),
                "wallet_doc": wallet_doc.to_dict(),
                "User Doc Update": update
            }
                
        except Exception as e:
            print(f"Error creating vehicle DIDs: {e}")
            if 'vehicle_did' in locals():
                self.address_manager.release_address(vehicle_did)
            return None
        
    def update_did_document(self, did, car_did, credential=None): 
        """Update a DID document with new credential or owner information."""
        try:
            
            if not car_did:
                self.set_account_address(did)
                owner_doc = self.blockchain_service.get_did_document(did)
                if not owner_doc:
                    print("Failed to retrieve owner's DID document")
                    self.address_manager.release_address(did)
                    return None

                # Convert owner_doc to dictionary if it's not already
                if isinstance(owner_doc, str):
                    owner_doc = json.loads(owner_doc)

                # Add vehicle to owner's document
                if 'info' not in owner_doc:
                    owner_doc['info'] = []
                
                owner_doc['info'].append(credential)

                # Update owner's document on blockchain
                status = self.blockchain_service.store_did_document(did, json.dumps(owner_doc))
                if not status:
                    print("Failed to update owner's DID document")
                    return None
                return status
            
            elif credential: 
                # Update document with new credential
                self.set_account_address(did)
                # Get and parse the document
                did_doc = self.blockchain_service.get_did_document(did)
                if not did_doc:
                    print("Failed to get DID document")
                    return None
                
                # Parse the document if it's a string, otherwise use as is
                if isinstance(did_doc, str):
                    did_doc = json.loads(did_doc)
                
                # Initialize credentials array if it doesn't exist
                if 'credentials' not in did_doc:
                    did_doc['credentials'] = []
                
                # Add the new credential
                did_doc['credentials'].append(credential)
                
                # Store updated document
                did_str = json.dumps(did_doc)
                status = self.blockchain_service.store_did_document(did, did_str)
                if not status:
                    print("Failed to update DID document")
                    return None
                return status    
            
            else:
                # Update vehicle owner
                self.set_account_address(car_did)
                # Get and parse the document
                did_doc = self.blockchain_service.get_did_document(car_did)
                if not did_doc:
                    print("Failed to get DID document")
                    return None

                # Parse the document if it's a string, otherwise use as is
                if isinstance(did_doc, str):
                    did_doc = json.loads(did_doc)

                # Initialize info array if it doesn't exist
                if 'info' not in did_doc:
                    did_doc['info'] = [{}]
                elif len(did_doc['info']) == 0:
                    did_doc['info'].append({})

                # Update owner DID
                owner_info = did_doc['info'][0]

                # Initialize previous owners list if it doesn't exist
                if 'previous_owners' not in owner_info:
                    owner_info['previous_owners'] = []

                # Append the current owner to the previous owners list
                owner_info['previous_owners'].append(owner_info.get('owner_did', None))  # Append current owner if exists

                # Update the current owner DID
                owner_info['owner_did'] = did

                # Store updated document
                did_str = json.dumps(did_doc)
                status = self.blockchain_service.store_did_document(car_did, did_str)
                if not status:
                    print("Failed to update DID document")
                    return None

                return status

            
        except Exception as e:
            print(f"Error updating DID document: {e}")
            return None
        


    def set_account_address(self, did):
        # Update vehicle owner
        address_info = self.address_manager.get_address(did)
        if not address_info:
            print("No available blockchain addresses")
            return None
            
        address, private_key = address_info
        print(f"Got address {address} with private key {private_key}")
        if not address or not private_key:
            print("Failed to get address or private key")
            return None
        # Create blockchain service instance with owner's credentials
        blockchain_service = BlockchainService(account=address, private_key=private_key)
        self.blockchain_service = blockchain_service    

    def encrypt_didcomm_message(self, message: Dict, sender_key: str, recipient_key: str) -> Dict:
        """
        Encrypt a DIDComm message using authenticated encryption.
        
        Args:
            message: The DIDComm message to encrypt
            sender_key: The sender's authentication key
            recipient_key: The recipient's key agreement key
            
        Returns:
            Dict: The encrypted message
        """
        # In a real implementation, this would use proper encryption
        # For now, we'll just mark it as encrypted
        return {
            **message,
            "encrypted": True,
            "sender_key": sender_key,
            "recipient_key": recipient_key
        }

    def decrypt_didcomm_message(self, encrypted_message: Dict, decryption_key: str) -> Dict:
        """
        Decrypt a DIDComm message.
        
        Args:
            encrypted_message: The encrypted DIDComm message
            decryption_key: The key to decrypt the message
            
        Returns:
            Dict: The decrypted message
        """
        # In a real implementation, this would use proper decryption
        # For now, we'll just remove the encryption markers
        message = encrypted_message.copy()
        del message["encrypted"]
        del message["sender_key"]
        del message["recipient_key"]
        return message

    def create_didcomm_message(
        self, 
        sender_did: str, 
        recipient_did: str, 
        message_type: str,
        body: Dict,
        reply_to: str = None,
        reply_url: str = None
    ) -> Dict:
        """
        Create a DIDComm message with proper formatting.
        
        Args:
            sender_did: The DID of the sender
            recipient_did: The DID of the recipient
            message_type: The type of message (e.g., "request", "response")
            body: The message content
            reply_to: Optional message ID this is replying to
            reply_url: Optional URL for receiving replies
        """
        message = {
            "type": f"https://didcomm.org/iov/1.0/{message_type}",
            "id": str(uuid.uuid4()),
            "from": sender_did,
            "to": [recipient_did],
            "created_time": datetime.now().isoformat(),
            "body": body
        }
        
        if reply_to:
            message["thid"] = reply_to
        if reply_url:
            message["reply_url"] = reply_url
            
        return message

    def evaluate_data_request(
        self,
        requester_did: str,
        subject_did: str,
        requested_data: List[str],
        context: Dict,
        is_emergency: bool = False
    ) -> Tuple[bool, str, Dict]:
        """
        Evaluate a data request using LLM and context.
        
        Args:
            requester_did: DID of the entity requesting data
            subject_did: DID of the entity whose data is requested
            requested_data: List of requested data types
            context: Additional context about the request
            is_emergency: Whether this is an emergency request
            
        Returns:
            Tuple[bool, str, Dict]: (approved, reason, suggested_response)
        """
        # Get entity information
        requester_doc = self.get_did_document(requester_did)
        subject_doc = self.get_did_document(subject_did)
        
        if not requester_doc or not subject_doc:
            return False, "Invalid DIDs", {}
            
        # Get entity types, ensuring we have a string to work with
        requester_type = requester_doc.get("type", ["unknown"])[0] if isinstance(requester_doc.get("type"), list) else "unknown"
        subject_type = subject_doc.get("type", ["unknown"])[0] if isinstance(subject_doc.get("type"), list) else "unknown"
            
        # Prepare context for LLM
        llm_context = {
            "requester": {
                "did": requester_did,
                "type": requester_type,
                "name": requester_doc.get("name", "unknown")
            },
            "subject": {
                "did": subject_did,
                "type": subject_type,
                "name": subject_doc.get("name", "unknown")
            },
            "request": {
                "data_types": requested_data,
                "is_emergency": is_emergency,
                "context": context
            }
        }

        # Automatic approval for emergency requests
        if is_emergency:
            return True, "Emergency request approved", {
                "message": "Emergency data access granted",
                "action_required": "Immediate response needed",
                "timestamp": datetime.now().isoformat()
            }
        
        # Evaluate based on message type and context
        message_type = context.get("message_type", "").lower()
        message_content = context.get("content", "").strip()
        
        # Automatic approval for traffic-related requests from RSU
        if "roadside_unit" in requester_type.lower():
            response_message = ""
            if "traffic" in message_type.lower():
                response_message = "Traffic data access granted for traffic management"
            elif message_type == "road condition":
                response_message = "Road condition data access granted for safety monitoring"
            elif message_type == "weather alert":
                response_message = "Weather-related data access granted for safety alerts"
            else:
                response_message = "Data access granted for RSU monitoring"
                
            return True, "Valid RSU request", {
                "message": response_message,
                "action_required": "Regular monitoring",
                "timestamp": datetime.now().isoformat(),
                "data_shared": requested_data
            }
            
        # If message content is too short or vague
        if len(message_content) < 10:
            return False, "Insufficient context", {
                "message": "Please provide more detailed information about why you need this data",
                "action_required": "Add more context",
                "timestamp": datetime.now().isoformat()
            }
            
        return False, "Insufficient justification", {
            "message": "Request denied - please provide more context",
            "action_required": None,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_entity_interactions(self, entity_did: str) -> List[Dict]:
        """Get all interactions for a specific entity."""
        try:
            interactions = self.blockchain_service.get_entity_interactions(entity_did)
            return interactions
        except Exception as e:
            print(f"Error getting entity interactions: {e}")
            return []

    def record_interaction(self, source_address: str, destination_address: str, 
                         source_identifier: str, destination_identifier: str,
                         interaction_type: str, payload: bytes) -> bool:
        """Record an interaction between any two entities."""
        try:
            self.set_account_address(source_identifier)
            tx_hash = self.blockchain_service.record_interaction(
                source_address,
                destination_address,
                source_identifier,
                destination_identifier,
                interaction_type,
                payload
            )
            return tx_hash
        except Exception as e:
            print(f"Error recording entity interaction: {e}")
            return False

# Export the DIDService class
__all__ = ['DIDService']













