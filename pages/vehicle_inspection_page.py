import streamlit as st

def VehicleInspectionPage(self):
    """Vehicle inspection page"""
    st.title("Vehicle Inspection")
    users = []
    # Get all registered addresses
    all_users = self.blockchain_service.get_registered_users()
    for user in all_users:
        if user["type"] == [1,2]:  # Assuming type 5 is for Vehicles
            user_info = {
                'name': user['name'],
                'did': user['did'],
                'address': user['address'],
                'type': user['type']  # This is the type ID
            }
            users.append(user_info)
    
    # User selection
    selected_user = st.selectbox(
        "Select User",
        options=[f"{user['name']} ({user['did']})" for user in users],
        format_func=lambda x: x.split(' (')[0]
    )
    
    if selected_user:
        user_did = selected_user.split(' (')[1].rstrip(')')
        user_vehicles = self.did_service.get_user_vehicles(user_did)
        
        if user_vehicles:
            selected_vehicle = st.selectbox(
                "Select Vehicle",
                options=[f"{v['make']} {v['model']} ({v['vin']})" for v in user_vehicles],
                format_func=lambda x: x.split(' (')[0]
            )
            
            if selected_vehicle:
                vehicle_vin = selected_vehicle.split('(')[1].rstrip(')')
                vehicle_info = next(v for v in user_vehicles if v['vin'] == vehicle_vin)
                
                st.subheader("Vehicle Information")
                st.json({
                    'Make': vehicle_info['make'],
                    'Model': vehicle_info['model'],
                    'Year': vehicle_info['year'],
                    'VIN': vehicle_info['vin'],
                    'Vehicle DID': vehicle_info['vehicle_did']
                })
                
                st.subheader("Inspection Form")
                inspection_date = st.date_input("Inspection Date")
                mileage = st.number_input("Current Mileage", min_value=0)
                condition = st.selectbox("Overall Condition", ["Excellent", "Good", "Fair", "Poor"])
                notes = st.text_area("Inspection Notes")
                
                if st.button("Submit Inspection"):
                    try:
                        # Create inspection credential
                        inspection_data = {
                            "inspectionDate": inspection_date.isoformat(),
                            "mileage": mileage,
                            "condition": condition,
                            "notes": notes,
                            "inspector": user_did,
                            "vehicle": vehicle_info['vehicle_did']
                        }
                        
                        credential = self.did_service.create_credential(
                            issuer_did=user_did,
                            subject_did=vehicle_info['vehicle_did'],
                            claims=inspection_data
                        )
                        
                        if credential:
                            st.success("Inspection record created successfully!")
                            st.json(inspection_data)
                        else:
                            st.error("Failed to create inspection record")
                            
                    except Exception as e:
                        st.error(f"Error creating inspection record: {str(e)}")
        else:
            st.warning("No vehicles found for this user")
    else:
        st.warning("Please select a user to proceed")