#!/usr/bin/env python3
"""Detailed analysis of a specific arbitrage transaction"""

import requests
import json

RPC = "https://bsc-dataseed.bnbchain.org"

SWAP_SIG = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"

TOKEN_NAMES = {
    "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c": "WBNB",
    "0xe9e7cea3dedca5984780bafc599bd69add087d56": "BUSD",
    "0x55d398326f99059ff775485246999027b3197955": "USDT",
    "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82": "CAKE",
    "0x2170ed0880ac9a755fd29b2688956bd959f933f8": "ETH",
}

def rpc_call(method, params):
    response = requests.post(RPC, json={
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }, timeout=10)
    return response.json().get("result")

def analyze_tx(tx_hash):
    print("="*80)
    print(f"DETAILED ARBITRAGE TRANSACTION ANALYSIS")
    print("="*80)
    print(f"\nTransaction: {tx_hash}")

    # Get transaction
    tx = rpc_call("eth_getTransactionByHash", [tx_hash])
    receipt = rpc_call("eth_getTransactionReceipt", [tx_hash])

    if not tx or not receipt:
        print("❌ Could not fetch transaction")
        return

    # Basic info
    print(f"\n📋 BASIC INFORMATION")
    print(f"  Block: {int(tx['blockNumber'], 16)}")
    print(f"  From: {tx['from']}")
    print(f"  To: {tx.get('to', 'N/A')}")
    print(f"  Value: {int(tx.get('value', '0'), 16) / 1e18:.4f} BNB")

    # Gas info
    gas_price = int(tx.get('gasPrice', '0'), 16) / 1e9
    gas_used = int(receipt['gasUsed'], 16)
    gas_cost = gas_price * gas_used / 1e9

    print(f"\n⛽ GAS INFORMATION")
    print(f"  Gas Price: {gas_price:.2f} Gwei")
    print(f"  Gas Used: {gas_used:,}")
    print(f"  Gas Cost: {gas_cost:.6f} BNB (${gas_cost * 943:.2f})")
    print(f"  Status: {'✅ Success' if receipt.get('status') == '0x1' else '❌ Failed'}")

    # Parse swaps
    swaps = []
    pools_involved = set()
    tokens_involved = set()

    print(f"\n🔄 SWAP EVENTS")
    for i, log in enumerate(receipt.get('logs', [])):
        if len(log.get('topics', [])) > 0 and log['topics'][0] == SWAP_SIG:
            pool = log['address'].lower()
            pools_involved.add(pool)

            # Parse swap data
            data = log.get('data', '0x')[2:]
            if len(data) >= 256:
                amount0In = int(data[0:64], 16)
                amount1In = int(data[64:128], 16)
                amount0Out = int(data[128:192], 16)
                amount1Out = int(data[192:256], 16)

                swaps.append({
                    'pool': pool,
                    'amount0In': amount0In / 1e18,
                    'amount1In': amount1In / 1e18,
                    'amount0Out': amount0Out / 1e18,
                    'amount1Out': amount1Out / 1e18,
                })

                # Get pool tokens
                token0 = rpc_call("eth_call", [{"to": pool, "data": "0x0dfe1681"}, "latest"])
                token1 = rpc_call("eth_call", [{"to": pool, "data": "0xd21220a7"}, "latest"])

                if token0 and token1:
                    token0_addr = "0x" + token0[-40:].lower()
                    token1_addr = "0x" + token1[-40:].lower()
                    tokens_involved.add(token0_addr)
                    tokens_involved.add(token1_addr)

                    token0_name = TOKEN_NAMES.get(token0_addr, token0_addr[:10])
                    token1_name = TOKEN_NAMES.get(token1_addr, token1_addr[:10])

                    print(f"\n  Swap #{len(swaps)}:")
                    print(f"    Pool: {pool[:10]}...")
                    print(f"    Pair: {token0_name}-{token1_name}")
                    if amount0In > 0:
                        print(f"    In: {amount0In / 1e18:,.4f} {token0_name}")
                    if amount1In > 0:
                        print(f"    In: {amount1In / 1e18:,.4f} {token1_name}")
                    if amount0Out > 0:
                        print(f"    Out: {amount0Out / 1e18:,.4f} {token0_name}")
                    if amount1Out > 0:
                        print(f"    Out: {amount1Out / 1e18:,.4f} {token1_name}")

    print(f"\n📊 SUMMARY")
    print(f"  Total Swaps: {len(swaps)}")
    print(f"  Pools Involved: {len(pools_involved)}")
    print(f"  Unique Tokens: {len(tokens_involved)}")

    # Arbitrage path
    if len(swaps) >= 2:
        print(f"\n🔀 ARBITRAGE PATH")
        print(f"  Strategy: {len(swaps)}-hop arbitrage")
        print(f"  Type: {'Same pool (sandwich?)' if len(pools_involved) == 1 else 'Multi-pool'}")

    # Profit estimation
    if len(swaps) >= 2:
        first = swaps[0]
        last = swaps[-1]

        # Try to determine profit
        # For same-token arbitrage: output - input
        print(f"\n💰 PROFIT ESTIMATION")
        print(f"  First swap input: {first['amount0In'] if first['amount0In'] > 0 else first['amount1In']:.4f}")
        print(f"  Last swap output: {last['amount0Out'] if last['amount0Out'] > 0 else last['amount1Out']:.4f}")
        print(f"  (Exact profit requires matching tokens)")

    print(f"\n" + "="*80)

if __name__ == '__main__':
    # Analyze the first example
    tx = "0x15e01267db2fb114593a10022a11f1d500d0509357a03e924dc0e45cd85932a1"
    analyze_tx(tx)
