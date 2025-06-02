import json
import os
from pathlib import Path
import google.generativeai as genai
from typing import Dict, Any, Optional
from services.blockchain_service import BlockchainService
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

PREFERENCES_FILE = Path(__file__).parent.parent / "api/wallet_preferences.json"

class LLMService:
    def __init__(self, api_key=None, use_local_model=True, local_model_path=None):
        """
        Initialize the LLM service with support for both local Llama model and Google's Generative AI
        
        Args:
            api_key: Google API key for authentication (will load from .env if not provided)
            use_local_model: Whether to try using local Llama model first
            local_model_path: Path to local Llama model (optional)
        """
        self.blockchain = BlockchainService()
        self.model = None
        self.model_type = None
        
        # Try to initialize local model first if requested
        if use_local_model:
            local_model_path = os.getenv('LOCAL_MODEL_PATH')
            if local_model_path is not None:
                try:
                    self._initialize_local_model(local_model_path)
                except Exception as e:
                    print(f"Failed to initialize local model: {e}")
                    print("Falling back to Google Generative AI...")
            else:
                print("Local model path not provided. Falling back to Google Generative AI...")
        # If local model failed or not requested, use Google API
        if self.model is None:
            self._initialize_google_api(api_key)

    def _initialize_local_model(self, local_model_path=None):
        """Initialize local Llama 3.2 3B model"""
        try:
            # Try importing transformers and torch
            from transformers import AutoTokenizer, AutoModelForCausalLM
            import torch
            
            # Default model name for Llama 3.2 3B
            model_name = local_model_path
            
            print(f"Loading local model: {model_name}")
            
            # Check if CUDA is available
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"Using device: {device}")
            
            # Load tokenizer and model
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                trust_remote_code=True
            )
            
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                device_map="auto" if device == "cuda" else None,
                trust_remote_code=True
            )
            
            if device == "cpu":
                self.model = self.model.to(device)
            
            self.model_type = "local"
            print("Local Llama model initialized successfully!")
            
        except ImportError as e:
            raise Exception(f"Required packages not installed. Please install: pip install transformers torch accelerate. Error: {e}")
        except Exception as e:
            raise Exception(f"Failed to load local model: {e}")

    def _initialize_google_api(self, api_key=None):
        """Initialize Google Generative AI model"""
        try:
            # Get API key from parameter, environment variable, or use default
            if api_key is None:
                api_key = os.getenv('GOOGLE_API_KEY')
            
            
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            self.model_type = "google"
            print("Google Generative AI model initialized successfully!")
            
        except Exception as e:
            raise Exception(f"Failed to initialize Google API: {e}")

    def _generate_with_local_model(self, prompt):
        """Generate response using local Llama model"""
        try:
            # Prepare the input with proper chat template
            messages = [
                {"role": "system", "content": "You are a helpful AI assistant that evaluates data sharing requests in IoV-SSI context."},
                {"role": "user", "content": prompt}
            ]
            
            # Apply chat template
            input_text = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            
            # Tokenize input
            inputs = self.tokenizer(input_text, return_tensors="pt")
            
            # Move to same device as model
            if hasattr(self.model, 'device'):
                inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
            
            # Generate response
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=512,
                    temperature=0.7,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            # Decode response
            response = self.tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
            return response.strip()
            
        except Exception as e:
            print(f"Error generating with local model: {e}")
            raise

    def _generate_with_google_api(self, prompt):
        """Generate response using Google API"""
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Error generating with Google API: {e}")
            raise

    def get_prefrences(self, did):
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
    
    def evaluate_request(self, request):
        try:
            vehicle_sensor_data = {
                "engine_temperature": 95,  # Degrees Celsius
                "tire_pressure_front_left": 32,  # PSI
                "speed": 60,  # km/h
                "location": {"latitude": 34.0522, "longitude": -118.2437},
                "diagnostic_codes": ["P0128", "C1234"],  # Example DTCs (Diagnostic Trouble Codes)
                "battery": '80%'
            }
            
            dest_did = request.get('destination_identifier', 'Unknown')
            print(f"Destination DID: {dest_did}")
            user_pref = self.get_prefrences(dest_did)
            prompt = self.craft_prompt(request, vehicle_sensor_data, user_pref)
            
            # Generate response based on model type
            if self.model_type == "local":
                response_text = self._generate_with_local_model(prompt)
            else:
                response_text = self._generate_with_google_api(prompt)
            
            decision_text = response_text.lower()
            is_approved = "approve" in decision_text or "approved" in decision_text
            
            return is_approved, response_text
            
        except Exception as e:
            print(f"Error in LLM evaluation: {e}")
            return False, "Error in request evaluation"
        
    def craft_prompt(self, request, vehicle_sensor_data, user_prefrence):
        """Crafts an LLM prompt to evaluate a data sharing request in an IoV-SSI context.

        Args:
            request (dict): The data sharing request object.
            vehicle_sensor_data (dict): A dictionary containing the current vehicle sensor information.

        Returns:
            str: The crafted prompt for the LLM.
        """

        try:
            payload = request["payload"]
            if not payload:
                return "Error: Payload missing from the request."

            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError) as e:
            return f"Error: Invalid payload format. {e}"

        source_did = request['source_identifier']
        source_address = request['source_address']
        sender_type_code = int(payload['sender_type'])  

        # Map numerical type codes to human-readable names
        type_mapping = {
            0: "Individual",
            1: "Mechanic",
            2: "Insurance Provider",
            3: "Roadside Unit",
            4: "Vehicle Manufacturer",
            5: "Car"
        }
       
        sender_type = type_mapping.get(sender_type_code, f"Unknown (code: {sender_type_code})")

        prompt = f"""Evaluate this data sharing request in the IoV-SSI context:

        **Data Sharing Request:**
        {request}

        **Request Origin:**
        - Source DID: {source_did}
        - Source Address: {source_address}
        - Sender Type: {sender_type}

        **Current User Wallet Configuration:**
        {user_prefrence}
        "Make sure to follow these whenever you decide to either send request to user wallet for consent/approval or not"

        **Current Vehicle Sensor Information:**
        {vehicle_sensor_data}

        **Contextual Notes based on Requester Type:**

        """

        if sender_type == "Mechanic":
            prompt += """
            - **MECHANIC REQUEST:** This request is from a mechanic.  It's crucial to understand the necessity of the requested data for vehicle diagnostics and repair.  Prioritize requests that directly relate to identified issues or safety concerns. Consider if access to specific sensor data could help prevent future problems or improve vehicle performance.  If the requested data appears excessive or unrelated to the stated purpose, carefully evaluate the justification.  Suggestions about the issue the request is likely for based on sensor data should be mentioned.
            """
        elif sender_type == "Insurance Provider":
            prompt += """
            - **INSURANCE PROVIDER REQUEST:**  Insurance providers often request data for risk assessment, claims processing, or usage-based insurance programs.  Ensure that the data requested is directly relevant to the insurance policy and that user consent is explicitly documented.  Be wary of requests for highly granular location data or personal driving behavior that may infringe on user privacy.
            """
        elif sender_type == "Roadside Unit":
            prompt += """
            - **ROADSIDE UNIT REQUEST:** Roadside Units (RSUs) typically request data for traffic management, safety alerts, or infrastructure monitoring. Verify the RSU's authenticity using its DID. Allow sharing of non-sensitive data that can improve road safety, but require explicit consent for location tracking or personal information.
            """
        elif sender_type == "Vehicle Manufacturer":
            prompt += """
            - **VEHICLE MANUFACTURER REQUEST:** Vehicle manufacturers may request data for research and development, over-the-air updates, or remote diagnostics. Strictly verify the manufacturer's DID and ensure that the data request aligns with the user's data sharing preferences. Be cautious of requests for data that could be used to track or profile individual drivers.
            """
        elif sender_type == "Car":
            prompt += """
            - **VEHICLE-TO-VEHICLE REQUEST:**  Evaluate the request in the context of vehicle-to-vehicle (V2V) communication. Both vehicles should have valid DIDs. Share only necessary safety-related data, such as speed, location, and braking status, to prevent collisions.  Respect privacy settings of both parties.
            """

        else:
            prompt += """
            - **REQUEST FROM AN INDIVIDUAL/UNKNOWN:**  A request is being made from an individual or an unknown requester type.  Ensure a high level of security and data minimisation.  Strictly verify identity and ask for further clarification and consent.

            """

        prompt += f"""

        **Relevant Vehicle Sensor Information:**
        - {vehicle_sensor_data}

        **IoV-SSI Principles to Consider:**
        1. Decentralized Identity Verification
        2. User Consent and Control
        3. Privacy Protection
        4. Selective Disclosure
        5. Zero-Knowledge Proofs when applicable

        **Evaluation Rules:**
        1. Emergency Services:
        - In emergencies, recommend approval for critical data unless car meets an accident, but maintain minimal necessary disclosure.
        2. RSU Interactions:
        - Verify RSU authenticity via DID.
        - Allow sharing of non-sensitive data.
        - Require consent for location tracking.
        3. Vehicle-to-Vehicle:
        - Both vehicles must have valid DIDs.
        - Share only necessary safety-related data.
        - Respect privacy settings of both parties.
        4. Service Providers:
        - Strict verification of service provider DID.
        - Only share data specified in user policy.
        - Require explicit consent for maintenance data.

        **Respond with (Concise and Structured):**
        1. Decision (approve/deny)
        2. Justification (Based on SSI principles, requester type, sensor data, and evaluation rules) 
        3. Recommended Data Access Scope (Specify which data elements should be shared if approved, or suggest a more limited scope)
        4. User Wallet Approval (yes/no) 
        5. Return Requested Data:  Based on the request return the data asked

        Note: User Wallet Approval = user consent, it will be based on wallet configuration and you will take approval unless its a life threating situation like accident and for accident you first confirm with other car sensor data then decide.
        """

        return prompt













# if the above code is not working, you can use the below code snippet to implement the LLMService class using Google Generative AI.





# import json
# from pathlib import Path
# import google.generativeai as genai
# from typing import Dict, Any, Optional
# from services.blockchain_service import BlockchainService
# from dotenv import load_dotenv

# # Load environment variables
# load_dotenv()


# PREFERENCES_FILE = Path(__file__).parent.parent / "api/wallet_preferences.json"
# class LLMService:
#     def __init__(self, api_key=None):
#         """
#         Initialize the LLM service with Google's Generative AI
        
#         Args:
#             api_key: Google API key for authentication
#         """
#         api_key = os.getenv('GOOGLE_API_KEY')
#         genai.configure(api_key=api_key)
#         self.model = genai.GenerativeModel('gemini-1.5-flash')
#         self.blockchain = BlockchainService()

#     def get_prefrences(self, did):
#         with open(PREFERENCES_FILE, 'r') as f:
#             all_preferences = json.load(f)
        
#         # Get preferences for this specific DID
#         did_preferences = all_preferences["preferences"].get(did, {})
#         if not did_preferences:
#             # Return default preferences if none are set
#             return {
#                 "preferences": {
#                     "speed": {"share_with": [], "requires_consent": True},
#                     "location": {"share_with": [], "requires_consent": True},
#                     "temperature": {"share_with": [], "requires_consent": True},
#                     "fuel": {"share_with": [], "requires_consent": True},
#                     "battery": {"share_with": [], "requires_consent": True}
#                 }
#             }
#         return {"preferences": did_preferences}
    
#     def evaluate_request(self, request):
#         try:
#             vehicle_sensor_data = {
#                 "engine_temperature": 95,  # Degrees Celsius
#                 "tire_pressure_front_left": 32,  # PSI
#                 "speed": 60,  # km/h
#                 "location": {"latitude": 34.0522, "longitude": -118.2437},
#                 "diagnostic_codes": ["P0128", "C1234"],  # Example DTCs (Diagnostic Trouble Codes)
#                 "battery": '80%'
#             }
#             # payload = response["payload"]
#             # payload = json.loads(payload)
#             dest_did = request.get('destination_identifier', 'Unknown')
#             print(f"Destination DID: {dest_did}")
#             user_pref = self.get_prefrences(dest_did)
#             prompt = self.craft_prompt(request, vehicle_sensor_data, user_pref)
#             response = self.model.generate_content(prompt)
#             decision_text = response.text.lower()
            
#             is_approved = "approve" in decision_text or "approved" in decision_text
#             return is_approved, response.text
#         except Exception as e:
#             print(f"Error in LLM evaluation: {e}")
#             return False, "Error in request evaluation"
        
#     def craft_prompt(self,request, vehicle_sensor_data, user_prefrence):
#         """Crafts an LLM prompt to evaluate a data sharing request in an IoV-SSI context.

#         Args:
#             request (dict): The data sharing request object.
#             vehicle_sensor_data (dict): A dictionary containing the current vehicle sensor information.

#         Returns:
#             str: The crafted prompt for the LLM.
#         """

#         try:
#             payload = request["payload"]
#             # payload = json.loads(payload)
#             if not payload:
#                 return "Error: Payload missing from the request."

#             payload = json.loads(payload)
#         except (json.JSONDecodeError, TypeError) as e:
#             return f"Error: Invalid payload format. {e}"

#         source_did = request['source_identifier']
#         source_address = request['source_address']
#         sender_type_code = int(payload['sender_type'])  

#         # Map numerical type codes to human-readable names
#         type_mapping = {
#             0: "Individual",
#             1: "Mechanic",
#             2: "Insurance Provider",
#             3: "Roadside Unit",
#             4: "Vehicle Manufacturer",
#             5: "Car"
#         }
#         # sender_type = self.blockchain._get_user_type_name(sender_type_code)
       
#         sender_type = type_mapping.get(sender_type_code, f"Unknown (code: {sender_type_code})")  # Get the sender type or "Unknown"

#         prompt = f"""Evaluate this data sharing request in the IoV-SSI context:

#         **Data Sharing Request:**
#         {request}

#         **Request Origin:**
#         - Source DID: {source_did}
#         - Source Address: {source_address}
#         - Sender Type: {sender_type}

#         **Current User Wallet Configuration:**
#         {user_prefrence}
#         "Make sure to follow these whenever you decide to either send request to user wallet for consent/approval or not"

#         **Current Vehicle Sensor Information:**
#         {vehicle_sensor_data}

#         **Contextual Notes based on Requester Type:**

#         """

#         if sender_type == "Mechanic":
#             prompt += """
#             - **MECHANIC REQUEST:** This request is from a mechanic.  It's crucial to understand the necessity of the requested data for vehicle diagnostics and repair.  Prioritize requests that directly relate to identified issues or safety concerns. Consider if access to specific sensor data could help prevent future problems or improve vehicle performance.  If the requested data appears excessive or unrelated to the stated purpose, carefully evaluate the justification.  Suggestions about the issue the request is likely for based on sensor data should be mentioned.
#             """
#         elif sender_type == "Insurance Provider":
#             prompt += """
#             - **INSURANCE PROVIDER REQUEST:**  Insurance providers often request data for risk assessment, claims processing, or usage-based insurance programs.  Ensure that the data requested is directly relevant to the insurance policy and that user consent is explicitly documented.  Be wary of requests for highly granular location data or personal driving behavior that may infringe on user privacy.
#             """
#         elif sender_type == "Roadside Unit":
#             prompt += """
#             - **ROADSIDE UNIT REQUEST:** Roadside Units (RSUs) typically request data for traffic management, safety alerts, or infrastructure monitoring. Verify the RSU's authenticity using its DID. Allow sharing of non-sensitive data that can improve road safety, but require explicit consent for location tracking or personal information.
#             """
#         elif sender_type == "Vehicle Manufacturer":
#             prompt += """
#             - **VEHICLE MANUFACTURER REQUEST:** Vehicle manufacturers may request data for research and development, over-the-air updates, or remote diagnostics. Strictly verify the manufacturer's DID and ensure that the data request aligns with the user's data sharing preferences. Be cautious of requests for data that could be used to track or profile individual drivers.
#             """
#         elif sender_type == "Car":
#             prompt += """
#             - **VEHICLE-TO-VEHICLE REQUEST:**  Evaluate the request in the context of vehicle-to-vehicle (V2V) communication. Both vehicles should have valid DIDs. Share only necessary safety-related data, such as speed, location, and braking status, to prevent collisions.  Respect privacy settings of both parties.
#             """

#         else:
#             prompt += """
#             - **REQUEST FROM AN INDIVIDUAL/UNKNOWN:**  A request is being made from an individual or an unknown requester type.  Ensure a high level of security and data minimisation.  Strictly verify identity and ask for further clarification and consent.

#             """


#         prompt += f"""

#         **Relevant Vehicle Sensor Information:**
#         - {vehicle_sensor_data}


#         **IoV-SSI Principles to Consider:**
#         1. Decentralized Identity Verification
#         2. User Consent and Control
#         3. Privacy Protection
#         4. Selective Disclosure
#         5. Zero-Knowledge Proofs when applicable

#         **Evaluation Rules:**
#         1. Emergency Services:
#         - In emergencies, recommend approval for critical data unless car meets an accident, but maintain minimal necessary disclosure.
#         2. RSU Interactions:
#         - Verify RSU authenticity via DID.
#         - Allow sharing of non-sensitive data.
#         - Require consent for location tracking.
#         3. Vehicle-to-Vehicle:
#         - Both vehicles must have valid DIDs.
#         - Share only necessary safety-related data.
#         - Respect privacy settings of both parties.
#         4. Service Providers:
#         - Strict verification of service provider DID.
#         - Only share data specified in user policy.
#         - Require explicit consent for maintenance data.


#         **Respond with (Concise and Structured):**
#         1. Decision (approve/deny)
#         2. Justification (Based on SSI principles, requester type, sensor data, and evaluation rules) 
#         3. Recommended Data Access Scope (Specify which data elements should be shared if approved, or suggest a more limited scope)
#         4. User Wallet Approval (yes/no) 
#         5. Return Requested Data:  Based on the request return the data asked

#         Note: User Wallet Approval = user consent, it will be based on wallet configuration and you will take approval unless its a life threating situation like accident and for accident you first confirm with other car sensor data then decide.
#         """

#         return prompt

    

        