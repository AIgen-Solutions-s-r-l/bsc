#!/usr/bin/env python3
"""
Cross-DEX and Multi-Hop Arbitrage Tracker
Monitors prices across multiple DEXs and finds arbitrage opportunities:
- 2-way: Cross-DEX simple (buy DEX A, sell DEX B)
- 3-way: Triangular arbitrage
- 4-way: Multi-hop arbitrage
- 5-way: Complex multi-hop

Author: BSC Arbitrage Research Team
Date: November 16, 2025
"""

from web3 import Web3
from decimal import Decimal
import time
import sqlite3
from datetime import datetime
import json
from typing import List, Dict, Tuple, Optional
from itertools import permutations, combinations

# BSC RPC
BSC_RPC = "https://bsc-dataseed.bnbchain.org"

# DEX Configurations
DEXS = {
    "PancakeSwap_V2": {
        "name": "PancakeSwap V2",
        "factory": "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",
        "router": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
        "fee": 0.0025,  # 0.25%
        "init_code_hash": "0x00fb7f630766e6a796048ea87d01acd3068e8ff67d078148a3fa3f4a84f69bd5"
    },
    "Biswap": {
        "name": "Biswap",
        "factory": "0x858E3312ed3A876947EA49d572A7C42DE08af7EE",
        "router": "0x3a6d8cA21D1CF76F653A67577FA0D27453350dD8",
        "fee": 0.001,  # 0.1%
        "init_code_hash": "0xfea293c909d87cd4153593f077b76bb7e94340200f4ee84211ae8e4f9bd7ffdf"
    },
    "ApeSwap": {
        "name": "ApeSwap",
        "factory": "0x0841BD0B734E4F5853f0dD8d7Ea041c241fb0Da6",
        "router": "0xcF0feBd3f17CEf5b47b0cD257aCf6025c5BFf3b7",
        "fee": 0.002,  # 0.2%
        "init_code_hash": "0xf4ccce374816856d11f00e4069e7cada164065686fbef53c6167a63ec2fd8c5b"
    }
}

# Token addresses
TOKENS = {
    "WBNB": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
    "BUSD": "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
    "USDT": "0x55d398326f99059fF775485246999027B3197955",
    "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
    "ETH": "0x2170Ed0880ac9A755fd29B2688956BD959F933F8",
    "BTC": "0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c",
    "CAKE": "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82",
}

# Priority pairs to monitor
PRIORITY_PAIRS = [
    ("WBNB", "USDT"),
    ("WBNB", "BUSD"),
    ("WBNB", "USDC"),
    ("USDT", "BUSD"),
    ("USDT", "USDC"),
    ("BUSD", "USDC"),
    ("WBNB", "ETH"),
    ("WBNB", "BTC"),
    ("WBNB", "CAKE"),
]

# Triangular paths (3-way)
TRIANGULAR_PATHS = [
    ["WBNB", "USDT", "BUSD"],
    ["WBNB", "USDT", "USDC"],
    ["WBNB", "BUSD", "USDC"],
    ["WBNB", "ETH", "USDT"],
    ["WBNB", "BTC", "USDT"],
    ["WBNB", "CAKE", "USDT"],
]

# ERC20 ABI (minimal)
ERC20_ABI = json.loads('[{"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"payable":false,"stateMutability":"view","type":"function"}]')

# Pair ABI (minimal - getReserves)
PAIR_ABI = json.loads('[{"constant":true,"inputs":[],"name":"getReserves","outputs":[{"internalType":"uint112","name":"reserve0","type":"uint112"},{"internalType":"uint112","name":"reserve1","type":"uint112"},{"internalType":"uint32","name":"blockTimestampLast","type":"uint32"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"token0","outputs":[{"internalType":"address","name":"","type":"address"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"token1","outputs":[{"internalType":"address","name":"","type":"address"}],"payable":false,"stateMutability":"view","type":"function"}]')


class CrossDEXArbitrageTracker:
    """
    Tracker for cross-DEX and multi-hop arbitrage opportunities
    """

    def __init__(self, db_path="arbitrage-data/cross_dex_arbitrage.db"):
        self.w3 = Web3(Web3.HTTPProvider(BSC_RPC))
        self.db_path = db_path
        self.init_database()

        # Cache for pair addresses
        self.pair_cache = {}

        # Gas price in Gwei
        self.gas_price_gwei = 3

    def init_database(self):
        """Initialize SQLite database for storing opportunities"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Table for 2-way cross-DEX opportunities
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cross_dex_2way (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                token0 TEXT NOT NULL,
                token1 TEXT NOT NULL,
                dex_buy TEXT NOT NULL,
                dex_sell TEXT NOT NULL,
                price_buy REAL NOT NULL,
                price_sell REAL NOT NULL,
                price_diff_pct REAL NOT NULL,
                estimated_profit_eur REAL NOT NULL,
                trade_size_eur REAL NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Table for 3-way triangular
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS triangular_3way (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                path TEXT NOT NULL,
                dex_combination TEXT NOT NULL,
                input_amount REAL NOT NULL,
                output_amount REAL NOT NULL,
                profit_pct REAL NOT NULL,
                estimated_profit_eur REAL NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Table for 4-way and 5-way
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS multihop_4way_5way (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                path TEXT NOT NULL,
                num_hops INTEGER NOT NULL,
                dex_combination TEXT NOT NULL,
                input_amount REAL NOT NULL,
                output_amount REAL NOT NULL,
                profit_pct REAL NOT NULL,
                estimated_profit_eur REAL NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

        print(f"✅ Database initialized: {self.db_path}")

    def get_pair_address(self, dex_name: str, token0_addr: str, token1_addr: str) -> Optional[str]:
        """
        Calculate pair address for Uniswap V2 style DEX
        Using CREATE2 deterministic address calculation
        """
        cache_key = f"{dex_name}_{token0_addr}_{token1_addr}"
        if cache_key in self.pair_cache:
            return self.pair_cache[cache_key]

        dex = DEXS.get(dex_name)
        if not dex:
            return None

        # Sort tokens
        token0, token1 = (token0_addr, token1_addr) if int(token0_addr, 16) < int(token1_addr, 16) else (token1_addr, token0_addr)

        # Calculate pair address using CREATE2
        # pair = keccak256(0xff + factory + keccak256(token0, token1) + init_code_hash)
        factory = dex["factory"]
        init_code_hash = dex["init_code_hash"]

        # For simplicity, we'll query the factory instead of calculating
        # In production, calculate with CREATE2 for speed
        factory_abi = json.loads('[{"constant":true,"inputs":[{"internalType":"address","name":"tokenA","type":"address"},{"internalType":"address","name":"tokenB","type":"address"}],"name":"getPair","outputs":[{"internalType":"address","name":"pair","type":"address"}],"payable":false,"stateMutability":"view","type":"function"}]')

        try:
            factory_contract = self.w3.eth.contract(address=factory, abi=factory_abi)
            pair_address = factory_contract.functions.getPair(token0, token1).call()

            if pair_address == "0x0000000000000000000000000000000000000000":
                return None

            self.pair_cache[cache_key] = pair_address
            return pair_address
        except Exception as e:
            print(f"Error getting pair {token0_addr}-{token1_addr} on {dex_name}: {e}")
            return None

    def get_price(self, dex_name: str, token_in: str, token_out: str, amount_in: float = 1.0) -> Optional[float]:
        """
        Get price for token swap on a specific DEX
        Returns: amount of token_out for amount_in of token_in
        """
        token_in_addr = TOKENS.get(token_in)
        token_out_addr = TOKENS.get(token_out)

        if not token_in_addr or not token_out_addr:
            return None

        pair_addr = self.get_pair_address(dex_name, token_in_addr, token_out_addr)
        if not pair_addr:
            return None

        try:
            pair = self.w3.eth.contract(address=pair_addr, abi=PAIR_ABI)
            reserves = pair.functions.getReserves().call()
            token0_addr = pair.functions.token0().call()

            reserve0 = reserves[0] / 1e18
            reserve1 = reserves[1] / 1e18

            # Determine which reserve is which token
            if token0_addr.lower() == token_in_addr.lower():
                reserve_in = reserve0
                reserve_out = reserve1
            else:
                reserve_in = reserve1
                reserve_out = reserve0

            # Calculate output using constant product formula
            # amountOut = (amountIn * reserveOut) / (reserveIn + amountIn)
            dex_fee = DEXS[dex_name]["fee"]
            amount_in_with_fee = amount_in * (1 - dex_fee)

            amount_out = (amount_in_with_fee * reserve_out) / (reserve_in + amount_in_with_fee)

            return amount_out

        except Exception as e:
            # Pair doesn't exist or error
            return None

    def find_cross_dex_2way(self, trade_size_eur: float = 10000) -> List[Dict]:
        """
        Find 2-way cross-DEX arbitrage opportunities
        Buy on DEX A, sell on DEX B
        """
        opportunities = []

        for token0, token1 in PRIORITY_PAIRS:
            prices = {}

            # Get prices on all DEXs
            for dex_name in DEXS.keys():
                # Price for token0 → token1
                price_forward = self.get_price(dex_name, token0, token1, 1.0)
                # Price for token1 → token0
                price_backward = self.get_price(dex_name, token1, token0, 1.0)

                if price_forward and price_backward:
                    prices[dex_name] = {
                        "forward": price_forward,  # token0 → token1
                        "backward": price_backward,  # token1 → token0
                    }

            # Find arbitrage opportunities
            dex_list = list(prices.keys())
            for i in range(len(dex_list)):
                for j in range(i+1, len(dex_list)):
                    dex_a = dex_list[i]
                    dex_b = dex_list[j]

                    # Direction 1: Buy token1 on DEX A, sell on DEX B
                    price_buy_a = prices[dex_a]["forward"]
                    price_sell_b = prices[dex_b]["backward"]

                    # Calculate profit
                    # Start with 1 token0 → buy token1 on A → sell token1 for token0 on B
                    amount_token1 = price_buy_a
                    amount_token0_back = amount_token1 * price_sell_b
                    profit_pct = (amount_token0_back - 1.0) * 100

                    # Account for gas costs
                    flash_loan_fee = trade_size_eur * 0.0009  # 0.09%
                    gas_cost = 15  # EUR

                    if profit_pct > 0:
                        gross_profit = trade_size_eur * (profit_pct / 100)
                        net_profit = gross_profit - flash_loan_fee - gas_cost

                        if net_profit > 5:  # Min €5 profit
                            opportunities.append({
                                "type": "2-way",
                                "token0": token0,
                                "token1": token1,
                                "dex_buy": dex_a,
                                "dex_sell": dex_b,
                                "price_buy": price_buy_a,
                                "price_sell": price_sell_b,
                                "price_diff_pct": profit_pct,
                                "gross_profit": gross_profit,
                                "net_profit": net_profit,
                                "trade_size": trade_size_eur
                            })

                    # Direction 2: Buy token1 on DEX B, sell on DEX A
                    price_buy_b = prices[dex_b]["forward"]
                    price_sell_a = prices[dex_a]["backward"]

                    amount_token1 = price_buy_b
                    amount_token0_back = amount_token1 * price_sell_a
                    profit_pct = (amount_token0_back - 1.0) * 100

                    if profit_pct > 0:
                        gross_profit = trade_size_eur * (profit_pct / 100)
                        net_profit = gross_profit - flash_loan_fee - gas_cost

                        if net_profit > 5:
                            opportunities.append({
                                "type": "2-way",
                                "token0": token0,
                                "token1": token1,
                                "dex_buy": dex_b,
                                "dex_sell": dex_a,
                                "price_buy": price_buy_b,
                                "price_sell": price_sell_a,
                                "price_diff_pct": profit_pct,
                                "gross_profit": gross_profit,
                                "net_profit": net_profit,
                                "trade_size": trade_size_eur
                            })

        return opportunities

    def find_triangular_3way(self, start_amount: float = 10000) -> List[Dict]:
        """
        Find 3-way triangular arbitrage opportunities
        Example: WBNB → USDT → BUSD → WBNB
        """
        opportunities = []

        for path in TRIANGULAR_PATHS:
            # Try all combinations of DEXs for each hop
            dex_list = list(DEXS.keys())

            for dex_combo in [(d1, d2, d3) for d1 in dex_list for d2 in dex_list for d3 in dex_list]:
                try:
                    # Start with start_amount of path[0]
                    amount = start_amount

                    # Hop 1: path[0] → path[1]
                    price1 = self.get_price(dex_combo[0], path[0], path[1], amount)
                    if not price1:
                        continue
                    amount = price1

                    # Hop 2: path[1] → path[2]
                    price2 = self.get_price(dex_combo[1], path[1], path[2], amount)
                    if not price2:
                        continue
                    amount = price2

                    # Hop 3: path[2] → path[0]
                    price3 = self.get_price(dex_combo[2], path[2], path[0], amount)
                    if not price3:
                        continue
                    final_amount = price3

                    # Calculate profit
                    profit = final_amount - start_amount
                    profit_pct = (profit / start_amount) * 100

                    # Account for gas (more hops = more gas)
                    flash_fee = start_amount * 0.0009
                    gas_cost = 30  # EUR (3 swaps)

                    net_profit = profit - flash_fee - gas_cost

                    if net_profit > 10:  # Min €10 profit
                        opportunities.append({
                            "type": "3-way",
                            "path": " → ".join(path + [path[0]]),
                            "dex_combo": " → ".join(dex_combo),
                            "start_amount": start_amount,
                            "final_amount": final_amount,
                            "profit_pct": profit_pct,
                            "gross_profit": profit,
                            "net_profit": net_profit
                        })

                except Exception as e:
                    continue

        return opportunities

    def scan_all(self):
        """
        Scan for all types of arbitrage opportunities
        """
        print(f"\n⏰ Scan - {datetime.now().strftime('%H:%M:%S')}")
        print("-" * 70)

        # 2-way cross-DEX
        print("Scanning 2-way cross-DEX...")
        opps_2way = self.find_cross_dex_2way(trade_size_eur=10000)

        if opps_2way:
            print(f"  Found {len(opps_2way)} opportunities:")
            for opp in opps_2way[:5]:  # Show top 5
                print(f"    💰 {opp['token0']}-{opp['token1']}: Buy {opp['dex_buy']} → Sell {opp['dex_sell']}")
                print(f"       Profit: €{opp['net_profit']:.2f} ({opp['price_diff_pct']:.3f}%)")

            # Save to database
            self.save_2way_opportunities(opps_2way)
        else:
            print("  No opportunities found")

        # 3-way triangular
        print("\nScanning 3-way triangular...")
        opps_3way = self.find_triangular_3way(start_amount=10000)

        if opps_3way:
            print(f"  Found {len(opps_3way)} opportunities:")
            for opp in opps_3way[:3]:  # Show top 3
                print(f"    🔺 {opp['path']}")
                print(f"       DEXs: {opp['dex_combo']}")
                print(f"       Profit: €{opp['net_profit']:.2f} ({opp['profit_pct']:.3f}%)")

            # Save to database
            self.save_3way_opportunities(opps_3way)
        else:
            print("  No opportunities found")

        print(f"\nTotal: {len(opps_2way)} 2-way + {len(opps_3way)} 3-way = {len(opps_2way) + len(opps_3way)} opportunities")

    def save_2way_opportunities(self, opportunities: List[Dict]):
        """Save 2-way opportunities to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for opp in opportunities:
            cursor.execute('''
                INSERT INTO cross_dex_2way
                (timestamp, token0, token1, dex_buy, dex_sell, price_buy, price_sell,
                 price_diff_pct, estimated_profit_eur, trade_size_eur)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now(),
                opp['token0'],
                opp['token1'],
                opp['dex_buy'],
                opp['dex_sell'],
                opp['price_buy'],
                opp['price_sell'],
                opp['price_diff_pct'],
                opp['net_profit'],
                opp['trade_size']
            ))

        conn.commit()
        conn.close()

    def save_3way_opportunities(self, opportunities: List[Dict]):
        """Save 3-way opportunities to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for opp in opportunities:
            cursor.execute('''
                INSERT INTO triangular_3way
                (timestamp, path, dex_combination, input_amount, output_amount,
                 profit_pct, estimated_profit_eur)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now(),
                opp['path'],
                opp['dex_combo'],
                opp['start_amount'],
                opp['final_amount'],
                opp['profit_pct'],
                opp['net_profit']
            ))

        conn.commit()
        conn.close()

    def run(self, interval_seconds: int = 30):
        """
        Main loop: scan continuously
        """
        print("="*70)
        print("🚀 CROSS-DEX & MULTI-HOP ARBITRAGE TRACKER")
        print("="*70)
        print(f"Monitoring {len(DEXS)} DEXs:")
        for dex_name, dex_info in DEXS.items():
            print(f"  - {dex_info['name']} (fee: {dex_info['fee']*100}%)")
        print(f"\nPairs: {len(PRIORITY_PAIRS)}")
        print(f"Triangular paths: {len(TRIANGULAR_PATHS)}")
        print(f"Scan interval: {interval_seconds}s")
        print("="*70)

        scan_count = 0

        while True:
            scan_count += 1
            print(f"\n📊 Scan #{scan_count}")

            try:
                self.scan_all()
            except Exception as e:
                print(f"❌ Error during scan: {e}")

            print(f"\n💤 Waiting {interval_seconds}s...")
            time.sleep(interval_seconds)


if __name__ == "__main__":
    tracker = CrossDEXArbitrageTracker()
    tracker.run(interval_seconds=30)
