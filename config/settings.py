# config/settings.py
import os
import json
from dotenv import load_dotenv
# from sqlalchemy import false, true

load_dotenv()

class Settings:
    TRUVITY_API_KEY = os.getenv('TRUVITY_API_KEY', '')
    BLOCKCHAIN_URL = os.getenv('BLOCKCHAIN_URL', 'http://127.0.0.1:7545')
    CONTRACT_ADDRESS = os.getenv('SMART_CONTRACT_ADDRESS', '')
    ACCOUNT = os.getenv('BLOCKCHAIN_ACCOUNT', '')
    PRIVATE_KEY = os.getenv('BLOCKCHAIN_PRIVATE_KEY', '')
    ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', os.urandom(32))

class BlockchainConfig:
    # Load ABI from contract JSON file
    CONTRACT_JSON_PATH = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 
        'build', 
        'contracts', 
        'SmartContract.json'
    )
    
    try:
        with open(CONTRACT_JSON_PATH, 'r') as f:
            contract_json = json.load(f)
            ABI = contract_json.get('abi', [])
    except Exception as e:
        print(f"Warning: Failed to load contract ABI: {str(e)}")
        ABI = []