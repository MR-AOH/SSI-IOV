import json
import os
from typing import Dict, Optional, List
from datetime import datetime

class WalletService:
    def __init__(self, wallet_directory='did_wallet'):
        self.wallet_directory = wallet_directory
        self.wallets = {}
        self.load_wallets()  # Load existing wallets from JSON files
        self.notifications = {}
        self.messages = {}
        self.default_policies = {
            'location': {
                'share_with': ['emergency'],
                'requires_consent': True,
                'auto_share_emergency': True
            },
            'vehicle_info': {
                'share_with': ['emergency', 'service', 'insurance'],
                'requires_consent': True,
                'auto_share_emergency': True
            },
            'sensor_data': {
                'share_with': ['emergency', 'roadside_unit'],
                'requires_consent': True,
                'auto_share_emergency': True
            },
            'driving_behavior': {
                'share_with': ['emergency', 'insurance'],
                'requires_consent': True,
                'auto_share_emergency': False
            },
            'maintenance_history': {
                'share_with': ['service', 'insurance'],
                'requires_consent': True,
                'auto_share_emergency': False
            }
        }
        self.blocked_users = {}

    def load_wallets(self):
        """Load wallets from JSON files."""
        if not os.path.exists(self.wallet_directory):
            os.makedirs(self.wallet_directory)

        for filename in os.listdir(self.wallet_directory):
            if filename.endswith('.json'):
                with open(os.path.join(self.wallet_directory, filename), 'r') as f:
                    did = filename[:-5]  # Remove .json extension for DID
                    self.wallets[did] = json.load(f)

    def save_wallet(self, did: str):
        """Save a specific wallet to a JSON file."""
        if did in self.wallets:
            with open(os.path.join(self.wallet_directory, f"{did}.json"), 'w') as f:
                json.dump(self.wallets[did], f, indent=4)

    def create_wallet(self, did: str, entity_type: str):
        """Create a new wallet for an entity."""
        if did not in self.wallets:
            self.wallets[did] = {
                'did': did,
                'type': entity_type,
                'policies': self.default_policies.copy(),
                'shared_data': {},
                'pending_requests': []
            }
            self.notifications[did] = []
            self.messages[did] = []
            self.blocked_users[did] = []

            # Save the new wallet to a JSON file
            self.save_wallet(did)
        return self.wallets[did]

    def update_policy(self, did: str, data_type: str, policy: dict):
        """Update sharing policy for a specific data type."""
        if did in self.wallets and data_type in self.wallets[did]['policies']:
            self.wallets[did]['policies'][data_type].update(policy)
            # Save updated wallet to JSON file
            self.save_wallet(did)
            return True
        return False

    # Include similar save calls in other methods where the wallet is modified

    def get_wallet(self, did: str):
        """Get wallet for an entity."""
        return self.wallets.get(did)

    def update_policy(self, did: str, data_type: str, policy: dict):
        """Update sharing policy for a specific data type."""
        if did in self.wallets and data_type in self.wallets[did]['policies']:
            self.wallets[did]['policies'][data_type].update(policy)
            return True
        return False

    def check_permission(self, requester_type: str, owner_did: str, data_type: str, is_emergency: bool = False) -> bool:
        """Check if requester has permission to access data."""
        wallet = self.wallets.get(owner_did)
        if not wallet:
            return False

        policy = wallet['policies'].get(data_type)
        if not policy:
            return False

        # Auto-approve for emergencies if configured
        if is_emergency and policy['auto_share_emergency']:
            return True

        # Check if requester type is allowed
        if requester_type not in policy['share_with']:
            return False

        # If consent is required and it's not an emergency, return False
        if policy['requires_consent'] and not is_emergency:
            return False

        return True

    def request_data_access(self, requester_did: str, owner_did: str, data_type: str, reason: str, is_emergency: bool = False):
        """Request access to data from another entity."""
        owner_wallet = self.wallets.get(owner_did)
        if not owner_wallet:
            return False, "Owner wallet not found"

        request = {
            'id': f"{requester_did}_{data_type}_{len(owner_wallet['pending_requests'])}",
            'sender': requester_did,
            'data_type': data_type,
            'reason': reason,
            'is_emergency': is_emergency,
            'status': 'pending',
            'timestamp': datetime.now().isoformat()
        }
        
        owner_wallet['pending_requests'].append(request)
        self.notifications[owner_did].append({
            'type': 'data_request',
            'content': f"New data access request from {requester_did}",
            'request_id': request['id']
        })
        
        return True, request['id']

    def respond_to_request(self, owner_did: str, requester_did: str, data_type: str, approved: bool):
        """Respond to a data access request."""
        wallet = self.wallets.get(owner_did)
        if not wallet:
            return False, "Wallet not found"

        for request in wallet['pending_requests']:
            if (request['sender'] == requester_did and 
                request['data_type'] == data_type and 
                request['status'] == 'pending'):
                request['status'] = 'approved' if approved else 'rejected'
                return True, "Response recorded"

        return False, "Request not found"

    def get_notifications(self, did: str):
        """Get notifications for an entity."""
        return self.notifications.get(did, [])

    def clear_notifications(self, did: str):
        """Clear notifications for an entity."""
        if did in self.notifications:
            self.notifications[did] = []

    def share_data(self, owner_did: str, data_type: str, data: dict):
        """Store shared data in the wallet."""
        wallet = self.wallets.get(owner_did)
        if wallet:
            if 'shared_data' not in wallet:
                wallet['shared_data'] = {}
            wallet['shared_data'][data_type] = data
            return True
        return False

    def get_shared_data(self, did: str, data_type: str):
        """Get shared data from the wallet."""
        wallet = self.wallets.get(did)
        if wallet and 'shared_data' in wallet:
            return wallet['shared_data'].get(data_type)
        return None

    def store_didcomm_message(self, did: str, message: dict):
        """Store a DIDComm message in the wallet."""
        if did not in self.messages:
            self.messages[did] = []
        
        # Add timestamp if not present
        if 'timestamp' not in message:
            message['timestamp'] = datetime.now().isoformat()
            
        self.messages[did].append(message)
        
        # If it's a request, also add to pending requests
        if message.get('type') == 'request':
            self.add_pending_request(did, message)
            
        return True

    def get_didcomm_messages(self, did: str) -> list:
        """Get all DIDComm messages for a DID."""
        if did not in self.messages:
            return []
        # Sort messages by timestamp
        return sorted(self.messages[did], 
                     key=lambda x: x.get('timestamp', ''),
                     reverse=True)

    def add_pending_request(self, did: str, request: dict):
        """Add a pending request to the wallet."""
        if did not in self.wallets:
            self.create_wallet(did, 'unknown')
            
        if 'pending_requests' not in self.wallets[did]:
            self.wallets[did]['pending_requests'] = []
            
        # Add timestamp if not present
        if 'timestamp' not in request:
            request['timestamp'] = datetime.now().isoformat()
            
        # Add unique request ID if not present
        if 'id' not in request:
            request['id'] = f"{request.get('sender_did', 'unknown')}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
        self.wallets[did]['pending_requests'].append(request)
        return True

    def get_pending_requests(self, did: str) -> list:
        """Get all pending requests for a DID."""
        if did not in self.wallets:
            return []
            
        # Sort requests by timestamp
        requests = self.wallets[did].get('pending_requests', [])
        return sorted(requests,
                     key=lambda x: x.get('timestamp', ''),
                     reverse=True)

    def remove_pending_request(self, did: str, request: dict):
        """Remove a pending request from the wallet."""
        if did not in self.wallets:
            return False
            
        # Remove request by matching either ID or entire request
        self.wallets[did]['pending_requests'] = [
            req for req in self.wallets[did].get('pending_requests', [])
            if (req.get('id') != request.get('id') if 'id' in request 
                else req != request)
        ]
        return True

    def store_credential(self, did: str, credential: Dict):
        """Store a verifiable credential in the wallet."""
        if did not in self.wallets:
            return False
            
        if 'credentials' not in self.wallets[did]:
            self.wallets[did]['credentials'] = []
            
        self.wallets[did]['credentials'].append(credential)
        return True

    def get_credentials(self, did: str, credential_type: str = None) -> List[Dict]:
        """
        Get credentials for an entity.
        
        Args:
            did: The DID of the wallet owner
            credential_type: Optional type to filter credentials
        """
        if did not in self.wallets:
            return []
            
        credentials = self.wallets[did].get('credentials', [])
        if credential_type:
            credentials = [
                cred for cred in credentials 
                if cred.get('type') == credential_type
            ]
        return credentials

    def block_user(self, did: str, user_did: str, reason: str):
        """
        Block a user from interacting with the wallet owner
        
        Args:
            did: Wallet owner's DID
            user_did: DID of user to block
            reason: Reason for blocking
        """
        if did not in self.blocked_users:
            self.blocked_users[did] = []
            
        # Check if already blocked
        if not any(user['did'] == user_did for user in self.blocked_users[did]):
            self.blocked_users[did].append({
                'did': user_did,
                'blocked_at': datetime.now().isoformat(),
                'reason': reason
            })
    
    def unblock_user(self, did: str, user_did: str):
        """
        Unblock a previously blocked user
        
        Args:
            did: Wallet owner's DID
            user_did: DID of user to unblock
        """
        if did in self.blocked_users:
            self.blocked_users[did] = [user for user in self.blocked_users[did] if user['did'] != user_did]
    
    def get_blocked_users(self, did: str) -> List[Dict]:
        """
        Get list of blocked users for a wallet
        
        Args:
            did: Wallet owner's DID
            
        Returns:
            List of blocked users with their details
        """
        return self.blocked_users.get(did, [])

