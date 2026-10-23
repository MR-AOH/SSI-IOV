#!/bin/bash
# Deploys DIDRegistry.sol to a running Ganache instance and prints the
# account + contract address you'll need for the C++ client.
#
# Automatically tries several EVM-version-targeted bytecode variants
# (produced by compile.js) until one deploys successfully, since Ganache
# installations vary in which hardfork they emulate. The ABI/function
# selectors are identical across all variants -- only the compiled
# opcodes differ -- so whichever one actually deploys is safe to use.
#
# USAGE:
#   1. Make sure Ganache is running. Note its RPC port (Ganache Desktop
#      GUI defaults to 7545; the `ganache` CLI defaults to 8545).
#   2. Compile first:  node compile.js   (requires: npm install solc)
#   3. Run:  ./deploy.sh 7545

set -e

RPC_PORT="${1:-7545}"
RPC_URL="http://127.0.0.1:${RPC_PORT}"
EVM_VERSIONS=("istanbul" "berlin" "london" "paris" "shanghai" "cancun")

echo "Checking Ganache at ${RPC_URL} ..."
if ! curl -s -m 3 -X POST "$RPC_URL" -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' | grep -q result; then
    echo "Could not reach Ganache at ${RPC_URL}. Is it running on this port?" >&2
    exit 1
fi

ACCOUNT=$(curl -s -m 3 -X POST "$RPC_URL" -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"eth_accounts","params":[],"id":1}' | jq -r '.result[0]')
echo "Using account: $ACCOUNT"
echo ""

DEPLOYED=0
for EVM in "${EVM_VERSIONS[@]}"; do
    BCFILE="bytecode_${EVM}.txt"
    if [ ! -f "$BCFILE" ]; then
        echo "[$EVM] $BCFILE not found -- run 'node compile.js' first." >&2
        continue
    fi

    echo "--- Trying EVM target: $EVM ---"
    BYTECODE=$(cat "$BCFILE")
    SEND_RESPONSE=$(curl -s -m 10 -X POST "$RPC_URL" -H "Content-Type: application/json" \
        -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_sendTransaction\",\"params\":[{\"from\":\"$ACCOUNT\",\"data\":\"0x$BYTECODE\",\"gas\":\"0x500000\",\"gasPrice\":\"0x4A817C800\"}],\"id\":1}")

    if echo "$SEND_RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
        ERRMSG=$(echo "$SEND_RESPONSE" | jq -r '.error.message')
        echo "  [$EVM] rejected: $ERRMSG"
        continue
    fi

    TXHASH=$(echo "$SEND_RESPONSE" | jq -r '.result')
    if [ "$TXHASH" = "null" ] || [ -z "$TXHASH" ]; then
        echo "  [$EVM] no tx hash returned, skipping"
        continue
    fi

    sleep 0.5
    RECEIPT=$(curl -s -m 3 -X POST "$RPC_URL" -H "Content-Type: application/json" \
        -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_getTransactionReceipt\",\"params\":[\"$TXHASH\"],\"id\":1}")
    CONTRACT_ADDR=$(echo "$RECEIPT" | jq -r '.result.contractAddress')
    STATUS=$(echo "$RECEIPT" | jq -r '.result.status')

    if [ "$STATUS" = "0x1" ] && [ "$CONTRACT_ADDR" != "null" ] && [ -n "$CONTRACT_ADDR" ]; then
        echo "  [$EVM] SUCCESS"
        echo ""
        echo "=== Deployment successful ==="
        echo "Working EVM target: $EVM   (use this same bytecode_${EVM}.txt for any redeploys)"
        echo "Account:  $ACCOUNT"
        echo "Contract: $CONTRACT_ADDR"
        echo ""
        echo "Run the client with:"
        echo "g++ -O2 -std=c++17 -o did_registry_client did_registry_client.cpp -l curl  ./did_registry_client $ACCOUNT $CONTRACT_ADDR"
        DEPLOYED=1
        break
    else
        echo "  [$EVM] deployed but reverted (status: $STATUS) -- trying next target"
    fi
done

if [ "$DEPLOYED" -eq 0 ]; then
    echo ""
    echo "None of the tried EVM targets (${EVM_VERSIONS[*]}) deployed successfully." >&2
    echo "Check your Ganache workspace settings for its configured hardfork," >&2
    echo "and add that exact name to the EVM_VERSIONS list in compile.js." >&2
    exit 1
fi