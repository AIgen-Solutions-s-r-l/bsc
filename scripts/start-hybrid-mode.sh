#!/bin/bash

# BSC Imbalance Engine - Hybrid Mode Launcher
# Uses external RPC for state queries + local minimal node for mempool

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║    BSC Imbalance Engine - Hybrid Mode (No Sync Required)    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Configuration
BSC_STATE_RPC="${BSC_STATE_RPC:-https://bsc-dataseed.bnbchain.org}"
BSC_MEMPOOL_RPC="${BSC_MEMPOOL_RPC:-http://127.0.0.1:8545}"
DATADIR="./bsc-data-minimal"

# Stop existing node
echo "📋 Stopping existing node..."
pkill -f "geth --config" 2>/dev/null || echo "   No existing node found"

# Create minimal datadir
if [ ! -d "$DATADIR" ]; then
    echo "📁 Creating minimal datadir..."
    ./build/bin/geth --datadir $DATADIR init genesis.json
fi

# Start minimal node (for mempool access only)
echo ""
echo "🚀 Starting minimal BSC node..."
echo "   Purpose: Mempool monitoring only"
echo "   State queries: Using external RPC at $BSC_STATE_RPC"
echo ""

./build/bin/geth \
  --datadir $DATADIR \
  --networkid 56 \
  --http \
  --http.api eth,net,web3,txpool,imbalance \
  --http.addr 127.0.0.1 \
  --http.port 8545 \
  --http.vhosts "*" \
  --http.corsdomain "*" \
  --ws \
  --ws.api eth,net,web3,txpool,imbalance \
  --ws.addr 127.0.0.1 \
  --ws.port 8546 \
  --maxpeers 50 \
  --syncmode snap \
  --cache 512 \
  >> geth-hybrid.log 2>&1 &

NODE_PID=$!

echo "✅ Node started with PID: $NODE_PID"
echo ""
echo "⏳ Waiting for node to initialize (10 seconds)..."
sleep 10

# Test connection
echo ""
echo "🔍 Testing connections..."

# Test local node
if curl -s -X POST http://127.0.0.1:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"net_version","params":[],"id":1}' \
  | grep -q '"result":"56"'; then
    echo "   ✅ Local node: Connected"
else
    echo "   ❌ Local node: Failed to connect"
    exit 1
fi

# Test external RPC
if curl -s -X POST $BSC_STATE_RPC \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  | grep -q '"result"'; then
    echo "   ✅ External RPC: Connected"
    BLOCK=$(curl -s -X POST $BSC_STATE_RPC \
      -H "Content-Type: application/json" \
      -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
      | jq -r '.result' | xargs printf "%d")
    echo "      Current block: $BLOCK"
else
    echo "   ❌ External RPC: Failed to connect"
    exit 1
fi

# Test imbalance API
if curl -s -X POST http://127.0.0.1:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"imbalance_getStats","params":[],"id":1}' \
  | grep -q '"running":true'; then
    echo "   ✅ Imbalance Engine: Running"
else
    echo "   ❌ Imbalance Engine: Not available"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                     HYBRID MODE ACTIVE                       ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Configuration:"
echo "  • Local Mempool RPC: $BSC_MEMPOOL_RPC"
echo "  • External State RPC: $BSC_STATE_RPC"
echo "  • Node PID: $NODE_PID"
echo "  • Logs: geth-hybrid.log"
echo ""
echo "Usage:"
echo "  • Test client:    ./build/bin/imbalance-client --test"
echo "  • Monitor pool:   ./build/bin/imbalance-client --pool 0x..."
echo "  • View logs:      tail -f geth-hybrid.log"
echo "  • Stop node:      kill $NODE_PID"
echo ""
echo "✨ Ready to detect arbitrage opportunities!"
echo ""

# Export for use in other scripts
export BSC_STATE_RPC
export BSC_MEMPOOL_RPC
echo "BSC_STATE_RPC=$BSC_STATE_RPC" > .env.hybrid
echo "BSC_MEMPOOL_RPC=$BSC_MEMPOOL_RPC" >> .env.hybrid
echo "NODE_PID=$NODE_PID" >> .env.hybrid

echo "Environment exported to .env.hybrid"
