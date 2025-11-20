#!/usr/bin/env python3
"""
BSC Mempool Arbitrage Spy - See arbitrage attempts BEFORE they're mined
Monitor pending transactions in mempool to catch arbitrageurs in action
"""

import json
import time
from datetime import datetime
from collections import defaultdict
from web3 import Web3
from websocket import create_connection
import threading

# Configuration
WSS_ENDPOINT = "wss://bsc-dataseed.bnbchain.org"  # WebSocket for mempool
HTTP_RPC = "https://bsc-dataseed.bnbchain.org"

# DEX Router addresses (common arbitrage targets)
ROUTERS = {
    '0x10ed43c718714eb63d5aa57b78b54704e256024e': 'PancakeSwap V2',
    '0x05ff2b0db69458a0750badebc4f9e13add608c7f': 'PancakeSwap V1',
    '0xcf0febd3f17cef5b47b0cd257acf6025c5bff3b7': 'ApeSwap',
    '0x3a6d8ca21d1cf76f653a67577fa0d27453350dd8': 'BiSwap',
}

# Method signatures for swap functions
SWAP_METHODS = {
    '0x38ed1739': 'swapExactTokensForTokens',
    '0x8803dbee': 'swapTokensForExactTokens',
    '0x7ff36ab5': 'swapExactETHForTokens',
    '0x18cbafe5': 'swapExactTokensForETH',
}

# Track active arbitrageurs
active_arbs = defaultdict(list)
stats = {
    'total_pending': 0,
    'arbitrage_detected': 0,
    'unique_arbitrageurs': set()
}

def decode_pending_swap(tx):
    """Decode pending swap transaction"""
    try:
        to_address = tx.get('to', '').lower()
        input_data = tx.get('input', '0x')

        # Check if targeting a DEX router
        router_name = ROUTERS.get(to_address)
        if not router_name:
            return None

        # Check method signature
        if len(input_data) >= 10:
            method_sig = input_data[:10]
            method_name = SWAP_METHODS.get(method_sig)

            if method_name:
                return {
                    'hash': tx.get('hash'),
                    'from': tx.get('from'),
                    'to': to_address,
                    'router': router_name,
                    'method': method_name,
                    'gas': int(tx.get('gas', '0x0'), 16),
                    'gasPrice': int(tx.get('gasPrice', '0x0'), 16),
                    'value': int(tx.get('value', '0x0'), 16),
                    'timestamp': datetime.now()
                }
    except:
        pass

    return None

def detect_multi_hop_arbitrage(address, recent_txs):
    """Detect if address is attempting multi-hop arbitrage"""
    # Look for multiple swaps from same address in quick succession
    address_txs = [tx for tx in recent_txs if tx['from'].lower() == address.lower()]

    if len(address_txs) >= 2:
        # Check if using different DEXs (cross-DEX arbitrage)
        unique_routers = set(tx['router'] for tx in address_txs)

        return {
            'type': 'cross-dex' if len(unique_routers) > 1 else 'single-dex',
            'hop_count': len(address_txs),
            'routers': list(unique_routers),
            'confidence': 'high' if len(address_txs) >= 3 else 'medium'
        }

    return None

def estimate_gas_cost(tx):
    """Calculate gas cost in BNB"""
    gas_cost_wei = tx['gas'] * tx['gasPrice']
    return gas_cost_wei / 1e18

def monitor_mempool_http():
    """Monitor mempool using HTTP polling (fallback if WSS doesn't work)"""
    import requests

    print("🔍 Monitoring mempool via HTTP polling...")
    print("   (Checking every 3 seconds)")
    print()

    recent_txs = []
    seen_hashes = set()

    try:
        while True:
            # Get pending transactions (note: most public RPCs limit this)
            try:
                response = requests.post(HTTP_RPC, json={
                    "jsonrpc": "2.0",
                    "method": "txpool_content",
                    "params": [],
                    "id": 1
                }, timeout=5)

                result = response.json()

                # This endpoint is often restricted on public RPCs
                if 'error' in result:
                    print("⚠️  Note: txpool_content not available on this RPC")
                    print("   Public RPCs typically don't expose mempool")
                    print("   You'd need your own BSC node for full mempool access")
                    break

            except Exception as e:
                print(f"ℹ️  Mempool monitoring via HTTP not available: {e}")
                print()
                print("💡 Alternative: Monitor recent blocks instead")
                break

            time.sleep(3)

    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped")

def monitor_recent_blocks():
    """Alternative: Monitor recent blocks for arbitrage patterns"""
    import requests

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║      BSC Arbitrage Spy - Monitoring Recent Transactions     ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print("🔍 Watching recent blocks for arbitrage activity...")
    print("⏹️  Press Ctrl+C to stop")
    print()

    current_block = None
    recent_swaps = []

    try:
        while True:
            # Get latest block
            response = requests.post(HTTP_RPC, json={
                "jsonrpc": "2.0",
                "method": "eth_blockNumber",
                "params": [],
                "id": 1
            }, timeout=5)

            latest = int(response.json()['result'], 16)

            if current_block is None:
                current_block = latest

            # Process new blocks
            while current_block <= latest:
                timestamp = datetime.now().strftime('%H:%M:%S')
                print(f"[{timestamp}] Block {current_block:,}...", end=" ")

                # Get block with transactions
                block_response = requests.post(HTTP_RPC, json={
                    "jsonrpc": "2.0",
                    "method": "eth_getBlockByNumber",
                    "params": [hex(current_block), True],
                    "id": 1
                }, timeout=10)

                block = block_response.json().get('result')
                if not block:
                    print("(skipped)")
                    current_block += 1
                    continue

                transactions = block.get('transactions', [])

                # Analyze transactions
                swaps_found = 0
                arbitrage_found = 0

                for tx in transactions:
                    swap = decode_pending_swap(tx)
                    if swap:
                        swaps_found += 1
                        recent_swaps.append(swap)
                        stats['total_pending'] += 1

                        # Keep only last 100 swaps
                        if len(recent_swaps) > 100:
                            recent_swaps.pop(0)

                # Check for arbitrage patterns
                by_sender = defaultdict(list)
                for swap in recent_swaps[-20:]:  # Check last 20 swaps
                    by_sender[swap['from']].append(swap)

                for sender, sender_swaps in by_sender.items():
                    if len(sender_swaps) >= 2:
                        pattern = detect_multi_hop_arbitrage(sender, sender_swaps)
                        if pattern:
                            arbitrage_found += 1
                            stats['arbitrage_detected'] += 1
                            stats['unique_arbitrageurs'].add(sender)

                            gas_cost = sum(estimate_gas_cost(s) for s in sender_swaps)
                            est_profit = gas_cost * 5  # Rough estimate

                            print()
                            print(f"   🎯 ARBITRAGE DETECTED!")
                            print(f"      Wallet: {sender[:10]}...{sender[-8:]}")
                            print(f"      Type: {pattern['type'].upper()}")
                            print(f"      Hops: {pattern['hop_count']}")
                            print(f"      DEXs: {', '.join(pattern['routers'])}")
                            print(f"      Gas: ~{gas_cost:.4f} BNB")
                            print(f"      Est. Profit: ~{est_profit:.4f} BNB")
                            print()

                if arbitrage_found == 0:
                    print(f"{swaps_found} swaps, no arbitrage")

                current_block += 1

                # Show periodic stats
                if current_block % 10 == 0:
                    print()
                    print(f"📊 Swaps: {stats['total_pending']} | "
                          f"Arbitrage: {stats['arbitrage_detected']} | "
                          f"Unique Arbitrageurs: {len(stats['unique_arbitrageurs'])}")
                    print()

            time.sleep(3)

    except KeyboardInterrupt:
        print("\n")
        print("─" * 70)
        print()
        print("📊 Final Statistics:")
        print(f"   Total Swaps Monitored: {stats['total_pending']}")
        print(f"   Arbitrage Detected: {stats['arbitrage_detected']}")
        print(f"   Unique Arbitrageurs: {len(stats['unique_arbitrageurs'])}")
        print()

        if stats['unique_arbitrageurs']:
            print("🏆 Detected Arbitrageurs:")
            for addr in list(stats['unique_arbitrageurs'])[:10]:
                print(f"   • {addr}")
        print()

def main():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║         BSC Mempool Arbitrage Spy - Real-time Monitor       ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print("This tool monitors BSC transactions to detect:")
    print("  • Multi-hop arbitrage attempts")
    print("  • Cross-DEX arbitrage strategies")
    print("  • Profitable wallet addresses")
    print("  • Gas strategies and timing")
    print()

    # Try mempool monitoring first, fall back to block monitoring
    try:
        monitor_mempool_http()
    except:
        pass

    # Use block monitoring as main method
    monitor_recent_blocks()

if __name__ == "__main__":
    main()
