#!/usr/bin/env python3
"""Analyze current pool state to verify opportunity detection logic"""

import requests

RPC = "https://bsc-dataseed.bnbchain.org"

# Pool addresses
POOLS = {
    "USDT-WBNB": "0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE",
    "WBNB-BUSD": "0x58F876857a02D6762E0101bb5C46A8c1ED44Dc16",
    "CAKE-WBNB": "0x0eD7e52944161450477ee417DE9Cd3a859b14fD0",
}

# Token prices
TOKEN_PRICES = {
    "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c": 943.0,  # WBNB
    "0xe9e7cea3dedca5984780bafc599bd69add087d56": 1.0,    # BUSD
    "0x55d398326f99059ff775485246999027b3197955": 1.0,    # USDT
    "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82": 2.45,   # CAKE
}

TOKEN_NAMES = {
    "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c": "WBNB",
    "0xe9e7cea3dedca5984780bafc599bd69add087d56": "BUSD",
    "0x55d398326f99059ff775485246999027b3197955": "USDT",
    "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82": "CAKE",
}

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

def analyze_pool(pool_name, pool_address):
    """Analyze a specific pool for arbitrage opportunity"""

    print("\n" + "=" * 80)
    print(f"ANALYZING: {pool_name}")
    print("=" * 80)
    print(f"Pool: {pool_address}")

    # Get current block
    block_result = rpc_call("eth_blockNumber", [])
    current_block = int(block_result, 16) if block_result else 0
    print(f"Current Block: {current_block}")

    # Get token addresses
    token0_result = rpc_call("eth_call", [
        {"to": pool_address, "data": "0x0dfe1681"},  # token0()
        "latest"
    ])
    token1_result = rpc_call("eth_call", [
        {"to": pool_address, "data": "0xd21220a7"},  # token1()
        "latest"
    ])

    if not token0_result or not token1_result:
        print("❌ Could not get token addresses")
        return

    token0 = "0x" + token0_result[-40:].lower()
    token1 = "0x" + token1_result[-40:].lower()

    token0_name = TOKEN_NAMES.get(token0, "UNKNOWN")
    token1_name = TOKEN_NAMES.get(token1, "UNKNOWN")

    print(f"\nTokens:")
    print(f"  token0: {token0} ({token0_name})")
    print(f"  token1: {token1} ({token1_name})")

    # Get reserves
    reserves_result = rpc_call("eth_call", [
        {"to": pool_address, "data": "0x0902f1ac"},  # getReserves()
        "latest"
    ])

    if not reserves_result or len(reserves_result) < 130:
        print("❌ Could not get reserves")
        return

    reserve0 = int(reserves_result[2:66], 16)
    reserve1 = int(reserves_result[66:130], 16)

    reserve0_normalized = reserve0 / 1e18
    reserve1_normalized = reserve1 / 1e18

    print(f"\nReserves:")
    print(f"  {token0_name}: {reserve0_normalized:,.2f}")
    print(f"  {token1_name}: {reserve1_normalized:,.2f}")

    # Get prices
    price0 = TOKEN_PRICES.get(token0, 0)
    price1 = TOKEN_PRICES.get(token1, 0)

    print(f"\nPrices:")
    print(f"  {token0_name}: ${price0:.2f}")
    print(f"  {token1_name}: ${price1:.2f}")

    # Calculate USD values
    value0_usd = reserve0_normalized * price0
    value1_usd = reserve1_normalized * price1
    total_value = value0_usd + value1_usd
    optimal_each = total_value / 2

    print(f"\nUSD Values:")
    print(f"  {token0_name} side: ${value0_usd:,.2f}")
    print(f"  {token1_name} side: ${value1_usd:,.2f}")
    print(f"  Total TVL: ${total_value:,.2f}")
    print(f"  Optimal (50/50): ${optimal_each:,.2f}")

    # Calculate imbalance
    deviation = abs(value0_usd - optimal_each)
    imbalance_pct = (deviation / optimal_each) * 100

    print(f"\n📊 IMBALANCE ANALYSIS:")
    print(f"  Deviation: ${deviation:,.2f}")
    print(f"  Imbalance: {imbalance_pct:.4f}%")

    if imbalance_pct < 0.3:
        print(f"  Status: ✓ WELL BALANCED (< 0.3%)")
        return

    # Arbitrage calculation
    print(f"\n💰 ARBITRAGE OPPORTUNITY:")

    if value0_usd > optimal_each:
        print(f"  Strategy: Sell {token0_name}, buy {token1_name}")
        excess_value = value0_usd - optimal_each
        sell_token = token0_name
        sell_amount = excess_value / price0 if price0 > 0 else 0
    else:
        print(f"  Strategy: Sell {token1_name}, buy {token0_name}")
        excess_value = value1_usd - optimal_each
        sell_token = token1_name
        sell_amount = excess_value / price1 if price1 > 0 else 0

    print(f"  Excess Value: ${excess_value:,.2f}")
    print(f"  Sell: {sell_amount:,.4f} {sell_token}")

    # Profit calculation
    profit_before_fees = excess_value
    profit_after_swap = profit_before_fees * 0.997  # 0.3% swap fee

    print(f"\n  Gross Profit: ${profit_before_fees:,.2f}")
    print(f"  After 0.3% Swap Fee: ${profit_after_swap:,.2f}")

    # Gas costs
    gas_price_gwei = 3.0
    gas_used = 150000  # Single swap estimate
    gas_cost_bnb = (gas_price_gwei * gas_used) / 1e9
    gas_cost_usd = gas_cost_bnb * 943

    print(f"\n⛽ GAS COSTS:")
    print(f"  Gas: {gas_price_gwei} Gwei × {gas_used:,} = ${gas_cost_usd:.2f}")

    # Net profit
    net_profit = profit_after_swap - gas_cost_usd
    roi = (net_profit / excess_value * 100) if excess_value > 0 else 0

    print(f"\n💵 NET PROFIT:")
    print(f"  After Gas: ${net_profit:,.2f}")
    print(f"  ROI: {roi:.4f}%")

    # Capital required
    capital_required = excess_value

    print(f"\n💼 EXECUTION REQUIREMENTS:")
    print(f"  Capital Needed: ${capital_required:,.2f}")
    print(f"  Method: Single swap on PancakeSwap")

    if net_profit > 1000:
        print(f"\n✅ PROFITABLE OPPORTUNITY! (>${net_profit:,.2f} net)")
    elif net_profit > 0:
        print(f"\n⚠️  MARGINALLY PROFITABLE (${net_profit:,.2f}, may not be worth it)")
    else:
        print(f"\n❌ NOT PROFITABLE after gas")

    # Flash loan option
    if capital_required > 10000:
        flash_loan_fee = capital_required * 0.0009  # 0.09% PancakeSwap flash loan fee
        net_profit_flash = net_profit - flash_loan_fee
        print(f"\n🔥 FLASH LOAN OPTION:")
        print(f"  Loan: ${capital_required:,.2f}")
        print(f"  Fee (0.09%): ${flash_loan_fee:,.2f}")
        print(f"  Net Profit: ${net_profit_flash:,.2f}")

        if net_profit_flash > 100:
            print(f"  ✅ PROFITABLE WITH FLASH LOAN!")

if __name__ == '__main__':
    print("=" * 80)
    print("CURRENT POOL STATE ANALYSIS")
    print("=" * 80)
    print("\nAnalyzing all monitored pools for arbitrage opportunities...")

    for pool_name, pool_address in POOLS.items():
        analyze_pool(pool_name, pool_address)

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
