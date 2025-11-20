#!/usr/bin/env python3
"""
BSC Arbitrage Hunter - Monitor who's profiting from arbitrage
Tracks executed arbitrage transactions and analyzes strategies
"""

import requests
import json
import time
from datetime import datetime
from collections import defaultdict
from web3 import Web3

# Configuration
EXTERNAL_RPC = "https://bsc-dataseed.bnbchain.org"
LOCAL_RPC = "http://127.0.0.1:8545"

# PancakeSwap V2 Router address
PANCAKE_ROUTER = "0x10ED43C718714eb63d5aA57B78B54704E256024E"

# Track arbitrageurs
arbitrageur_stats = defaultdict(lambda: {
    'total_trades': 0,
    'estimated_profit': 0.0,
    'first_seen': None,
    'last_seen': None,
    'strategies': []
})

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
    """Get all transactions in a block"""
    try:
        response = requests.post(EXTERNAL_RPC, json={
            "jsonrpc": "2.0",
            "method": "eth_getBlockByNumber",
            "params": [hex(block_number), True],  # True = include full tx objects
            "id": 1
        }, timeout=10)

        block = response.json().get("result")
        if block:
            return block.get("transactions", [])
    except:
        pass
    return []

def decode_swap_transaction(tx):
    """Analyze if transaction is a swap and extract details"""
    if not tx.get('to'):
        return None

    to_address = tx['to'].lower()
    input_data = tx.get('input', '0x')

    # Check if it's interacting with PancakeSwap Router
    if to_address != PANCAKE_ROUTER.lower():
        return None

    # Common swap method signatures
    swap_methods = {
        '0x38ed1739': 'swapExactTokensForTokens',
        '0x8803dbee': 'swapTokensForExactTokens',
        '0x7ff36ab5': 'swapExactETHForTokens',
        '0x18cbafe5': 'swapExactTokensForETH',
        '0xfb3bdb41': 'swapETHForExactTokens',
        '0x4a25d94a': 'swapTokensForExactETH',
    }

    if len(input_data) >= 10:
        method_sig = input_data[:10]
        if method_sig in swap_methods:
            return {
                'hash': tx['hash'],
                'from': tx['from'],
                'method': swap_methods[method_sig],
                'gas': int(tx.get('gas', '0x0'), 16),
                'gasPrice': int(tx.get('gasPrice', '0x0'), 16),
                'value': int(tx.get('value', '0x0'), 16),
                'input': input_data
            }

    return None

def detect_arbitrage_pattern(from_address, transactions):
    """Detect if multiple swaps from same address = potential arbitrage"""
    # Count swaps from this address in recent transactions
    swaps_from_address = [tx for tx in transactions if tx.get('from') == from_address]

    # If same address did multiple swaps in same block = likely arbitrage
    if len(swaps_from_address) >= 2:
        return {
            'type': 'multi-hop',
            'swap_count': len(swaps_from_address),
            'confidence': 'high' if len(swaps_from_address) >= 3 else 'medium'
        }

    return None

def estimate_arbitrage_profit(tx_details):
    """Rough estimation of profit (would need receipt for exact amounts)"""
    # This is a simplified estimation
    # Real profit calculation requires parsing transaction logs

    gas_cost_wei = tx_details['gas'] * tx_details['gasPrice']
    gas_cost_bnb = gas_cost_wei / 1e18

    # If they're willing to pay high gas, likely profitable
    if gas_cost_bnb > 0.01:  # More than 0.01 BNB gas
        # Estimate profit as 5-10x gas cost for successful arbitrage
        estimated_profit = gas_cost_bnb * 7
        return estimated_profit

    return 0.0

def track_arbitrageur(address, profit, strategy, timestamp):
    """Track arbitrageur statistics"""
    stats = arbitrageur_stats[address]
    stats['total_trades'] += 1
    stats['estimated_profit'] += profit

    if stats['first_seen'] is None:
        stats['first_seen'] = timestamp
    stats['last_seen'] = timestamp

    if strategy not in stats['strategies']:
        stats['strategies'].append(strategy)

def get_top_arbitrageurs(limit=10):
    """Get top arbitrageurs by profit"""
    sorted_arbs = sorted(
        arbitrageur_stats.items(),
        key=lambda x: x[1]['estimated_profit'],
        reverse=True
    )
    return sorted_arbs[:limit]

def main():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║        BSC Arbitrage Hunter - Who's Making Money?           ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print("🔍 Monitoring BSC for arbitrage transactions...")
    print("🎯 Tracking wallet addresses and profit estimates")
    print("⏹️  Press Ctrl+C to stop and see results")
    print()
    print("─" * 70)
    print()

    current_block = get_latest_block()
    start_block = current_block
    blocks_scanned = 0
    total_swaps_found = 0
    arbitrage_detected = 0

    try:
        while True:
            latest_block = get_latest_block()

            # Process new blocks
            while current_block <= latest_block:
                timestamp = datetime.now().strftime('%H:%M:%S')
                print(f"[{timestamp}] Scanning block {current_block:,}...", end=" ")

                # Get all transactions in block
                transactions = get_block_transactions(current_block)

                if not transactions:
                    print("(no txs)")
                    current_block += 1
                    continue

                # Analyze each transaction
                swaps_in_block = []
                for tx in transactions:
                    swap = decode_swap_transaction(tx)
                    if swap:
                        swaps_in_block.append(swap)
                        total_swaps_found += 1

                print(f"found {len(swaps_in_block)} swaps")

                # Detect arbitrage patterns
                if swaps_in_block:
                    # Group by sender address
                    by_sender = defaultdict(list)
                    for swap in swaps_in_block:
                        by_sender[swap['from']].append(swap)

                    # Look for multi-swap patterns (potential arbitrage)
                    for sender, sender_swaps in by_sender.items():
                        if len(sender_swaps) >= 2:
                            arbitrage_detected += 1

                            # Calculate estimated profit
                            total_gas = sum(s['gas'] * s['gasPrice'] for s in sender_swaps)
                            gas_cost_bnb = total_gas / 1e18
                            estimated_profit = gas_cost_bnb * 7  # Rough estimate

                            print(f"   🎯 ARBITRAGE DETECTED!")
                            print(f"      Address: {sender[:10]}...{sender[-8:]}")
                            print(f"      Swaps: {len(sender_swaps)}")
                            print(f"      Est. Profit: ~{estimated_profit:.4f} BNB")

                            # Track this arbitrageur
                            track_arbitrageur(
                                sender,
                                estimated_profit,
                                f"{len(sender_swaps)}-hop",
                                datetime.now()
                            )

                blocks_scanned += 1
                current_block += 1

                # Show stats every 10 blocks
                if blocks_scanned % 10 == 0:
                    print()
                    print(f"📊 Stats: {blocks_scanned} blocks | {total_swaps_found} swaps | {arbitrage_detected} arbitrage txs")
                    print()

                time.sleep(1)  # Rate limiting

            # Wait for new block
            time.sleep(3)

    except KeyboardInterrupt:
        print("\n")
        print("─" * 70)
        print()
        print("🛑 Monitoring stopped. Generating report...")
        print()
        print("╔══════════════════════════════════════════════════════════════╗")
        print("║                    ARBITRAGE HUNTER REPORT                   ║")
        print("╚══════════════════════════════════════════════════════════════╝")
        print()
        print(f"📊 Scan Summary:")
        print(f"   Blocks Scanned: {blocks_scanned}")
        print(f"   Total Swaps Found: {total_swaps_found}")
        print(f"   Arbitrage Transactions: {arbitrage_detected}")
        print()

        if arbitrageur_stats:
            print("🏆 Top Arbitrageurs (by estimated profit):")
            print()

            top_arbs = get_top_arbitrageurs(10)
            for rank, (address, stats) in enumerate(top_arbs, 1):
                print(f"#{rank}. {address[:10]}...{address[-8:]}")
                print(f"    Trades: {stats['total_trades']}")
                print(f"    Est. Profit: ~{stats['estimated_profit']:.4f} BNB (~${stats['estimated_profit'] * 600:.2f})")
                print(f"    Strategies: {', '.join(stats['strategies'])}")
                print(f"    Last Seen: {stats['last_seen'].strftime('%H:%M:%S')}")
                print()
        else:
            print("ℹ️  No arbitrage transactions detected in this session.")
            print("   Try running for longer to catch arbitrage activity.")

        print("─" * 70)
        print()

if __name__ == "__main__":
    main()
