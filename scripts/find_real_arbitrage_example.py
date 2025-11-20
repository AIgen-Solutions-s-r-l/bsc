#!/usr/bin/env python3
"""Find real arbitrage transaction examples from recent BSC blocks"""

import requests
import time

RPC = "https://bsc-dataseed.bnbchain.org"

# Known arbitrage bot addresses (from BSCScan)
KNOWN_ARBITRAGE_BOTS = [
    "0x00000000003b3cc22aF3aE1EAc0440BcEe416B40",  # Known MEV bot
    "0x51C72848c68a965f66FA7a88855F9f7784502a7F",  # Known arbitrage bot
]

# DEX Routers
DEX_ROUTERS = {
    "PancakeSwap V2": "0x10ED43C718714eb63d5aA57B78B54704E256024E".lower(),
    "BiSwap": "0x3a6d8cA21D1CF76F653A67577FA0D27453350dD8".lower(),
}

# Swap event signature
SWAP_SIG = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"

def rpc_call(method, params):
    try:
        response = requests.post(RPC, json={
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        }, timeout=10)
        return response.json().get("result")
    except Exception as e:
        print(f"RPC Error: {e}")
        return None

def get_latest_block():
    result = rpc_call("eth_blockNumber", [])
    return int(result, 16) if result else 0

def analyze_transaction(tx_hash):
    """Analyze a transaction to see if it's arbitrage"""
    print(f"\nAnalyzing TX: {tx_hash}")

    # Get transaction
    tx = rpc_call("eth_getTransactionByHash", [tx_hash])
    if not tx:
        print("  ❌ Could not get transaction")
        return None

    # Get receipt
    receipt = rpc_call("eth_getTransactionReceipt", [tx_hash])
    if not receipt:
        print("  ❌ Could not get receipt")
        return None

    # Count swaps
    swap_count = 0
    pools_involved = set()

    for log in receipt.get('logs', []):
        if len(log.get('topics', [])) > 0:
            if log['topics'][0] == SWAP_SIG:
                swap_count += 1
                pools_involved.add(log['address'])

    if swap_count >= 2:
        print(f"  ✅ ARBITRAGE FOUND!")
        print(f"     Swaps: {swap_count}")
        print(f"     Pools: {len(pools_involved)}")
        print(f"     From: {tx['from']}")
        print(f"     To: {tx.get('to', 'Contract Creation')}")
        print(f"     Block: {int(tx['blockNumber'], 16)}")

        gas_used = int(receipt['gasUsed'], 16)
        gas_price = int(tx.get('gasPrice', '0'), 16) / 1e9

        print(f"     Gas: {gas_used:,} @ {gas_price:.2f} Gwei")

        return {
            'tx_hash': tx_hash,
            'swaps': swap_count,
            'pools': list(pools_involved),
            'from': tx['from'],
            'to': tx.get('to'),
            'block': int(tx['blockNumber'], 16),
            'gas_used': gas_used,
            'gas_price_gwei': gas_price
        }

    return None

def scan_recent_blocks(num_blocks=10):
    """Scan recent blocks for multi-swap transactions"""
    print(f"Scanning last {num_blocks} blocks for arbitrage examples...")

    current = get_latest_block()
    start = current - num_blocks

    found = []

    for block_num in range(start, current):
        block_hex = hex(block_num)
        block = rpc_call("eth_getBlockByNumber", [block_hex, True])

        if not block or not block.get('transactions'):
            continue

        print(f"\nBlock {block_num}: {len(block['transactions'])} transactions")

        # Check each transaction
        for tx in block['transactions']:
            # Quick filter: only check router transactions
            to_addr = tx.get('to', '').lower()
            if to_addr in DEX_ROUTERS.values():
                # Get receipt and count swaps
                receipt = rpc_call("eth_getTransactionReceipt", [tx['hash']])
                if receipt:
                    swap_count = sum(1 for log in receipt.get('logs', [])
                                    if len(log.get('topics', [])) > 0
                                    and log['topics'][0] == SWAP_SIG)

                    if swap_count >= 2:
                        result = analyze_transaction(tx['hash'])
                        if result:
                            found.append(result)
                            if len(found) >= 3:  # Found enough examples
                                return found

        time.sleep(0.5)  # Rate limiting

    return found

if __name__ == '__main__':
    examples = scan_recent_blocks(20)

    print("\n" + "="*80)
    print(f"FOUND {len(examples)} ARBITRAGE EXAMPLES")
    print("="*80)

    for i, ex in enumerate(examples, 1):
        print(f"\nExample {i}:")
        print(f"  TX: {ex['tx_hash']}")
        print(f"  Swaps: {ex['swaps']}")
        print(f"  Pools: {len(ex['pools'])}")
        print(f"  Block: {ex['block']}")
