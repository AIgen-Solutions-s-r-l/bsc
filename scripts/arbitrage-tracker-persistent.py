#!/usr/bin/env python3
"""
Persistent Arbitrage Tracker - Saves all data to files for long-term analysis
Logs: arbitrageurs, opportunities, profits, timestamps
"""

import requests
import json
import time
import os
import csv
from datetime import datetime
from collections import defaultdict

# Configuration
EXTERNAL_RPC = "https://bsc-dataseed.bnbchain.org"
DATA_DIR = "./arbitrage-data"
LOG_FILE = f"{DATA_DIR}/monitoring.log"
ARBITRAGEURS_CSV = f"{DATA_DIR}/arbitrageurs.csv"
OPPORTUNITIES_CSV = f"{DATA_DIR}/opportunities.csv"
TRANSACTIONS_CSV = f"{DATA_DIR}/transactions.csv"
SESSION_FILE = f"{DATA_DIR}/session.json"

# Create data directory
os.makedirs(DATA_DIR, exist_ok=True)

# Pools to monitor
POOLS = [
    {"address": "0x58F876857a02D6762E0101bb5C46A8c1ED44Dc16", "name": "WBNB-BUSD", "emoji": "💵"},
    {"address": "0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE", "name": "WBNB-USDT", "emoji": "💲"},
    {"address": "0x7EFaEf62fDdCCa950418312c6C91Aef321375A00", "name": "WBNB-USDC", "emoji": "💴"},
    {"address": "0x0eD7e52944161450477ee417DE9Cd3a859b14fD0", "name": "WBNB-CAKE", "emoji": "🥞"},
    {"address": "0x1B96B92314C44b159149f7E0303511fB2Fc4774f", "name": "WBNB-ETH", "emoji": "💎"},
]

ROUTERS = {
    '0x10ed43c718714eb63d5aa57b78b54704e256024e': 'PancakeSwap',
    '0xcf0febd3f17cef5b47b0cd257acf6025c5bff3b7': 'ApeSwap',
    '0x3a6d8ca21d1cf76f653a67577fa0d27453350dd8': 'BiSwap',
}

SWAP_METHODS = {
    '0x38ed1739': 'swapExactTokensForTokens',
    '0x7ff36ab5': 'swapExactETHForTokens',
    '0x18cbafe5': 'swapExactTokensForETH',
}

# Statistics
stats = {
    'start_time': datetime.now(),
    'opportunities_logged': 0,
    'arbitrage_detected': 0,
    'unique_arbitrageurs': set(),
    'total_estimated_profit': 0.0,
    'blocks_scanned': 0,
}

arbitrageurs = defaultdict(lambda: {
    'address': '',
    'total_trades': 0,
    'total_profit_bnb': 0.0,
    'total_profit_usd': 0.0,
    'first_seen': None,
    'last_seen': None,
    'strategies': set()
})

def log_message(msg):
    """Log message to file and console"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] {msg}"
    print(log_line)

    with open(LOG_FILE, 'a') as f:
        f.write(log_line + '\n')

def save_opportunity(pool_name, pool_address, imbalance, profit_usd):
    """Save opportunity to CSV"""
    file_exists = os.path.isfile(OPPORTUNITIES_CSV)

    with open(OPPORTUNITIES_CSV, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['timestamp', 'pool_name', 'pool_address', 'imbalance_pct', 'profit_usd'])

        writer.writerow([
            datetime.now().isoformat(),
            pool_name,
            pool_address,
            f"{imbalance:.2f}",
            f"{profit_usd:.2f}"
        ])

def save_arbitrageur(address, trades, profit_bnb, profit_usd, strategy):
    """Save/update arbitrageur to CSV"""
    # Update in-memory stats
    arb = arbitrageurs[address]
    arb['address'] = address
    arb['total_trades'] = trades
    arb['total_profit_bnb'] = profit_bnb
    arb['total_profit_usd'] = profit_usd
    arb['strategies'].add(strategy)

    if arb['first_seen'] is None:
        arb['first_seen'] = datetime.now()
    arb['last_seen'] = datetime.now()

    # Rewrite entire CSV with updated data
    with open(ARBITRAGEURS_CSV, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['address', 'total_trades', 'total_profit_bnb', 'total_profit_usd',
                        'strategies', 'first_seen', 'last_seen'])

        for addr, data in sorted(arbitrageurs.items(), key=lambda x: x[1]['total_profit_usd'], reverse=True):
            writer.writerow([
                addr,
                data['total_trades'],
                f"{data['total_profit_bnb']:.4f}",
                f"{data['total_profit_usd']:.2f}",
                ','.join(data['strategies']),
                data['first_seen'].isoformat() if data['first_seen'] else '',
                data['last_seen'].isoformat() if data['last_seen'] else ''
            ])

def save_transaction(tx_hash, from_address, swaps_count, gas_bnb, profit_bnb, profit_usd):
    """Save transaction to CSV"""
    file_exists = os.path.isfile(TRANSACTIONS_CSV)

    with open(TRANSACTIONS_CSV, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['timestamp', 'tx_hash', 'from_address', 'swaps_count',
                           'gas_bnb', 'profit_bnb', 'profit_usd'])

        writer.writerow([
            datetime.now().isoformat(),
            tx_hash if tx_hash else f"multi-{from_address[:10]}",
            from_address,
            swaps_count,
            f"{gas_bnb:.4f}",
            f"{profit_bnb:.4f}",
            f"{profit_usd:.2f}"
        ])

def save_session():
    """Save session statistics"""
    session_data = {
        'start_time': stats['start_time'].isoformat(),
        'end_time': datetime.now().isoformat(),
        'duration_seconds': (datetime.now() - stats['start_time']).total_seconds(),
        'opportunities_logged': stats['opportunities_logged'],
        'arbitrage_detected': stats['arbitrage_detected'],
        'unique_arbitrageurs': len(stats['unique_arbitrageurs']),
        'total_estimated_profit': stats['total_estimated_profit'],
        'blocks_scanned': stats['blocks_scanned']
    }

    with open(SESSION_FILE, 'w') as f:
        json.dump(session_data, f, indent=2)

def get_pool_reserves(pool_address):
    """Fetch pool reserves"""
    try:
        response = requests.post(EXTERNAL_RPC, json={
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{"to": pool_address, "data": "0x0902f1ac"}, "latest"],
            "id": 1
        }, timeout=5)
        result = response.json().get("result")
        if result and result != "0x":
            reserve0 = int(result[2:66], 16)
            reserve1 = int(result[66:130], 16)
            return reserve0, reserve1
    except:
        pass
    return None, None

def calculate_value_imbalance(reserve0, reserve1, bnb_price=600):
    """Calculate value-based imbalance"""
    value0 = reserve0 / 1e18
    value1 = (reserve1 / 1e18) * bnb_price
    total_value = value0 + value1

    if total_value == 0:
        return 0.0, 0.0

    diff = abs(value0 - value1)
    imbalance_pct = (diff / total_value) * 100
    potential_profit = diff * 0.003

    return imbalance_pct, potential_profit

def get_latest_block():
    """Get latest block number"""
    try:
        response = requests.post(EXTERNAL_RPC, json={
            "jsonrpc": "2.0",
            "method": "eth_blockNumber",
            "params": [],
            "id": 1
        }, timeout=5)
        return int(response.json().get("result", "0x0"), 16)
    except:
        return 0

def get_block_transactions(block_number):
    """Get block transactions"""
    try:
        response = requests.post(EXTERNAL_RPC, json={
            "jsonrpc": "2.0",
            "method": "eth_getBlockByNumber",
            "params": [hex(block_number), True],
            "id": 1
        }, timeout=10)
        block = response.json().get("result")
        if block:
            return block.get("transactions", [])
    except:
        pass
    return []

def analyze_transaction(tx):
    """Check if transaction is a swap"""
    if not tx.get('to'):
        return None

    to_address = tx['to'].lower()
    router_name = ROUTERS.get(to_address)

    if not router_name:
        return None

    input_data = tx.get('input', '0x')
    if len(input_data) >= 10:
        method_sig = input_data[:10]
        method_name = SWAP_METHODS.get(method_sig)

        if method_name:
            return {
                'hash': tx.get('hash'),
                'from': tx['from'],
                'router': router_name,
                'method': method_name,
                'gas': int(tx.get('gas', '0x0'), 16),
                'gasPrice': int(tx.get('gasPrice', '0x0'), 16)
            }

    return None

def main():
    log_message("=" * 70)
    log_message("BSC ARBITRAGE TRACKER - Persistent Monitoring Started")
    log_message("=" * 70)
    log_message(f"Data directory: {DATA_DIR}")
    log_message(f"Log file: {LOG_FILE}")
    log_message(f"Arbitrageurs CSV: {ARBITRAGEURS_CSV}")
    log_message(f"Opportunities CSV: {OPPORTUNITIES_CSV}")
    log_message(f"Transactions CSV: {TRANSACTIONS_CSV}")
    log_message("")

    current_block = get_latest_block() - 1
    scan_count = 0
    bnb_price = 600  # Update this periodically if needed

    try:
        while True:
            scan_count += 1

            # Scan for opportunities
            if scan_count % 6 == 0:  # Every minute (6 * 10 seconds)
                log_message("Scanning pools for opportunities...")

                for pool in POOLS:
                    r0, r1 = get_pool_reserves(pool['address'])
                    if r0:
                        imb, profit_usd = calculate_value_imbalance(r0, r1, bnb_price)

                        if imb >= 10:  # Log if >= 10% imbalance
                            stats['opportunities_logged'] += 1
                            save_opportunity(pool['name'], pool['address'], imb, profit_usd)
                            log_message(f"  Opportunity: {pool['name']} - {imb:.1f}% - ${profit_usd:,.0f}")

            # Scan recent block for arbitrage
            latest_block = get_latest_block()

            if current_block < latest_block:
                stats['blocks_scanned'] += 1

                log_message(f"Scanning block {latest_block}...")

                txs = get_block_transactions(latest_block)

                # Analyze transactions
                by_sender = defaultdict(list)
                for tx in txs:
                    swap = analyze_transaction(tx)
                    if swap:
                        by_sender[swap['from']].append(swap)

                # Detect arbitrage
                for sender, swaps in by_sender.items():
                    if len(swaps) >= 2:
                        stats['arbitrage_detected'] += 1
                        stats['unique_arbitrageurs'].add(sender)

                        gas_cost_bnb = sum(s['gas'] * s['gasPrice'] for s in swaps) / 1e18
                        est_profit_bnb = gas_cost_bnb * 5
                        est_profit_usd = est_profit_bnb * bnb_price

                        stats['total_estimated_profit'] += est_profit_usd

                        strategy = f"{len(swaps)}-hop"

                        # Get current totals for this arbitrageur
                        current_trades = arbitrageurs[sender]['total_trades'] + 1
                        current_profit_bnb = arbitrageurs[sender]['total_profit_bnb'] + est_profit_bnb
                        current_profit_usd = arbitrageurs[sender]['total_profit_usd'] + est_profit_usd

                        # Save to files
                        save_arbitrageur(sender, current_trades, current_profit_bnb, current_profit_usd, strategy)
                        save_transaction(swaps[0]['hash'] if swaps else None, sender,
                                       len(swaps), gas_cost_bnb, est_profit_bnb, est_profit_usd)

                        log_message(f"  🎯 ARBITRAGE: {sender[:10]}...{sender[-6:]} - "
                                  f"{len(swaps)} swaps - ${est_profit_usd:.0f} profit")

                current_block = latest_block

            # Show stats every 10 scans
            if scan_count % 10 == 0:
                log_message("")
                log_message(f"📊 Stats: Opps: {stats['opportunities_logged']} | "
                          f"Arbitrage: {stats['arbitrage_detected']} | "
                          f"Arbitrageurs: {len(stats['unique_arbitrageurs'])} | "
                          f"Profit: ${stats['total_estimated_profit']:,.0f}")
                log_message("")

                # Save session
                save_session()

            time.sleep(10)

    except KeyboardInterrupt:
        log_message("")
        log_message("=" * 70)
        log_message("Monitoring stopped by user")
        log_message("=" * 70)
        log_message("")

        # Final save
        save_session()

        log_message("FINAL STATISTICS:")
        log_message(f"  Duration: {(datetime.now() - stats['start_time']).total_seconds() / 60:.1f} minutes")
        log_message(f"  Blocks Scanned: {stats['blocks_scanned']}")
        log_message(f"  Opportunities Logged: {stats['opportunities_logged']}")
        log_message(f"  Arbitrage Detected: {stats['arbitrage_detected']}")
        log_message(f"  Unique Arbitrageurs: {len(stats['unique_arbitrageurs'])}")
        log_message(f"  Total Est. Profit: ${stats['total_estimated_profit']:,.0f}")
        log_message("")
        log_message(f"📁 All data saved to: {DATA_DIR}/")
        log_message(f"   • {ARBITRAGEURS_CSV}")
        log_message(f"   • {OPPORTUNITIES_CSV}")
        log_message(f"   • {TRANSACTIONS_CSV}")
        log_message(f"   • {LOG_FILE}")
        log_message("")

if __name__ == "__main__":
    main()
