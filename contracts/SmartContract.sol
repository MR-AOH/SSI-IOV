// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/**
 * @title SmartContract
 * @dev Comprehensive smart contract for managing decentralized identities, 
 * vehicle registrations, multi-party interactions, and IoV ecosystem interactions
 */
contract SmartContract {
    // Enum for user types with expanded roles
    enum UserType { 
        Individual, 
        Mechanic, 
        InsuranceCompany, 
        RoadsideUnit,
        VehicleManufacturer,
        Car
    }

    // Struct to represent different entities
    struct User {
        address userAddress;
        string name;
        UserType userType;
        string entityDID;
        string walletDID;
        bool isRegistered;
        uint256 registrationTimestamp;
    }

    struct Vehicle {
        string vin;
        string make;
        string model;
        uint256 year;
        address currentOwner;
        address[] previousOwners;
        string entityDID;
        string walletDID;
        string credentialDID;
        bool isRegistered;
        address currentInsurer;
        address[] maintenanceProviders;
    }

    struct RoadsideUnit {
        address unitAddress;
        string name;
        string location;
        string entityDID;
        string walletDID;
        bool isActive;
        uint256 registrationTimestamp;
    }

    struct MaintenanceRecord {
        address mechanic;
        string serviceDescription;
        uint256 timestamp;
        bool isCritical;
    }

    struct InsurancePolicy {
        address insurer;
        address vehicleOwner;
        string vin;
        uint256 startDate;
        uint256 endDate;
        bool isActive;
    }

    struct Interaction {
        address source;
        address destination;
        string sourceIdentifier;      // Can be VIN, DID, or other identifier
        string destinationIdentifier; // Can be VIN, DID, or other identifier
        string interactionType;
        bytes payload;
        uint256 timestamp;
    }

    struct DIDDocument {
        string did;
        string document;  // JSON string of the DID document
        uint256 timestamp;
        bool isActive;
        address controller;  // Address that controls this DID
    }

    // Mappings to store entities
    mapping(address => User) public users;
    mapping(string => Vehicle) public vehicles;
    mapping(string => InsurancePolicy) public vehicleInsurance;
    mapping(address => RoadsideUnit) public roadsideUnits;
    
    // DID Management
    mapping(string => bool) public didRegistry;
    mapping(string => DIDDocument) public didDocuments;  // Store DID documents

    // Mapping from DID to user address
    mapping(string => address) public didToAddress;

    // Mapping to track registered DIDs
    mapping(string => bool) public registeredDIDs;

    // Array to track all registered addresses
    address[] private registeredAddresses;

    // Array to track all registered VINs
    string[] public registeredVINs;

    // Tracking arrays
    Interaction[] public interactions;

    // Mappings for authorized mechanics and maintenance history
    mapping(string => mapping(address => bool)) public authorizedMechanics;
    mapping(string => mapping(address => MaintenanceRecord[])) public maintenanceHistory;

    // Credential storage
    mapping(string => string) private credentials;
    mapping(string => address) private credentialIssuers;
    mapping(string => string) private credentialSubjects;

    // Events for tracking actions
    event UserRegistered(address indexed userAddress, string name, UserType userType);
    event VehicleRegistered(string indexed vin, address indexed owner);
    event VehicleOwnershipTransferred(string indexed vin, address indexed previousOwner, address indexed newOwner);
    event MaintenanceRecordAdded(string indexed vin, address indexed mechanic, string serviceDescription);
    event InsurancePolicyCreated(string indexed vin, address indexed insurer, address indexed owner);
    event MechanicAuthorized(string indexed vin, address indexed mechanic);
    event RoadsideUnitRegistered(address indexed unitAddress, string name, string location);
    event DIDRegistered(string indexed did);
    event InteractionRecorded(string indexed sourceIdentifier, string indexed destinationIdentifier, string interactionType);
    event DIDDocumentUpdated(string indexed did, address indexed controller, uint256 timestamp);

    // Modifiers (remain the same)
    modifier onlyUnregisteredUser() {
        require(!users[msg.sender].isRegistered, "User already registered");
        _;
    }

    modifier onlyRegisteredUser() {
        require(users[msg.sender].isRegistered, "User not registered");
        _;
    }

    modifier onlyVehicleOwner(string memory _vin) {
        require(vehicles[_vin].currentOwner == msg.sender, "Not vehicle owner");
        _;
    }

    modifier onlyMechanic() {
        require(users[msg.sender].userType == UserType.Mechanic, "Not a mechanic");
        _;
    }

    modifier onlyInsuranceCompany() {
        require(users[msg.sender].userType == UserType.InsuranceCompany, "Not an insurance company");
        _;
    }

    modifier onlyRoadsideUnit() {
        require(users[msg.sender].userType == UserType.RoadsideUnit, "Not a roadside unit");
        _;
    }

    /**
     * @dev Register a new user with Decentralized Identity
     */
    function registerUser(
        string memory _name, 
        UserType _userType,
        string memory _entityDID,
        string memory _walletDID
    ) public {
        require(bytes(_name).length > 0, "Name cannot be empty");
        require(bytes(_entityDID).length > 0, "Entity DID cannot be empty");
        require(bytes(_walletDID).length > 0, "Wallet DID cannot be empty");
        require(!users[msg.sender].isRegistered, "User already registered");
        
        users[msg.sender] = User({
            userAddress: msg.sender,
            name: _name,
            userType: _userType,
            entityDID: _entityDID,
            walletDID: _walletDID,
            isRegistered: true,
            registrationTimestamp: block.timestamp
        });
        
        registeredAddresses.push(msg.sender);
        
        didToAddress[_entityDID] = msg.sender;
        didToAddress[_walletDID] = msg.sender;
        
        registeredDIDs[_entityDID] = true;
        registeredDIDs[_walletDID] = true;
        
        emit UserRegistered(msg.sender, _name, _userType);
        emit DIDRegistered(_entityDID);
        emit DIDRegistered(_walletDID);
    }

    /**
     * @dev Authorize a mechanic for a specific vehicle
     */
    function authorizeMechanic(
        string memory _vin, 
        address _mechanic
    ) public onlyVehicleOwner(_vin) {
        require(users[_mechanic].userType == UserType.Mechanic, "Not a registered mechanic");
        
        authorizedMechanics[_vin][_mechanic] = true;
        
        emit MechanicAuthorized(_vin, _mechanic);
    }

    /**
     * @dev Add maintenance record for a vehicle
     */
    function addMaintenanceRecord(
        string memory _vin, 
        string memory _serviceDescription, 
        bool _isCritical
    ) public onlyMechanic {
        require(authorizedMechanics[_vin][msg.sender], "Not authorized for this vehicle");

        MaintenanceRecord memory record = MaintenanceRecord({
            mechanic: msg.sender,
            serviceDescription: _serviceDescription,
            timestamp: block.timestamp,
            isCritical: _isCritical
        });
        
        maintenanceHistory[_vin][msg.sender].push(record);
        vehicles[_vin].maintenanceProviders.push(msg.sender);
        
        emit MaintenanceRecordAdded(_vin, msg.sender, _serviceDescription);
    }

    /**
     * @dev Create insurance policy for a vehicle
     */
    function createInsurancePolicy(
        string memory _vin, 
        uint256 _startDate, 
        uint256 _endDate
    ) public onlyInsuranceCompany {
        Vehicle storage vehicle = vehicles[_vin];
        
        require(vehicle.isRegistered, "Vehicle not registered");
        require(vehicle.currentOwner != address(0), "Vehicle has no owner");

        vehicleInsurance[_vin] = InsurancePolicy({
            insurer: msg.sender,
            vehicleOwner: vehicle.currentOwner,
            vin: _vin,
            startDate: _startDate,
            endDate: _endDate,
            isActive: true
        });

        vehicle.currentInsurer = msg.sender;

        emit InsurancePolicyCreated(_vin, msg.sender, vehicle.currentOwner);
    }

    /**
     * @dev Transfer vehicle ownership with comprehensive checks
     */
    function transferVehicleOwnership(
        string memory _vin, 
        address _newOwner
    ) public onlyVehicleOwner(_vin) {
        require(users[_newOwner].isRegistered, "New owner must be registered");

        Vehicle storage vehicle = vehicles[_vin];
        address previousOwner = vehicle.currentOwner;

        vehicle.currentOwner = _newOwner;
        vehicle.previousOwners.push(_newOwner);

        if (vehicleInsurance[_vin].isActive) {
            vehicleInsurance[_vin].isActive = false;
        }

        emit VehicleOwnershipTransferred(_vin, previousOwner, _newOwner);
    }

    /**
     * @dev Record any interaction between two entities in the system
     */
    function recordInteraction(
        address _source,
        address _destination,
        string memory _sourceIdentifier,
        string memory _destinationIdentifier,
        string memory _interactionType,
        bytes memory _payload
    ) public {
        require(users[_source].isRegistered || vehicles[_sourceIdentifier].isRegistered, 
            "Source entity not registered");
        require(
            users[_destination].isRegistered || 
            vehicles[_destinationIdentifier].isRegistered || 
            roadsideUnits[_destination].isActive, 
            "Destination entity not registered"
        );

        Interaction memory interaction = Interaction({
            source: _source,
            destination: _destination,
            sourceIdentifier: _sourceIdentifier,
            destinationIdentifier: _destinationIdentifier,
            interactionType: _interactionType,
            payload: _payload,
            timestamp: block.timestamp
        });

        interactions.push(interaction);

        emit InteractionRecorded(_sourceIdentifier, _destinationIdentifier, _interactionType);
    }

    /**
     * @dev Get all interactions for a specific entity
     * @param _identifier The identifier (VIN, DID, etc.) of the entity
     * @return Array of interactions where the entity was either source or destination
     */
    function getEntityInteractions(string memory _identifier) public view returns (Interaction[] memory) {
        Interaction[] memory filteredInteractions = new Interaction[](interactions.length);
        uint256 count = 0;

        for (uint256 i = 0; i < interactions.length; i++) {
            if (keccak256(abi.encodePacked(interactions[i].sourceIdentifier)) == keccak256(abi.encodePacked(_identifier)) ||
                keccak256(abi.encodePacked(interactions[i].destinationIdentifier)) == keccak256(abi.encodePacked(_identifier))) {
                filteredInteractions[count] = interactions[i];
                count++;
            }
        }

        // Resize array to actual count
        assembly {
            mstore(filteredInteractions, count)
        }

        return filteredInteractions;
    }

    /**
     * @dev Get all interactions between two specific entities
     */
    function getInteractionsBetweenEntities(
        string memory _identifier1, 
        string memory _identifier2
    ) public view returns (Interaction[] memory) {
        Interaction[] memory filteredInteractions = new Interaction[](interactions.length);
        uint256 count = 0;

        for (uint256 i = 0; i < interactions.length; i++) {
            if ((keccak256(abi.encodePacked(interactions[i].sourceIdentifier)) == keccak256(abi.encodePacked(_identifier1)) &&
                 keccak256(abi.encodePacked(interactions[i].destinationIdentifier)) == keccak256(abi.encodePacked(_identifier2))) ||
                (keccak256(abi.encodePacked(interactions[i].sourceIdentifier)) == keccak256(abi.encodePacked(_identifier2)) &&
                 keccak256(abi.encodePacked(interactions[i].destinationIdentifier)) == keccak256(abi.encodePacked(_identifier1)))) {
                filteredInteractions[count] = interactions[i];
                count++;
            }
        }

        // Resize array to actual count
        assembly {
            mstore(filteredInteractions, count)
        }

        return filteredInteractions;
    }



    /**
     * @dev Verify if a DID is valid
     */
    function isValidDID(string memory _did) public view returns (bool) {
        return didRegistry[_did];
    }

    /**
     * @dev Store a verifiable credential
     */
    function storeCredential(
        string memory _credentialId,
        string memory _issuerDid,
        string memory _subjectDid,
        string memory _credentialData
    ) public {
        require(isValidDID(_issuerDid), "Invalid issuer DID");
        require(isValidDID(_subjectDid), "Invalid subject DID");
        require(bytes(credentials[_credentialId]).length == 0, "Credential ID already exists");

        credentials[_credentialId] = _credentialData;
        credentialIssuers[_credentialId] = msg.sender;
        credentialSubjects[_credentialId] = _subjectDid;
    }

    /**
     * @dev Get a stored credential
     */
    function getCredential(string memory _credentialId) public view returns (string memory) {
        require(bytes(credentials[_credentialId]).length > 0, "Credential not found");
        return credentials[_credentialId];
    }

    /**
     * @dev Get the number of registered addresses
     */
    function getRegisteredAddressesCount() public view returns (uint256) {
        return registeredAddresses.length;
    }

    /**
     * @dev Get all registered addresses
     */
    function getRegisteredAddresses() public view returns (address[] memory) {
        return registeredAddresses;
    }

    /**
     * @dev Register a vehicle with its DIDs
     */
    function registerVehicle(
        string memory _vin,
        string memory _ownerDID,
        string memory _entityDID,
        uint256 _year,
        string memory _make,
        string memory _model,
        string memory _walletDID
    ) public {
        // Find owner's address from their DID
        address ownerAddress;
        bool found = false;
        for (uint256 i = 0; i < registeredAddresses.length; i++) {
            address userAddress = registeredAddresses[i];
            if (keccak256(bytes(users[userAddress].entityDID)) == keccak256(bytes(_ownerDID))) {
                ownerAddress = userAddress;
                found = true;
                break;
            }
        }
        require(found, "Owner not found");

        // Create new vehicle
        address[] memory emptyAddresses = new address[](0);
        vehicles[_vin] = Vehicle({
            vin: _vin,
            make: _make,
            model: _model,
            year: _year,
            currentOwner: ownerAddress,  // Set the owner's address
            previousOwners: emptyAddresses,
            entityDID: _entityDID,
            walletDID: _walletDID,
            credentialDID: "",
            isRegistered: true,
            currentInsurer: address(0),
            maintenanceProviders: emptyAddresses
        });

        // Add to registered VINs
        registeredVINs.push(_vin);

        // Register DIDs
        didRegistry[_entityDID] = true;
        didRegistry[_walletDID] = true;

        emit VehicleRegistered(_vin, ownerAddress);
        emit DIDRegistered(_entityDID);
        emit DIDRegistered(_walletDID);
    }

    /**
     * @dev Function to get user address by DID
     */
    function getUserAddressByDID(string memory _entityDID) public view returns (address) {
        address userAddress = didToAddress[_entityDID];
        require(userAddress != address(0), "User not found");
        return userAddress;
    }

    /**
     * @dev Store or update a DID document
     * @param _did The DID to store/update
     * @param _document The DID document as a JSON string
     */
    function storeDIDDocument(
        string memory _did,
        string memory _document
    ) public {
        require(bytes(_did).length > 0, "DID cannot be empty");
        require(bytes(_document).length > 0, "Document cannot be empty");
        
        // Check if caller is authorized to update this DID
        if (didDocuments[_did].controller != address(0)) {
            require(
                didDocuments[_did].controller == msg.sender,
                "Not authorized to update this DID document"
            );
        }
        
        // Store/update the DID document
        didDocuments[_did] = DIDDocument({
            did: _did,
            document: _document,
            timestamp: block.timestamp,
            isActive: true,
            controller: msg.sender
        });
        
        // Register the DID if not already registered
        if (!didRegistry[_did]) {
            didRegistry[_did] = true;
        }
        
        emit DIDDocumentUpdated(_did, msg.sender, block.timestamp);
    }

    /**
     * @dev Get a DID document
     * @param _did The DID to retrieve
     * @return document The DID document as a JSON string
     * @return timestamp When the document was last updated
     * @return isActive Whether the DID is active
     * @return controller Address that controls this DID
     */
    function getDIDDocument(string memory _did) 
        public 
        view 
        returns (
            string memory document,
            uint256 timestamp,
            bool isActive,
            address controller
        ) 
    {
        require(bytes(_did).length > 0, "DID cannot be empty");
        require(didRegistry[_did], "DID not registered");
        
        DIDDocument memory doc = didDocuments[_did];
        return (
            doc.document,
            doc.timestamp,
            doc.isActive,
            doc.controller
        );
    }

   
    /**
     * @dev Check if a user exists
     */
    function isUserRegistered(string memory _did) public view returns (bool) {
        return registeredDIDs[_did];
    }

    /**
     * @dev Get all vehicles owned by a user based on their DID
     */
    function getUserVehicles(string memory _ownerDID) public view returns (Vehicle[] memory) {
        // First count how many vehicles the user owns
        uint256 count = 0;
        for (uint256 i = 0; i < registeredVINs.length; i++) {
            string memory vin = registeredVINs[i];
            Vehicle memory vehicle = vehicles[vin];
            
            // Find owner's address from their DID
            for (uint256 j = 0; j < registeredAddresses.length; j++) {
                address userAddress = registeredAddresses[j];
                if (keccak256(bytes(users[userAddress].entityDID)) == keccak256(bytes(_ownerDID))) {
                    if (vehicle.currentOwner == userAddress) {
                        count++;
                    }
                    break;
                }
            }
        }
        
        // Create array of owned vehicles
        Vehicle[] memory ownedVehicles = new Vehicle[](count);
        uint256 index = 0;
        
        // Fill the array with owned vehicles
        for (uint256 i = 0; i < registeredVINs.length; i++) {
            string memory vin = registeredVINs[i];
            Vehicle memory vehicle = vehicles[vin];
            
            // Find owner's address from their DID
            for (uint256 j = 0; j < registeredAddresses.length; j++) {
                address userAddress = registeredAddresses[j];
                if (keccak256(bytes(users[userAddress].entityDID)) == keccak256(bytes(_ownerDID))) {
                    if (vehicle.currentOwner == userAddress) {
                        ownedVehicles[index] = vehicle;
                        index++;
                    }
                    break;
                }
            }
        }
        
        return ownedVehicles;
    }
}