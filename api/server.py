import logging
import re
import sys
import os
import json
from pathlib import Path
from turtle import st

project_root = Path(__file__).resolve().parent.parent.parent
PREFERENCES_FILE = Path(__file__).parent / "wallet_preferences.json"

# Initialize preferences file if it doesn't exist
if not PREFERENCES_FILE.exists():
    with open(PREFERENCES_FILE, 'w') as f:
        json.dump({"preferences": {}}, f)

sys.path.insert(0, str(project_root))
from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import uuid
from services.blockchain_service import BlockchainService
from services.did_services import DIDService
from services.wallet_service import WalletService
from services.llm_service import LLMService
from services.simulation_service import SimulationService
from services.address_manager import AddressManager


app = FastAPI(title="SSI-IoV API", version="1.0.0")
security = HTTPBearer()

# Initialize services
did_service = None
blockchain_service = None
wallet_service = WalletService()
llm_service = LLMService()
simulation_service = SimulationService()


class EntityRegistration(BaseModel):
    name: str
    entity_type: str

class DataRequest(BaseModel):
    request_id: str
    message_type: str
    content: str
    requested_data: List[str]  # Changed from str to List[str]
    is_emergency: bool
    sender_type: str
    sender_did: str
    recipient_did: str
    time: str

class DataResponse(BaseModel):
    request_id: str
    response_type: str
    data: Optional[Dict[str, Any]]
    reason: Optional[str]
    sender_did: str
    recipient_did: str

class VerificationResponse(BaseModel):
    is_valid: bool
    message: str

class VehicleRegistration(BaseModel):
    owner_did: str
    make: str
    model: str
    year: int
    vin: str

class DIDRequest(BaseModel):
    name: str
    user_type: str

class DIDResponse(BaseModel):
    entity_did: str
    wallet_did: str

class RegisteredUser(BaseModel):
    name: str
    did: str
    address: str
    type: int  # or str if you map to user type name

@app.on_event("startup")
def startup_event():
    global blockchain_service
    global did_service
    did_service = DIDService()
    blockchain_service = BlockchainService()
    
    # Force loading addresses
    AddressManager(blockchain_service=blockchain_service)

    print("System initialized. Blockchain + addresses ready.")

# Helper functions
async def verify_did(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """Verify DID from bearer token"""
    did = credentials.credentials
    try:
        # Verify DID exists and is valid
        doc = did_service.get_did_document(did)
        print(f"ptring fro serverrrrrr  {did}")
        if not doc:
            raise HTTPException(status_code=401, detail="Invalid DID")
        return did
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
    


@app.get("/registered-dids", response_model=List[RegisteredUser])
def get_registered_dids():
    try:
        users = blockchain_service.get_registered_users()
        return users
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/create-did", response_model=DIDResponse)
def create_did(request: DIDRequest):
    if not request.name:
        raise HTTPException(status_code=400, detail="Name is required")

    try:
        print(str(request.user_type), str(request.name))
        result = did_service.create_did(str(request.user_type), str(request.name))
        
        return DIDResponse(
            entity_did=result["entity_did"],
            wallet_did=result["wallet_did"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/register-vehicle")
async def register_vehicle(registration: VehicleRegistration, owner_did: str = Depends(verify_did)):
    """Register a vehicle for an entity"""
    if owner_did != registration.owner_did:
        raise HTTPException(status_code=403, detail="DID mismatch")
    
    try:
        # Create vehicle DID
        vehicle_did = did_service.create_did()
        
        # Create vehicle wallet DID
        vehicle_wallet_did = did_service.create_did()
        
        # Register vehicle on blockchain
        tx_hash = blockchain_service.register_vehicle(
            registration.owner_did,
            vehicle_did,
            vehicle_wallet_did,
            registration.make,
            registration.model,
            registration.year,
            registration.vin
        )
        
        # Create vehicle wallet
        wallet = wallet_service.create_wallet(vehicle_did, "vehicle")
        
        return {
            "status": "success",
            "vehicle_did": vehicle_did,
            "wallet_did": vehicle_wallet_did,
            "tx_hash": tx_hash
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/verify-did")
async def verify_did_endpoint(did: str):
    """Verify if a DID is valid - public endpoint for login"""
    try:
        # Get DID document
        doc = blockchain_service.is_valid_did(did)
        if doc:
            return {"status": "valid", "did": did}
        raise HTTPException(status_code=401, detail="Invalid DID")
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.get("/did-document/{did}")
async def get_did_document(did: str):
    """Get the DID document for a DID"""
    try:
        doc = did_service.get_did_document(did)
        if not doc:
            raise HTTPException(status_code=404, detail="DID document not found")
        return doc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/entity/{did}")
async def get_entity(did: str):
    """Get entity information by DID"""
    # try:
    print(f"Getting entity for DID: {did}")
    # First check if DID is valid
    doc = blockchain_service.is_valid_did(did)
    if not doc:
        raise HTTPException(status_code=404, detail="DID not found")
        
    # Get entity from blockchain
    entity = blockchain_service.get_registered_users()
    if not entity:
        # If not found in blockchain, check if it's a new registration
        return {
            "type": "unknown",
            "name": "Unknown Entity",
            "address": "",
            "did": did
        }
    for user in entity:
        if user['did'] == did:
            print(f"Entity from blockchain: {entity}")
            return user
    return None    
    # except Exception as e:
    #     print(f"Error getting entity: {str(e)}")
    #     # Return a default entity rather than error
    #     return {
    #         "type": "unknown",
    #         "name": "Unknown Entity",
    #         "address": "",
    #         "did": did
    #     }

@app.post("/test-request-data")
async def request_data(request: DataRequest):
    """Send a data request from one entity to another"""
    
    # Generate request ID
    request_id = request.request_id        
    # Get DID documents
    sender_doc = did_service.get_did_document(request.sender_did)
    recipient_doc = did_service.get_did_document(request.recipient_did)
    if not sender_doc or not recipient_doc:
        raise HTTPException(status_code=400, detail="Invalid DIDs")
    
    # Create and encrypt DIDComm message
    didcomm_message = did_service.create_didcomm_message(
        sender_did=request.sender_did,
        recipient_did=request.recipient_did,
        message_type="request",
        body=request.dict()  # Convert Pydantic model to dict
    )
    
    encrypted_message = did_service.encrypt_didcomm_message(
        didcomm_message,
        sender_doc["authentication"][0],
        recipient_doc["authentication"][0]
    )
    
    # Store in both wallets
    wallet_service.store_didcomm_message(request.sender_did, encrypted_message.copy())
    wallet_service.store_didcomm_message(request.recipient_did, encrypted_message.copy())
    
    # Record on blockchain
    sender_address = blockchain_service.get_address_by_did(request.sender_did)
    recipient_address = blockchain_service.get_address_by_did(request.recipient_did)
    
    tx_hash = did_service.record_interaction(
        sender_address,
        recipient_address,
        request.sender_did,
        request.recipient_did,
        request.message_type,
        json.dumps(request.model_dump()).encode('utf-8')  # Convert to dict before dumping to JSON
    )
    if tx_hash:

    
        return {
            "status": "success",
            "request_id": request_id,
            "tx_hash": tx_hash
        }
    else:
        return "this is error"

# Data Request/Response Endpoints
@app.post("/request-data")
async def request_data(request: DataRequest, requester_did: str = Depends(verify_did)):
    """Send a data request from one entity to another"""
    if requester_did != request.sender_did:
        raise HTTPException(status_code=403, detail="DID mismatch")
    
    # Generate request ID
    request_id = request.request_id        
    # Get DID documents
    sender_doc = did_service.get_did_document(request.sender_did)
    recipient_doc = did_service.get_did_document(request.recipient_did)
    if not sender_doc or not recipient_doc:
        raise HTTPException(status_code=400, detail="Invalid DIDs")
    
    # Create and encrypt DIDComm message
    didcomm_message = did_service.create_didcomm_message(
        sender_did=request.sender_did,
        recipient_did=request.recipient_did,
        message_type="request",
        body=request.dict()  # Convert Pydantic model to dict
    )
    
    encrypted_message = did_service.encrypt_didcomm_message(
        didcomm_message,
        sender_doc["authentication"][0],
        recipient_doc["authentication"][0]
    )
    
    # Store in both wallets
    wallet_service.store_didcomm_message(request.sender_did, encrypted_message.copy())
    wallet_service.store_didcomm_message(request.recipient_did, encrypted_message.copy())
    
    # Record on blockchain
    sender_address = blockchain_service.get_address_by_did(request.sender_did)
    recipient_address = blockchain_service.get_address_by_did(request.recipient_did)
    
    tx_hash = did_service.record_interaction(
        sender_address,
        recipient_address,
        request.sender_did,
        request.recipient_did,
        request.message_type,
        json.dumps(request.model_dump()).encode('utf-8')  # Convert to dict before dumping to JSON
    )
    if tx_hash:

    
        return {
            "status": "success",
            "request_id": request_id,
            "tx_hash": tx_hash
        }
    else:
        return "this is error"

@app.post("/respond-to-req/{request_id}")
async def responed_to_req(request_id: str, response: DataResponse, responder_did: str = Depends(verify_did)):
    """Handle response to a data request"""
    if responder_did != response.sender_did:
        raise HTTPException(status_code=403, detail="DID mismatch")
    
    sender_address = blockchain_service.get_address_by_did(responder_did)
    recipient_address = blockchain_service.get_address_by_did(response.recipient_did)
    
    response_message = {
        **response.dict(),
        "timestamp": datetime.now().isoformat(),
        "interaction_type": "response"  # Explicitly set interaction type
    }
    
    tx_hash = did_service.record_interaction(
        sender_address,
        recipient_address,
        responder_did,
        response.recipient_did,
        "response",
        json.dumps(response_message).encode('utf-8')
    )
    
    if tx_hash:
        return {
            "status": "success",
            "tx_hash": tx_hash
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to record interaction")

def log_response(request_id, response_body, log_file="llm_response_log.json"):
    """Store or append logs in JSON format based on unique request_id."""
    
    # Load existing logs if the file exists
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            try:
                logs = json.load(f)
            except json.JSONDecodeError:
                logs = {}
    else:
        logs = {}
    
    # Append new response to the log
    logs[request_id] = response_body
    
    # Write back to the file
    with open(log_file, "w") as f:
        json.dump(logs, f, indent=4)

def respond_to_request(
    request,
    responder_did: str = Depends(verify_did)
):
    """Respond to a data request and log the response."""
    # logging.info("in respose to request")
    payload = request["payload"]
    payload = json.loads(payload)    
    
    # Create response body
    llm_approved, llm_reason = llm_service.evaluate_request(
        request
    )
    # logging.info(llm_approved, llm_reason)
    response_body = {
        **request,
        "timestamp": datetime.now().isoformat(),
        "llm_decision": llm_approved,
        "llm_reason": llm_reason,
    }

    
    # Extract information from LLM response
    decision_pattern = r'\*\*Decision:\*\* (approve|deny)\n'
    justification_pattern = r'\*\*Justification:\*\* (.+?)\n'
    wallet_approval_pattern = r'\*\*User Wallet Approval:\*\* (yes|no)'
    data_pattern = r'\*\*Return Requested Data:\*\* (.+?)\n'

    decision = re.search(decision_pattern, llm_reason, re.DOTALL | re.IGNORECASE)
    justification = re.search(justification_pattern, llm_reason, re.DOTALL)
    wallet_approval = re.search(wallet_approval_pattern, llm_reason, re.DOTALL | re.IGNORECASE)
    data_match = re.search(data_pattern, llm_reason, re.DOTALL)

    decision = decision.group(1).strip() if decision else "None"
    justification = justification.group(1).strip() if justification else None
    wallet_approval = wallet_approval.group(1).strip() if wallet_approval else "None"
    data_str = data_match.group(1).strip() if data_match else None
    
    try:
        data = json.loads(data_str) if data_str else {}
    except (json.JSONDecodeError, TypeError):
        data = {"raw": data_str} if data_str else {}
    
    if wallet_approval.lower() == "no" and decision.lower() == 'approve':
        response_data = {
            "request_id": payload['request_id'],
            "response_type": "approval",
            "data": data,
            "sender_did": responder_did,
            "recipient_did": request['source_identifier'],
        }
        
        # Record on blockchain
        sender_address = blockchain_service.get_address_by_did(responder_did)
        recipient_address = blockchain_service.get_address_by_did(request['source_identifier'])
        
        tx_hash = did_service.record_interaction(
            sender_address,
            recipient_address,
            responder_did,
            request['source_identifier'],
            "response",
            json.dumps(response_data).encode('utf-8')
        )
        data = {
            'response_data': response_data,
            'llm_decision': llm_approved,
            'llm_reason': llm_reason
        }
        
        if tx_hash:
            log_response(payload['request_id'], data)
            return {"status": "success"}
        else:
            return "this is error"
    else:
        # log_response(payload['request_id'], data)
        return response_body


@app.get("/wallet/{did}/requests")
async def get_wallet_requests(did: str = Depends(verify_did)):
    """Get all requests for a specific DID"""
    res = []
    requests = blockchain_service.get_entity_interactions(did)
    if not requests:
        return {"requests": []}
        
    for request in requests:
        # Only process incoming requests that haven't been processed
        if 'destination_identifier' in request:
            if (request['destination_identifier'] == did and 
                'llm_decision' not in request):
                processed_request = respond_to_request(request, did)
                if processed_request:
                    res.append(processed_request)
            # Include already processed requests
            elif (request['destination_identifier'] == did and 
                'llm_decision' in request):
                res.append(request)
            
    return {"requests": res}

    # except Exception as e:
    #     raise HTTPException(status_code=500, detail=str(e))

@app.get("/wallet/{did}/messages")
async def get_wallet_messages(did: str = Depends(verify_did)):
    """Get all DIDComm messages for a specific DID"""
    try:
        messages = blockchain_service.get_entity_interactions(did)
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/wallet/{did}/preferences")
async def get_wallet_preferences(did: str = Depends(verify_did)):
    """Get data sharing preferences for a specific DID"""
    try:
        with open(PREFERENCES_FILE, 'r') as f:
            all_preferences = json.load(f)
        
        # Get preferences for this specific DID
        did_preferences = all_preferences["preferences"].get(did, {})
        if not did_preferences:
            # Return default preferences if none are set
            return {
                "preferences": {
                    "speed": {"share_with": [], "requires_consent": True},
                    "location": {"share_with": [], "requires_consent": True},
                    "temperature": {"share_with": [], "requires_consent": True},
                    "fuel": {"share_with": [], "requires_consent": True},
                    "battery": {"share_with": [], "requires_consent": True}
                }
            }
        return {"preferences": did_preferences}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/wallet/{did}/preferences")
async def update_wallet_preferences(
    did: str,
    preferences: dict,
    authenticated_did: str = Depends(verify_did)
):
    """Update data sharing preferences for a specific DID"""
    if authenticated_did != did:
        raise HTTPException(status_code=403, detail="Not authorized to update preferences")
    
    try:
        with open(PREFERENCES_FILE, 'r') as f:
            all_preferences = json.load(f)
        
        # Initialize preferences for this DID if it doesn't exist
        if did not in all_preferences["preferences"]:
            all_preferences["preferences"][did] = {}
        
        # Get the data type and its new settings from the request
        data_type = next(iter(preferences["preferences"].keys()))
        new_settings = preferences["preferences"][data_type]
        
        # Update only the specific data type's preferences while preserving others
        all_preferences["preferences"][did][data_type] = new_settings
        
        # Write back all preferences
        with open(PREFERENCES_FILE, 'w') as f:
            json.dump(all_preferences, f, indent=4)
        
        return {"status": "success", "message": f"Preferences for {data_type} updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
