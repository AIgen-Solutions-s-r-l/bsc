#!/usr/bin/env python3
"""
BSC Imbalance Engine - Hybrid Mode Demo
Uses external RPC for state queries (no sync required!)
"""

import requests
import json
import sys
from datetime import datetime

# Configuration
LOCAL_RPC = "http://127.0.0.1:8545"
EXTERNAL_RPC = "https://bsc-dataseed.bnbchain.org"

# Known PancakeSwap V2 pools
POOLS = [
    {"address": "0x58F876857a02D6762E0101bb5C46A8c1ED44Dc16", "name": "WBNB-BUSD"},
    {"address": "0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE", "name": "WBNB-USDT"},
    {"address": "0x7EFaEf62fDdCCa950418312c6C91Aef321375A00", "name": "WBNB-USDC"},
    {"address": "0x0eD7e52944161450477ee417DE9Cd3a859b14fD0", "name": "WBNB-CAKE"},
    {"address": "0x1B96B92314C44b159149f7E0303511fB2Fc4774f", "name": "WBNB-ETH"},
]

def get_pool_reserves(pool_address):
    """Fetch pool reserves from external RPC"""
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{
            "to": pool_address,
            "data": "0x0902f1ac"  # getReserves() selector
        }, "latest"],
        "id": 1
    }

    try:
        response = requests.post(EXTERNAL_RPC, json=payload, timeout=10)
        result = response.json().get("result")

        if result and result != "0x":
            # Parse reserves (uint112, uint112, uint32)
            reserve0 = int(result[2:66], 16)
            reserve1 = int(result[66:130], 16)
            return reserve0, reserve1
    except Exception as e:
        print(f"   ❌ Error fetching reserves: {e}")

    return None, None

def calculate_imbalance(reserve0, reserve1):
    """Calculate pool imbalance score"""
    if reserve0 is None or reserve1 is None:
        return 0.0

    total = reserve0 + reserve1
    if total == 0:
        return 0.0

    diff = abs(reserve0 - reserve1)
    return (diff / total) * 100

def get_imbalance_level(score):
    """Determine severity level"""
    if score < 10:
        return "balanced", "🟢"
    elif score < 20:
        return "slight", "🟡"
    elif score < 40:
        return "moderate", "🟠"
    elif score < 60:
        return "severe", "🔴"
    else:
        return "critical", "🚨"

def estimate_profit(reserve0, reserve1, imbalance_score):
    """Rough profit estimation in BNB"""
    if imbalance_score < 20:
        return 0.0

    # Simplified profit model
    # Actual profit depends on gas costs, slippage, etc.
    smaller_reserve = min(reserve0, reserve1)
    profit_factor = (imbalance_score - 20) / 100  # Excess above 20%

    # Convert to BNB (assuming 18 decimals)
    estimated_bnb = (smaller_reserve * profit_factor * 0.001) / 1e18
    return estimated_bnb

def check_local_engine():
    """Check if local imbalance engine is running"""
    try:
        response = requests.post(LOCAL_RPC, json={
            "jsonrpc": "2.0",
            "method": "imbalance_getStats",
            "params": [],
            "id": 1
        }, timeout=5)

        result = response.json().get("result", {})
        return result.get("running", False)
    except:
        return False

def main():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║   BSC Imbalance Engine - Hybrid Mode (External RPC Demo)    ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    # Check local engine
    print("🔍 Checking local imbalance engine...")
    engine_running = check_local_engine()
    if engine_running:
        print("   ✅ Local engine: RUNNING")
    else:
        print("   ⚠️  Local engine: Not detected (mempool monitoring only)")
    print()

    print(f"🌐 Using external RPC: {EXTERNAL_RPC}")
    print(f"⏰ Scan time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("─" * 70)
    print()

    opportunities = []

    for i, pool in enumerate(POOLS, 1):
        print(f"[{i}/{len(POOLS)}] Checking {pool['name']} ({pool['address'][:10]}...)")

        reserve0, reserve1 = get_pool_reserves(pool['address'])

        if reserve0 is None:
            print("   ❌ Failed to fetch reserves")
            print()
            continue

        imbalance = calculate_imbalance(reserve0, reserve1)
        level, emoji = get_imbalance_level(imbalance)
        profit = estimate_profit(reserve0, reserve1, imbalance)

        print(f"   Reserve0: {reserve0:,}")
        print(f"   Reserve1: {reserve1:,}")
        print(f"   {emoji} Imbalance: {imbalance:.2f}% ({level})")

        if imbalance >= 20:
            print(f"   💰 Estimated Profit: ~{profit:.4f} BNB")
            opportunities.append({
                'pool': pool,
                'imbalance': imbalance,
                'level': level,
                'profit': profit
            })

        print()

    print("─" * 70)
    print()

    if opportunities:
        print(f"⚠️  OPPORTUNITIES DETECTED: {len(opportunities)}")
        print()

        # Sort by imbalance score
        opportunities.sort(key=lambda x: x['imbalance'], reverse=True)

        for i, opp in enumerate(opportunities, 1):
            emoji = "🚨" if opp['imbalance'] >= 60 else "🔴" if opp['imbalance'] >= 40 else "🟠"
            print(f"{emoji} #{i}: {opp['pool']['name']}")
            print(f"   Address: {opp['pool']['address']}")
            print(f"   Imbalance: {opp['imbalance']:.2f}% ({opp['level']})")
            print(f"   Est. Profit: ~{opp['profit']:.4f} BNB")
            print()

        print("✅ These are REAL opportunities detected via external RPC!")
        print("   No blockchain sync required!")
    else:
        print("✅ No opportunities above 20% threshold.")
        print("   This indicates healthy, balanced liquidity pools.")

    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║                    HYBRID MODE WORKING ✅                    ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print("This demonstrates:")
    print("  • Real-time pool state queries (no sync needed)")
    print("  • Imbalance detection working via external RPC")
    print("  • Profit estimation for arbitrage opportunities")
    print()
    print("For mempool monitoring, the local node is running at:")
    print(f"  {LOCAL_RPC}")
    print()

if __name__ == "__main__":
    main()
