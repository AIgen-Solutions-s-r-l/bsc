#!/usr/bin/env python3
"""Verify a specific arbitrage opportunity is real and calculate exact profit"""

import requests
import sys
from datetime import datetime

RPC = "https://bsc-dataseed.bnbchain.org"

def rpc_call(method, params):
    """Make RPC call"""
    try:
        response = requests.post(RPC, json={
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        }, timeout=10)
        result = response.json()
        return result.get("result")
    except Exception as e:
        print(f"RPC Error: {e}")
        return None

def get_pool_state(pool_address, block_number):
    """Get pool reserves at specific block"""
    block_hex = hex(block_number)
    result = rpc_call("eth_call", [
        {"to": pool_address, "data": "0x0902f1ac"},  # getReserves()
        block_hex
    ])

    if result and len(result) >= 130:
        reserve0 = int(result[2:66], 16)
        reserve1 = int(result[66:130], 16)
        return reserve0, reserve1
    return None, None

def get_token_addresses(pool_address):
    """Get token0 and token1 from pool"""
    token0_result = rpc_call("eth_call", [
        {"to": pool_address, "data": "0x0dfe1681"},  # token0()
        "latest"
    ])
    token1_result = rpc_call("eth_call", [
        {"to": pool_address, "data": "0xd21220a7"},  # token1()
        "latest"
    ])

    if token0_result and token1_result:
        token0 = "0x" + token0_result[-40:]
        token1 = "0x" + token1_result[-40:]
        return token0, token1
    return None, None

def verify_opportunity(pool_address, block_number, expected_imbalance, expected_profit):
    """Verify an opportunity by recalculating at the exact block"""

    print("=" * 80)
    print("OPPORTUNITY VERIFICATION")
    print("=" * 80)
    print(f"\nPool: {pool_address}")
    print(f"Block: {block_number}")
    print(f"Expected Imbalance: {expected_imbalance:.4f}%")
    print(f"Expected Profit: ${expected_profit:,.2f}")

    # Get pool state at that block
    reserve0, reserve1 = get_pool_state(pool_address, block_number)

    if not reserve0:
        print("\n❌ Could not fetch pool state at that block")
        return False

    print(f"\nReserves at Block {block_number}:")
    print(f"  reserve0: {reserve0 / 1e18:,.2f}")
    print(f"  reserve1: {reserve1 / 1e18:,.2f}")

    # Get token addresses
    token0, token1 = get_token_addresses(pool_address)
    print(f"\nTokens:")
    print(f"  token0: {token0}")
    print(f"  token1: {token1}")

    # Token prices (from our oracle)
    TOKEN_PRICES = {
        "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c": 943.0,  # WBNB
        "0xe9e7cea3dedca5984780bafc599bd69add087d56": 1.0,    # BUSD
        "0x55d398326f99059ff775485246999027b3197955": 1.0,    # USDT
        "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82": 2.45,   # CAKE
    }

    price0 = TOKEN_PRICES.get(token0.lower(), 0)
    price1 = TOKEN_PRICES.get(token1.lower(), 0)

    print(f"\nPrices:")
    print(f"  token0: ${price0:.2f}")
    print(f"  token1: ${price1:.2f}")

    # Calculate USD values
    value0_usd = (reserve0 / 1e18) * price0
    value1_usd = (reserve1 / 1e18) * price1
    total_value = value0_usd + value1_usd
    optimal_each = total_value / 2

    print(f"\nUSD Values:")
    print(f"  Side 0: ${value0_usd:,.2f}")
    print(f"  Side 1: ${value1_usd:,.2f}")
    print(f"  Total: ${total_value:,.2f}")
    print(f"  Optimal (50/50): ${optimal_each:,.2f}")

    # Calculate imbalance
    imbalance_pct = abs(value0_usd - optimal_each) / optimal_each * 100

    # Profit calculation
    excess_value = abs(value0_usd - optimal_each)
    profit_before_fees = excess_value
    profit_after_swap_fees = profit_before_fees * 0.997  # 0.3% swap fee

    print(f"\n📊 CALCULATED IMBALANCE:")
    print(f"  Imbalance: {imbalance_pct:.4f}%")
    print(f"  Excess Value: ${excess_value:,.2f}")
    print(f"  Profit (before fees): ${profit_before_fees:,.2f}")
    print(f"  Profit (after 0.3% swap): ${profit_after_swap_fees:,.2f}")

    # Verify matches expected
    imbalance_match = abs(imbalance_pct - expected_imbalance) < 0.01
    profit_match = abs(profit_after_swap_fees - expected_profit) < 100

    print(f"\n✅ VERIFICATION:")
    print(f"  Imbalance matches: {'✓' if imbalance_match else '✗'}")
    print(f"  Profit matches: {'✓' if profit_match else '✗'}")

    # Calculate realistic execution costs
    print(f"\n💰 EXECUTION ANALYSIS:")

    # Arbitrage would require swapping the excess
    # For USDT-WBNB with ~$60K excess:
    # - Need to swap ~$60K of the overweighted token
    # - Get back ~$60K of underweighted token
    # - Net profit = excess * 0.997 (after swap fee)

    # Determine which token to swap
    if value0_usd > optimal_each:
        swap_token = token0
        swap_amount_usd = excess_value
        swap_amount_tokens = (excess_value / price0) if price0 > 0 else 0
        print(f"  Strategy: Sell token0 ({swap_token[:10]}...)")
    else:
        swap_token = token1
        swap_amount_usd = excess_value
        swap_amount_tokens = (excess_value / price1) if price1 > 0 else 0
        print(f"  Strategy: Sell token1 ({swap_token[:10]}...)")

    print(f"  Trade Size: ${swap_amount_usd:,.2f} ({swap_amount_tokens:,.4f} tokens)")

    # Gas cost estimation
    gas_price_gwei = 3.0  # Typical BSC gas price
    gas_used = 150000  # Estimate for single swap
    gas_cost_bnb = (gas_price_gwei * gas_used) / 1e9
    gas_cost_usd = gas_cost_bnb * 943  # BNB price

    print(f"\n⛽ GAS COSTS:")
    print(f"  Gas Price: {gas_price_gwei} Gwei")
    print(f"  Gas Used: {gas_used:,}")
    print(f"  Cost: {gas_cost_bnb:.6f} BNB (${gas_cost_usd:.2f})")

    # Net profit
    net_profit = profit_after_swap_fees - gas_cost_usd
    roi = (net_profit / swap_amount_usd * 100) if swap_amount_usd > 0 else 0

    print(f"\n💵 NET PROFIT:")
    print(f"  Gross Profit: ${profit_after_swap_fees:,.2f}")
    print(f"  Gas Cost: -${gas_cost_usd:.2f}")
    print(f"  NET PROFIT: ${net_profit:,.2f}")
    print(f"  ROI: {roi:.3f}%")

    if net_profit > 0:
        print(f"\n✅ OPPORTUNITY IS REAL AND PROFITABLE!")
    else:
        print(f"\n❌ NOT PROFITABLE AFTER GAS")

    # Check if it was captured in the next few blocks
    print(f"\n🔍 CHECKING IF CAPTURED...")
    blocks_to_check = 5

    for i in range(1, blocks_to_check + 1):
        next_block = block_number + i
        next_reserve0, next_reserve1 = get_pool_state(pool_address, next_block)

        if next_reserve0:
            next_value0 = (next_reserve0 / 1e18) * price0
            next_value1 = (next_reserve1 / 1e18) * price1
            next_total = next_value0 + next_value1
            next_optimal = next_total / 2
            next_imbalance = abs(next_value0 - next_optimal) / next_optimal * 100

            imbalance_reduced = next_imbalance < (imbalance_pct * 0.5)  # 50% reduction

            if imbalance_reduced:
                print(f"  Block {next_block}: Imbalance reduced to {next_imbalance:.4f}% ✓ (LIKELY CAPTURED)")
                return True
            else:
                print(f"  Block {next_block}: Imbalance {next_imbalance:.4f}%")

    print(f"\n  No significant reduction in next {blocks_to_check} blocks")
    print(f"  Opportunity may have persisted or was captured later")

    return imbalance_match and profit_match

if __name__ == '__main__':
    # Example: Verify the largest opportunity detected
    # USDT-WBNB: 0.968698057544209|144726.74837252|2025-11-16 02:52:46

    POOL = "0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE"  # USDT-WBNB

    # We need to find the block number for that timestamp
    # For now, let's verify one of the recent opportunities

    print("Fetching latest opportunity to verify...")

    import sqlite3
    conn = sqlite3.connect('/home/alessio/Projects/bsc/arbitrage-data/arbitrage.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT pool_address, block_number, imbalance_pct, estimated_profit_usd, timestamp
        FROM opportunities
        ORDER BY estimated_profit_usd DESC
        LIMIT 1
    """)

    row = cursor.fetchone()
    if row:
        pool_addr, block_num, imbalance, profit, timestamp = row
        print(f"\nVerifying opportunity from: {timestamp}")
        verify_opportunity(pool_addr, block_num, imbalance, profit)
    else:
        print("No opportunities found in database")

    conn.close()
