from web3 import Web3
import json
from config.settings import Settings, BlockchainConfig
from typing import List, Dict, Any, Optional, Union, Tuple
from enum import Enum, auto

class UserType(Enum):
    """
    Enum to map user types to contract's uint8 enum values
    Ensures consistent mapping between string and contract enum
    """
    INDIVIDUAL = 0
    MECHANIC = 1
    INSURANCE_PROVIDER = 2
    ROADSIDE_UNIT = 3
    VEHICLE_MANUFACTURER = 4
    CAR = 5

class BlockchainService:
    def __init__(self, account=None, private_key=None):
        self.web3 = Web3(Web3.HTTPProvider(Settings.BLOCKCHAIN_URL))
        self.contract_address = self.web3.to_checksum_address(Settings.CONTRACT_ADDRESS)
        self.contract = self.web3.eth.contract(
            address=self.contract_address,
            abi=BlockchainConfig.ABI
        )
        self.account = account if account else Settings.ACCOUNT
        self.private_key = private_key if private_key else Settings.PRIVATE_KEY

    def _build_and_send_transaction(self, function_call, gas: int = 6000000) -> str:
        """
        Helper method to build, sign, and send transactions
        
        Args:
            function_call: The contract function to call
            gas: Gas limit for the transaction
        
        Returns:
            Transaction hash as hex string
        """
        try:
            print(f"Building transaction with account: {self.account}")
            nonce = self.web3.eth.get_transaction_count(self.account)
            
            transaction = function_call.build_transaction({
                'from': self.account,
                'gas': gas,
                'gasPrice': self.web3.to_wei('20', 'gwei'),
                'nonce': nonce
            })
            
            print(f"Signing transaction with private key: {self.private_key}")
            signed_tx = self.web3.eth.account.sign_transaction(
                transaction, 
                private_key=self.private_key
            )
            
            # print(f"Signed transaction {signed_tx}")
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            # Convert bytes to hex string if needed
            if isinstance(tx_hash, bytes):
                return tx_hash.hex()
            return tx_hash
        except Exception as e:
            print(f"Error in _build_and_send_transaction: {e}")
            raise

    def store_did_document(self, did: str, document: str) -> bool:
        """
        Store a DID document on the blockchain
        
        Args:
            did: The DID to store the document for
            document: The DID document as a JSON string
        
        Returns:
            bool: True if successful
        """
        try:
            function_call = self.contract.functions.storeDIDDocument(did, document)
            tx_hash = self._build_and_send_transaction(function_call)
            
            # Wait for transaction to be mined
            tx_receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            return tx_receipt.status == 1
        except Exception as e:
            print(f"Error storing DID document on blockchain: {e}")
            return False

    def get_did_document(self, did: str) -> Optional[Dict]:
        """
        Retrieve a DID document from the blockchain
        
        Args:
            did: The DID to retrieve the document for
            
        Returns:
            Optional[Dict]: The DID document if found, None otherwise
        """
        try:
            # Get the raw DID document from the contract
            did_doc = self.contract.functions.didDocuments(did).call()
            # print(f"Raw DID document from contract: {did_doc}")
            # print(f"Type of did_doc: {type(did_doc)}")
            
            if did_doc and isinstance(did_doc, (list, tuple)) and len(did_doc) > 1:
                # The actual DID document is in the second element (index 1)
                doc_str = did_doc[1]
                # print(f"DID document string: {doc_str}")
                # print(f"Type of document string: {type(doc_str)}")
                
                if doc_str:  # If document string is not empty
                    try:
                        # If it's already a dict, return it
                        if isinstance(doc_str, dict):
                            return doc_str
                        
                        # If it's bytes or bytearray, decode first
                        if isinstance(doc_str, (bytes, bytearray)):
                            json_str = doc_str.decode('utf-8')
                        else:
                            json_str = str(doc_str)
                            
                        # Try to parse JSON
                        if json_str and json_str.strip():
                            return json.loads(json_str)
                    except json.JSONDecodeError as e:
                        print(f"Error parsing DID document JSON: {e}")
                        print(f"Failed JSON string: {json_str}")
            
            print("DID document not found in didDocuments, checking users and vehicles...")
            
            # If not found in didDocuments, check users and vehicles
            registered_addresses = self.contract.functions.getRegisteredAddresses().call()
            print(f"Found {len(registered_addresses)} registered addresses")
            
            # Check users
            for address in registered_addresses:
                user = self.contract.functions.users(address).call()
                print(f"Checking user at address {address}: {user}")
                
                if user[3] == did:  # Match entity_did
                    try:
                        # Construct DID document from user data
                        doc = {
                            '@context': ['https://www.w3.org/ns/did/v1'],
                            'id': did,
                            'controller': address,
                            'type': self._get_user_type_name(user[1]),
                            'name': user[0],
                            'entityDid': user[3],
                            'walletDid': user[4],
                            'service': []
                        }
                        if user[5]:  # Additional data/service endpoints
                            try:
                                if isinstance(user[5], (bytes, bytearray)):
                                    service_str = user[5].decode('utf-8')
                                else:
                                    service_str = str(user[5])
                                if service_str and service_str.strip():
                                    doc['service'] = json.loads(service_str)
                            except Exception as e:
                                print(f"Error parsing service endpoints: {e}")
                        return doc
                    except Exception as e:
                        print(f"Error constructing user DID document: {e}")
                        continue
                    
            
            
            print(f"DID document not found for {did}")
            return None
            
        except Exception as e:
            print(f"Error retrieving DID document: {e}")
            return None

    def revoke_did_document(self, did: str) -> bool:
        """
        Revoke a DID document
        
        Args:
            did: The DID to revoke
            
        Returns:
            bool: True if successful
        """
        try:
            function_call = self.contract.functions.revokeDIDDocument(did)
            tx_hash = self._build_and_send_transaction(function_call)
            
            # Wait for transaction to be mined
            tx_receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            return tx_receipt.status == 1
        except Exception as e:
            print(f"Error revoking DID document: {e}")
            return False

    def register_user(self, name: str, user_type: str, entity_did: str, wallet_did: str) -> Tuple[bool, str]:
        """
        Register a user in the smart contract
        
        Args:
            name: User's name
            user_type: User type as a string
            entity_did: The user's entity DID
            wallet_did: The user's wallet DID
        
        Returns:
            Tuple of (success, message)
        """
        try:
            # Convert string user type to enum integer value
            try:
                user_type_enum = UserType[user_type.upper().replace(' ', '_')].value
            except KeyError:
                return False, f"Invalid user type: {user_type}. Must be one of {list(UserType.__members__.keys())}"
            
            # Check if user is already registered
            user_info = self.contract.functions.users(self.account).call()
            if user_info[5]:  # isRegistered field
                return False, "Address already registered"
            
            print(f"Registering user with account: {self.account}")
            print(f"Private key: {self.private_key}")
            
            # Call the smart contract to register user
            function_call = self.contract.functions.registerUser(
                name,
                int(user_type_enum),
                entity_did,
                wallet_did
            )
            
            # Build and send transaction
            tx_hash = self._build_and_send_transaction(function_call)
            
            # Wait for transaction receipt
            tx_receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            if tx_receipt['status'] == 1:
                return True, "User registered successfully!"
            else:
                return False, "Transaction failed"
            
        except Exception as e:
            error_msg = str(e)
            if "revert" in error_msg.lower():
                if "already registered" in error_msg.lower():
                    return False, "Address already registered"
                return False, f"Smart contract error: {error_msg}"
            return False, f"Error: {error_msg}"

    def get_user_vehicles(self, owner_did: str) -> List[Dict]:
        """
        Get all vehicles owned by a user
        
        Args:
            owner_did: DID of the vehicle owner
            
        Returns:
            List[Dict]: List of vehicle information
        """
        try:
            vehicles = self.contract.functions.getUserVehicles(owner_did).call()
            return vehicles
        except Exception as e:
            print(f"Error getting user vehicles: {e}")
            return []

    def update_vehicle_config(self, vehicle_wallet_did: str, config: str) -> Tuple[bool, str]:
        """
        Update vehicle configuration settings
        
        Args:
            vehicle_wallet_did: Wallet DID of the vehicle
            config: Configuration settings in JSON format
            
        Returns:
            Tuple[bool, str]: Success status and message
        """
        try:
            # Build transaction
            update_config = self.contract.functions.updateVehicleConfig(
                vehicle_wallet_did,
                config
            )
            
            # Build and send transaction
            success = self._build_and_send_transaction(update_config)
            
            if success:
                return True, "Vehicle configuration updated successfully"
            else:
                return False, "Failed to update vehicle configuration"
                
        except Exception as e:
            print(f"Error updating vehicle configuration: {e}")
            return False, str(e)

    def authorize_mechanic(self, vin: str, mechanic_address: str) -> str:
        """
        Authorize a mechanic for a specific vehicle
        
        Args:
            vin: Vehicle Identification Number
            mechanic_address: Ethereum address of the mechanic
        
        Returns:
            Transaction hash
        """
        function_call = self.contract.functions.authorizeMechanic(
            vin,
            mechanic_address
        )
        return self._build_and_send_transaction(function_call)

    def add_maintenance_record(self, vin: str, service_description: str, is_critical: bool) -> str:
        """
        Add a maintenance record for a vehicle
        
        Args:
            vin: Vehicle Identification Number
            service_description: Description of the maintenance service
            is_critical: Whether the maintenance is critical
        
        Returns:
            Transaction hash
        """
        function_call = self.contract.functions.addMaintenanceRecord(
            vin,
            service_description,
            is_critical
        )
        return self._build_and_send_transaction(function_call)

    def create_insurance_policy(self, vin: str, start_date: int, end_date: int) -> str:
        """
        Create an insurance policy for a vehicle
        
        Args:
            vin: Vehicle Identification Number
            start_date: Policy start timestamp
            end_date: Policy end timestamp
        
        Returns:
            Transaction hash
        """
        function_call = self.contract.functions.createInsurancePolicy(
            vin,
            start_date,
            end_date
        )
        return self._build_and_send_transaction(function_call)

    def record_interaction(self, source_address: str, destination_address: str, 
                         source_identifier: str, destination_identifier: str,
                         interaction_type: str, payload: bytes) -> str:
        """
        Record an interaction between any two entities in the system
        
        Args:
            source_address: Blockchain address of the source entity
            destination_address: Blockchain address of the destination entity
            source_identifier: Identifier (VIN, DID, etc.) of the source entity
            destination_identifier: Identifier (VIN, DID, etc.) of the destination entity
            interaction_type: Type of interaction
            payload: Additional interaction data
        
        Returns:
            Transaction hash
        """
        function_call = self.contract.functions.recordInteraction(
            source_address,
            destination_address,
            source_identifier,
            destination_identifier,
            interaction_type,
            payload
        )
        return self._build_and_send_transaction(function_call)


    def get_entity_interactions(self, identifier: str) -> List[Dict[str, Any]]:
        """
        Retrieve all interactions for a specific entity
        
        Args:
            identifier: Entity identifier (VIN, DID, etc.)
        
        Returns:
            List of interactions
        """
        try:
            # Get raw interactions from contract
            raw_interactions = self.contract.functions.getEntityInteractions(identifier).call()
            
            # Convert tuples to dictionaries
            interactions = []
            for interaction in raw_interactions:
                # Expected tuple structure:
                # (source_address, destination_address, source_identifier, destination_identifier, 
                #  interaction_type, payload, timestamp, transaction_hash)
                interaction_dict = {
                    'source_address': interaction[0],
                    'destination_address': interaction[1],
                    'source_identifier': interaction[2],
                    'destination_identifier': interaction[3],
                    'interaction_type': interaction[4],
                    'payload': interaction[5],
                    'timestamp': interaction[6],
                    'transaction_hash': interaction[7] if len(interaction) > 7 else None
                }
                interactions.append(interaction_dict)
            
            return interactions
        except Exception as e:
            print(f"Error getting entity interactions: {e}")
            return []

    def get_vehicle_interactions(self, vin: str) -> List[Dict[str, Any]]:
        """
        Retrieve vehicle interactions for a specific VIN (legacy support)
        
        Args:
            vin: Vehicle Identification Number
        
        Returns:
            List of vehicle interactions
        """
        return self.get_entity_interactions(vin)

    def get_interactions_between_entities(self, identifier1: str, identifier2: str) -> List[Dict[str, Any]]:
        """
        Retrieve all interactions between two specific entities
        
        Args:
            identifier1: First entity's identifier (VIN, DID, etc.)
            identifier2: Second entity's identifier (VIN, DID, etc.)
        
        Returns:
            List of interactions between the two entities
        """
        return self.contract.functions.getInteractionsBetweenEntities(identifier1, identifier2).call()


    def is_valid_did(self, did: str) -> bool:
        """
        Check if a Decentralized Identifier (DID) is valid
        
        Args:
            did: Decentralized Identifier to validate
        
        Returns:
            Boolean indicating DID validity
        """
        return self.contract.functions.isValidDID(did).call()

    def get_address_by_did(self, did: str) -> Optional[str]:
        """
        Get user address by their DID
        
        Args:
            did: User's Decentralized Identifier
        """
        user_address = self.contract.functions.didToAddress(did).call()
        return user_address

    def get_vehicle_by_did(self, did: str) -> Optional[Dict[str, Any]]:
        """
        Get vehicle information by its DID
        
        Args:
            did: Vehicle's Decentralized Identifier
        
        Returns:
            Vehicle information if found, None otherwise
        """
        # Check if DID is valid and not revoked
        is_valid = self.contract.functions.isValidDID(did).call()
        if not is_valid:
            return None

        # Since vehicles are stored by VIN, we need to search through the events
        # to find the vehicle registration event with this DID
        register_filter = self.contract.events.VehicleRegistered.create_filter(
            fromBlock=0,
            argument_filters={'entityDID': did}
        )
        events = register_filter.get_all_entries()
        
        if not events:
            return None
            
        # Get the most recent registration event
        event = events[-1]
        vin = event.args.vin
        vehicle = self.contract.functions.vehicles(vin).call()
        
        return {
            'vin': vin,
            'make': vehicle[1],
            'model': vehicle[2],
            'year': vehicle[3],
            'current_owner': vehicle[4],
            'entity_did': vehicle[6],
            'wallet_did': vehicle[7],
            'credential_did': vehicle[8],
            'is_registered': vehicle[9]
        }

    def store_credential(self, credential_id: str, issuer_did: str, subject_did: str, credential_data: str) -> str:
        """
        Store a verifiable credential on the blockchain
        
        Args:
            credential_id: Unique identifier for the credential
            issuer_did: DID of the issuer
            subject_did: DID of the subject
            credential_data: JSON string of the credential data
        
        Returns:
            Transaction hash
        """
        function_call = self.contract.functions.storeCredential(
            credential_id,
            issuer_did,
            subject_did,
            credential_data
        )
        return self._build_and_send_transaction(function_call)

    def get_credential(self, credential_id: str) -> Optional[str]:
        """
        Get a stored credential from the blockchain
        
        Args:
            credential_id: Unique identifier for the credential
        
        Returns:
            Credential data as JSON string if found, None otherwise
        """
        try:
            return self.contract.functions.getCredential(credential_id).call()
        except Exception:
            return None


    def _get_user_type_name(self, type_id: int) -> str:
        """
        Convert user type ID to string name
        
        Args:
            type_id: Integer ID of the user type
            
        Returns:
            str: Name of the user type
        """
        user_types = {
            0: "Individual",
            1: "Mechanic",
            2: "Insurance Provider",
            3: "Roadside Unit",
            4: "Vehicle Manufacturer"
        }
        return user_types.get(type_id, "Unknown")

    def get_registered_addresses(self) -> list:
        """
        Get list of all registered addresses from the smart contract
        
        Returns:
            list: List of registered addresses
        """
        try:
            return self.contract.functions.getRegisteredAddresses().call()
        except Exception as e:
            print(f"Error getting registered addresses: {e}")
            return []
        
    def get_account(self) -> str:
        """Get the current account address being used"""
        return self.account

    def get_registered_users(self) -> List[Dict[str, Any]]:
        """Get all registered users with their DIDs and types."""
        # try:
        registered_addresses = self.contract.functions.getRegisteredAddresses().call()
        users = []
        
        for address in registered_addresses:
            user = self.contract.functions.users(address).call()
            if user[3]:  # If user has a DID
                user_info = {
                    'name': user[1],
                    'did': user[3],
                    'address': address,
                    'type': user[2]  # This is the type ID
                }
                users.append(user_info)
        
        return users
        # except Exception as e:
        #     print(f"Error getting registered users: {str(e)}")
        #     return []

    def get_user_info(self,did) -> List[Dict[str, Any]]:
        """Get all registered users with their DIDs and types."""
        try:
            registered_addresses = self.contract.functions.getRegisteredAddresses().call()
            users = []
            
            for address in registered_addresses:
                user = self.contract.functions.users(address).call()
                if user[3] == did:  # If user has a DID
                    return {
                        'name': user[1],
                        'did': user[3],
                        'address': address,
                        'type': user[2]  # This is the type ID
                    }
            return None
        except Exception as e:
            print(f"Error getting registered users: {str(e)}")
            return []

    def get_registered_vehicles(self) -> List[Dict[str, Any]]:
        """Get all registered users with their DIDs and types."""
        try:
            registered_addresses = self.contract.functions.getRegisteredAddresses().call()
            vehicles = []
            
            for address in registered_addresses:
                user = self.contract.functions.users(address).call()
                if user[2]== 5: 
                    user_info = {
                        'name': user[1],
                        'did': user[3],
                        'address': address,
                        'type': user[2]  # This is the type ID
                    }
                    vehicles.append(user_info)
            
            return vehicles

        except Exception as e:
            print(f"Error getting registered users: {str(e)}")
            return []

    def get_registered_rsus(self) -> List[Dict[str, Any]]:
        """Get all registered users with their DIDs and types."""
        try:
            registered_addresses = self.contract.functions.getRegisteredAddresses().call()
            rsus = []
            
            for address in registered_addresses:
                user = self.contract.functions.users(address).call()
                if user[2]== 3:  # If user has a DID
                    user_info = {
                        'name': user[1],
                        'did': user[3],
                        'address': address,
                        'type': user[2]  # This is the type ID
                    }
                    rsus.append(user_info)
            
            return rsus

        except Exception as e:
            print(f"Error getting registered users: {str(e)}")
            return []
        
    def register_vehicle(self, did: str, vin: str, make: str, model: str, year: int,
                        entity_did: str, wallet_did: str, credential_did: str) -> Tuple[bool, str]:
        """
        Register a vehicle using DID as primary identifier
        
        Args:
            did: Primary DID identifier for the vehicle
            vin: Vehicle Identification Number
            make: Vehicle make
            model: Vehicle model
            year: Vehicle year
            entity_did: Entity DID
            wallet_did: Wallet DID
            credential_did: Credential DID
        
        Returns:
            Tuple[bool, str]: Success status and message
        """
        try:
            function_call = self.contract.functions.registerVehicle(
                did,
                vin,
                make,
                model,
                year,
                entity_did,
                wallet_did,
                credential_did
            )
            
            tx_hash = self._build_and_send_transaction(function_call)
            tx_receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            if tx_receipt.status == 1:
                return True, f"Vehicle registered successfully. Transaction: {tx_hash.hex()}"
            else:
                return False, "Transaction failed"
                
        except Exception as e:
            return False, f"Error registering vehicle: {str(e)}"
        
    def get_registered_mechanic(self) -> List[Dict[str, Any]]:
        """Get all registered users with their DIDs and types."""
        try:
            registered_addresses = self.contract.functions.getRegisteredAddresses().call()
            vehicles = []
            
            for address in registered_addresses:
                user = self.contract.functions.users(address).call()
                if user[2]== 1:  # If user has a DID
                    user_info = {
                        'name': user[1],
                        'did': user[3],
                        'address': address,
                        'type': user[2]  # This is the type ID
                    }
                    vehicles.append(user_info)
            
            return vehicles

        except Exception as e:
            print(f"Error getting registered users: {str(e)}")
            return []

    def is_address_registered(self, address: str) -> bool:
        """
        Check if an address is already registered in the smart contract
        
        Args:
            address: The blockchain address to check
            
        Returns:
            bool: True if address is registered, False otherwise
        """
        try:
            # Convert address to checksum format
            checksum_address = self.web3.to_checksum_address(address)
            # Call the smart contract to check if user exists
            user_info = self.contract.functions.users(checksum_address).call()
            # Check isRegistered field directly
            return user_info[5]  # isRegistered is at index 5 in the User struct
        except Exception as e:
            print(f"Error checking address registration: {e}")
            return False        