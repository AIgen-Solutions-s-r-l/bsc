#!/usr/bin/env python3
"""Real Profit Analyzer - Parses transaction logs for actual profits"""

import requests
import json
from web3 import Web3
from decimal import Decimal

# Configuration
EXTERNAL_RPC = "https://bsc-dataseed.bnbchain.org"
web3 = Web3(Web3.HTTPProvider(EXTERNAL_RPC))

# Token decimals (most common on BSC)
DECIMALS = {
    'WBNB': 18,
    'BUSD': 18,
    'USDT': 18,
    'USDC': 18,
    'CAKE': 18,
    'ETH': 18,
}

# Swap event signature
SWAP_SIGNATURE = web3.keccak(text="Swap(address,uint256,uint256,uint256,uint256,address)").hex()

# Known token addresses (lowercase)
TOKENS = {
    '0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c': 'WBNB',
    '0xe9e7cea3dedca5984780bafc599bd69add087d56': 'BUSD',
    '0x55d398326f99059ff775485246999027b3197955': 'USDT',
    '0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d': 'USDC',
    '0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82': 'CAKE',
    '0x2170ed0880ac9a755fd29b2688956bd959f933f8': 'ETH',
}

# Approximate token prices (USD)
PRICES = {
    'WBNB': 620.0,
    'BUSD': 1.0,
    'USDT': 1.0,
    'USDC': 1.0,
    'CAKE': 2.5,
    'ETH': 3500.0,
}

def analyze_transaction(tx_hash: str) -> dict:
    """Analyze a transaction and calculate real profit"""

    try:
        # Get transaction receipt
        receipt = web3.eth.get_transaction_receipt(tx_hash)

        if not receipt or receipt.status != 1:
            return None

        # Get transaction details
        tx = web3.eth.get_transaction(tx_hash)

        # Parse logs for Swap events
        swaps = []
        for log in receipt.logs:
            if len(log.topics) > 0 and log.topics[0].hex() == SWAP_SIGNATURE:
                swaps.append(parse_swap_event(log))

        if not swaps:
            return None

        # Analyze token flows
        result = analyze_token_flows(swaps, tx)

        if result:
            result['tx_hash'] = tx_hash
            result['from_address'] = tx['from'].lower()
            result['gas_price_gwei'] = float(tx['gasPrice']) / 1e9
            result['gas_used'] = receipt.gasUsed
            result['swap_count'] = len(swaps)

        return result

    except Exception as e:
        print(f"Error analyzing {tx_hash}: {e}")
        return None

def parse_swap_event(log) -> dict:
    """Parse a Swap event from log"""
    try:
        # Swap event: Swap(address indexed sender, uint amount0In, uint amount1In, uint amount0Out, uint amount1Out, address indexed to)
        # Topics: [signature, sender, to]
        # Data: [amount0In, amount1In, amount0Out, amount1Out]

        data = log.data.hex()[2:]  # Remove 0x

        # Each uint256 is 64 hex chars
        amount0In = int(data[0:64], 16)
        amount1In = int(data[64:128], 16)
        amount0Out = int(data[128:192], 16)
        amount1Out = int(data[192:256], 16)

        pool_address = log.address.lower()

        return {
            'pool': pool_address,
            'amount0In': amount0In,
            'amount1In': amount1In,
            'amount0Out': amount0Out,
            'amount1Out': amount1Out,
        }
    except Exception as e:
        print(f"Error parsing swap event: {e}")
        return None

def get_pool_tokens(pool_address: str) -> tuple:
    """Get token0 and token1 for a pool"""
    try:
        # Call token0() and token1() on pool
        token0_data = web3.eth.call({
            'to': pool_address,
            'data': '0x0dfe1681'  # token0()
        })
        token0 = '0x' + token0_data.hex()[-40:]

        token1_data = web3.eth.call({
            'to': pool_address,
            'data': '0xd21220a7'  # token1()
        })
        token1 = '0x' + token1_data.hex()[-40:]

        return (token0.lower(), token1.lower())
    except:
        return (None, None)

def analyze_token_flows(swaps: list, tx: dict) -> dict:
    """Analyze token flows to determine actual profit"""

    # Track net token flows
    net_flows = {}

    # Get pool tokens for each swap
    for swap in swaps:
        if not swap:
            continue

        pool = swap['pool']
        token0, token1 = get_pool_tokens(pool)

        if not token0 or not token1:
            continue

        # Calculate net flows
        # If amount0In > 0, we're putting in token0
        # If amount0Out > 0, we're getting token0

        if token0 not in net_flows:
            net_flows[token0] = 0
        if token1 not in net_flows:
            net_flows[token1] = 0

        # Net flow = out - in (positive means we gained this token)
        net_flows[token0] += (swap['amount0Out'] - swap['amount0In'])
        net_flows[token1] += (swap['amount1Out'] - swap['amount1In'])

    # Calculate profit in USD
    total_profit_usd = 0
    profit_breakdown = {}

    for token_address, net_amount in net_flows.items():
        if abs(net_amount) < 1000:  # Ignore dust
            continue

        token_name = TOKENS.get(token_address, 'UNKNOWN')
        decimals = DECIMALS.get(token_name, 18)
        amount = float(net_amount) / (10 ** decimals)

        if token_name in PRICES:
            usd_value = amount * PRICES[token_name]
            total_profit_usd += usd_value
            profit_breakdown[token_name] = {
                'amount': amount,
                'usd_value': usd_value
            }

    # Subtract gas cost
    gas_cost_bnb = (float(tx['gasPrice']) * tx.get('gas', 200000)) / 1e18
    gas_cost_usd = gas_cost_bnb * PRICES['WBNB']

    net_profit_usd = total_profit_usd - gas_cost_usd

    return {
        'gross_profit_usd': total_profit_usd,
        'gas_cost_usd': gas_cost_usd,
        'net_profit_usd': net_profit_usd,
        'profit_breakdown': profit_breakdown,
        'net_flows': {TOKENS.get(k, k): v / (10**18) for k, v in net_flows.items() if abs(v) > 1000}
    }

def analyze_sample_transactions(limit=10):
    """Analyze sample transactions from database"""
    import sqlite3

    db_path = 'arbitrage-data/arbitrage.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get sample transactions
    cursor.execute('''
        SELECT tx_hash, estimated_profit_usd
        FROM transactions
        ORDER BY RANDOM()
        LIMIT ?
    ''', (limit,))

    transactions = cursor.fetchall()

    print(f"🔬 ANALYZING {len(transactions)} SAMPLE TRANSACTIONS")
    print("=" * 60)
    print()

    results = []

    for i, tx_row in enumerate(transactions, 1):
        tx_hash = tx_row['tx_hash']
        estimated = tx_row['estimated_profit_usd']

        print(f"{i}. Analyzing {tx_hash[:20]}...")
        print(f"   Estimated profit: ${estimated:,.0f}")

        result = analyze_transaction(tx_hash)

        if result:
            print(f"   ✅ REAL gross profit: ${result['gross_profit_usd']:,.2f}")
            print(f"   ✅ Gas cost: ${result['gas_cost_usd']:,.2f}")
            print(f"   ✅ NET profit: ${result['net_profit_usd']:,.2f}")

            if result['profit_breakdown']:
                print(f"   Breakdown:")
                for token, data in result['profit_breakdown'].items():
                    print(f"     {token}: {data['amount']:.4f} (${data['usd_value']:,.2f})")

            accuracy = (result['net_profit_usd'] / estimated * 100) if estimated > 0 else 0
            print(f"   Accuracy: {accuracy:.1f}% of estimate")

            results.append({
                'estimated': estimated,
                'actual': result['net_profit_usd'],
                'accuracy': accuracy
            })
        else:
            print(f"   ❌ Could not analyze")

        print()

    # Summary
    if results:
        print("=" * 60)
        print("📊 SUMMARY")
        print("=" * 60)
        avg_estimated = sum(r['estimated'] for r in results) / len(results)
        avg_actual = sum(r['actual'] for r in results) / len(results)

        print(f"Average estimated profit: ${avg_estimated:,.0f}")
        print(f"Average REAL profit: ${avg_actual:,.2f}")
        print(f"Estimate accuracy: {(avg_actual / avg_estimated * 100) if avg_estimated > 0 else 0:.1f}%")

        if avg_actual < avg_estimated * 0.5:
            print("\n⚠️  Estimates are SIGNIFICANTLY OVERSTATED")
        elif avg_actual > avg_estimated * 2:
            print("\n⚠️  Estimates are SIGNIFICANTLY UNDERSTATED")
        else:
            print("\n✅ Estimates are reasonably accurate (within 2x)")

    conn.close()

if __name__ == '__main__':
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║            REAL PROFIT ANALYZER                              ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print("This tool analyzes actual transaction logs to calculate")
    print("REAL profits instead of rough estimates.")
    print()

    analyze_sample_transactions(limit=20)
