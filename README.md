# 🚗 Self-Sovereign Identity Framework for Internet of Vehicles (IoV)

This project implements a Self-Sovereign Identity (SSI) based framework for managing decentralized identities (DIDs) for vehicles and users. It simulates real-world use cases including car-to-car communication, secure data transfer, and identity verification via a smart contract on Ethereum.

## 📦 Features

- DID creation for vehicles and users
- Smart contract deployment and management using Truffle
- Wallet simulation for cars and users
- Communication between entities (cars, users)
- Benchmarking performance and generating graphs for paper reproduction

---

## 🛠 Prerequisites

Before running the project, make sure you have the following installed:

- [Ganache](https://trufflesuite.com/ganache/) (Desktop version preferred)
- [Node.js & npm](https://nodejs.org/)
- [Truffle](https://trufflesuite.com/truffle/)
- Python 3.8+
- `pip` (Python package manager)
- MetaMask (optional, for contract interaction)

---

## 📂 Project Structure

```
.
├── services/address_manager.py      # Manage and store private keys and account addresses
├── api/server.py                    # Backend server for SSI functions
├── main.py                          # Main dashboard for creating and managing DIDs
├── wallet/entity_wallet.py          # Wallet simulation for users/cars using DIDs
├── benchmark.py                     # Run benchmarks for the framework
├── graphs.py                        # Generate visual graphs from benchmark results
├── contracts/                       # Truffle smart contract files
├── migrations/                      # Truffle deployment scripts
├── .env                             # Environment variables
```

---

## 🚀 Getting Started

First of all run the requirements file to have all the  modules:

```bash
pip install -r requirements.txt
```

### Step 1: Setup Ganache

1. Open Ganache desktop application.
2. Copy the **first address** and **private key**.
3. Paste the first address and key into the `.env` file:

```
PRIVATE_KEY=your_first_private_key
PUBLIC_ADDRESS=your_first_account_address
```

4. Also Paste **all keys and addresses** into the `address_manager.py` file.

---

### Step 2: Deploy Smart Contract

Make sure Truffle is installed:

```bash
npm install -g truffle
```

Then deploy the contract:

```bash
cd contracts
truffle compile
truffle migrate --reset
```

After successful deployment, copy the deployed **contract address** from the terminal and paste it into your `.env` file:

```
SMART_CONTRACT_ADDRESS=your_deployed_contract_address
```

---
Adding other .env keys:
```
GOOGLE_API_KEY=your_google_api_key_here

# Optional: Path to local Llama model (if you have a custom path)
# LOCAL_MODEL_PATH=/path/to/your/local/model
```

### Step 3: Start the Backend Server

Run the backend server:

```bash
python server.py
```

This handles DID interactions, contract functions, and wallet communication.

---

### Step 4: Launch the Framework Dashboard

```bash
python main.py
```

This is the primary interface where you:

- Create DIDs for users and cars
- Transfer car ownership
- View DID details

---

### Step 5: Simulate Wallet Interaction

To simulate wallet communication or perform specific actions:

```bash
python entity_wallet.py
```

- Log in using the **DID** you previously created.
- Simulate user or car preferences, interactions, and identity management.
- To test communication between two cars/entities:
  - Run two instances of `entity_wallet.py` in separate terminals
  - Login using different DIDs

---

### Step 6: Reproduce Paper Results (Optional)

To reproduce experimental benchmarks and graphs as shown in the associated research paper:

```bash
python benchmark.py
python graphs.py
```

---

## 📄 Environment File (.env) Example

```env
PRIVATE_KEY=your_first_private_key
PUBLIC_ADDRESS=your_first_account_address
SMART_CONTRACT_ADDRESS=deployed_contract_address
```

---

## 📊 Research Contribution

This project is part of a broader research initiative to demonstrate the applicability of SSI in securing IoV communications, vehicle identification, and privacy-preserving data exchange. For technical details, benchmarks, and architecture diagrams, refer to the associated research paper.

---

## 🧪 Technologies Used

- Python 3.8+
- Ethereum / Solidity
- Truffle
- Ganache
- Web3.py
- Matplotlib / Pandas (for graphs)
- Flask or similar (if used in server.py)

---

## 📬 Contact

For issues, suggestions, or collaborations, please open an issue or reach out through the repository.

---

## 📜 License

MIT License – see [LICENSE](LICENSE) file for details.
