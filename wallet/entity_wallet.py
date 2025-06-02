import random
import re, uuid
import streamlit as st
import requests
from datetime import datetime
import pandas as pd
import json
from typing import Optional, Dict, Any

class SmartCarSimulator:
    def __init__(self):
        self.sensors = {
            'gps': {'lat': 0, 'lon': 0},
            'speed': 0,
            'battery': 100,
            'temperature': 25,
            'fuel': 100
        }
    
    def update_sensors(self):
        """Update sensor values with realistic changes"""
        self.sensors['gps']['lat'] += random.uniform(-0.001, 0.001)
        self.sensors['gps']['lon'] += random.uniform(-0.001, 0.001)
        self.sensors['speed'] = max(0, min(120, self.sensors['speed'] + random.uniform(-5, 5)))
        self.sensors['battery'] = max(0, min(100, self.sensors['battery'] - random.uniform(0, 0.1)))
        self.sensors['temperature'] = max(15, min(35, self.sensors['temperature'] + random.uniform(-0.5, 0.5)))
        self.sensors['fuel'] = max(0, min(100, self.sensors['fuel'] - random.uniform(0, 0.2)))
        
class EntityWallet:
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self._initialize_session_state()
    
    def _initialize_session_state(self):
        """Initialize session state variables"""
        if 'did' not in st.session_state:
            st.session_state.did = None
        if 'auth_token' not in st.session_state:
            st.session_state.auth_token = None
        if 'entity_type' not in st.session_state:
            st.session_state.entity_type = None
    
    def _make_api_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Make authenticated API request."""
        headers = {"Authorization": f"Bearer {st.session_state.auth_token}"} if st.session_state.auth_token else {}
        
        # try:
        if method == "GET":
            response = requests.get(f"{self.api_url}{endpoint}", headers=headers)
        elif method == "POST":
            response = requests.post(f"{self.api_url}{endpoint}", json=data, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        # Raise an error for bad responses (4xx and 5xx)
        response.raise_for_status()
        
        # Return the JSON response if the request was successful
        return response.json()
        
        # except requests.exceptions.RequestException as e:
        #     st.error(f"API request failed: {str(e)}")
        #     # Optionally log the error or handle it differently
        #     return None  # Return None to indicate failure
    
    def render(self):
        """Render the wallet interface"""
        st.title("SSI Entity Wallet")
        
        # DID Authentication
        if not st.session_state.did:
            self._render_registration_or_login()
        else:
            self._render_wallet_interface()
    
    def _render_registration_or_login(self):
        """Render registration or login interface"""
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            self._render_login()
        
        with tab2:
            self._render_registration()
    
    def _render_registration(self):
        """Render the registration interface"""
        st.header("Register New Entity")
        
        name = st.text_input("Entity Name")
        entity_type = st.selectbox(
            "Entity Type",
            ["Individual", "Mechanic", "Insurance Provider", "Roadside Unit", "Vehicle Manufacturer"]
        )
        
        if st.button("Register"):
            if name and entity_type:
                try:
                    response = self._make_api_request(
                        "POST",
                        "/register-entity",
                        {
                            "name": name,
                            "entity_type": entity_type,
                        }
                    )
                    st.write(response)
                    if response.get("status") == "success":
                        st.session_state.did = response["entity_did"]
                        st.session_state.auth_token = response["entity_did"]
                        st.session_state.entity_type = entity_type
                        st.success(f"Successfully registered! Your DID: {response['entity_did']}")
                        st.info("Please save your DID for future logins")
                        st.rerun()
                    else:
                        st.error("Registration failed")
                except Exception as e:
                    st.error(f"Registration failed: {str(e)}")
            else:
                st.warning("Please fill in all fields")
    
    def _render_login(self):
        """Render the login interface"""
        st.header("Login with DID")
        
        did = st.text_input("Enter your DID")
        if st.button("Login"):
            try:
                # First verify DID without auth
                response = requests.get(f"{self.api_url}/verify-did", params={"did": did})
                if response.status_code == 200 and response.json().get("status") == "valid":
                    # Get entity details
                    st.session_state.did = did
                    st.session_state.auth_token = did
                    
                    # Now we can make authenticated requests
                    entity = self._make_api_request("GET", f"/entity/{did}")
                    if entity:
                        st.session_state.entity_type = entity.get("type")
                        st.success("Successfully logged in!")
                        st.rerun()
                    else:
                        st.session_state.did = None
                        st.session_state.auth_token = None
                        st.error("Entity not found")
                else:
                    st.error("Invalid DID")
            except Exception as e:
                st.error(f"Login failed: {str(e)}")
    
    def _render_wallet_interface(self):
        """Render the main wallet interface"""
        x = st.session_state.did
        st.sidebar.success(f"Logged in as:")
        st.sidebar.text(x)
        st.sidebar.info(f"Entity Type: {st.session_state.entity_type}")
        # Initialize simulation components if not done
        if st.session_state.entity_type == 5:
            if 'simulators' not in st.session_state:
                st.session_state.simulators = {}
                st.session_state.simulators[st.session_state.did] = SmartCarSimulator()
        if st.sidebar.button("Logout"):
            st.session_state.did = None
            st.session_state.auth_token = None
            st.session_state.entity_type = None
            st.rerun()
        if st.button("Refresh"):
            st.rerun()
        
        # Create tabs for different wallet functions
        tabs = st.tabs(["Requests", "Messages", "Send Request", "Data Sharing", "Log"])
        # tabs = st.tabs(["Log"])
        
        with tabs[0]:
            self._render_requests_tab()
        
        with tabs[1]:
            self._render_messages_tab()
        
        with tabs[2]:
            self._render_send_request_tab()
        
        with tabs[3]:
            self._render_data_sharing_tab()
        with tabs[4]:
            self._render_log_tab()
    
    def _render_requests_tab(self):
        """Render the requests tab"""
        st.header("Pending Requests")
        
        # Get requests from API
        responses = self._make_api_request("GET", f"/wallet/{st.session_state.did}/requests")
        if not responses or not responses.get("requests"):
            st.info("No pending requests")
            return
        st.write(responses)    
        for response in responses["requests"]:
            if 'destination_identifier' in response:
                if (response['destination_identifier'] == st.session_state.did and 
                    response['interaction_type'] == 'request'):
                    payload = json.loads(response["payload"])
                    st.markdown("inside payload")
                    st.write(payload)
                    with st.expander(f"Request from {response['source_identifier']}"):
                        st.write("**Type:** ", response['interaction_type'])
                        st.write("**Content:** ", payload['content'])
                        st.write("**Requested Data:** ", ", ".join(payload['requested_data']))
                        st.write("**Emergency:** ", "Yes" if payload['is_emergency'] else "No")
                        
                        if 'llm_reason' in response:
                            llm_reason = response['llm_reason']
                        # Extract LLM decision information
                        decision_pattern = r'\*\*Decision:\*\* (approve|deny)\n'
                        justification_pattern = r'\*\*Justification:\*\* (.+?)\n'
                        wallet_approval_pattern = r'\*\*User Wallet Approval:\*\* (yes|no)'
                        data_pattern = r'\*\*Return Requested Data:\*\* (.+?)\n'

                        decision = re.search(decision_pattern, llm_reason, re.DOTALL | re.IGNORECASE)
                        justification = re.search(justification_pattern, llm_reason, re.DOTALL)
                        wallet_approval = re.search(wallet_approval_pattern, llm_reason, re.DOTALL | re.IGNORECASE)
                        data = re.search(data_pattern, llm_reason, re.DOTALL)

                        decision = decision.group(1).strip() if decision else "None"
                        justification = justification.group(1).strip() if justification else None
                        wallet_approval = wallet_approval.group(1).strip() if wallet_approval else "None"
                        data = data.group(1).strip() if data else None
                        
                        st.write("**LLM Decision:** ", decision)
                        st.write("**LLM Reason:** ", justification)
                        st.write("**User Wallet Approval:** ", wallet_approval)
                        st.write("**Data:** ", data)

                        col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Approve", key=f"approve_{payload['request_id']}"):
                            response_data = {
                                "request_id": payload['request_id'],
                                "response_type": "approval",
                                "reason": "Request Approved by User",
                                "data": {
                                    "requested_data": payload['requested_data'],
                                    "values": data if data else {}
                                },
                                "sender_did": st.session_state.did,
                                "recipient_did": response['source_identifier']
                            }
                            resp = self._make_api_request(
                                "POST",
                                f"/respond-to-req/{payload['request_id']}",
                                response_data
                            )
                            if resp and resp.get("status") == "success":
                                st.success("Request approved")
                                st.rerun()
                            else:
                                st.error("Failed to approve request")
                    
                    with col2:
                        if st.button("Reject", key=f"reject_{payload['request_id']}"):
                            response_data = {
                                "request_id": payload['request_id'],
                                "response_type": "rejection",
                                "reason": "Request Rejected by User",
                                "sender_did": st.session_state.did,
                                "recipient_did": response['source_identifier']
                            }
                            resp = self._make_api_request(
                                "POST",
                                f"/respond-to-req/{payload['request_id']}",
                                response_data
                            )
                            if resp and resp.get("status") == "success":
                                st.success("Request rejected")
                                st.rerun()
                            else:
                                st.error("Failed to reject request")

    def _render_messages_tab(self):
        """Render the messages tab"""
        st.header("Messages")
        
        # Get messages from API
        response = self._make_api_request("GET", f"/wallet/{st.session_state.did}/messages")
        messages = response.get("messages", [])
        # st.write(messages)
        if not messages:
            st.info("No messages")
            return

        # Group messages by request_id
        message_pairs = {}
        for message in messages:
            try:
                payload = json.loads(message['payload'])
                request_id = payload.get('request_id')
                if request_id:
                    if request_id not in message_pairs:
                        message_pairs[request_id] = {'request': None, 'response': None}
                    
                    if message['interaction_type'] != 'response':
                        message_pairs[request_id]['request'] = message
                    elif message['interaction_type'] == 'response':
                        message_pairs[request_id]['response'] = message
                    # elif message['interaction_type'] == 'history':
                    #     message_pairs[request_id]['history'] = message
            except json.JSONDecodeError:
                continue

        # Display message pairs
        for request_id, pair in message_pairs.items():
            st.markdown("---")
            st.markdown(f"### Interaction ID: {request_id}")
            # st.write(pair)
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### Request")
                if pair['request']:
                    req = pair['request']
                    try:
                        req_payload = json.loads(req['payload'])
                        st.write(f"**From:**")
                        # st.json(prev_owners)
                        st.text(req['source_identifier'])
                    
                        dt_object = datetime.fromtimestamp(req['timestamp'])
                        st.markdown(f"**Time:** {dt_object.strftime('%Y-%m-%d %H:%M:%S')}")
                        st.markdown(f"**Type:** {req_payload.get('message_type', 'N/A')}")
                        st.markdown(f"**Content:** {req_payload.get('content', 'N/A')}")
                        if 'requested_data' in req_payload:
                            st.markdown(f"**Requested Data:** {', '.join(req_payload['requested_data'])}")
                        st.markdown(f"**Emergency:** {'Yes' if req_payload.get('is_emergency') else 'No'}")
                    except json.JSONDecodeError:
                        st.error("Error parsing request payload")
                else:
                    st.info("No request found")

            with col2:
                st.markdown("#### Response")
                # st.write(pair)
                # st.write(pair['response'])
                if pair['response']:
                    resp = pair['response']
                    try:
                        resp_payload = json.loads(resp['payload'])
                        st.write(f"**To:**")
                        # st.json(prev_owners)
                        st.text(req['source_identifier'])
                        dt_object = datetime.fromtimestamp(resp['timestamp'])
                        st.markdown(f"**Time:** {dt_object.strftime('%Y-%m-%d %H:%M:%S')}")
                        st.markdown(f"**Type:** {resp_payload.get('response_type', 'N/A')}")
                        
                        if 'llm_reason' in resp:
                            st.markdown("**LLM Analysis:**")
                            st.markdown(resp['llm_reason'])
                        
                        if 'data' in resp_payload:
                            st.markdown("**Shared Data:**")
                            if isinstance(resp_payload['data'], str):
                                try:
                                    # Try to parse the data if it's a string
                                    data = json.loads(resp_payload['data'])
                                    st.json(data)
                                except json.JSONDecodeError:
                                    st.write(resp_payload['data'])
                            else:
                                st.json(resp_payload['data'])
                        
                        if 'reason' in resp_payload:
                            st.markdown(f"**Reason:** {resp_payload['reason']}")
                    except json.JSONDecodeError:
                        st.error("Error parsing response payload")
                else:
                    st.info("Awaiting response")
            
            # if pair['history']:
            #     response = pair['history']
            #     st.write(response)
            #     if 'llm_reason' in response:
            #         llm_reason = response['llm_reason']
            #         # Extract LLM decision information
            #         decision_pattern = r'\*\*Decision:\*\* (approve|deny)\n'
            #         justification_pattern = r'\*\*Justification:\*\* (.+?)\n'
            #         wallet_approval_pattern = r'\*\*User Wallet Approval:\*\* (yes|no)'
            #         data_pattern = r'\*\*Return Requested Data:\*\* (.+?)\n'

            #         decision = re.search(decision_pattern, llm_reason, re.DOTALL | re.IGNORECASE)
            #         justification = re.search(justification_pattern, llm_reason, re.DOTALL)
            #         wallet_approval = re.search(wallet_approval_pattern, llm_reason, re.DOTALL | re.IGNORECASE)
            #         data = re.search(data_pattern, llm_reason, re.DOTALL)

            #         decision = decision.group(1).strip() if decision else "None"
            #         justification = justification.group(1).strip() if justification else None
            #         wallet_approval = wallet_approval.group(1).strip() if wallet_approval else "None"
            #         data = data.group(1).strip() if data else None
                    
            #         st.write("**LLM Decision:** ", decision)
            #         st.write("**LLM Reason:** ", justification)
            #         st.write("**User Wallet Approval:** ", wallet_approval)
            #         st.write("**Data:** ", data)


    def _render_send_request_tab(self):
        """Render the send request tab"""
        st.header("Send Data Request")
        
        recipient_did = st.text_input("Recipient DID")
        message_type = st.selectbox(
            "Request Type",
            ["Traffic Data Request", "Emergency Alert", "Road Condition Check", "Weather Data Request", "Custom Request"]
        )
        content = st.text_area("Request Details")
        requested_data = st.multiselect(
            "Request Data Types",
            ["speed", "location", "temperature", "fuel", "battery"]
        )
        is_emergency = st.checkbox("Mark as Emergency Request")
        if st.button("Send Request"):
            if recipient_did and message_type and content and requested_data:
                request_id = str(uuid.uuid4())
                request_data = {
                    "request_id":  str(request_id),
                    "message_type": message_type,
                    "content": content,
                    "requested_data": requested_data,  # Now sending as a list directly
                    "is_emergency": is_emergency,
                    "sender_type": str(st.session_state.entity_type),
                    "sender_did": str(st.session_state.did),
                    "recipient_did": recipient_did,
                    "time":  str(datetime.now().strftime("%Y-%m-%d %H:%M"))
                }
                st.write(request_data)
                # json_string = json.dumps(request_data)
                response = self._make_api_request("POST", "/request-data", request_data)
                st.write(response)
                if response and response.get("status") == "success":
                    st.success(f"Request sent! ID: {response.get('request_id')}")
                else:
                    st.error("Failed to send request")
            else:
                st.warning("Please fill in all required fields")


    
    def _render_data_sharing_tab(self, did=None):
        """Render the data sharing preferences tab"""
        st.header("Data Sharing Preferences")
        if did is None:
            did = st.session_state.did

        # Get current preferences from API
        response = self._make_api_request("GET", f"/wallet/{did}/preferences")
        if not response:
            st.error("Failed to fetch preferences. Please try again later.")
            return
        
        preferences = response.get("preferences", {})
        
        data_types = ["speed", "location", "temperature", "fuel", "battery"]
        entity_types = ["emergency", "roadside_unit", "vehicle", "service", "insurance", "mechanic"]
        
        for data_type in data_types:
            st.write(f"\n{data_type.title()} Sharing Policy:")
            current_prefs = preferences.get(data_type, {})
            share_with = st.multiselect(
                f"Share {data_type} with:",
                entity_types,
                default=current_prefs.get("share_with", []),
                key=f"policy_{data_type}"
            )
            requires_consent = st.checkbox(
                f"Require consent for {data_type}",
                value=current_prefs.get("requires_consent", True),
                key=f"consent_{data_type}"
            )
            
            if st.button(f"Update {data_type} Policy"):
                update_response = self._make_api_request(
                    "POST",
                    f"/wallet/{st.session_state.did}/preferences",
                    {
                        "preferences": {
                            data_type: {
                                "share_with": share_with,
                                "requires_consent": requires_consent
                            }
                        }
                    }
                )
                if update_response and update_response.get("status") == "success":
                    st.success(f"Updated {data_type} sharing policy")
                else:
                    st.error(f"Failed to update {data_type} policy")

    def _render_log_tab(self, did=None):
        # st.write("Log Tab")

        # Load JSON data
        with open(r'C:\Users\User\Desktop\ssi-iov-final\llm_response_log.json', 'r') as file:
            data = json.load(file)

        # Extract relevant information
        log_entries = []
        for request_id, entry in data.items():
            response_data = entry['response_data']
            llm_reason = entry['llm_reason']
            
            # Extract justification from llm_reason
            justification_lines = llm_reason.split('\n')
            justification = ''
            for line in justification_lines:
                if line.startswith('2. **Justification:**'):
                    justification = line.replace('2. **Justification:**', '').strip()
                    break
            
            log_entry = {
                'ID': request_id,
                'Response Type': response_data['response_type'],
                'Data': response_data['data']['raw'],
                'Justification': justification
            }
            
            log_entries.append(log_entry)

        # # Create a DataFrame
        df = pd.DataFrame(log_entries)
        # for index, row in df.iterrows():
        #     st.write(f"**ID:** {row['ID']}")
        #     st.write(f"**Response Type:** {row['Response Type']}")
        #     st.write(f"**Data:** {row['Data']}")
        #     st.write(f"**Justification:**")
        #     st.text_area(label="", value=row['Justification'], height=200, disabled=True)
        #     st.markdown("---")
        # Display in Streamlit

        st.title("Log Table")
   
        st.write(df)
       


def main():
    wallet = EntityWallet()
    wallet.render()

if __name__ == "__main__":
    main()
