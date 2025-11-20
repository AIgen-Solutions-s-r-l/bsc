#!/usr/bin/env python3
"""Debug a single transaction to see what's really happening"""

import requests
from web3 import Web3
import sys

EXTERNAL_RPC = "https://bsc-dataseed.bnbchain.org"
web3 = Web3(Web3.HTTPProvider(EXTERNAL_RPC))

def debug_transaction(tx_hash):
    """Deep dive into a transaction"""

    print(f"\n╔══════════════════════════════════════════════════════════════╗")
    print(f"║  DEBUGGING TRANSACTION: {tx_hash[:20]}...  ║")
    print(f"╚══════════════════════════════════════════════════════════════╝\n")

    # Get transaction
    tx = web3.eth.get_transaction(tx_hash)
    print(f"📝 TRANSACTION DETAILS:")
    print(f"   From: {tx['from']}")
    print(f"   To: {tx['to']}")
    print(f"   Value: {web3.from_wei(tx['value'], 'ether')} BNB")
    print(f"   Gas Price: {web3.from_wei(tx['gasPrice'], 'gwei')} Gwei")
    print(f"   Input Data Length: {len(tx['input'])} bytes")
    print()

    # Get receipt
    receipt = web3.eth.get_transaction_receipt(tx_hash)
    print(f"📋 RECEIPT:")
    print(f"   Status: {'✅ Success' if receipt.status == 1 else '❌ Failed'}")
    print(f"   Gas Used: {receipt.gasUsed:,}")
    print(f"   Logs Count: {len(receipt.logs)}")
    print()

    # Analyze logs
    print(f"📊 LOGS ANALYSIS:")

    swap_signature = web3.keccak(text="Swap(address,uint256,uint256,uint256,uint256,address)").hex()
    transfer_signature = web3.keccak(text="Transfer(address,address,uint256)").hex()

    swap_count = 0
    transfer_count = 0

    for i, log in enumerate(receipt.logs):
        if len(log.topics) == 0:
            continue

        sig = log.topics[0].hex()

        if sig == swap_signature:
            swap_count += 1
            print(f"\n   Log #{i}: SWAP EVENT")
            print(f"      Pool: {log.address}")

            # Decode amounts
            data = log.data.hex()[2:]
            amount0In = int(data[0:64], 16)
            amount1In = int(data[64:128], 16)
            amount0Out = int(data[128:192], 16)
            amount1Out = int(data[192:256], 16)

            print(f"      amount0In: {amount0In / 1e18:.6f}")
            print(f"      amount1In: {amount1In / 1e18:.6f}")
            print(f"      amount0Out: {amount0Out / 1e18:.6f}")
            print(f"      amount1Out: {amount1Out / 1e18:.6f}")

        elif sig == transfer_signature:
            transfer_count += 1

    print(f"\n   ✅ Total Swaps: {swap_count}")
    print(f"   ✅ Total Transfers: {transfer_count}")

    # Check if this looks like arbitrage
    print(f"\n🔍 ANALYSIS:")
    if swap_count >= 2:
        print(f"   ✅ Multiple swaps ({swap_count}) - LOOKS like arbitrage")
    else:
        print(f"   ❌ Only {swap_count} swap(s) - NOT arbitrage")

    if swap_count == 0:
        print(f"\n   ⚠️  NO SWAP EVENTS FOUND!")
        print(f"   This might not be a DEX transaction.")
        print(f"   Could be:")
        print(f"     • Failed transaction")
        print(f"     • Different contract interaction")
        print(f"     • MEV transaction of different type")

    return swap_count

if __name__ == '__main__':
    # Get random transactions from DB
    import sqlite3

    db_path = 'arbitrage-data/arbitrage.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('SELECT tx_hash FROM transactions ORDER BY RANDOM() LIMIT 5')
    transactions = [row[0] for row in cursor.fetchall()]

    print(f"\n🔬 ANALYZING 5 RANDOM TRANSACTIONS\n")

    swap_counts = []
    for tx_hash in transactions:
        count = debug_transaction(tx_hash)
        swap_counts.append(count)
        print(f"\n{'='*70}\n")

    print(f"\n📊 SUMMARY:")
    print(f"   Transactions analyzed: {len(swap_counts)}")
    print(f"   With swap events: {sum(1 for c in swap_counts if c > 0)}")
    print(f"   Without swap events: {sum(1 for c in swap_counts if c == 0)}")
    print(f"   Avg swaps per tx: {sum(swap_counts) / len(swap_counts):.1f}")

    if sum(swap_counts) == 0:
        print(f"\n   ⚠️  WARNING: NO SWAP EVENTS FOUND IN ANY TRANSACTION!")
        print(f"   This means our transaction detection logic might be flawed.")
        print(f"   We're detecting transactions that aren't actually DEX swaps.")

    conn.close()
