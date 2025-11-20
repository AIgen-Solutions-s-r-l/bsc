#!/usr/bin/env python3
"""Deep analysis of collected data"""

import sqlite3
from datetime import datetime

db_path = 'arbitrage-data/arbitrage.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("╔══════════════════════════════════════════════════════════════╗")
print("║               DEEP DIVE ANALYSIS                             ║")
print("╚══════════════════════════════════════════════════════════════╝")
print()

cursor = conn.cursor()

# 1. Examine actual opportunities in detail
print("🔍 DETAILED OPPORTUNITY ANALYSIS")
print("=" * 60)

cursor.execute('''
    SELECT
        timestamp,
        pool_name,
        imbalance_pct,
        estimated_profit_usd,
        reserve0,
        reserve1
    FROM opportunities
    ORDER BY timestamp DESC
''')

print("\nAll Opportunities Detected:")
print()
for row in cursor.fetchall():
    print(f"Time: {row['timestamp']}")
    print(f"Pool: {row['pool_name']}")
    print(f"Imbalance: {row['imbalance_pct']:.2f}%")
    print(f"Est. Profit: ${row['estimated_profit_usd']:,.0f}")
    print(f"Reserves: {row['reserve0']:,.2f} / {row['reserve1']:,.2f}")
    print("-" * 60)

print()
print()

# 2. Analyze transaction distribution
print("📈 TRANSACTION DISTRIBUTION ANALYSIS")
print("=" * 60)

cursor.execute('''
    SELECT
        estimated_profit_usd,
        COUNT(*) as tx_count
    FROM transactions
    GROUP BY estimated_profit_usd
    ORDER BY estimated_profit_usd
''')

print("\nTransaction count by profit level:")
print()
for row in cursor.fetchall():
    print(f"${row['estimated_profit_usd']:,.0f}: {row['tx_count']} transactions")

print()
print()

# 3. Look at actual transaction details
print("🔬 SAMPLE TRANSACTION DETAILS")
print("=" * 60)

cursor.execute('''
    SELECT
        tx_hash,
        from_address,
        block_number,
        swap_count,
        gas_price_gwei,
        gas_used,
        estimated_profit_usd,
        strategy_type
    FROM transactions
    ORDER BY timestamp DESC
    LIMIT 5
''')

print("\nMost Recent 5 Transactions:")
print()
for row in cursor.fetchall():
    print(f"TX Hash: {row['tx_hash']}")
    print(f"From: {row['from_address']}")
    print(f"Block: {row['block_number']}")
    print(f"Swaps: {row['swap_count']}")
    print(f"Gas: {row['gas_price_gwei']:.2f} Gwei (used: {row['gas_used']})")
    print(f"Est. Profit: ${row['estimated_profit_usd']:,.0f}")
    print(f"Strategy: {row['strategy_type']}")
    print("-" * 60)

print()
print()

# 4. Arbitrageur activity patterns
print("👥 ARBITRAGEUR ACTIVITY PATTERNS")
print("=" * 60)

cursor.execute('''
    SELECT
        CASE
            WHEN total_trades = 1 THEN '1 trade'
            WHEN total_trades <= 5 THEN '2-5 trades'
            WHEN total_trades <= 10 THEN '6-10 trades'
            WHEN total_trades <= 50 THEN '11-50 trades'
            ELSE '>50 trades'
        END as activity_level,
        COUNT(*) as arbitrageur_count,
        AVG(total_profit_usd) as avg_profit,
        AVG(avg_gas_price_gwei) as avg_gas
    FROM arbitrageurs
    GROUP BY activity_level
    ORDER BY MIN(total_trades)
''')

print("\nArbitrageur distribution by activity:")
print()
for row in cursor.fetchall():
    print(f"{row['activity_level']}")
    print(f"  Count: {row['arbitrageur_count']} arbitrageurs")
    print(f"  Avg Total Profit: ${row['avg_profit']:,.0f}")
    print(f"  Avg Gas: {row['avg_gas']:.2f} Gwei")
    print()

print()

# 5. Check if profit estimates are realistic
print("💵 PROFIT ESTIMATE REALITY CHECK")
print("=" * 60)

cursor.execute('''
    SELECT
        t.tx_hash,
        t.swap_count,
        t.estimated_profit_usd,
        t.gas_price_gwei,
        t.gas_used,
        a.total_trades,
        a.total_profit_usd
    FROM transactions t
    JOIN arbitrageurs a ON t.from_address = a.address
    ORDER BY t.timestamp DESC
    LIMIT 3
''')

print("\nSample profit calculations:")
print()
for row in cursor.fetchall():
    gas_cost_bnb = (row['gas_price_gwei'] * row['gas_used']) / 1e9
    gas_cost_usd = gas_cost_bnb * 620  # BNB price
    net_profit = row['estimated_profit_usd'] - gas_cost_usd

    print(f"TX: {row['tx_hash'][:20]}...")
    print(f"  Swaps: {row['swap_count']}")
    print(f"  Gross Profit Estimate: ${row['estimated_profit_usd']:,.0f}")
    print(f"  Gas Cost: ${gas_cost_usd:.2f} ({row['gas_price_gwei']:.2f} Gwei)")
    print(f"  Net Profit: ${net_profit:,.2f}")
    print(f"  Wallet Total Trades: {row['total_trades']}")
    print(f"  Wallet Total Profit: ${row['total_profit_usd']:,.0f}")
    print()

print()

# 6. Time-based analysis
print("⏰ TIME-BASED PATTERNS")
print("=" * 60)

cursor.execute('''
    SELECT
        strftime('%H:%M', timestamp) as minute,
        COUNT(*) as tx_count
    FROM transactions
    GROUP BY minute
    ORDER BY minute DESC
    LIMIT 10
''')

print("\nTransaction activity by minute (last 10 minutes):")
print()
for row in cursor.fetchall():
    bar = "█" * min(50, row['tx_count'] // 20)
    print(f"{row['minute']}: {row['tx_count']:4d} txs {bar}")

print()
print()

# 7. Check for data quality issues
print("🔧 DATA QUALITY ASSESSMENT")
print("=" * 60)

# Check for suspicious patterns
cursor.execute('''
    SELECT
        COUNT(DISTINCT estimated_profit_usd) as unique_profit_values,
        COUNT(*) as total_transactions
    FROM transactions
''')
row = cursor.fetchone()
print(f"\nTotal transactions: {row['total_transactions']}")
print(f"Unique profit values: {row['unique_profit_values']}")
print(f"Diversity ratio: {row['unique_profit_values'] / row['total_transactions']:.2%}")

if row['unique_profit_values'] < 20:
    print("⚠️  WARNING: Very few unique profit values suggests estimates are rough")

# Check gas prices
cursor.execute('''
    SELECT
        MIN(gas_price_gwei) as min_gas,
        MAX(gas_price_gwei) as max_gas,
        AVG(gas_price_gwei) as avg_gas,
        COUNT(DISTINCT gas_price_gwei) as unique_gas_prices
    FROM transactions
''')
row = cursor.fetchone()
print(f"\nGas price range: {row['min_gas']:.2f} - {row['max_gas']:.2f} Gwei")
print(f"Average gas: {row['avg_gas']:.2f} Gwei")
print(f"Unique gas prices: {row['unique_gas_prices']}")

# Check block distribution
cursor.execute('''
    SELECT
        COUNT(DISTINCT block_number) as unique_blocks,
        MIN(block_number) as first_block,
        MAX(block_number) as last_block
    FROM transactions
''')
row = cursor.fetchone()
blocks_scanned = row['last_block'] - row['first_block'] + 1
print(f"\nBlocks scanned: {blocks_scanned} ({row['first_block']} - {row['last_block']})")
print(f"Blocks with arbitrage: {row['unique_blocks']}")
print(f"Hit rate: {row['unique_blocks'] / blocks_scanned:.1%} of blocks contain arbitrage")

print()
print()

# 8. Competition intensity
print("⚔️  COMPETITION INTENSITY")
print("=" * 60)

cursor.execute('''
    SELECT
        block_number,
        COUNT(*) as tx_count,
        COUNT(DISTINCT from_address) as unique_traders
    FROM transactions
    GROUP BY block_number
    HAVING tx_count > 5
    ORDER BY tx_count DESC
    LIMIT 5
''')

print("\nMost competitive blocks (>5 transactions):")
print()
for row in cursor.fetchall():
    print(f"Block {row['block_number']}")
    print(f"  Transactions: {row['tx_count']}")
    print(f"  Unique traders: {row['unique_traders']}")
    print(f"  Avg tx per trader: {row['tx_count'] / row['unique_traders']:.1f}")
    print()

print()

# 9. Success patterns
print("✅ SUCCESS PATTERNS")
print("=" * 60)

cursor.execute('''
    SELECT
        a.address,
        a.total_trades,
        a.total_profit_usd,
        a.avg_gas_price_gwei,
        a.strategies_used,
        COUNT(DISTINCT t.block_number) as blocks_active
    FROM arbitrageurs a
    JOIN transactions t ON a.address = t.from_address
    WHERE a.total_trades >= 20
    GROUP BY a.address
    ORDER BY a.total_profit_usd DESC
    LIMIT 5
''')

print("\nTop 5 successful arbitrageurs (≥20 trades):")
print()
for i, row in enumerate(row, 1):
    addr = row['address']
    print(f"{i}. {addr[:10]}...{addr[-8:]}")
    print(f"   Total Trades: {row['total_trades']}")
    print(f"   Total Profit: ${row['total_profit_usd']:,.0f}")
    print(f"   Profit per Trade: ${row['total_profit_usd'] / row['total_trades']:,.0f}")
    print(f"   Avg Gas: {row['avg_gas_price_gwei']:.2f} Gwei")
    print(f"   Strategies: {row['strategies_used']}")
    print(f"   Active in {row['blocks_active']} blocks")
    print()

print()
print("=" * 60)
print("📊 ANALYSIS COMPLETE")
print("=" * 60)

conn.close()
