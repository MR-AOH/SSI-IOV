import streamlit as st
import json
from datetime import datetime
from services.blockchain_service import BlockchainService
from services.did_services import DIDService
from services.wallet_service import WalletService
from services.llm_service import LLMService
from services.simulation_service import SimulationService, Entity, Position
import uuid
import random

#import pages
from pages.home_page import HomePage
from pages.create_did_page import CreateDIDPage
from pages.register_vehicle_page import RegisterVehiclePage
from pages.vehicle_inspection_page import VehicleInspectionPage
from pages.wallet import RenderWalletUI
from wallet.entity_wallet import EntityWallet

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

class SSIWallet:
    def __init__(self, did: str, entity_type: str):
        self.did = did
        self.entity_type = entity_type
        self.policies = {
            'gps': {'share_with': [], 'requires_consent': True},
            'speed': {'share_with': [], 'requires_consent': True},
            'battery': {'share_with': [], 'requires_consent': True},
            'temperature': {'share_with': [], 'requires_consent': True},
            'fuel': {'share_with': [], 'requires_consent': True}
        }
        self.pending_approvals = {}
        self.credentials = []
        self.blocked_users = []
    
    def update_policy(self, data_type: str, policy: dict):
        """Update data sharing policy"""
        if data_type in self.policies:
            self.policies[data_type] = policy
            return True
        return False
    
    def check_permission(self, requester_type: str, data_type: str) -> bool:
        """Check if requester has permission to access data"""
        if data_type in self.policies:
            return requester_type in self.policies[data_type]['share_with']
        return False
    
    def request_approval(self, data_type: str, requester: str, is_emergency: bool = False) -> str:
        """Request approval for data access"""
        approval_id = f"{data_type}_{requester}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.pending_approvals[approval_id] = {
            "data_type": data_type,
            "requester": requester,
            "is_emergency": is_emergency,
            "status": "pending"
        }
        return approval_id
    
    def block_user(self, did: str, user_did: str, reason: str):
        """Block a user from accessing data"""
        self.blocked_users.append({
            "did": user_did,
            "blocked_at": datetime.now().isoformat(),
            "reason": reason
        })
    
    def unblock_user(self, did: str, user_did: str):
        """Unblock a user"""
        self.blocked_users = [user for user in self.blocked_users if user['did'] != user_did]
    
    def get_blocked_users(self, did: str):
        """Get list of blocked users"""
        return self.blocked_users

class IoVSSIPlatform:
    def __init__(self):
        """Initialize the IoV SSI Platform with required services."""
        self.blockchain_service = BlockchainService()
        self.did_service = DIDService()
        self.wallet_service = WalletService()
        self.llm_service = LLMService()
        self.simulation_service = SimulationService()
        self.wallet_polices = EntityWallet()
        
        # Initialize session state
        if 'simulation_running' not in st.session_state:
            st.session_state.simulation_running = False
        if 'notifications' not in st.session_state:
            st.session_state.notifications = {}
        if 'initialized_wallets' not in st.session_state:
            st.session_state.initialized_wallets = False
        
        # Set up simulation entities
        if not st.session_state.get('simulation_initialized', False):
            self._initialize_simulation()
            st.session_state.simulation_initialized = True

    def _initialize_simulation(self):
        """Initialize simulation with some example entities."""
        # Add some RSUs along the road
        rsu_positions = [100, 300, 500, 700]
        for i, x in enumerate(rsu_positions):
            self.simulation_service.add_entity(
                f"rsu_{i}",
                "Roadside Unit",
                Position(x, 80),
                {"name": f"RSU {i+1}"}
            )
        
        # Add some vehicles
        vehicle_positions = [0, 200, 400, 600]
        for i, x in enumerate(vehicle_positions):
            self.simulation_service.add_entity(
                f"vehicle_{i}",
                "Vehicle",
                Position(x, 100),
                {"name": f"Vehicle {i+1}"}
            )

    def run(self):
        # st.title("IOV Self-Sovereign Identity Platform")
        
        menu = [
            "Home", 
            "Create DID", 
            "Register Vehicle", 
            "Vehicle Inspection", 
            "DIDs Overview", 
            "Interactions Hub",
            "View Vehicles Page",
            "Wallet",
            "Issue Credentials"  # Added new page
        ]
        choice = st.sidebar.selectbox("Navigation", menu)
        
        if choice == "Home":
            HomePage(self)
        elif choice == "Create DID":
            CreateDIDPage(self)
        elif choice == "Register Vehicle":
            RegisterVehiclePage(self)
        elif choice == "Vehicle Inspection":
            VehicleInspectionPage(self)
        elif choice == "DIDs Overview":
            self._dids_overview_page()
        elif choice == "Interactions Hub":
            self._interactions_hub_page()
        elif choice == "Wallet":
            RenderWalletUI(self)
        elif choice == "View Vehicles Page":
            self.view_vehicles_page()
        elif choice == "Issue Credentials":  # Added new page handler
            self._issue_credentials_page()

    def _count_user_types(self, registered_addresses):
        """Count different types of users"""
        counts = {
            'RSU': 0,
            'Insurance': 0,
            'Companies': 0,  # Other companies
            'Vehicles': 0    # Added vehicle count
        }
        
        for address in registered_addresses:
            user = self.blockchain_service.contract.functions.users(address).call()
            user_type = self._get_user_type_name(user[2])
            if user_type == 'Roadside Unit':
                counts['RSU'] += 1
            elif user_type == 'Insurance Provider':
                counts['Insurance'] += 1
            elif user_type in ['Mechanic', 'Vehicle Manufacturer']:
                counts['Companies'] += 1
            
            # Count vehicles by checking DID document's service endpoints
            if user[3]:  # If user has a DID
                user_doc = self.did_service.get_did_document(user[3])
                if user_doc and 'service_endpoints' in user_doc:
                    vehicle_count = sum(1 for endpoint in user_doc['service_endpoints'] 
                                     if endpoint.get('type') == 'VehicleOwnership')
                    counts['Vehicles'] += vehicle_count
        
        return counts

  
    def _dids_overview_page(self):
        st.title("DIDs Overview")
        
        try:
            registered_addresses = self.blockchain_service.contract.functions.getRegisteredAddresses().call()
            
            if not registered_addresses:
                st.info("No users registered yet.")
                return

            for address in registered_addresses:
                try:
                    user = self.blockchain_service.contract.functions.users(address).call()
                    name = user[1]
                    user_type = self._get_user_type_name(user[2])
                    entity_did = user[3]
                    wallet_did = user[4]

                    with st.expander(f"{name} ({user_type})", expanded=False):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("**Entity DID**")
                            st.code(entity_did)
                            if st.button("View Entity Document", key=f"view_entity_{entity_did}"):
                                doc = self.blockchain_service.get_did_document(entity_did)
                                if doc:
                                    st.json(doc)  # doc is already a dictionary
                        
                        with col2:
                            st.markdown("**Wallet DID**")
                            st.code(wallet_did)
                            if st.button("View Wallet Document", key=f"view_wallet_{wallet_did}"):
                                doc = self.blockchain_service.get_did_document(wallet_did)
                                if doc:
                                    st.json(doc)  # doc is already a dictionary
                        
                        # Get vehicles using blockchain directly
                        try:
                            vehicles = self.blockchain_service.contract.functions.getUserVehicles(entity_did).call()
                            if vehicles:
                                st.markdown("**Registered Vehicles**")
                                for vehicle in vehicles:
                                    st.markdown(f"- {vehicle['make']} {vehicle['model']} ({vehicle['year']})")
                                    st.markdown(f"  VIN: `{vehicle['vin']}`")
                                    if 'vehicle_did' in vehicle:
                                        st.markdown(f"  Vehicle DID: `{vehicle['vehicle_did']}`")
                                    if 'wallet_did' in vehicle:
                                        st.markdown(f"  Wallet DID: `{vehicle['wallet_did']}`")
                        except Exception as e:
                            if "getUserVehicles" not in str(e):  # Don't show error if function doesn't exist
                                st.error(f"Error getting vehicles: {e}")
                
                except Exception as e:
                    st.error(f"Error loading user data for {address}: {str(e)}")
                    
        except Exception as e:
            st.error(f"Error loading registered users: {str(e)}")

    def _interactions_hub_page(self):
        """Render the interactions hub page with enhanced SSI features."""
        st.title("Interaction Hub")

        try:
            # Get registered users and vehicles
            registered_users = self.blockchain_service.get_registered_users()
            registered_vehicles = self.blockchain_service.get_registered_vehicles()

            if not registered_users:
                st.warning("No registered users found")
                return

            # Initialize simulation components if not done
            if 'simulators' not in st.session_state:
                st.session_state.simulators = {}
                for vehicle in registered_vehicles:
                    st.session_state.simulators[vehicle['did']] = SmartCarSimulator()

            # Initialize request tracking if not done
            if 'pending_requests' not in st.session_state:
                st.session_state.pending_requests = {}
            if 'request_history' not in st.session_state:
                st.session_state.request_history = []

            # Display interaction options
            st.header("Select Interaction Type")
            interaction_type = st.radio(
                "Choose interaction type:",
                ["RSU to Vehicle", "Vehicle to Service Provider"]
            )

            # Create tabs for different sections
            data_tab, policy_tab, interaction_tab = st.tabs(["Vehicle Data", "Policy Management", "Interaction"])

            with data_tab:
                st.subheader("Vehicle Sensor Data")
                if registered_vehicles:
                    selected_vehicle = st.selectbox(
                        "Select Vehicle",
                        options=[f"{v['name']} ({v['did']})" for v in registered_vehicles],
                        key="data_vehicle_select"
                    )
                    if selected_vehicle:
                        vehicle_did = selected_vehicle.split(' (')[1].rstrip(')')
                        simulator = st.session_state.simulators[vehicle_did]
                        simulator.update_sensors()
                        
                        # Display sensor data
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Speed", f"{simulator.sensors['speed']:.1f} km/h")
                            st.metric("Battery", f"{simulator.sensors['battery']:.1f}%")
                        with col2:
                            st.metric("Temperature", f"{simulator.sensors['temperature']:.1f}°C")
                            st.metric("Fuel Level", f"{simulator.sensors['fuel']:.1f}%")
                        with col3:
                            st.metric("GPS", f"({simulator.sensors['gps']['lat']:.6f}, {simulator.sensors['gps']['lon']:.6f})")

            with policy_tab:
                st.subheader("Data Sharing Policies")
                if registered_vehicles:
                    selected_vehicle = st.selectbox(
                        "Select Vehicle",
                        options=[f"{v['name']} ({v['did']})" for v in registered_vehicles],
                        key="policy_vehicle_select"
                    )
                    if selected_vehicle:
                        vehicle_did = selected_vehicle.split(' (')[1].rstrip(')')
                        
                        self.wallet_polices._render_data_sharing_tab(vehicle_did)
                        
            with interaction_tab:
                if interaction_type == "RSU to Vehicle":
                    self._rsu_to_vehicle_interaction()
                elif interaction_type == "Vehicle to Service Provider":
                    self._mechanic_vehicle_interaction()

        except Exception as e:
            st.error(f"Error in interaction hub: {str(e)}")

    def _rsu_to_vehicle_interaction(self):
        """Handle RSU to vehicle interaction with DID verification and policy checks"""
        st.subheader("RSU to Vehicle Communication")

        # Get vehicles and RSUs
        vehicles = self.blockchain_service.get_registered_vehicles()
        rsus = self.blockchain_service.get_registered_rsus()

        if not vehicles or not rsus:
            st.warning("Both vehicles and RSUs are required for this interaction")
            return

        # Create tabs for different sections
        request_tab, response_tab, history_tab = st.tabs(["Send Request", "Handle Responses", "Interaction History"])
        
        with request_tab:
            col1, col2 = st.columns(2)
            
            with col1:
                selected_rsu = st.selectbox(
                    "Select RSU (Sender)",
                    options=[f"{r['name']} ({r['did']})" for r in rsus],
                    key="send_rsu_select"
                )
                if selected_rsu:
                    rsu_did = selected_rsu.split(' (')[1].rstrip(')')
                    rsu_wallet = self.wallet_service.get_wallet(rsu_did)
                    rsu_address = self.blockchain_service.get_address_by_did(rsu_did)
                    st.write(f"RSU DID: {rsu_did}")

            with col2:
                selected_vehicle = st.selectbox(
                    "Select Vehicle (Recipient)",
                    options=[f"{v['name']} ({v['did']})" for v in vehicles],
                    key="send_vehicle_select"
                )
                if selected_vehicle:
                    vehicle_did = selected_vehicle.split(' (')[1].rstrip(')')
                    vehicle_wallet = self.wallet_service.get_wallet(vehicle_did)
                    vehicle_address = self.blockchain_service.get_address_by_did(vehicle_did)
                    st.text(f"Vehicle DID: {vehicle_did}")

            if selected_vehicle and selected_rsu:
                # Verify DIDs and establish DIDComm connection
                vehicle_doc = self.did_service.get_did_document(vehicle_did)
                rsu_doc = self.did_service.get_did_document(rsu_did)

                if not vehicle_doc or not rsu_doc:
                    st.error("Invalid DIDs detected. Communication not allowed.")
                    return

                # Message composition for RSU
                st.subheader("Compose Request")
                message_type = st.selectbox(
                    "Request Type",
                    ["Traffic Data Request", "Emergency Alert", "Road Condition Check", "Weather Data Request", "Custom Request"]
                )
                
                message = st.text_area("Request Details (Please provide context)")
                
                # Show available data types from vehicle
                simulator = st.session_state.simulators.get(vehicle_did)
                if not simulator:
                    simulator = SmartCarSimulator()
                    st.session_state.simulators[vehicle_did] = simulator
                simulator.update_sensors()
                
                st.subheader("Available Vehicle Data")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Speed", f"{simulator.sensors['speed']:.1f} km/h")
                    st.metric("Battery", f"{simulator.sensors['battery']:.1f}%")
                with col2:
                    st.metric("Temperature", f"{simulator.sensors['temperature']:.1f}°C")
                    st.metric("Fuel Level", f"{simulator.sensors['fuel']:.1f}%")
                with col3:
                    st.metric("GPS", f"({simulator.sensors['gps']['lat']:.6f}, {simulator.sensors['gps']['lon']:.6f})")
                
                requested_data = st.multiselect(
                    "Request Data Types",
                    list(simulator.sensors.keys())
                )
                
                is_emergency = st.checkbox("Mark as Emergency Request")

                if st.button("Send Request"):
                    try:
                        # Generate unique request ID
                        request_id = str(uuid.uuid4())
                        
                        # First, evaluate request using LLM if not emergency
                        context = {
                            "requester_type": "roadside_unit",
                            "request_type": message_type,
                            "data_requested": requested_data,
                            "reason": message,
                            "vehicle_type": vehicle_wallet.get('type', 'unknown'),
                            "time_of_day": datetime.now().strftime("%H:%M")
                        }
                        
                        llm_approved, llm_reason = self.llm_service.evaluate_request(
                            request_type=message_type,
                            requester="roadside_unit",
                            user_context=json.dumps(context),
                            is_emergency=is_emergency
                        )
                            
                        # Create request body
                        request_body = {
                            "request_id": request_id,
                            "message_type": message_type,
                            "content": message,
                            "requested_data": requested_data,
                            "is_emergency": is_emergency,
                            "timestamp": datetime.now().isoformat(),
                            "sender_did": rsu_did,
                            "recipient_did": vehicle_did,
                            "llm_decision": llm_approved,
                            "llm_reason": llm_reason,
                            "status": "pending"
                        }
                        
                        # Create DIDComm message
                        didcomm_message = self.did_service.create_didcomm_message(
                            sender_did=rsu_did,
                            recipient_did=vehicle_did,
                            message_type="request",
                            body=request_body
                        )

                        # Encrypt and store request
                        encrypted_message = self.did_service.encrypt_didcomm_message(
                            didcomm_message,
                            rsu_doc["authentication"][0],
                            vehicle_doc["authentication"][0]
                        )
                        
                        # Store in session state
                        if vehicle_did not in st.session_state.pending_requests:
                            st.session_state.pending_requests[vehicle_did] = []
                        st.session_state.pending_requests[vehicle_did].append(request_body)
                        
                        # Store in both wallets
                        self.wallet_service.store_didcomm_message(rsu_did, encrypted_message.copy())
                        self.wallet_service.store_didcomm_message(vehicle_did, encrypted_message.copy())
                        
                        # Add to pending requests with the original unencrypted message
                        self.wallet_service.add_pending_request(vehicle_did, request_body)
                        
                        # Record the interaction on blockchain
                        try:
                            interaction_payload = json.dumps(request_body).encode('utf-8')
                            tx_hash = self.did_service.record_interaction(
                                rsu_address,
                                vehicle_address,
                                rsu_did,
                                vehicle_did,
                                message_type,
                                interaction_payload
                            )
                            st.success(f"Request sent successfully! Request ID: {request_id}")
                            st.info(f"Transaction hash: {tx_hash}")
                        except Exception as e:
                            st.error(f"Failed to record interaction on blockchain: {str(e)}")
                            st.error("The request was sent but could not be recorded on the blockchain")
                            
                    except Exception as e:
                        st.error(f"Error sending request: {str(e)}")
        
        with response_tab:
            st.subheader("Handle Pending Requests")
            if selected_vehicle:
                vehicle_did = selected_vehicle.split(' (')[1].rstrip(')')
                pending_requests = st.session_state.pending_requests.get(vehicle_did, [])
                
                if not pending_requests:
                    st.info("No pending requests")
                else:
                    for request in pending_requests:
                        with st.expander(f"Request {request['request_id'][:8]} - {request['message_type']}"):
                            st.write("**From:** ", request['sender_did'])
                            st.write("**Type:** ", request['message_type'])
                            st.write("**Message:** ", request['content'])
                            st.write("**Requested Data:** ", ", ".join(request['requested_data']))
                            st.write("**Emergency:** ", "Yes" if request['is_emergency'] else "No")
                            st.write("**LLM Decision:** ", "Approved" if request['llm_decision'] else "Not Approved")
                            st.write("**LLM Reason:** ", request['llm_reason'])
                            
                            if request['status'] == 'pending':
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.button("Approve", key=f"approve_{request['request_id']}"):
                                        try:
                                            # Create response body
                                            response_body = {
                                                "request_id": request['request_id'],
                                                "response_type": "approval",
                                                "timestamp": datetime.now().isoformat(),
                                                "sender_did": vehicle_did,
                                                "recipient_did": request['sender_did'],
                                                "data": {
                                                    data_type: st.session_state.simulators[vehicle_did].sensors[data_type]
                                                    for data_type in request['requested_data']
                                                }
                                            }
                                            
                                            # Create and encrypt DIDComm response
                                            response_message = self.did_service.create_didcomm_message(
                                                sender_did=vehicle_did,
                                                recipient_did=request['sender_did'],
                                                message_type="response",
                                                body=response_body
                                            )
                                            
                                            encrypted_response = self.did_service.encrypt_didcomm_message(
                                                response_message,
                                                vehicle_doc["authentication"][0],
                                                rsu_doc["authentication"][0]
                                            )
                                            
                                            # Store response in wallets
                                            self.wallet_service.store_didcomm_message(vehicle_did, encrypted_response.copy())
                                            self.wallet_service.store_didcomm_message(request['sender_did'], encrypted_response.copy())
                                            
                                            # Update request status
                                            request['status'] = 'approved'
                                            st.success("Request approved and data shared")
                                            
                                            # Record response on blockchain
                                            response_payload = json.dumps(response_body).encode('utf-8')
                                            tx_hash = self.did_service.record_interaction(
                                                vehicle_address,
                                                rsu_address,
                                                vehicle_did,
                                                request['sender_did'],
                                                "response",
                                                response_payload
                                            )
                                            
                                        except Exception as e:
                                            st.error(f"Error processing approval: {str(e)}")
                                
                                with col2:
                                    if st.button("Reject", key=f"reject_{request['request_id']}"):
                                        try:
                                            # Create rejection response
                                            response_body = {
                                                "request_id": request['request_id'],
                                                "response_type": "rejection",
                                                "timestamp": datetime.now().isoformat(),
                                                "sender_did": vehicle_did,
                                                "recipient_did": request['sender_did'],
                                                "reason": "Request rejected by vehicle owner"
                                            }
                                            
                                            # Create and encrypt DIDComm response
                                            response_message = self.did_service.create_didcomm_message(
                                                sender_did=vehicle_did,
                                                recipient_did=request['sender_did'],
                                                message_type="response",
                                                body=response_body
                                            )
                                            
                                            encrypted_response = self.did_service.encrypt_didcomm_message(
                                                response_message,
                                                vehicle_doc["authentication"][0],
                                                rsu_doc["authentication"][0]
                                            )
                                            
                                            # Store response in wallets
                                            self.wallet_service.store_didcomm_message(vehicle_did, encrypted_response.copy())
                                            self.wallet_service.store_didcomm_message(request['sender_did'], encrypted_response.copy())
                                            
                                            # Update request status
                                            request['status'] = 'rejected'
                                            st.success("Request rejected")
                                            
                                            # Record rejection on blockchain
                                            response_payload = json.dumps(response_body).encode('utf-8')
                                            tx_hash = self.did_service.record_interaction(
                                                vehicle_address,
                                                rsu_address,
                                                vehicle_did,
                                                request['sender_did'],
                                                "response",
                                                response_payload
                                            )
                                            
                                        except Exception as e:
                                            st.error(f"Error processing rejection: {str(e)}")
                            else:
                                st.info(f"Status: {request['status'].title()}")
                                
        with history_tab:
            st.subheader("Interaction History")
            if selected_vehicle or selected_rsu:
                did_to_check = vehicle_did if selected_vehicle else rsu_did
                try:
                    # Get interaction history from blockchain
                    history = self.blockchain_service.get_interaction_history(did_to_check)
                    if history:
                        for interaction in history:
                            with st.expander(f"{interaction['type']} - {interaction['timestamp']}"):
                                st.write("**From:** ", interaction['sender_did'])
                                st.write("**To:** ", interaction['recipient_did'])
                                st.write("**Type:** ", interaction['type'])
                                st.write("**Details:** ", interaction['payload'])
                                st.write("**Transaction Hash:** ", interaction['tx_hash'])
                    else:
                        st.info("No interaction history found")
                except Exception as e:
                    st.error(f"Error fetching interaction history: {str(e)}")

    def _mechanic_vehicle_interaction(self):
        """
        Handle mechanic-to-vehicle and vehicle-to-mechanic interactions.
        Both entities have their own wallets and LLMs for intelligent communication.
        """
        st.header("Mechanic-Vehicle Interaction")
        
        # Get list of mechanics and vehicles
        mechanics = self.blockchain_service.get_registered_mechanic()
        vehicles = self.blockchain_service.get_registered_vehicles()
        
        # Create columns for mechanic and vehicle selection
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Mechanic")
            selected_mechanic = st.selectbox(
                "Select Mechanic",
                [f"{m['name']} ({m['did']})" for m in mechanics],
                key="mechanic_select"
            )
            
            if selected_mechanic:
                mechanic_did = selected_mechanic.split(' (')[1].rstrip(')')
                mechanic_doc = self.did_service.get_did_document(mechanic_did)
                
                # Mechanic's LLM configuration
                st.write("Mechanic's AI Assistant")
                mechanic_llm_config = {
                    "role": "mechanic",
                    "expertise": ["diagnostics", "repair", "maintenance"],
                    "access_level": "professional"
                }
                
                # Mechanic actions
                st.subheader("Mechanic Actions")
                action_type = st.selectbox(
                    "Action Type",
                    ["Diagnostic Request", "Maintenance Schedule", "Repair Proposal"],
                    key="mechanic_action"
                )
                
                message = st.text_area("Message to Vehicle", key="mechanic_message")
                requested_data = st.multiselect(
                    "Request Vehicle Data",
                    ["diagnostic_codes", "maintenance_history", "sensor_data", "performance_metrics"],
                    key="mechanic_data_request"
                )
                
                is_urgent = st.checkbox("Mark as Urgent", key="mechanic_urgent")
        
        with col2:
            st.subheader("Vehicle")
            selected_vehicle = st.selectbox(
                "Select Vehicle",
                [f"{v['name']} ({v['did']})" for v in vehicles],
                key="vehicle_select_mechanic"
            )
            
            if selected_vehicle:
                vehicle_did = selected_vehicle.split(' (')[1].rstrip(')')
                vehicle_doc = self.did_service.get_did_document(vehicle_did)
                
                # Get vehicle simulator for sensor data
                simulator = st.session_state.simulators.get(vehicle_did)
                if simulator:
                    # Display current sensor data
                    st.write("Current Vehicle Status:")
                    speed = simulator.sensors.get('speed', 0)
                    st.write(f"Speed: {speed:.1f} km/h")
                    motion_status = "🅿️ Parked" if speed < 0.5 else "🚗 In Motion"
                    st.write(f"Status: {motion_status}")
                
                # Add blocked users management
                st.subheader("Blocked Users")
                blocked_users = self.wallet_service.get_blocked_users(vehicle_did)
                if blocked_users:
                    for user in blocked_users:
                        user_name = user['did']
                        for mechanic in mechanics:
                            if mechanic['did'] == user['did']:
                                user_name = mechanic['name']
                                break
                        
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"🚫 {user_name}")
                            st.write(f"Blocked on: {user['blocked_at']}")
                            st.write(f"Reason: {user['reason']}")
                        with col2:
                            if st.button("Unblock", key=f"unblock_{user['did']}"):
                                self.wallet_service.unblock_user(vehicle_did, user['did'])
                                st.success(f"Unblocked {user_name}")
                                st.rerun()
                else:
                    st.info("No blocked users")
                
                # Vehicle's LLM configuration with sensor data
                vehicle_llm_config = {
                    "role": "vehicle",
                    "systems": ["engine", "transmission", "electronics", "safety"],
                    "access_level": "owner",
                    "sensors": simulator.sensors if simulator else {}
                }
        
        # Interaction Tabs
        request_tab, inbox_tab, history_tab = st.tabs(["Send Request", "Inbox", "History"])
        
        with request_tab:
            if st.button("Send Request", key="send_mechanic_request"):
                try:
                    if not selected_mechanic or not selected_vehicle:
                        st.error("Please select both mechanic and vehicle")
                        return
                    
                    if not message:
                        st.error("Please enter a message")
                        return
                    
                    # Get addresses for blockchain
                    mechanic_address = self.blockchain_service.get_address_by_did(mechanic_did)
                    vehicle_address = self.blockchain_service.get_address_by_did(vehicle_did)
                    
                    # Prepare request using mechanic's LLM
                    mechanic_llm_response = self.llm_service.process_request(
                        message,
                        mechanic_llm_config,
                        context={
                            "action_type": action_type,
                            "requested_data": requested_data,
                            "is_urgent": is_urgent
                        }
                    )
                    
                    # Create request body
                    body = {
                        "action_type": action_type,
                        "content": message,
                        "llm_analysis": mechanic_llm_response,
                        "requested_data": requested_data,
                        "is_urgent": is_urgent,
                        "timestamp": datetime.now().isoformat(),
                        "sender_did": mechanic_did,
                        "recipient_did": vehicle_did
                    }
                    
                    # Get vehicle's policies
                    vehicle_wallet = self.wallet_service.get_wallet(vehicle_did)
                    policies = vehicle_wallet.get('policies', {})
                    
                    # Check if requested data types are allowed
                    allowed_data = []
                    denied_data = []
                    for data_type in requested_data:
                        policy = policies.get(data_type, {})
                        if policy.get('consent', False):
                            allowed_data.append(data_type)
                        else:
                            denied_data.append(data_type)
                    
                    if not allowed_data:
                        # If no data types are allowed, reject immediately
                        response_data = {
                            "status": "denied",
                            "reason": f"No consent for requested data types: {', '.join(requested_data)}",
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        # Create response message
                        response_message = self.did_service.create_didcomm_message(
                            sender_did=vehicle_did,
                            recipient_did=mechanic_did,
                            message_type="mechanic_response",
                            body=response_data
                        )
                        
                        # Store response
                        self.wallet_service.store_didcomm_message(vehicle_did, response_message)
                        
                        # Record on blockchain
                        try:
                            response_payload = json.dumps(response_data).encode('utf-8')
                            tx_hash = self.did_service.record_interaction(
                                vehicle_address,
                                mechanic_address,
                                vehicle_did,
                                mechanic_did,
                                "mechanic_response",
                                response_payload
                            )
                            st.error(f"Request rejected - No consent for data access: {', '.join(denied_data)}")
                        except Exception as e:
                            st.error(f"Failed to record interaction on blockchain: {str(e)}")
                            
                    else:
                        # If some data types are allowed, proceed with request
                        if denied_data:
                            st.warning(f"Note: No consent for some requested data: {', '.join(denied_data)}")
                        
                        # Create request body with only allowed data types
                        body = {
                            "action_type": action_type,
                            "content": message,
                            "llm_analysis": mechanic_llm_response,
                            "requested_data": allowed_data,  # Only include allowed data types
                            "is_urgent": is_urgent,
                            "timestamp": datetime.now().isoformat(),
                            "sender_did": mechanic_did,
                            "recipient_did": vehicle_did
                        }
                        
                        # Create and encrypt DIDComm message
                        didcomm_message = self.did_service.create_didcomm_message(
                            sender_did=mechanic_did,
                            recipient_did=vehicle_did,
                            message_type="mechanic_request",
                            body=body
                        )
                        
                        # Store in both wallets
                        self.wallet_service.store_didcomm_message(mechanic_did, didcomm_message.copy())
                        self.wallet_service.store_didcomm_message(vehicle_did, didcomm_message.copy())
                        
                        # Add to pending requests
                        self.wallet_service.add_pending_request(vehicle_did, body)
                        
                        # Record on blockchain
                        try:
                            interaction_payload = json.dumps(body).encode('utf-8')
                            tx_hash = self.did_service.record_interaction(
                                mechanic_address,
                                vehicle_address,
                                mechanic_did,
                                vehicle_did,
                                "mechanic_request",
                                interaction_payload
                            )
                            st.success(f"Request sent successfully! Transaction hash: {tx_hash}")
                        except Exception as e:
                            st.error(f"Failed to record interaction on blockchain: {str(e)}")
                        
                except Exception as e:
                    st.error(f"Error sending request: {str(e)}")
        
        with inbox_tab:
            st.subheader("Pending Requests")
            try:
                if selected_vehicle:
                    pending_requests = self.wallet_service.get_pending_requests(vehicle_did)
                    
                    if not pending_requests:
                        st.info("No pending requests")
                    else:
                        for request in pending_requests:
                            try:
                                sender_did = request.get('sender_did', '')
                                sender_name = sender_did  # Default to DID
                                for mechanic in mechanics:
                                    if mechanic['did'] == sender_did:
                                        sender_name = mechanic['name']
                                        break
                                
                                with st.expander(f"Request from {sender_name}"):
                                    st.write("Request Details:")
                                    if 'action_type' in request:
                                        st.write(f"Type: {request['action_type']}")
                                    if 'content' in request:
                                        st.write(f"Message: {request['content']}")
                                    if 'requested_data' in request:
                                        st.write(f"Requested Data: {', '.join(request['requested_data'])}")
                                    if 'is_urgent' in request:
                                        st.write(f"Urgent: {'Yes' if request['is_urgent'] else 'No'}")
                                    if 'llm_analysis' in request:
                                        st.write("AI Analysis:", request['llm_analysis'])
                                    
                                    # Process with vehicle's LLM
                                    vehicle_llm_response = self.llm_service.process_request(
                                        request['content'],
                                        vehicle_llm_config,
                                        context={
                                            "action_type": request.get('action_type'),
                                            "requested_data": request.get('requested_data'),
                                            "is_urgent": request.get('is_urgent'),
                                            "sender_did": sender_did,
                                            "sensors": simulator.sensors if simulator else {}
                                        }
                                    )
                                    
                                    st.write("Vehicle AI Analysis:", vehicle_llm_response)
                                    
                                    # Check if sender is blocked
                                    is_blocked = any(user['did'] == sender_did for user in blocked_users)
                                    
                                    if is_blocked:
                                        st.error("⛔ This user is blocked. Unblock them to process requests.")
                                        continue
                                    
                                    # Parse LLM response for decision
                                    is_motion_safe = "MOTION_SAFE" in vehicle_llm_response
                                    is_suspicious = "SUSPICIOUS" in vehicle_llm_response
                                    
                                    # If LLM detected unsafe motion state and suspicious activity
                                    if not is_motion_safe and is_suspicious:
                                        response_data = {
                                            "status": "denied",
                                            "reason": "Request denied - Vehicle in motion and request deemed suspicious",
                                            "ai_response": vehicle_llm_response,
                                            "sensor_data": {
                                                "speed": simulator.sensors.get('speed', 0),
                                                "timestamp": datetime.now().isoformat()
                                            },
                                            "timestamp": datetime.now().isoformat()
                                        }
                                        
                                        # Block user if suspicious
                                        if is_suspicious:
                                            self.wallet_service.block_user(
                                                vehicle_did, 
                                                sender_did,
                                                reason=f"Suspicious request while vehicle in motion. Speed: {simulator.sensors.get('speed', 0)} km/h"
                                            )
                                            response_data["reason"] += " User has been blocked due to suspicious activity."
                                        
                                        # Create response message
                                        response_message = self.did_service.create_didcomm_message(
                                            sender_did=vehicle_did,
                                            recipient_did=sender_did,
                                            message_type="mechanic_response",
                                            body=response_data
                                        )
                                        
                                        # Store and remove request
                                        self.wallet_service.store_didcomm_message(vehicle_did, response_message)
                                        self.wallet_service.remove_pending_request(vehicle_did, request)
                                        
                                        # Record on blockchain with LLM decision
                                        try:
                                            response_payload = json.dumps(response_data).encode('utf-8')
                                            tx_hash = self.did_service.record_interaction(
                                                vehicle_address,
                                                mechanic_address,
                                                vehicle_did,
                                                sender_did,
                                                "mechanic_response",
                                                response_payload
                                            )
                                        except Exception as e:
                                            st.error(f"Error recording response: {str(e)}")
                                        
                                        st.error("Request automatically rejected - Unsafe motion state detected")
                                        st.rerun()
                                        continue
                                    
                                    # Add approve/deny buttons for manual decision if motion is safe
                                    if is_motion_safe:
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            if st.button(f"Approve {sender_name}", key=f"approve_{sender_did}"):
                                                # Prepare response data
                                                response_data = {
                                                    "status": "approved",
                                                    "data": {k: simulator.sensors[k] for k in request['requested_data'] if k in simulator.sensors},
                                                    "ai_response": vehicle_llm_response,
                                                    "timestamp": datetime.now().isoformat()
                                                }
                                                
                                                # Create response message
                                                response_message = self.did_service.create_didcomm_message(
                                                    sender_did=vehicle_did,
                                                    recipient_did=sender_did,
                                                    message_type="mechanic_response",
                                                    body=response_data
                                                )
                                                
                                                # Store and remove request
                                                self.wallet_service.store_didcomm_message(vehicle_did, response_message)
                                                self.wallet_service.remove_pending_request(vehicle_did, request)
                                                
                                                # Record on blockchain
                                                try:
                                                    response_payload = json.dumps(response_data).encode('utf-8')
                                                    tx_hash = self.did_service.record_interaction(
                                                        vehicle_address,
                                                        mechanic_address,
                                                        vehicle_did,
                                                        sender_did,
                                                        "mechanic_response",
                                                        response_payload
                                                    )
                                                except Exception as e:
                                                    st.error(f"Error recording response: {str(e)}")
                                                
                                                st.success("Request approved and data sent!")
                                                st.rerun()
                                        
                                        with col2:
                                            if st.button(f"Deny {sender_name}", key=f"deny_{sender_did}"):
                                                response_data = {
                                                    "status": "denied",
                                                    "reason": "Request denied by vehicle owner",
                                                    "ai_response": vehicle_llm_response,
                                                    "timestamp": datetime.now().isoformat()
                                                }
                                                
                                                # Create response message
                                                response_message = self.did_service.create_didcomm_message(
                                                    sender_did=vehicle_did,
                                                    recipient_did=sender_did,
                                                    message_type="mechanic_response",
                                                    body=response_data
                                                )
                                                
                                                # Store and remove request
                                                self.wallet_service.store_didcomm_message(vehicle_did, response_message)
                                                self.wallet_service.remove_pending_request(vehicle_did, request)
                                                
                                                # Record on blockchain
                                                try:
                                                    response_payload = json.dumps(response_data).encode('utf-8')
                                                    tx_hash = self.did_service.record_interaction(
                                                        vehicle_address,
                                                        mechanic_address,
                                                        vehicle_did,
                                                        sender_did,
                                                        "mechanic_response",
                                                        response_payload
                                                    )
                                                except Exception as e:
                                                    st.error(f"Error recording response: {str(e)}")
                                                
                                                st.success("Request denied!")
                                                st.rerun()
                            
                            except Exception as e:
                                st.error(f"Error processing request: {str(e)}")
                                continue
                                    
            except Exception as e:
                st.error(f"Error loading inbox: {str(e)}")
        
        with history_tab:
            st.subheader("Interaction History")
            try:
                if selected_vehicle:
                    interactions = self.blockchain_service.get_entity_interactions(vehicle_did)
                    
                    if not interactions:
                        st.info("No interaction history found")
                    else:
                        for interaction in interactions:
                            try:
                                timestamp = datetime.fromtimestamp(interaction.get('timestamp', 0))
                                source_did = interaction.get('source_identifier', '')
                                dest_did = interaction.get('destination_identifier', '')
                                interaction_type = interaction.get('interaction_type', '').lower()
                                
                                # Get entity names
                                source_name = source_did
                                dest_name = dest_did
                                for entity in (mechanics + vehicles):
                                    if entity['did'] == source_did:
                                        source_name = entity['name']
                                    if entity['did'] == dest_did:
                                        dest_name = entity['name']
                                
                                # Determine interaction direction
                                if interaction_type == 'mechanic_response':
                                    title = f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {dest_name} ← {source_name} (Response)"
                                else:
                                    title = f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {dest_name} ← {source_name} (Request)"
                                
                                with st.expander(title):
                                    st.write(f"Type: {interaction.get('interaction_type', 'Unknown')}")
                                    
                                    try:
                                        if 'payload' in interaction:
                                            payload = interaction['payload']
                                            if isinstance(payload, (bytes, bytearray)):
                                                payload = payload.decode('utf-8')
                                            if isinstance(payload, str):
                                                payload_data = json.loads(payload)
                                                if interaction_type == 'mechanic_response':
                                                    st.write("Response:")
                                                    if payload_data.get('status') == 'approved':
                                                        st.success("✓ Approved")
                                                        if 'data' in payload_data:
                                                            st.write("Shared Data:")
                                                            st.json(payload_data['data'])
                                                        if 'ai_response' in payload_data:
                                                            st.write("Vehicle AI Analysis:", payload_data['ai_response'])
                                                    else:
                                                        st.error("✗ Denied")
                                                        if 'reason' in payload_data:
                                                            st.write(f"Reason: {payload_data['reason']}")
                                                        if 'ai_response' in payload_data:
                                                            st.write("Vehicle AI Analysis:", payload_data['ai_response'])
                                                else:
                                                    st.write("Request Details:")
                                                    if 'action_type' in payload_data:
                                                        st.write(f"Type: {payload_data['action_type']}")
                                                    if 'content' in payload_data:
                                                        st.write(f"Message: {payload_data['content']}")
                                                    if 'requested_data' in payload_data:
                                                        st.write(f"Requested Data: {', '.join(payload_data['requested_data'])}")
                                                    if 'is_urgent' in payload_data:
                                                        st.write(f"Urgent: {'Yes' if payload_data['is_urgent'] else 'No'}")
                                                    if 'llm_analysis' in payload_data:
                                                        st.write("Mechanic AI Analysis:", payload_data['llm_analysis'])
                                            else:
                                                st.write("Payload:", payload)
                                    except Exception as e:
                                        st.write("Payload: [Could not decode]")
                                        
                            except Exception as e:
                                st.error(f"Error displaying interaction: {str(e)}")
                                continue
                                
            except Exception as e:
                st.error(f"Error loading history: {str(e)}")
    def _get_user_type_name(self, type_id: int) -> str:
        """Get user type name from type ID."""
        types = [
            "Individual",          # 0
            "Mechanic",           # 1
            "Insurance Provider", # 2
            "Roadside Unit",     # 3
            "Vehicle Manufacturer", # 4
            "Vehicle"            # 5
        ]
        return types[type_id] if type_id < len(types) else f"Unknown ({type_id})"

    def view_vehicles_page(self):
        """Display all registered vehicles with their detailed information."""
        st.title("Registered Vehicles")
        st.write(f"**Current date:** {datetime.now().strftime('%A, %B %d, %Y, %I %p PKT')}")

        try:
            # Get all registered vehicles
            vehicles = []
            users = self.blockchain_service.get_registered_users()
            
            # First, get all vehicle DIDs
            for user in users:
                if user['type'] == 5:  # Check for CAR type
                    try:
                        # Get the full DID document for this vehicle
                        vehicle_doc = self.did_service.get_did_document(user['did'])
                        if vehicle_doc:
                            # Extract vehicle info from the document
                            if isinstance(vehicle_doc, str):
                                vehicle_doc = json.loads(vehicle_doc)

                            # Extract info from the document
                            info = vehicle_doc.get('info', [])
                            created = vehicle_doc.get('created', '')
                            # print(f"Vehicle created: {created}")
                            if info:
                                vehicles.append(info)
                                
                            else:
                                print(f"No valid vehicle info found in document for {user['did']}")
                    except Exception as e:
                        print(f"Error processing vehicle {user['did']}: {e}")

            if not vehicles:
                st.warning("No registered vehicles found.")
                return

            # Create tabs for different views
            list_view, detail_view = st.tabs(["List View", "Detailed View"])

            with list_view:
                # Create a table of all vehicles
                table_data = []
                for vehicle in vehicles:
                    owner_info = vehicle[0].get('owner_did', {})
                    table_data.append({
                        "Owner": owner_info,
                        "Make": vehicle[0].get('make', 'N/A'),
                        "Model": vehicle[0].get('model', 'N/A'),
                        "Year": vehicle[0].get('year', 'N/A'),
                        "VIN": vehicle[0].get('vin', 'N/A'),
                        "Status": vehicle[0].get('status', 'N/A'),
                        "Manufacturer": vehicle[0].get('manufacturer', 'N/A'),
                    })
                
                if table_data:
                    st.dataframe(table_data, use_container_width=True)

            with detail_view:
                # Create a dropdown to select a specific vehicle
                vehicle_options = []
                for v in vehicles:
                    vin = v[0].get('vin')
                    make = v[0].get('make')
                    model = v[0].get('model')
                    if vin and make and model:
                        vehicle_options.append((vin, f"{make} {model} (VIN: {vin})"))

                if vehicle_options:
                    selected_vin = st.selectbox(
                        "Select Vehicle",
                        options=vehicle_options,
                        format_func=lambda x: x[1]
                    )

                    if selected_vin:
                        # Find the selected vehicle
                        vehicle = next((v for v in vehicles if v[0].get('vin') == selected_vin[0]), None)
                        
                        if vehicle:
                            # Create columns for basic info
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.subheader("Basic Information")
                                st.write(f"**Make:** {vehicle[0].get('make', 'N/A')}")
                                st.write(f"**Model:** {vehicle[0].get('model', 'N/A')}")
                                st.write(f"**Year:** {vehicle[0].get('year', 'N/A')}")
                                st.write(f"**Color:** {vehicle[0].get('color', 'N/A')}")
                                st.write(f"**VIN:** {vehicle[0].get('vin', 'N/A')}")
                                st.write(f"**Status:** {vehicle[0].get('status', 'N/A')}")
                                st.write(f"**Created:** {created[:10]}")

                            with col2:
                                st.subheader("Ownership Information")
                                st.write(f"**Manufacturer:** {vehicle[0].get('manufacturer', 'N/A')}")
                                
                                # Get current owner DID
                                owner = vehicle[0].get('owner_did', 'N/A')
                                
                                # Get previous owners; ensure it's displayed correctly
                                prev_owners = vehicle[0].get('previous_owners', [])                            
                                st.write(f"**Previous Owner(s):**")
                                st.json(prev_owners)
                                own = {
                                    "Current Owner": owner
                                }
                                st.write(f"**Owner DID:**")
                      
                                st.json(own)

                            with col3:
                                st.subheader("Digital Identity")
                                
                                # Wrap DIDs in a dictionary for JSON display
                                json_data = {
                                    "Vehicle DID": vehicle[0].get('id', 'N/A'),
                                    "Wallet DID": vehicle[1].get('id', 'N/A')
                                }
                                
                                st.json(json_data)  # Display as JSON for better readability

                            # Service History
                            st.subheader("Service History")
                            service_history = vehicle[0].get('serviceHistory', [])
                            print(vehicle)
                            if service_history:
                                history_data = []
                                for service in service_history:
                                    history_data.append({
                                        "Date": service.get('date', 'N/A'),
                                        "Service Type": service.get('serviceType', 'N/A')
                                    })
                                st.dataframe(history_data, use_container_width=True)
                            else:
                                st.info("No service history available")

                            # Available Services
                            st.subheader("Available Services")
                            service_endpoints = vehicle[0].get('service_endpoints', [])
                            if service_endpoints:
                                for endpoint in service_endpoints:
                                    st.write(f"**{endpoint.get('type', ['Service'])[0]}:** {endpoint.get('serviceEndpoint', 'N/A')}")
                            else:
                                st.info("No service endpoints available")
                else:
                    st.warning("No vehicles available for detailed view")

        except Exception as e:
            st.error(f"Error loading vehicles: {str(e)}")
            print(f"Detailed error: {e}")


    def _issue_credentials_page(self):
        """Page for issuing and managing verifiable credentials for vehicle ownership."""
        st.header("Issue Verifiable Credentials")
        manus = []
        
        # Get the list of registered users
        users = self.blockchain_service.get_registered_users()
        
        # Filter users by type = 5 (assuming this is for vehicles)
        for user in users:
            if user["type"] == 5:  # Assuming type 5 is for Vehicles
                user_info = {
                    'name': user['name'],
                    'did': user['did'],
                    'address': user['address'],
                    'type': user['type']  # This is the type ID
                }
                manus.append(user_info)

        # Check if there are any registered vehicles
        if not manus:
            st.warning("No registered vehicles found. Please register a vehicle first.")
            return  # Exit the function if no vehicles are found

        st.subheader("Assign Verifiable Credential")

        selected_user = st.selectbox(
            "Select User",
            options=[(user['name'], user) for user in manus],  # Store entire user info
        )
        car_did = selected_user[1]['did']
        # Get all registered vehicles owned by the selected user
        all_vehicles = self.did_service.get_user_vehicles(selected_user[1]['did'])  # Use DID from selected user
       
        if not all_vehicles:
            st.warning("No registered vehicles found for the selected user.")
            return

        # Select credential issuer (current owner)
        st.subheader("Select Credential Issuer")
        
        issuer_options = {
            f"{user['name']} ({user['did']})": user 
            for user in users 
            if user['did'] in [v.get('owner_did','') for v in all_vehicles]  # Only show users who own vehicles
        }
        
        if not issuer_options:
            st.warning("No users with registered vehicles found.")
            return

        selected_issuer = st.selectbox("Select Owner (Issuer)", list(issuer_options.keys()))
        issuer = issuer_options[selected_issuer]

        # Get issuer's vehicles
        issuer_vehicles = [v for v in all_vehicles if v.get('owner_did') == issuer['did']]
        
        # Select vehicle to issue credential for
        st.subheader("Select Vehicle")
        
        vehicle_options = {
            f"{v.get('make', '')} {v.get('model', '')} (VIN: {v.get('vin', '')})": v 
            for v in issuer_vehicles
        }
        
        selected_vehicle = st.selectbox("Select Vehicle", list(vehicle_options.keys()))
        
        vehicle = vehicle_options[selected_vehicle]

        # Select credential recipient
        st.subheader("Select Credential Recipient")
        
        recipient_options = {
            f"{user['name']} ({user['did']})": user 
            for user in users 
            if user['did'] != issuer['did']  # Exclude the issuer
            and user['type'] != 5
        }
        
        selected_recipient = st.selectbox("Select Recipient", list(recipient_options.keys()))
        
        recipient = recipient_options[selected_recipient]

        # Credential details form
        st.subheader("Credential Details")
        
        with st.form("credential_form"):
            credential_type = st.selectbox(
                "Credential Type",
                ["VehicleOwnership", "VehicleAccess", "MaintenanceAuthorization"]
            )

            if credential_type == "VehicleOwnership":
                transfer_date = st.date_input("Transfer Date")
                price = st.number_input("Transfer Price", min_value=0)
                notes = st.text_area("Notes")

                claims = {
                    "type": credential_type,
                    "vehicleId": vehicle['did'],
                    "vehicleVIN": vehicle['vin'],
                    "previousOwner": issuer['did'],
                    "newOwner": recipient['did'],
                    "transferDate": transfer_date.isoformat(),
                    "transferPrice": price,
                    "notes": notes
                }

            elif credential_type == "VehicleAccess":
                start_date = st.date_input("Start Date")
                end_date = st.date_input("End Date")
                access_level = st.selectbox("Access Level", ["Full", "Limited", "Temporary"])

                claims = {
                    "type": credential_type,
                    "vehicleId": vehicle['did'],
                    "vehicleVIN": vehicle['vin'],
                    "grantor": issuer['did'],
                    "grantee": recipient['did'],
                    "startDate": start_date.isoformat(),
                    "endDate": end_date.isoformat(),
                    "accessLevel": access_level
                }

            else:  # MaintenanceAuthorization
                service_type = st.selectbox("Service Type", ["Full Service", "Repair", "Inspection"])
                valid_until = st.date_input("Valid Until")

                claims = {
                    "type": credential_type,
                    "vehicleId": vehicle['did'],
                    "vehicleVIN": vehicle['vin'],
                    "authorizer": issuer['did'],
                    "authorizedService": recipient['did'],
                    "serviceType": service_type,
                    "validUntil": valid_until.isoformat()
                }
            print(car_did)
            print(recipient['did'])
            if st.form_submit_button("Issue Credential"):
                try:
                    # Create the verifiable credential
                    credential = self.did_service.create_credential(
                        issuer_did=issuer['did'],
                        subject_did=recipient['did'],
                        claims=claims
                    )
                    
                    if credential:
                        st.success("Credential issued successfully!")
                        st.json(credential)
                        
                        # First update the recipient's DID document with the new credential
                        res = self.did_service.update_did_document(
                            did=recipient['did'],
                            car_did=car_did,
                            credential=credential
                        )
                        
                        if res:
                            st.success("Credential added to recipient's DID document!")
                            
                            # If this is a VehicleOwnership credential, update the vehicle's owner
                            if credential_type == "VehicleOwnership":
                                res = self.did_service.update_did_document(
                                    did=recipient['did'],  # New owner's DID
                                    car_did=car_did  # Vehicle's DID
                                )
                                if res:
                                    st.success("Vehicle ownership updated successfully!")
                                else:
                                    st.error("Failed to update vehicle ownership")
                        else:
                            st.error("Failed to update recipient's DID document")
                    else:
                        st.error("Failed to create credential")
                except Exception as e:
                    st.error(f"Error issuing credential: {e}")

    def _get_all_users(self):
        """Get all registered users with their DIDs and vehicles."""
        try:
            # Get all registered addresses
            registered_addresses = self.blockchain_service.contract.functions.getRegisteredAddresses().call()
            
            # Get all users with their DIDs and vehicles
            users = []
            for address in registered_addresses:
                user = self.blockchain_service.contract.functions.users(address).call()
                if user[3]:  # If user has a DID
                    user_info = {
                        'name': user[0],
                        'did': user[3],
                        'address': address,
                        'type': user[2]  # This is the type ID
                    }
                    users.append(user_info)
            
            return users
        except Exception as e:
            print(f"Error getting users: {str(e)}")
            return []

def main():
    platform = IoVSSIPlatform()
    platform.run()

if __name__ == "__main__":
    main()