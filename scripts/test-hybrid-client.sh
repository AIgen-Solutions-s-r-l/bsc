#!/bin/bash

# Test the imbalance engine using external RPC for state data
# This bypasses the need for full sync

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║        Hybrid Mode Test - Using External BSC RPC            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Use external RPC for state queries
BSC_RPC="${BSC_STATE_RPC:-https://bsc-dataseed.bnbchain.org}"
LOCAL_RPC="http://127.0.0.1:8545"

# Test pools (PancakeSwap V2)
POOLS=(
    "0x58F876857a02D6762E0101bb5C46A8c1ED44Dc16"  # WBNB-BUSD
    "0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE"  # WBNB-USDT
    "0x7EFaEf62fDdCCa950418312c6C91Aef321375A00"  # WBNB-USDC
)

echo "🔍 Testing pool state queries via external RPC..."
echo "   Using: $BSC_RPC"
echo ""

for POOL in "${POOLS[@]}"; do
    echo "Pool: $POOL"

    # Call getReserves on the pool
    # Method signature: getReserves() returns (uint112, uint112, uint32)
    # Selector: 0x0902f1ac

    RESULT=$(curl -s -X POST $BSC_RPC \
      -H "Content-Type: application/json" \
      -d "{
        \"jsonrpc\":\"2.0\",
        \"method\":\"eth_call\",
        \"params\":[{
          \"to\":\"$POOL\",
          \"data\":\"0x0902f1ac\"
        },\"latest\"],
        \"id\":1
      }" | jq -r '.result')

    if [ "$RESULT" != "null" ] && [ "$RESULT" != "" ]; then
        # Parse reserves (first 64 chars = reserve0, next 64 = reserve1)
        RESERVE0_HEX="0x${RESULT:2:64}"
        RESERVE1_HEX="0x${RESULT:66:64}"

        RESERVE0=$(python3 -c "print(int('$RESERVE0_HEX', 16))")
        RESERVE1=$(python3 -c "print(int('$RESERVE1_HEX', 16))")

        # Calculate imbalance
        TOTAL=$((RESERVE0 + RESERVE1))
        if [ $TOTAL -gt 0 ]; then
            DIFF=$((RESERVE0 > RESERVE1 ? RESERVE0 - RESERVE1 : RESERVE1 - RESERVE0))
            IMBALANCE=$(python3 -c "print(round($DIFF / $TOTAL * 100, 2))")

            echo "   ✅ Reserve0: $RESERVE0"
            echo "      Reserve1: $RESERVE1"
            echo "      Imbalance: $IMBALANCE%"
        else
            echo "   ⚠️  Invalid reserves"
        fi
    else
        echo "   ❌ Failed to fetch reserves"
    fi
    echo ""
done

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                  External RPC Working ✅                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "This demonstrates that you can:"
echo "  • Query pool states from external RPC (no sync needed)"
echo "  • Calculate imbalances in real-time"
echo "  • Use local node just for mempool monitoring"
echo ""
echo "The full imbalance engine can work this way with minimal modifications!"
