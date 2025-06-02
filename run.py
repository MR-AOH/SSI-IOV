import subprocess
import sys
import os
from pathlib import Path

# def run_api_server():
#     """Run the FastAPI server"""
#     print("Starting API server...")
#     env = os.environ.copy()
#     env["PYTHONPATH"] = str(project_root)
#     subprocess.Popen([sys.executable, "api/server.py"], env=env)

def run_wallet_interface():
    """Run the wallet interface"""
    print("Starting wallet interface...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)
    subprocess.Popen([sys.executable, "-m", "streamlit", "run", "wallet/entity_wallet.py"], env=env)

def run_blockchain_interface():
    """Run the blockchain explorer interface"""
    print("Starting blockchain explorer...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)
    subprocess.Popen([sys.executable, "-m", "streamlit", "run", "main.py"], env=env)

if __name__ == "__main__":
    # Ensure we're in the project root directory
    project_root = Path(__file__).parent.absolute()
    os.chdir(project_root)

    # Install requirements if needed
    # print("Installing requirements...")
    # subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    # Start all components
    # run_api_server()
    run_wallet_interface()
    run_blockchain_interface()

    print("\nAll components started!")
    print("Access the interfaces at:")
    print("- API Documentation: http://localhost:8000/docs")
    print("- Entity Wallet: http://localhost:8501")
    print("- Blockchain Explorer: http://localhost:8502")
