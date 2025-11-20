#!/usr/bin/env python3
"""
BSC Imbalance Engine - Live Dashboard
Compact real-time monitoring with auto-refresh
"""

import requests
import json
import time
import os
import sys
from datetime import datetime

EXTERNAL_RPC = "https://bsc-dataseed.bnbchain.org"
LOCAL_RPC = "http://127.0.0.1:8545"

POOLS = [
    {"address": "0x58F876857a02D6762E0101bb5C46A8c1ED44Dc16", "name": "WBNB-BUSD", "emoji": "💵"},
    {"address": "0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE", "name": "WBNB-USDT", "emoji": "💲"},
    {"address": "0x7EFaEf62fDdCCa950418312c6C91Aef321375A00", "name": "WBNB-USDC", "emoji": "💴"},
    {"address": "0x0eD7e52944161450477ee417DE9Cd3a859b14fD0", "name": "WBNB-CAKE", "emoji": "🥞"},
    {"address": "0x1B96B92314C44b159149f7E0303511fB2Fc4774f", "name": "WBNB-ETH", "emoji": "💎"},
]

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')

def get_pool_reserves(pool_address):
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{"to": pool_address, "data": "0x0902f1ac"}, "latest"],
        "id": 1
    }
    try:
        response = requests.post(EXTERNAL_RPC, json=payload, timeout=5)
        result = response.json().get("result")
        if result and result != "0x":
            reserve0 = int(result[2:66], 16)
            reserve1 = int(result[66:130], 16)
            return reserve0, reserve1
    except:
        pass
    return None, None

def calculate_imbalance(reserve0, reserve1):
    if reserve0 is None or reserve1 is None or reserve0 + reserve1 == 0:
        return 0.0
    return abs(reserve0 - reserve1) / (reserve0 + reserve1) * 100

def get_status_emoji(score):
    if score >= 60:
        return "🚨"
    elif score >= 40:
        return "🔴"
    elif score >= 20:
        return "🟠"
    elif score >= 10:
        return "🟡"
    else:
        return "🟢"

def get_block_number():
    try:
        response = requests.post(EXTERNAL_RPC, json={
            "jsonrpc": "2.0",
            "method": "eth_blockNumber",
            "params": [],
            "id": 1
        }, timeout=5)
        return int(response.json().get("result", "0x0"), 16)
    except:
        return 0

def main():
    scan_count = 0
    total_opps = 0

    print("\033[?25l")  # Hide cursor

    try:
        while True:
            scan_count += 1
            clear_screen()

            current_time = datetime.now().strftime('%H:%M:%S')
            block_num = get_block_number()

            print("╔══════════════════════════════════════════════════════════════╗")
            print("║     BSC IMBALANCE ENGINE - LIVE DASHBOARD (Hybrid Mode)     ║")
            print("╚══════════════════════════════════════════════════════════════╝")
            print()
            print(f"⏰ Time: {current_time}  |  📊 Scan: #{scan_count}  |  🔗 Block: {block_num:,}")
            print(f"🌐 RPC: {EXTERNAL_RPC}")
            print()
            print("─" * 70)
            print()

            opportunities = []

            for pool in POOLS:
                reserve0, reserve1 = get_pool_reserves(pool['address'])

                if reserve0 is None:
                    print(f"{pool['emoji']} {pool['name']:12} | ❌ Failed to fetch")
                    continue

                imbalance = calculate_imbalance(reserve0, reserve1)
                status = get_status_emoji(imbalance)

                # Format reserves
                r0_fmt = f"{reserve0/1e18:.2f}" if reserve0 < 1e24 else f"{reserve0/1e18:.0e}"
                r1_fmt = f"{reserve1/1e18:.2f}" if reserve1 < 1e24 else f"{reserve1/1e18:.0e}"

                print(f"{pool['emoji']} {pool['name']:12} | {status} {imbalance:5.1f}% | R0: {r0_fmt:12} | R1: {r1_fmt:12}")

                if imbalance >= 20:
                    opportunities.append({
                        'name': pool['name'],
                        'imbalance': imbalance,
                        'emoji': pool['emoji']
                    })

            print()
            print("─" * 70)
            print()

            if opportunities:
                total_opps += len(opportunities)
                print(f"⚠️  OPPORTUNITIES: {len(opportunities)}")
                print()
                for opp in sorted(opportunities, key=lambda x: x['imbalance'], reverse=True):
                    status = get_status_emoji(opp['imbalance'])
                    print(f"   {status} {opp['emoji']} {opp['name']:12} → {opp['imbalance']:.1f}%")
                print()
            else:
                print("✅ All pools balanced (no opportunities ≥20%)")
                print()

            print(f"📈 Session Total: {total_opps} opportunities detected")
            print()
            print("Legend: 🟢 Balanced | 🟡 Slight | 🟠 Moderate | 🔴 Severe | 🚨 Critical")
            print()
            print("Press Ctrl+C to stop monitoring")

            # Update every 10 seconds
            time.sleep(10)

    except KeyboardInterrupt:
        print("\033[?25h")  # Show cursor
        print("\n\n✋ Monitoring stopped by user")
        print(f"\n📊 Final Stats:")
        print(f"   Total Scans: {scan_count}")
        print(f"   Total Opportunities: {total_opps}")
        print()
        sys.exit(0)

if __name__ == "__main__":
    main()
