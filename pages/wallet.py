import streamlit as st

def RenderWalletUI(self):
    """Render wallet UI with policy management."""
    st.subheader("Wallet Configuration")
    
    # Get list of registered users
    users = self.blockchain_service.get_registered_users()
    if not users:
        st.error("No registered users found. Please register a user first.")
        return
    
    # User selection
    user_options = {f"{user['name']} ({user['did']})": user for user in users}
    selected_user = st.selectbox("Select User", list(user_options.keys()))
    
    if selected_user:
        user = user_options[selected_user]
        
        # Create wallet if it doesn't exist
        if not self.wallet_service.get_wallet(user['did']):
            self.wallet_service.create_wallet(user['did'], user['type'])
        
        wallet = self.wallet_service.get_wallet(user['did'])
        if not wallet:
            st.error("Failed to load wallet")
            return
        
        # Show DID and type
        st.write(f"DID: {wallet['did']}")
        st.write(f"Type: {wallet['type']}")
        
        # Data sharing policies
        st.subheader("Data Sharing Policies")
        
        for data_type, policy in wallet['policies'].items():
            with st.expander(f"{data_type.replace('_', ' ').title()} Policy"):
                # Share with selection
                share_with = st.multiselect(
                    f"Share {data_type} with:",
                    ['emergency', 'roadside_unit', 'insurance', 'service', 'vehicle'],
                    default=policy['share_with']
                )
                
                # Consent requirement with a unique key
                requires_consent = st.checkbox(
                    f"Require consent for {data_type}",
                    value=policy['requires_consent'],
                    key=f"requires_consent_{data_type}"  # Unique key using data_type
                )
                
                # Emergency auto-share with a unique key
                auto_share_emergency = st.checkbox(
                    f"Auto-share in emergencies",
                    value=policy['auto_share_emergency'],
                    key=f"auto_share_emergency_{data_type}"  # Unique key using data_type
                )
                
                # Update policy if changed
                if (share_with != policy['share_with'] or 
                    requires_consent != policy['requires_consent'] or 
                    auto_share_emergency != policy['auto_share_emergency']):
                    self.wallet_service.update_policy(wallet['did'], data_type, {
                        'share_with': share_with,
                        'requires_consent': requires_consent,
                        'auto_share_emergency': auto_share_emergency
                    })
        
        # Show shared data
        if 'shared_data' in wallet and wallet['shared_data']:
            st.subheader("Shared Data")
            for data_type, data in wallet['shared_data'].items():
                with st.expander(f"{data_type.replace('_', ' ').title()}"):
                    st.json(data)
        
        # Show notifications
        notifications = self.wallet_service.get_notifications(wallet['did'])
        if notifications:
            st.subheader("Notifications")
            for notif in notifications:
                with st.expander(f"📩 {notif['message']}", expanded=True):
                    st.write(f"Type: {notif['type']}")
                    if notif['type'] == 'data_request':
                        request = notif['request']
                        st.write(f"Requester: {request['requester_did']}")
                        st.write(f"Data Type: {request['data_type']}")
                        st.write(f"Reason: {request['reason']}")
                        st.write(f"Emergency: {'Yes' if request['is_emergency'] else 'No'}")
                        
                        if request['status'] == 'pending':
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("Approve", key=f"approve_{request['requester_did']}_{request['data_type']}"):
                                    self.wallet_service.respond_to_request(
                                        wallet['did'],
                                        request['requester_did'],
                                        request['data_type'],
                                        True
                                    )
                            with col2:
                                if st.button("Reject", key=f"reject_{request['requester_did']}_{request['data_type']}"):
                                    self.wallet_service.respond_to_request(
                                        wallet['did'],
                                        request['requester_did'],
                                        request['data_type'],
                                        False
                                    )
        
        if st.button("Clear Notifications"):
            self.wallet_service.clear_notifications(wallet['did'])
