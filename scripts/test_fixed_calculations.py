#!/usr/bin/env python3
"""Test the fixed imbalance calculations against real BSC pools"""

import requests
import sys

# Add parent directory to path
sys.path.insert(0, '/home/alessio/Projects/bsc/scripts')

from enhanced_tracker import EnhancedArbitrageTracker, POOLS

def test_pool_calculations():
    """Test the fixed imbalance calculation formula"""

    print("=" * 80)
    print("TESTING FIXED IMBALANCE CALCULATIONS")
    print("=" * 80)

    tracker = EnhancedArbitrageTracker()

    for pool_name, pool_address in POOLS.items():
        print(f"\n{pool_name}:")
        print(f"  Address: {pool_address}")

        # Get reserves
        reserve0, reserve1 = tracker.get_pool_reserves(pool_address)

        if reserve0 > 0 and reserve1 > 0:
            # Get token addresses
            token0, token1 = tracker.get_pool_token_addresses(pool_address)

            if token0 and token1:
                print(f"  token0: {token0}")
                print(f"  token1: {token1}")

                # Get prices
                price0 = tracker.get_token_price_usd(token0)
                price1 = tracker.get_token_price_usd(token1)

                print(f"  Prices: ${price0:.2f} / ${price1:.2f}")

                # Reserves
                r0_normalized = reserve0 / 1e18
                r1_normalized = reserve1 / 1e18
                print(f"  Reserves: {r0_normalized:.2f} / {r1_normalized:.2f}")

                # USD values
                value0 = r0_normalized * price0
                value1 = r1_normalized * price1
                print(f"  USD Values: ${value0:,.2f} / ${value1:,.2f}")

                # Calculate imbalance
                imbalance, profit = tracker.calculate_imbalance(
                    reserve0, reserve1, token0, token1
                )

                print(f"  Imbalance: {imbalance:.4f}%")
                print(f"  Profit Potential: ${profit:,.2f}")

                # Determine if this is a real opportunity
                if imbalance > 0.3 and profit > 100:
                    print(f"  ✅ REAL OPPORTUNITY (>{0.3}% imbalance, >${100} profit)")
                elif imbalance > 0.1:
                    print(f"  ⚠️  SMALL IMBALANCE (not profitable after gas)")
                else:
                    print(f"  ✓ WELL BALANCED")
            else:
                print(f"  ❌ Could not get token addresses")
        else:
            print(f"  ❌ Could not get reserves")

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    test_pool_calculations()
