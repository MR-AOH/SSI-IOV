import time
import streamlit as st

def CreateDIDPage(self):
    st.header("Create Decentralized Identifier (DID)")

    name = st.text_input("Enter your name:")
    user_type = st.selectbox("Select User Type:", [
        "Individual",
        "Mechanic",
        "Insurance Provider",
        "Roadside Unit",
        "Vehicle Manufacturer"
    ])

    if st.button("Create DID"):
        if not name:
            st.error("Please enter your name")
            return
            
        try:
            # Create DIDs and register user
            start_time = time.time()
            result = self.did_service.create_did(user_type, name)
            end_time = time.time()
            resolution_time = (end_time - start_time) * 1000  # Convert to milliseconds
            st.write(f"Resolution Time: {resolution_time:.2f} ms")
            if result:
                st.success(f"""DID created successfully! 
                Entity DID: {result['entity_did']}
                Wallet DID: {result['wallet_did']}""")
            else:
                st.error("Failed to create DID. Please try again.")
        except Exception as e:
            st.error(f"Error creating DID: {str(e)}")