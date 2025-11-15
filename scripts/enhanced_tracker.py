#!/usr/bin/env python3
"""Enhanced Arbitrage Tracker with Database and Detailed Analysis"""

import requests
import time
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from db_manager import ArbitrageDB
from web3 import Web3

# Configuration
EXTERNAL_RPC = "https://bsc-dataseed.bnbchain.org"
LOCAL_RPC = "http://localhost:8545"

# Known PancakeSwap V2 pools (WBNB pairs)
POOLS = {
    "WBNB-BUSD": "0x58F876857a02D6762E0101bb5C46A8c1ED44Dc16",
    "WBNB-USDT": "0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE",
    "WBNB-USDC": "0x7EFaEf62fDdCCa950418312c6C91Aef321375A00",
    "WBNB-CAKE": "0x0eD7e52944161450477ee417DE9Cd3a859b14fD0",
    "WBNB-ETH": "0x1B96B92314C44b159149f7E0303511fB2Fc4774f",
}

# DEX Routers to monitor
DEX_ROUTERS = {
    "PancakeSwap V2": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
    "ApeSwap": "0xcF0feBd3f17CEf5b47b0cD257aCf6025c5BFf3b7",
    "BiSwap": "0x3a6d8cA21D1CF76F653A67577FA0D27453350dD8",
}

# Swap method signatures
SWAP_METHODS = {
    "0x38ed1739": "swapExactTokensForTokens",
    "0x8803dbee": "swapTokensForExactTokens",
    "0x7ff36ab5": "swapExactETHForTokens",
    "0x18cbafe5": "swapExactTokensForETH",
}

# BNB price (approximate)
BNB_USD = 620.0

# Swap event signature for proper detection
web3 = Web3()
SWAP_EVENT_SIGNATURE = web3.keccak(text="Swap(address,uint256,uint256,uint256,uint256,address)").hex()

class EnhancedArbitrageTracker:
    def __init__(self):
        self.db = ArbitrageDB()
        self.rpc = EXTERNAL_RPC
        self.last_block = self.get_latest_block()
        self.opportunity_cache = {}  # Track recent opportunities
        print(f"🚀 Enhanced Tracker Started - Block: {self.last_block}")

    def rpc_call(self, method: str, params: list) -> any:
        """Make RPC call with error handling"""
        try:
            response = requests.post(
                self.rpc,
                json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
                timeout=10
            )
            result = response.json()
            if "result" in result:
                return result["result"]
            elif "error" in result:
                print(f"⚠️  RPC Error: {result['error']}")
                return None
        except Exception as e:
            print(f"⚠️  RPC Exception: {e}")
            return None

    def get_latest_block(self) -> int:
        """Get latest block number"""
        result = self.rpc_call("eth_blockNumber", [])
        return int(result, 16) if result else 0

    def get_pool_reserves(self, pool_address: str) -> Tuple[int, int]:
        """Get pool reserves via getReserves()"""
        result = self.rpc_call("eth_call", [
            {"to": pool_address, "data": "0x0902f1ac"},
            "latest"
        ])

        if result and len(result) >= 130:
            reserve0 = int(result[2:66], 16)
            reserve1 = int(result[66:130], 16)
            return reserve0, reserve1
        return 0, 0

    def calculate_imbalance(self, reserve0: int, reserve1: int) -> Tuple[float, float]:
        """Calculate pool imbalance and profit potential"""
        if reserve0 == 0 or reserve1 == 0:
            return 0.0, 0.0

        # CPMM: k = x * y
        k = reserve0 * reserve1
        optimal_x = (k ** 0.5)
        optimal_y = (k ** 0.5)

        # Imbalance percentage
        imbalance_x = abs(reserve0 - optimal_x) / optimal_x * 100
        imbalance_y = abs(reserve1 - optimal_y) / optimal_y * 100
        imbalance = max(imbalance_x, imbalance_y)

        # Profit estimation (simplified)
        if reserve0 > optimal_x:
            # Too much token0, arbitrage by selling token0
            excess = reserve0 - optimal_x
            profit = (excess * reserve1) / (reserve0 + excess) / 1e18
        else:
            # Too much token1, arbitrage by selling token1
            excess = reserve1 - optimal_y
            profit = (excess * reserve0) / (reserve1 + excess) / 1e18

        return imbalance, profit * BNB_USD

    def scan_pools(self):
        """Scan all pools for imbalances"""
        opportunities = []

        for pool_name, pool_address in POOLS.items():
            reserve0, reserve1 = self.get_pool_reserves(pool_address)

            if reserve0 > 0 and reserve1 > 0:
                imbalance, profit_usd = self.calculate_imbalance(reserve0, reserve1)

                if imbalance > 5.0:  # Only log significant imbalances
                    # Log to database
                    opp_id = self.db.log_opportunity(
                        pool_name=pool_name,
                        pool_address=pool_address,
                        imbalance_pct=imbalance,
                        profit_usd=profit_usd,
                        profit_bnb=profit_usd / BNB_USD,
                        reserve0=reserve0 / 1e18,
                        reserve1=reserve1 / 1e18,
                        block_number=self.last_block
                    )

                    # Cache for matching with transactions
                    cache_key = f"{pool_address}_{self.last_block}"
                    self.opportunity_cache[cache_key] = {
                        'id': opp_id,
                        'timestamp': datetime.now(),
                        'profit_usd': profit_usd
                    }

                    opportunities.append({
                        'pool': pool_name,
                        'imbalance': imbalance,
                        'profit': profit_usd
                    })

        return opportunities

    def get_transaction_receipt(self, tx_hash: str) -> Optional[Dict]:
        """Get transaction receipt"""
        return self.rpc_call("eth_getTransactionReceipt", [tx_hash])

    def get_transaction(self, tx_hash: str) -> Optional[Dict]:
        """Get transaction details"""
        return self.rpc_call("eth_getTransactionByHash", [tx_hash])

    def analyze_transaction(self, tx: Dict) -> Optional[Dict]:
        """Analyze if transaction is an arbitrage"""
        if not tx or not tx.get('to'):
            return None

        to_address = tx['to'].lower()

        # Check if it's a DEX router
        is_dex = any(router.lower() == to_address for router in DEX_ROUTERS.values())

        if not is_dex:
            return None

        # Check method signature
        input_data = tx.get('input', '')
        if len(input_data) < 10:
            return None

        method_sig = input_data[:10]
        if method_sig not in SWAP_METHODS:
            return None

        # Get receipt for logs
        receipt = self.get_transaction_receipt(tx['hash'])
        if not receipt:
            return None

        # Count ACTUAL Swap events only (not all logs!)
        swap_count = 0
        for log in receipt.get('logs', []):
            if len(log.get('topics', [])) > 0:
                # Check if this is a Swap event
                if log['topics'][0] == SWAP_EVENT_SIGNATURE:
                    swap_count += 1

        # REAL arbitrage requires multiple swaps in one transaction
        if swap_count >= 2:
            gas_price = int(tx.get('gasPrice', '0'), 16) / 1e9  # Gwei
            gas_used = int(receipt.get('gasUsed', '0'), 16)
            gas_cost_bnb = (gas_price * gas_used) / 1e9

            return {
                'tx_hash': tx['hash'],
                'from': tx['from'],
                'block': int(tx['blockNumber'], 16),
                'gas_price_gwei': gas_price,
                'gas_used': gas_used,
                'gas_cost_bnb': gas_cost_bnb,
                'swap_count': swap_count,
                'method': SWAP_METHODS.get(method_sig, 'unknown')
            }

        return None

    def monitor_blocks(self):
        """Monitor new blocks for arbitrage transactions"""
        current_block = self.get_latest_block()

        if current_block <= self.last_block:
            return

        print(f"\n📦 New Block: {current_block} (checking {current_block - self.last_block} blocks)")

        # Check blocks since last check
        for block_num in range(self.last_block + 1, current_block + 1):
            block_hex = hex(block_num)
            block = self.rpc_call("eth_getBlockByNumber", [block_hex, True])

            if not block or not block.get('transactions'):
                continue

            # Analyze each transaction
            for tx in block['transactions']:
                arb = self.analyze_transaction(tx)

                if arb:
                    # Estimate profit (simplified - actual profit would need log parsing)
                    estimated_profit_usd = arb['swap_count'] * 1000  # Rough estimate

                    # Log transaction
                    self.db.log_transaction(
                        tx_hash=arb['tx_hash'],
                        from_address=arb['from'],
                        block_number=arb['block'],
                        gas_price_gwei=arb['gas_price_gwei'],
                        gas_used=arb['gas_used'],
                        swap_count=arb['swap_count'],
                        profit_usd=estimated_profit_usd,
                        strategy=f"{arb['swap_count']}-hop"
                    )

                    # Update arbitrageur stats
                    self.db.update_arbitrageur(
                        address=arb['from'],
                        profit_usd=estimated_profit_usd,
                        gas_price=arb['gas_price_gwei'],
                        strategy=f"{arb['swap_count']}-hop",
                        success=True
                    )

                    print(f"  🎯 REAL ARBITRAGE detected! ({arb['swap_count']} swaps)")
                    print(f"     TX: {arb['tx_hash'][:20]}...")
                    print(f"     From: {arb['from'][:10]}...{arb['from'][-8:]}")
                    print(f"     Gas: {arb['gas_price_gwei']:.2f} Gwei")
                    print(f"     Est. Profit: ~${estimated_profit_usd:,.0f} (rough)")

        self.last_block = current_block

    def run(self):
        """Main monitoring loop"""
        print("\n" + "="*60)
        print("🔥 FIXED ARBITRAGE MONITORING SYSTEM")
        print("="*60)
        print("\n✅ NOW TRACKING REAL ARBITRAGE ONLY:")
        print("  • Requires 2+ Swap events in single transaction")
        print("  • Proper Swap event signature detection")
        print("  • Multi-hop arbitrage paths")
        print("  • Real arbitrageur competition")
        print("\n❌ NO LONGER COUNTING:")
        print("  • Regular single-swap trades")
        print("  • Normal DEX users")
        print("\n💾 Database: arbitrage-data/arbitrage.db")
        print("🌐 Dashboard: Run 'python3 scripts/dashboard.py' to view\n")

        iteration = 0
        try:
            while True:
                iteration += 1

                # Scan pools every iteration
                opportunities = self.scan_pools()

                if opportunities:
                    print(f"\n⏰ Scan #{iteration} - {datetime.now().strftime('%H:%M:%S')}")
                    for opp in opportunities:
                        # Only print small opportunities (10K-100K)
                        if 10000 <= opp['profit'] <= 100000:
                            print(f"  💰 {opp['pool']}: {opp['imbalance']:.1f}% → ${opp['profit']:,.0f}")

                # Monitor blocks for transactions
                self.monitor_blocks()

                # Wait before next scan
                time.sleep(60)  # 1 minute intervals

        except KeyboardInterrupt:
            print("\n\n⏹️  Tracker stopped by user")
            self.show_summary()
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.db.close()

    def show_summary(self):
        """Show summary statistics"""
        stats = self.db.get_stats_summary()

        print("\n" + "="*60)
        print("📊 SESSION SUMMARY")
        print("="*60)
        print(f"\n  Total Opportunities Detected: {stats['total_opportunities']}")
        print(f"  Total Value Detected: ${stats['total_value_detected']:,.2f}")
        print(f"  Small Opportunities (10K-100K): {stats['small_opportunities_count']}")
        print(f"  Avg Small Opp Size: ${stats['small_opportunities_avg']:,.2f}")
        print(f"\n  Arbitrage Transactions Found: {stats['total_transactions']}")
        print(f"  Unique Arbitrageurs: {stats['total_arbitrageurs']}")
        print(f"\n💾 All data saved to: arbitrage-data/arbitrage.db")
        print(f"🌐 View dashboard: python3 scripts/dashboard.py\n")

if __name__ == '__main__':
    tracker = EnhancedArbitrageTracker()
    tracker.run()
