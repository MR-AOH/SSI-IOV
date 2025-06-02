import os
import json

def load_contract_abi():
    """Load the contract ABI from the JSON file."""
    try:
        # Get the path to the contract JSON file
        contract_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'build', 
            'contracts', 
            'SmartContract.json'
        )
        
        # Load and return the ABI
        with open(contract_path, 'r') as f:
            contract_json = json.load(f)
            return contract_json.get('abi', [])
    except Exception as e:
        print(f"Warning: Failed to load contract ABI: {str(e)}")
        return []
