#!/usr/bin/env python3
"""
Competitive Flash Loan Arbitrage Bot
Shows how to compete with other arbitrageurs using gas bidding
"""

from web3 import Web3
from decimal import Decimal
import time
import json

# Configuration
BSC_RPC = "https://bsc-dataseed.bnbchain.org"  # Use your own node for better speed
PRIVATE_KEY = "YOUR_PRIVATE_KEY_HERE"  # NEVER commit real keys!
CONTRACT_ADDRESS = "0x..."  # Your deployed FlashLoanArbitrage contract

# Pools to monitor (from our analysis)
POOLS = {
    "WBNB-BUSD": "0x58F876857a02D6762E0101bb5C46A8c1ED44Dc16",
    "USDT-WBNB": "0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE",
    "CAKE-WBNB": "0x0eD7e52944161450477ee417DE9Cd3a859b14fD0",
}

# Token addresses
TOKENS = {
    "WBNB": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
    "BUSD": "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
    "USDT": "0x55d398326f99059fF775485246999027B3197955",
    "CAKE": "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82",
}

# Token prices (could fetch from oracle)
PRICES = {
    "WBNB": 943,
    "BUSD": 1,
    "USDT": 1,
    "CAKE": 1.8,
}


class CompetitiveArbitrageBot:
    """
    Bot that competes with other arbitrageurs using smart gas bidding
    """

    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(BSC_RPC))
        self.account = self.w3.eth.account.from_key(PRIVATE_KEY)

        # Load contract ABI (simplified for example)
        self.contract = self.w3.eth.contract(
            address=CONTRACT_ADDRESS,
            abi=self.get_contract_abi()
        )

        # Competition tracking
        self.failed_attempts = {}  # Track failed TXs to adjust gas
        self.successful_arbs = 0
        self.total_profit = 0

    def get_contract_abi(self):
        """Get contract ABI"""
        # Simplified - real implementation would load from JSON
        return json.loads('''[
            {
                "inputs": [
                    {"internalType": "address", "name": "poolAddress", "type": "address"},
                    {"internalType": "address", "name": "tokenToBorrow", "type": "address"},
                    {"internalType": "uint256", "name": "amountToBorrow", "type": "uint256"}
                ],
                "name": "executeArbitrage",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]''')

    def check_pool_imbalance(self, pool_address: str, token0_addr: str,
                            token1_addr: str) -> tuple:
        """
        Check if pool is imbalanced (has arbitrage opportunity)
        Returns: (imbalance_pct, profit_usd, excess_token, excess_amount)
        """
        # Get pool contract
        pool_abi = json.loads('''[
            {"inputs":[],"name":"getReserves","outputs":[
                {"internalType":"uint112","name":"reserve0","type":"uint112"},
                {"internalType":"uint112","name":"reserve1","type":"uint112"},
                {"internalType":"uint32","name":"blockTimestampLast","type":"uint32"}
            ],"stateMutability":"view","type":"function"},
            {"inputs":[],"name":"token0","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
            {"inputs":[],"name":"token1","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"}
        ]''')
        pool = self.w3.eth.contract(address=pool_address, abi=pool_abi)

        # Get reserves
        reserves = pool.functions.getReserves().call()
        reserve0 = reserves[0] / 1e18
        reserve1 = reserves[1] / 1e18

        # Get token symbols for prices
        token0_symbol = self.get_token_symbol(token0_addr)
        token1_symbol = self.get_token_symbol(token1_addr)

        price0 = PRICES.get(token0_symbol, 1)
        price1 = PRICES.get(token1_symbol, 1)

        # Calculate USD values
        value0_usd = reserve0 * price0
        value1_usd = reserve1 * price1
        total_value = value0_usd + value1_usd
        optimal_value = total_value / 2

        # Calculate imbalance
        imbalance_pct = abs(value0_usd - optimal_value) / optimal_value * 100

        # Determine which side has excess
        if value0_usd > optimal_value:
            excess_token = token0_addr
            excess_value = value0_usd - optimal_value
            excess_amount = excess_value / price0
        else:
            excess_token = token1_addr
            excess_value = value1_usd - optimal_value
            excess_amount = excess_value / price1

        # Calculate profit (after 0.3% swap fee)
        gross_profit = excess_value
        profit_after_swap_fee = gross_profit * 0.997

        # Flash loan fee (0.09%)
        flash_loan_fee = profit_after_swap_fee * 0.0009
        net_profit = profit_after_swap_fee - flash_loan_fee

        return imbalance_pct, net_profit, excess_token, excess_amount

    def calculate_competitive_gas_price(self, profit_usd: float,
                                        pool_address: str) -> int:
        """
        Calculate optimal gas price to win the competition
        but not overpay
        """
        # Get current base gas price
        base_gas = self.w3.eth.gas_price

        # Check if we've failed on this pool recently
        recent_failures = self.failed_attempts.get(pool_address, 0)

        # Competition levels based on profit size
        if profit_usd > 100000:
            # Extreme competition - bid aggressively
            competition_multiplier = 20 + (recent_failures * 5)
        elif profit_usd > 50000:
            # High competition
            competition_multiplier = 10 + (recent_failures * 3)
        elif profit_usd > 20000:
            # Medium competition
            competition_multiplier = 5 + (recent_failures * 2)
        else:
            # Lower competition on smaller opportunities
            competition_multiplier = 2 + recent_failures

        # Calculate competitive gas price
        competitive_gas = base_gas * competition_multiplier

        # Cap at maximum profitable gas price
        # Assume 250K gas usage for flash loan arbitrage
        estimated_gas_usage = 250000
        bnb_price = PRICES["WBNB"]

        # Max gas = 20% of profit (still leaves 80% profit)
        max_gas_budget_usd = profit_usd * 0.20
        max_gas_budget_bnb = max_gas_budget_usd / bnb_price
        max_gas_price = int((max_gas_budget_bnb * 1e18) / estimated_gas_usage)

        # Use lower of competitive or max
        final_gas_price = min(competitive_gas, max_gas_price)

        print(f"  Gas Strategy:")
        print(f"    Base: {base_gas / 1e9:.2f} Gwei")
        print(f"    Competitive ({competition_multiplier}x): {competitive_gas / 1e9:.2f} Gwei")
        print(f"    Max profitable: {max_gas_price / 1e9:.2f} Gwei")
        print(f"    Using: {final_gas_price / 1e9:.2f} Gwei")

        return final_gas_price

    def execute_arbitrage(self, pool_address: str, pool_name: str,
                         token_to_borrow: str, amount_to_borrow: float,
                         profit_usd: float):
        """
        Execute arbitrage with competitive gas pricing
        """
        print(f"\n{'='*60}")
        print(f"🎯 EXECUTING ARBITRAGE")
        print(f"{'='*60}")
        print(f"Pool: {pool_name}")
        print(f"Expected Profit: ${profit_usd:,.2f}")

        # Calculate competitive gas price
        gas_price = self.calculate_competitive_gas_price(profit_usd, pool_address)

        # Convert amount to Wei
        amount_wei = int(amount_to_borrow * 1e18)

        # Build transaction
        try:
            tx = self.contract.functions.executeArbitrage(
                pool_address,
                token_to_borrow,
                amount_wei
            ).build_transaction({
                'from': self.account.address,
                'gas': 350000,  # Generous gas limit
                'gasPrice': gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
            })

            # Sign transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx, PRIVATE_KEY)

            # Send transaction
            print(f"\n📤 Sending transaction...")
            print(f"   Gas Price: {gas_price / 1e9:.2f} Gwei")
            print(f"   Gas Cost: ${(gas_price * 350000 / 1e18) * PRICES['WBNB']:.2f}")

            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            print(f"   TX Hash: {tx_hash.hex()}")

            # Wait for receipt
            print(f"\n⏳ Waiting for confirmation...")
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

            if receipt['status'] == 1:
                # SUCCESS!
                actual_gas_used = receipt['gasUsed']
                gas_cost_usd = (gas_price * actual_gas_used / 1e18) * PRICES['WBNB']
                flash_loan_fee = profit_usd * 0.0009
                net_profit = profit_usd - gas_cost_usd - flash_loan_fee

                print(f"\n✅ ARBITRAGE SUCCESSFUL!")
                print(f"   Gross Profit: ${profit_usd:,.2f}")
                print(f"   Gas Cost: ${gas_cost_usd:.2f}")
                print(f"   Flash Loan Fee: ${flash_loan_fee:.2f}")
                print(f"   NET PROFIT: ${net_profit:,.2f}")

                self.successful_arbs += 1
                self.total_profit += net_profit

                # Reset failure counter
                self.failed_attempts[pool_address] = 0

                return True

            else:
                # Transaction failed
                print(f"\n❌ Transaction failed (status: {receipt['status']})")
                self.record_failure(pool_address)
                return False

        except Exception as e:
            print(f"\n❌ Error executing arbitrage: {e}")
            self.record_failure(pool_address)
            return False

    def record_failure(self, pool_address: str):
        """
        Record failed attempt to adjust gas bidding
        """
        current_failures = self.failed_attempts.get(pool_address, 0)
        self.failed_attempts[pool_address] = current_failures + 1
        print(f"   Failures on {pool_address}: {self.failed_attempts[pool_address]}")
        print(f"   Will bid higher gas next time")

    def get_token_symbol(self, token_address: str) -> str:
        """Get token symbol from address"""
        for symbol, addr in TOKENS.items():
            if addr.lower() == token_address.lower():
                return symbol
        return "UNKNOWN"

    def monitor_and_execute(self):
        """
        Main loop: Monitor pools and execute arbitrage when profitable
        """
        print("="*60)
        print("🤖 COMPETITIVE ARBITRAGE BOT STARTED")
        print("="*60)
        print(f"Monitoring {len(POOLS)} pools")
        print(f"Account: {self.account.address}")
        print(f"Contract: {CONTRACT_ADDRESS}")
        print("="*60)

        scan_count = 0

        while True:
            scan_count += 1
            print(f"\n⏰ Scan #{scan_count} - {time.strftime('%H:%M:%S')}")

            for pool_name, pool_address in POOLS.items():
                # Get token addresses (simplified - would query on-chain)
                tokens = pool_name.split('-')
                token0_addr = TOKENS[tokens[0]]
                token1_addr = TOKENS[tokens[1]]

                # Check for imbalance
                imbalance, profit, excess_token, excess_amount = \
                    self.check_pool_imbalance(pool_address, token0_addr, token1_addr)

                print(f"  {pool_name}: {imbalance:.2f}% → ${profit:,.0f}")

                # Execute if profitable (minimum $10K to be worth gas costs)
                if profit > 10000:
                    print(f"\n  🚨 PROFITABLE OPPORTUNITY DETECTED!")
                    print(f"     Profit: ${profit:,.2f}")
                    print(f"     Imbalance: {imbalance:.2f}%")

                    # Execute arbitrage
                    success = self.execute_arbitrage(
                        pool_address,
                        pool_name,
                        excess_token,
                        excess_amount,
                        profit
                    )

                    if success:
                        print(f"\n📊 SESSION STATS")
                        print(f"   Successful Arbitrages: {self.successful_arbs}")
                        print(f"   Total Profit: ${self.total_profit:,.2f}")

            # Sleep before next scan
            # NOTE: Real competitive bot would scan every 100ms or faster
            # We use 30s for this example to avoid rate limiting
            time.sleep(30)


if __name__ == '__main__':
    """
    COMPETITIVE ARBITRAGE BOT

    HOW IT COMPETES:
    1. Monitors pools every 100ms (faster = better)
    2. Calculates optimal gas price based on profit
    3. Bids higher gas if previous attempts failed
    4. Adjusts strategy based on competition

    GAS BIDDING STRATEGY:
    - Small profit ($10K-20K): 2x base gas
    - Medium profit ($20K-50K): 5x base gas
    - Large profit ($50K-100K): 10x base gas
    - Huge profit ($100K+): 20x base gas
    - After failure: +5x multiplier per failure

    EXAMPLE COMPETITION:
    - You detect $50K opportunity
    - Base gas: 3 Gwei
    - Your bid: 15 Gwei (5x)
    - Competitor A: 10 Gwei → You win!
    - Competitor B: 20 Gwei → They win :(
    - Next attempt: You bid 30 Gwei (10x)

    WIN RATE FACTORS:
    - Scan speed (faster = more chances)
    - Gas bidding (higher = priority)
    - Latency (closer to validators = faster)
    - Strategy (focus on less competitive opportunities)

    EXPECTED RESULTS:
    - Win rate: 5-20% (depends on competition)
    - Net profit per win: $10K-$100K
    - Daily wins: 1-50 (depends on activity)
    - Daily profit: $10K-$5M (varies widely)
    """

    print(__doc__)

    # WARNING: This is example code for educational purposes
    # Real implementation needs:
    # 1. Proper error handling
    # 2. Security checks
    # 3. Transaction simulation before sending
    # 4. Slippage protection
    # 5. Gas estimation
    # 6. Nonce management for concurrent TXs
    # 7. Private key management (never hardcode!)

    print("\n⚠️  This is example code - DO NOT use with real private keys!")
    print("⚠️  Add proper security and error handling before using with real funds!")

    # Uncomment to run (after adding your private key and contract address)
    # bot = CompetitiveArbitrageBot()
    # bot.monitor_and_execute()
