import streamlit as st

def HomePage(self):
    # Title with custom styling
    st.markdown("""
    <style>
    .title {
        font-size: 3em;
        color: #1E3D59;
        text-align: center;
        padding: 20px 0;
        margin-bottom: 30px;
    }
    .subtitle {
        font-size: 1.5em;
        color: #666;
        text-align: center;
        margin-bottom: 50px;
    }
    .stat-box {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        height: 100%;
    }
    .stat-number {
        font-size: 2em;
        font-weight: bold;
        color: #1E3D59;
    }
    .stat-label {
        color: #666;
        margin-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<h1 class="title">IoV Self-Sovereign Identity Platform</h1>', unsafe_allow_html=True)
    st.markdown("""
    <p class="subtitle">
    Empowering secure digital identities for vehicles and users in the Internet of Vehicles ecosystem
    </p>
    """, unsafe_allow_html=True)

    try:
        registered_addresses = self.blockchain_service.contract.functions.getRegisteredAddresses().call()
        total_users = len(registered_addresses)
        
        # Get user type counts
        type_counts = self._count_user_types(registered_addresses)
        
        # Count vehicles (using blockchain directly instead of did_service)
        total_vehicles = type_counts['Vehicles']
        
        # First row of statistics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            <div class="stat-box">
                <div class="stat-number">{}</div>
                <div class="stat-label">Total Users</div>
            </div>
            """.format(total_users), unsafe_allow_html=True)
            
        with col2:
            st.markdown("""
            <div class="stat-box">
                <div class="stat-number">{}</div>
                <div class="stat-label">Registered Vehicles</div>
            </div>
            """.format(total_vehicles), unsafe_allow_html=True)
            
        with col3:
            st.markdown("""
            <div class="stat-box">
                <div class="stat-number">{}</div>
                <div class="stat-label">Active DIDs</div>
            </div>
            """.format(total_users * 2 + total_vehicles * 2), unsafe_allow_html=True)

        # Second row of statistics
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            <div class="stat-box">
                <div class="stat-number">{}</div>
                <div class="stat-label">Roadside Units</div>
            </div>
            """.format(type_counts['RSU']), unsafe_allow_html=True)
            
        with col2:
            st.markdown("""
            <div class="stat-box">
                <div class="stat-number">{}</div>
                <div class="stat-label">Insurance Providers</div>
            </div>
            """.format(type_counts['Insurance']), unsafe_allow_html=True)
            
        with col3:
            st.markdown("""
            <div class="stat-box">
                <div class="stat-number">{}</div>
                <div class="stat-label">Service Providers</div>
            </div>
            """.format(type_counts['Companies']), unsafe_allow_html=True)

        # Quick actions section
        st.markdown("### Quick Actions")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("➕ Register New User", use_container_width=True):
                st.session_state['page'] = 'Create DID'
                st.experimental_rerun()
                
        with col2:
            if st.button("🚗 Register New Vehicle", use_container_width=True):
                st.session_state['page'] = 'Register Vehicle Page'
                st.experimental_rerun()

        # Recent activity
        st.markdown("### Recent Activity")
        if total_users > 0:
            recent_users = [self.blockchain_service.contract.functions.users(addr).call() 
                            for addr in registered_addresses[-3:]]  # Last 3 users
            for user in reversed(recent_users):
                st.markdown(f"- 🔷 New {self._get_user_type_name(user[2])}: {user[1]}")
        else:
            st.info("No recent activity")

    except Exception as e:
        st.error(f"Error loading platform statistics: {str(e)}")