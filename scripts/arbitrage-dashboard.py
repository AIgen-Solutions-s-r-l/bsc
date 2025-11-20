#!/usr/bin/env python3
"""
Complete Arbitrage Dashboard - Opportunities + Who's Taking Them
"""

import requests
import json
import time
import os
from datetime import datetime
from collections import defaultdict

# Configuration
EXTERNAL_RPC = "https://bsc-dataseed.bnbchain.org"

# Pools to monitor
POOLS = [
    {"address": "0x58F876857a02D6762E0101bb5C46A8c1ED44Dc16", "name": "WBNB-BUSD", "emoji": "💵"},
    {"address": "0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE", "name": "WBNB-USDT", "emoji": "💲"},
    {"address": "0x7EFaEf62fDdCCa950418312c6C91Aef321375A00", "name": "WBNB-USDC", "emoji": "💴"},
    {"address": "0x0eD7e52944161450477ee417DE9Cd3a859b14fD0", "name": "WBNB-CAKE", "emoji": "🥞"},
    {"address": "0x1B96B92314C44b159149f7E0303511fB2Fc4774f", "name": "WBNB-ETH", "emoji": "💎"},
]

# DEX Router addresses
ROUTERS = {
    '0x10ed43c718714eb63d5aa57b78b54704e256024e': 'PancakeSwap',
    '0xcf0febd3f17cef5b47b0cd257acf6025c5bff3b7': 'ApeSwap',
    '0x3a6d8ca21d1cf76f653a67577fa0d27453350dd8': 'BiSwap',
}

SWAP_METHODS = {
    '0x38ed1739': 'swapExactTokensForTokens',
    '0x7ff36ab5': 'swapExactETHForTokens',
    '0x18cbafe5': 'swapExactTokensForETH',
}

# Statistics
stats = {
    'opportunities_found': 0,
    'arbitrage_detected': 0,
    'unique_arbitrageurs': set(),
    'total_estimated_profit': 0.0,
    'blocks_scanned': 0,
    'last_arbitrage': None
}

arbitrageurs = defaultdict(lambda: {'trades': 0, 'profit': 0.0, 'last_seen': None})

def get_pool_reserves(pool_address):
    """Fetch pool reserves"""
    try:
        response = requests.post(EXTERNAL_RPC, json={
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{"to": pool_address, "data": "0x0902f1ac"}, "latest"],
            "id": 1
        }, timeout=5)
        result = response.json().get("result")
        if result and result != "0x":
            reserve0 = int(result[2:66], 16)
            reserve1 = int(result[66:130], 16)
            return reserve0, reserve1
    except:
        pass
    return None, None

def calculate_value_imbalance(reserve0, reserve1, bnb_price=600):
    """Calculate value-based imbalance"""
    # Assuming reserve0 is stablecoin, reserve1 is WBNB
    value0 = reserve0 / 1e18
    value1 = (reserve1 / 1e18) * bnb_price

    total_value = value0 + value1
    if total_value == 0:
        return 0.0, 0.0

    diff = abs(value0 - value1)
    imbalance_pct = (diff / total_value) * 100
    potential_profit = diff * 0.003  # 0.3% LP fee

    return imbalance_pct, potential_profit

def get_latest_block():
    """Get latest block number"""
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

def get_block_transactions(block_number):
    """Get block transactions"""
    try:
        response = requests.post(EXTERNAL_RPC, json={
            "jsonrpc": "2.0",
            "method": "eth_getBlockByNumber",
            "params": [hex(block_number), True],
            "id": 1
        }, timeout=10)
        block = response.json().get("result")
        if block:
            return block.get("transactions", [])
    except:
        pass
    return []

def analyze_transaction(tx):
    """Check if transaction is a swap"""
    if not tx.get('to'):
        return None

    to_address = tx['to'].lower()
    router_name = ROUTERS.get(to_address)

    if not router_name:
        return None

    input_data = tx.get('input', '0x')
    if len(input_data) >= 10:
        method_sig = input_data[:10]
        method_name = SWAP_METHODS.get(method_sig)

        if method_name:
            return {
                'from': tx['from'],
                'router': router_name,
                'method': method_name,
                'gas': int(tx.get('gas', '0x0'), 16),
                'gasPrice': int(tx.get('gasPrice', '0x0'), 16)
            }

    return None

def main():
    print("\033[?25l")  # Hide cursor

    current_block = get_latest_block() - 1  # Start from previous block
    scan_count = 0

    try:
        while True:
            os.system('clear')

            print("╔══════════════════════════════════════════════════════════════╗")
            print("║       BSC ARBITRAGE DASHBOARD - Live Monitoring             ║")
            print("╚══════════════════════════════════════════════════════════════╝")
            print()

            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"⏰ {timestamp}  |  🔗 Block: {current_block:,}  |  📊 Scans: {scan_count}")
            print()

            # Scan for opportunities
            print("🎯 CURRENT OPPORTUNITIES:")
            print("─" * 70)

            opportunities = []
            for pool in POOLS:
                r0, r1 = get_pool_reserves(pool['address'])
                if r0:
                    imb, profit = calculate_value_imbalance(r0, r1)
                    if imb >= 10:  # Only show if >= 10% imbalance
                        opportunities.append({
                            'pool': pool,
                            'imbalance': imb,
                            'profit': profit
                        })

                        emoji = "🚨" if imb >= 20 else "🟠"
                        print(f"{emoji} {pool['emoji']} {pool['name']:12} - {imb:5.1f}% (~${profit:,.0f})")
                        stats['opportunities_found'] += 1

            if not opportunities:
                print("✅ All pools balanced (< 10% imbalance)")

            print()
            print("─" * 70)
            print()

            # Scan recent block for arbitrage
            print("👤 RECENT ARBITRAGEURS:")
            print("─" * 70)

            latest_block = get_latest_block()
            if current_block < latest_block:
                stats['blocks_scanned'] += 1

                txs = get_block_transactions(latest_block - 1)

                # Analyze transactions
                by_sender = defaultdict(list)
                for tx in txs:
                    swap = analyze_transaction(tx)
                    if swap:
                        by_sender[swap['from']].append(swap)

                # Detect arbitrage (multiple swaps from same address)
                for sender, swaps in by_sender.items():
                    if len(swaps) >= 2:
                        stats['arbitrage_detected'] += 1
                        stats['unique_arbitrageurs'].add(sender)

                        gas_cost = sum(s['gas'] * s['gasPrice'] for s in swaps) / 1e18
                        est_profit = gas_cost * 5

                        arbitrageurs[sender]['trades'] += 1
                        arbitrageurs[sender]['profit'] += est_profit
                        arbitrageurs[sender]['last_seen'] = datetime.now()

                        stats['last_arbitrage'] = {
                            'address': sender,
                            'swaps': len(swaps),
                            'profit': est_profit,
                            'time': datetime.now()
                        }

                current_block = latest_block

            # Show top arbitrageurs
            top_arbs = sorted(
                arbitrageurs.items(),
                key=lambda x: x[1]['profit'],
                reverse=True
            )[:5]

            if top_arbs:
                for rank, (addr, data) in enumerate(top_arbs, 1):
                    age = (datetime.now() - data['last_seen']).seconds if data['last_seen'] else 999
                    status = "🟢" if age < 30 else "🟡" if age < 120 else "⚪"
                    print(f"{status} #{rank}. {addr[:10]}...{addr[-6:]} - {data['trades']} trades - ~${data['profit'] * 600:.0f}")
            else:
                print("⏳ Waiting for arbitrage activity...")

            print()
            print("─" * 70)
            print()

            # Session statistics
            print("📊 SESSION STATS:")
            print(f"   Opportunities Found: {stats['opportunities_found']}")
            print(f"   Arbitrage Detected: {stats['arbitrage_detected']}")
            print(f"   Unique Arbitrageurs: {len(stats['unique_arbitrageurs'])}")
            print(f"   Blocks Scanned: {stats['blocks_scanned']}")

            if stats['last_arbitrage']:
                la = stats['last_arbitrage']
                age = (datetime.now() - la['time']).seconds
                print(f"   Last Arbitrage: {age}s ago ({la['swaps']} swaps, ~${la['profit'] * 600:.0f})")

            print()
            print("Legend: 🟢 Active (< 30s) | 🟡 Recent (< 2m) | ⚪ Idle")
            print()
            print("Press Ctrl+C to stop")

            scan_count += 1
            time.sleep(10)

    except KeyboardInterrupt:
        print("\033[?25h")  # Show cursor
        print("\n\n✋ Monitoring stopped")
        print()
        print("📊 Final Report:")
        print(f"   Total Opportunities: {stats['opportunities_found']}")
        print(f"   Total Arbitrage Txs: {stats['arbitrage_detected']}")
        print(f"   Unique Arbitrageurs: {len(stats['unique_arbitrageurs'])}")
        print()

if __name__ == "__main__":
    main()
