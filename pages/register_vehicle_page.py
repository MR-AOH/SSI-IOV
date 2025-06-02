import uuid
import streamlit as st

def RegisterVehiclePage(self):
    st.title("Register Vehicle")
    check = False
    manus = []
    
    # Get the list of registered users
    users = self.blockchain_service.get_registered_users()
    for user in users:
        if user["type"] == 4:  # Assuming type 4 is for Manufacturers
            check = True
            user_info = {
                'name': user['name'],
                'did': user['did'],
                'address': user['address'],
                'type': user['type']  # This is the type ID
            }
            manus.append(user_info)

    # Check if there are any registered users
    if not check:
        st.warning("No registered Manufacturer found. Please register a Manufacturer first.")
        return  # Exit the function if no users are found

    # Editable JSON data for car
    car_info = {
        "@context": [
            "https://www.w3.org/2018/credentials/v1",
            "https://example.org/car-context"
        ],
        "type": ["VerifiableCredential", "Car"],
        "make": "",
        "model": "",
        "year": 2020,
        "vin": "",  
        "owner": {},  # Change to a dictionary to hold name and DID
        "registrationDate": "2020-01-15T00:00:00Z",
        "status": "",  
        "color": "", 
        "serviceHistory": [
            {
                "date": "2022-05-01",
                "serviceType": "Oil Change"
            }
        ],
        "verificationMethod": [
            {
                "type": "RsaVerificationKey2018",
            }
        ],
        "authentication": [],
    }

    # Display editable fields for car information
    st.subheader("Edit Car Information")
    car_info['make'] = st.text_input("Make", value=car_info['make'])
    car_info['model'] = st.text_input("Model", value=car_info['model'])
    car_info['year'] = st.number_input("Year", min_value=1886, max_value=2025, value=car_info['year'])
    car_info['vin'] = st.text_input("VIN", value=car_info['vin'])
    car_info['status'] = st.selectbox("Status", options=["active", "inactive", "sold"], index=0)
    car_info['color'] = st.text_input("Color", value=car_info['color'])

    # Dropdown menu for selecting user to assign VC
    st.subheader("Assign Verifiable Credential")
    
    selected_user = st.selectbox(
        "Select User",
        options=[(user['name'], user) for user in manus],  # Store entire user info
    )

    # Update owner information in car_info with selected user's details
    car_info['owner'] = {
        'name': selected_user[0],  # User's name
        'did': selected_user[1]['did']  # User's DID
    }

    # Submit button to register the car and create VC
    if st.button("Submit"):
        user_id = str(uuid.uuid4())
        registration_result = self.did_service.register_vehicle(car_info, selected_user[1]['did'])

        if registration_result:
            st.success(f"Vehicle registered successfully for {registration_result}.")
        else:
            st.error("Failed to register the vehicle.")

    # Display current JSON data for reference
    st.subheader("Current Car Information (JSON)")
    st.json(car_info)