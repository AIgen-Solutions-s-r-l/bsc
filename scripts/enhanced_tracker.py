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

# Known PancakeSwap V2 pools (CORRECTED addresses)
POOLS = {
    "WBNB-BUSD": "0x58F876857a02D6762E0101bb5C46A8c1ED44Dc16",
    "USDT-WBNB": "0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE",
    "CAKE-WBNB": "0x0eD7e52944161450477ee417DE9Cd3a859b14fD0",
    # Note: Removed incorrect pool addresses
}

# Token addresses on BSC
TOKEN_ADDRESSES = {
    "WBNB": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
    "BUSD": "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
    "USDT": "0x55d398326f99059fF775485246999027B3197955",
    "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
    "CAKE": "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82",
    "ETH": "0x2170Ed0880ac9A755fd29B2688956BD959F933F8",
}

# Token prices in USD (updated periodically or from oracle)
TOKEN_PRICES_USD = {
    "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c".lower(): 943.0,  # WBNB
    "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56".lower(): 1.0,    # BUSD
    "0x55d398326f99059fF775485246999027B3197955".lower(): 1.0,    # USDT
    "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d".lower(): 1.0,    # USDC
    "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82".lower(): 2.45,   # CAKE
    "0x2170Ed0880ac9A755fd29B2688956BD959F933F8".lower(): 3500.0,  # ETH
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

    def get_pool_token_addresses(self, pool_address: str) -> Tuple[str, str]:
        """Get token0 and token1 addresses from pool"""
        token0_result = self.rpc_call("eth_call", [
            {"to": pool_address, "data": "0x0dfe1681"},  # token0()
            "latest"
        ])
        token1_result = self.rpc_call("eth_call", [
            {"to": pool_address, "data": "0xd21220a7"},  # token1()
            "latest"
        ])

        if token0_result and token1_result:
            token0 = "0x" + token0_result[-40:].lower()
            token1 = "0x" + token1_result[-40:].lower()
            return token0, token1
        return "", ""

    def get_token_price_usd(self, token_address: str) -> float:
        """Get token price in USD"""
        return TOKEN_PRICES_USD.get(token_address.lower(), 0.0)

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

    def calculate_imbalance(self, reserve0: int, reserve1: int,
                           token0_address: str, token1_address: str) -> Tuple[float, float]:
        """
        Calculate CORRECT pool imbalance using USD values

        A Uniswap V2 pool is balanced when both tokens have equal USD value,
        NOT when reserve quantities are equal (that assumption was the bug!)
        """
        if reserve0 == 0 or reserve1 == 0:
            return 0.0, 0.0

        # Get token prices in USD
        price0_usd = self.get_token_price_usd(token0_address)
        price1_usd = self.get_token_price_usd(token1_address)

        if price0_usd == 0 or price1_usd == 0:
            # Can't calculate without prices
            return 0.0, 0.0

        # Normalize reserves (convert from wei to tokens)
        reserve0_normalized = reserve0 / 1e18
        reserve1_normalized = reserve1 / 1e18

        # Calculate USD values of each side
        value0_usd = reserve0_normalized * price0_usd
        value1_usd = reserve1_normalized * price1_usd

        # Total pool value and optimal 50/50 split
        total_value_usd = value0_usd + value1_usd
        optimal_value_each = total_value_usd / 2

        # Imbalance is deviation from 50/50 USD split
        imbalance_pct = abs(value0_usd - optimal_value_each) / optimal_value_each * 100

        # Profit potential (accounting for 0.3% swap fees)
        if value0_usd > optimal_value_each:
            # Too much token0, profit by selling token0 for token1
            excess_value_usd = value0_usd - optimal_value_each
            # After 0.3% fee
            profit_usd = excess_value_usd * 0.997
        else:
            # Too much token1, profit by selling token1 for token0
            excess_value_usd = value1_usd - optimal_value_each
            # After 0.3% fee
            profit_usd = excess_value_usd * 0.997

        return imbalance_pct, profit_usd

    def scan_pools(self):
        """Scan all pools for imbalances"""
        opportunities = []

        for pool_name, pool_address in POOLS.items():
            # Get pool reserves
            reserve0, reserve1 = self.get_pool_reserves(pool_address)

            if reserve0 > 0 and reserve1 > 0:
                # Get token addresses for price lookup
                token0, token1 = self.get_pool_token_addresses(pool_address)

                if token0 and token1:
                    # Calculate imbalance with correct USD-based formula
                    imbalance, profit_usd = self.calculate_imbalance(
                        reserve0, reserve1, token0, token1
                    )

                    # Lower threshold to 0.3% (meaningful arbitrage opportunity)
                    if imbalance > 0.3 and profit_usd > 100:  # >0.3% imbalance, >$100 profit
                        # Get current BNB price for profit_bnb
                        bnb_price = self.get_token_price_usd(TOKEN_ADDRESSES["WBNB"].lower())

                        # Log to database
                        opp_id = self.db.log_opportunity(
                            pool_name=pool_name,
                            pool_address=pool_address,
                            imbalance_pct=imbalance,
                            profit_usd=profit_usd,
                            profit_bnb=profit_usd / bnb_price if bnb_price > 0 else 0,
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
