from web3 import Web3
import os
import json
from typing import Optional, Tuple, Dict
from services.blockchain_service import BlockchainService

class AddressManager:
    def __init__(self, blockchain_service: BlockchainService = None):
        """Initialize address manager"""
        # Initialize blockchain service with default account
        self.blockchain_service = blockchain_service or BlockchainService()
        self.addresses_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data',
            'addresses.json'
        )
        self.addresses = None
        self._load_addresses()

    def _load_addresses(self):
        """Load addresses from Ganache and manage them"""
        os.makedirs(os.path.dirname(self.addresses_file), exist_ok=True)
        
        try:
            # Connect to Ganache
            w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:7545'))
            
            # Initialize addresses structure
            self.addresses = {
                'available': [],
                'used': {}
            }
            
            # Load existing used addresses from file if it exists
            if os.path.exists(self.addresses_file):
                with open(self.addresses_file, 'r') as f:
                    stored_data = json.load(f)
                    self.addresses['used'] = stored_data.get('used', {})
            
            # Ganache test accounts and their private keys
            test_accounts = [
                {#0
                    'address': '0x54b99Dc1C2f505CF0fAA465eCdA78c872b3749cC',
                    'private_key': '0xd09777239f86e807e5fbd5db02fe4cff51dcbc77b598dfcea6c62aea4117acd8'
                },
                {#1
                    'address': '0xF86C6fD8d11Bd7a5C4F19301BA6ab4Da0B69B206',
                    'private_key': '0xf30129e3a83a00cc00ffd35f43e6736102a64996074a01ea92abe12767e5fa4f'
                },
                {#2
                    'address': '0x53799B8c448521A6bA35CC4C78DD66dD804ce8a8',
                    'private_key': '0x319b7d2ee2f737787132c25e23a165467ae9f33e894bd27c80a840506b38014c'
                },
                {#3
                    'address': '0xdc2190cF7895688D2FEE20716cB7dD6dEBB30b56',
                    'private_key': '0x17fb49e5ec17ca0be9600cc9bc20fe953620c98cd50ddb3ca64296a158f5e089'
                },
                {#4
                    'address': '0x71980E1D5E4f176ADFE7bd90b968045B389274c7',
                    'private_key': '0x0350589197961a95ce7b2f20c6572e2935e2d1b71ea148cb8db115bd529dd0cf'
                },
                {#5
                    'address': '0x1A23AD04C94FEEe69d12b9F95b1F83fff0B6EB23',
                    'private_key': '0xe99d4ee80bde64c73c7677e8eea1290f3bf8141de6d1cbe6554f4ff22900b7cc'
                },
                {#6
                    'address': '0xA6b36a8E07e04F1295E609bc523fb9bC21900Bf1',
                    'private_key': '0xf3b9e5106823ff4393427367423ced5d74c8e8ffed38266d16808502e99b123b'
                },
                {# 7
                    'address': '0x44E4947b4E64DB6AE0697F7fc479f0BC7ec70CC7',
                    'private_key': '0xe1d9daa75524b61b8abd701ccdc9d16b8bea6397ae9bf6df0fe91d90f4841516'
                },
                {# 8
                    'address': '0xCDc10fDFBfF34Cb71180857D89756639799Ba78d',
                    'private_key': '0xb69bcb1262256040a2e1f90c31245a0d89664e20402bd8a7595c5ff7b01d0c07'
                },
                {# 9
                    'address': '0xF8a4c9d195B8Fcc4d453daB43afF54ba93d36311',
                    'private_key': '0x5edc5c96c4cd7e3e3378664d1380063df70fee8d539356650d2dd9b8262bad47'
                }
            ]

            # Get set of used addresses
            used_addresses = set(addr['address'] for addr in self.addresses['used'].values())
            
            # Add unused test accounts to available pool
            for account in test_accounts:
                if account['address'] not in used_addresses:
                    # Get account balance
                    balance = w3.eth.get_balance(account['address'])
                    # Only add accounts with balance
                    if balance > 0:
                        # Check if address is already registered in the smart contract
                        try:
                            is_registered = self.blockchain_service.is_address_registered(account['address'])
                            if not is_registered:
                                self.addresses['available'].append({
                                    'address': account['address'],
                                    'private_key': account['private_key']
                                })
                                print(f"Added Ganache account {account['address']} to available addresses")
                            else:
                                print(f"Skipping registered address {account['address']}")
                        except Exception as e:
                            print(f"Error checking address {account['address']}: {e}")
            
            # Save the current state
            self._save_addresses()
            
            print(f"Loaded {len(self.addresses['available'])} available addresses")
            
        except Exception as e:
            print(f"Error in _load_addresses: {e}")
            self.addresses = {
                'available': [],
                'used': {}
            }
            self._save_addresses()

    def _save_addresses(self):
        """Save the addresses to the JSON file"""
        with open(self.addresses_file, 'w') as f:
            json.dump(self.addresses, f, indent=4)

    def get_address(self, user_id: str) -> Optional[Tuple[str, str]]:
        """
        Get a blockchain address for a user. If the user already has an address,
        return that. Otherwise, assign a new address.
        
        Args:
            user_id: The unique identifier for the user
            
        Returns:
            Tuple[str, str]: (address, private_key) if available, None if no addresses left
        """
        # Check if user already has an address
        if user_id in self.addresses['used']:
            return (
                self.addresses['used'][user_id]['address'],
                self.addresses['used'][user_id]['private_key']
            )
        
        # Get a new address if available
        if self.addresses['available']:
            address_data = self.addresses['available'].pop(0)
            self.addresses['used'][user_id] = address_data
            self._save_addresses()
            return (address_data['address'], address_data['private_key'])
        
        # If no addresses available, try to reload from Ganache
        self._load_addresses()
        
        # Try again after reload
        if self.addresses['available']:
            address_data = self.addresses['available'].pop(0)
            self.addresses['used'][user_id] = address_data
            self._save_addresses()
            return (address_data['address'], address_data['private_key'])
        
        return None

    def get_private_key(self, address: str) -> Optional[str]:
        """Get private key for a given address"""
        try:
            # Check used addresses
            for user_id, addr_data in self.addresses['used'].items():
                if addr_data['address'].lower() == address.lower():
                    return addr_data['private_key']
            
            # Check available addresses
            for addr_data in self.addresses['available']:
                if addr_data['address'].lower() == address.lower():
                    return addr_data['private_key']
                    
            return None
        except Exception as e:
            print(f"Error getting private key: {e}")
            return None

    def release_address(self, user_id: str):
        """Release an address back to the available pool"""
        if user_id in self.addresses['used']:
            address_data = self.addresses['used'].pop(user_id)
            # Check if address is registered before adding back to pool
            try:
                is_registered = self.blockchain_service.is_address_registered(address_data['address'])
                if not is_registered:
                    self.addresses['available'].append(address_data)
                    print(f"Released address {address_data['address']} back to available pool")
                else:
                    print(f"Not releasing registered address {address_data['address']}")
            except Exception as e:
                print(f"Error checking address registration: {e}")
            self._save_addresses()
