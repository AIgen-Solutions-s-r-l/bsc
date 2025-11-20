#!/usr/bin/env python3
"""
BSC Imbalance Prediction Engine - Python Client
Monitors DEX pools for liquidity imbalance opportunities
"""

import json
import time
import argparse
import requests
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ImbalanceOpportunity:
    """Represents a detected imbalance opportunity"""
    pool_address: str
    imbalance_score: float
    level: str
    confidence: float
    profit_wei: int
    profit_bnb: float
    pending_swaps: int
    timestamp: str

    def is_actionable(self) -> bool:
        """Check if opportunity is actionable"""
        return (self.level in ['moderate', 'severe', 'critical'] and
                self.confidence >= 70.0 and
                self.profit_wei > 0)


# Known PancakeSwap V2 pools
TEST_POOLS = [
    "0x58F876857a02D6762E0101bb5C46A8c1ED44Dc16",  # WBNB-BUSD
    "0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE",  # WBNB-USDT
    "0x7EFaEf62fDdCCa950418312c6C91Aef321375A00",  # WBNB-USDC
    "0x0eD7e52944161450477ee417DE9Cd3a859b14fD0",  # WBNB-CAKE
    "0x1B96B92314C44b159149f7E0303511fB2Fc4774f",  # WBNB-ETH
]


class ImbalanceClient:
    """Client for BSC Imbalance Prediction Engine"""

    def __init__(self, rpc_url: str = "http://127.0.0.1:8545"):
        self.rpc_url = rpc_url

    def _rpc_call(self, method: str, params: List = None) -> Dict:
        """Make JSON-RPC call"""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or [],
            "id": 1
        }

        response = requests.post(self.rpc_url, json=payload)
        response.raise_for_status()

        result = response.json()
        if "error" in result:
            raise Exception(f"RPC error: {result['error']}")

        return result.get("result")

    def get_stats(self) -> Dict:
        """Get predictor statistics"""
        return self._rpc_call("imbalance_getStats")

    def get_pool_imbalance(self, pool_address: str) -> Optional[ImbalanceOpportunity]:
        """Get imbalance prediction for a pool"""
        try:
            result = self._rpc_call("imbalance_getPoolImbalance", [pool_address])

            profit_wei = int(result.get("profit_opportunity", "0"))
            profit_bnb = profit_wei / 1e18

            return ImbalanceOpportunity(
                pool_address=result.get("pool_address", pool_address),
                imbalance_score=result.get("imbalance_score", 0.0),
                level=result.get("level", "unknown"),
                confidence=result.get("confidence", 0.0),
                profit_wei=profit_wei,
                profit_bnb=profit_bnb,
                pending_swaps=result.get("pending_swaps", 0),
                timestamp=result.get("timestamp", "")
            )
        except Exception as e:
            if "pool state not in cache" in str(e):
                return None
            raise

    def scan_pools(self, pools: List[str], min_score: float = 20.0) -> List[ImbalanceOpportunity]:
        """Scan multiple pools for opportunities"""
        opportunities = []

        for pool in pools:
            opp = self.get_pool_imbalance(pool)
            if opp and opp.imbalance_score >= min_score:
                opportunities.append(opp)

        return opportunities


def print_header():
    """Print client header"""
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║  BSC Imbalance Prediction Engine - Python Monitor           ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print()


def print_stats(stats: Dict):
    """Print predictor statistics"""
    print("Predictor Status:")
    status = "✓ RUNNING" if stats.get("running") else "✗ STOPPED"
    print(f"  Status: {status}")
    print(f"  Active Pools: {stats.get('active_pools', 0)}")
    print(f"  Cache Size: {stats.get('cache_size', 0)} entries")
    print(f"  Cache Hit Rate: {stats.get('cache_hit_rate', 0) * 100:.2f}%")
    print(f"  Transactions Processed: {stats.get('filter_total_processed', 0)}")
    print(f"  Swap Transactions: {stats.get('filter_filtered', 0)}")
    print()


def print_opportunity(opp: ImbalanceOpportunity):
    """Print opportunity details with color coding"""

    # ANSI color codes
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"

    # Determine color based on level
    if opp.level == "critical":
        color = RED
        icon = "🚨"
    elif opp.level == "severe":
        color = RED
        icon = "⚠"
    elif opp.level == "moderate":
        color = YELLOW
        icon = "⚠"
    else:
        color = GREEN
        icon = "ℹ"

    print(f"{color}{icon} OPPORTUNITY DETECTED{RESET}")
    print(f"  Pool: {CYAN}{opp.pool_address}{RESET}")
    print(f"  Imbalance Score: {color}{opp.imbalance_score:.2f}%{RESET} ({opp.level})")
    print(f"  Confidence: {opp.confidence:.1f}%")
    print(f"  Estimated Profit: {GREEN}{opp.profit_bnb:.6f} BNB{RESET} ({opp.profit_wei} wei)")
    print(f"  Pending Swaps: {opp.pending_swaps}")
    print(f"  Timestamp: {opp.timestamp}")

    if opp.is_actionable():
        print(f"\n  {GREEN}✓ ACTIONABLE{RESET} - High confidence opportunity")
    elif opp.confidence < 50.0:
        print(f"\n  {YELLOW}⚠ LOW CONFIDENCE{RESET} - More data needed")

    print()


def scan_mode(client: ImbalanceClient, min_score: float):
    """Run in scanning mode"""
    print("Scanning known DEX pools for opportunities...\n")
    print("─" * 60)
    print()

    opportunities = client.scan_pools(TEST_POOLS, min_score)

    if opportunities:
        for opp in opportunities:
            print_opportunity(opp)

        total_profit = sum(opp.profit_bnb for opp in opportunities)
        actionable = sum(1 for opp in opportunities if opp.is_actionable())

        print("─" * 60)
        print(f"Total Opportunities: {len(opportunities)}")
        print(f"Actionable: {actionable}")
        print(f"Total Estimated Profit: {total_profit:.6f} BNB")
    else:
        print("No opportunities found above threshold.")
        print("\nPossible reasons:")
        print("  • Pools are well-balanced")
        print("  • Node still syncing")
        print("  • No pending transactions")
        print(f"  • Threshold too high (current: {min_score}%)")


def monitor_mode(client: ImbalanceClient, pool: str, interval: int, min_score: float):
    """Run in continuous monitoring mode"""
    print(f"Monitoring pool: {pool}")
    print(f"Check interval: {interval}s")
    print(f"Min score: {min_score}%")
    print("\nPress Ctrl+C to stop\n")
    print("─" * 60)
    print()

    try:
        while True:
            opp = client.get_pool_imbalance(pool)

            if opp:
                if opp.imbalance_score >= min_score:
                    print_opportunity(opp)
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] Score: {opp.imbalance_score:.2f}% - Below threshold")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] Pool not in cache (node may be syncing)")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nStopped monitoring.")


def main():
    parser = argparse.ArgumentParser(
        description="BSC Imbalance Prediction Engine - Python Monitor"
    )
    parser.add_argument(
        "--rpc",
        default="http://127.0.0.1:8545",
        help="BSC RPC endpoint"
    )
    parser.add_argument(
        "--pool",
        help="Monitor specific pool address"
    )
    parser.add_argument(
        "--minscore",
        type=float,
        default=20.0,
        help="Minimum imbalance score to display"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Check interval in seconds (for monitoring mode)"
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Scan known pools once"
    )

    args = parser.parse_args()

    print_header()

    # Create client
    client = ImbalanceClient(args.rpc)

    # Check connection
    try:
        stats = client.get_stats()
        print(f"✓ Connected to BSC node: {args.rpc}")
        print_stats(stats)
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        return 1

    print("─" * 60)
    print()

    # Run appropriate mode
    if args.pool:
        monitor_mode(client, args.pool, args.interval, args.minscore)
    else:
        scan_mode(client, args.minscore)

    return 0


if __name__ == "__main__":
    exit(main())
