// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

// Matches the manuscript's Blockchain Layer (Section V-B): a tamper-evident
// store for DID Documents and credential anchors. Signature verification
// itself stays off-chain (Section V, Algorithm 2/EdDSA over Curve25519 has
// no native EVM precompile); this contract only implements BC.store /
// BC.retrieve (Eq. 16-17).
contract DIDRegistry {
    mapping(bytes32 => bytes) private documents;
    mapping(bytes32 => bytes) private credentials;

    event DIDStored(bytes32 indexed didHash, uint256 length);
    event VCAnchored(bytes32 indexed credHash, uint256 length);

    // BC.store(DID, Doc) -> on-chain record (Eq. 16)
    function storeDocument(bytes32 didHash, bytes calldata docData) external {
        documents[didHash] = docData;
        emit DIDStored(didHash, docData.length);
    }

    // Doc = BC.retrieve(DID) (Eq. 17)
    function retrieveDocument(bytes32 didHash) external view returns (bytes memory) {
        return documents[didHash];
    }

    // Algorithm 1, step 6: "Attester anchors VC on blockchain"
    function anchorCredential(bytes32 credHash, bytes calldata credData) external {
        credentials[credHash] = credData;
        emit VCAnchored(credHash, credData.length);
    }

    function retrieveCredential(bytes32 credHash) external view returns (bytes memory) {
        return credentials[credHash];
    }
}
