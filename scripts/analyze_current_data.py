#!/usr/bin/env python3
"""Analyze current database data"""

import sqlite3
from datetime import datetime

db_path = 'arbitrage-data/arbitrage.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("╔══════════════════════════════════════════════════════════════╗")
print("║          CURRENT ARBITRAGE ANALYSIS                         ║")
print("╚══════════════════════════════════════════════════════════════╝")
print()

# Overall stats
cursor = conn.cursor()

print("📊 OVERALL STATISTICS")
print("=" * 60)

cursor.execute('SELECT COUNT(*) as count FROM opportunities')
total_opps = cursor.fetchone()['count']

cursor.execute('SELECT COUNT(*) as count FROM transactions')
total_txs = cursor.fetchone()['count']

cursor.execute('SELECT COUNT(*) as count FROM arbitrageurs')
total_arbs = cursor.fetchone()['count']

cursor.execute('SELECT SUM(estimated_profit_usd) as total FROM opportunities')
total_value = cursor.fetchone()['total'] or 0

print(f"Total Opportunities Detected: {total_opps}")
print(f"Total Transactions Found: {total_txs}")
print(f"Unique Arbitrageurs: {total_arbs}")
print(f"Total Value Detected: ${total_value:,.2f}")
print()

# Opportunities by size
print("💰 OPPORTUNITIES BY SIZE")
print("=" * 60)

cursor.execute('''
    SELECT
        CASE
            WHEN estimated_profit_usd < 1000 THEN 'Micro (<$1K)'
            WHEN estimated_profit_usd < 10000 THEN 'Small ($1K-$10K)'
            WHEN estimated_profit_usd < 100000 THEN '🎯 TARGET ($10K-$100K)'
            WHEN estimated_profit_usd < 1000000 THEN 'Large ($100K-$1M)'
            ELSE 'Whale (>$1M)'
        END as size_category,
        COUNT(*) as count,
        AVG(estimated_profit_usd) as avg_profit,
        MIN(estimated_profit_usd) as min_profit,
        MAX(estimated_profit_usd) as max_profit,
        SUM(estimated_profit_usd) as total_value
    FROM opportunities
    GROUP BY size_category
    ORDER BY avg_profit
''')

for row in cursor.fetchall():
    print(f"\n{row['size_category']}")
    print(f"  Count: {row['count']}")
    print(f"  Avg Profit: ${row['avg_profit']:,.0f}")
    print(f"  Range: ${row['min_profit']:,.0f} - ${row['max_profit']:,.0f}")
    print(f"  Total Value: ${row['total_value']:,.0f}")

print()
print()

# Pool breakdown
print("🏊 POOL STATISTICS")
print("=" * 60)

cursor.execute('''
    SELECT
        pool_name,
        COUNT(*) as total_opportunities,
        AVG(imbalance_pct) as avg_imbalance,
        AVG(estimated_profit_usd) as avg_profit,
        MIN(estimated_profit_usd) as min_profit,
        MAX(estimated_profit_usd) as max_profit
    FROM opportunities
    GROUP BY pool_name
    ORDER BY total_opportunities DESC
''')

for row in cursor.fetchall():
    print(f"\n{row['pool_name']}")
    print(f"  Opportunities: {row['total_opportunities']}")
    print(f"  Avg Imbalance: {row['avg_imbalance']:.2f}%")
    print(f"  Avg Profit: ${row['avg_profit']:,.0f}")
    print(f"  Range: ${row['min_profit']:,.0f} - ${row['max_profit']:,.0f}")

print()
print()

# Top arbitrageurs
print("👤 TOP ARBITRAGEURS (by profit)")
print("=" * 60)

cursor.execute('''
    SELECT
        address,
        total_trades,
        total_profit_usd,
        avg_profit_usd,
        avg_gas_price_gwei,
        win_rate
    FROM arbitrageurs
    ORDER BY total_profit_usd DESC
    LIMIT 10
''')

for i, row in enumerate(cursor.fetchall(), 1):
    addr = row['address']
    short_addr = f"{addr[:10]}...{addr[-8:]}"
    print(f"\n{i}. {short_addr}")
    print(f"   Trades: {row['total_trades']}")
    print(f"   Total Profit: ${row['total_profit_usd']:,.0f}")
    print(f"   Avg Profit: ${row['avg_profit_usd']:,.0f}")
    print(f"   Avg Gas: {row['avg_gas_price_gwei']:.2f} Gwei")
    print(f"   Win Rate: {(row['win_rate'] * 100):.1f}%")

print()
print()

# Recent transactions
print("💰 RECENT ARBITRAGE TRANSACTIONS")
print("=" * 60)

cursor.execute('''
    SELECT
        timestamp,
        from_address,
        swap_count,
        gas_price_gwei,
        estimated_profit_usd,
        strategy_type
    FROM transactions
    ORDER BY timestamp DESC
    LIMIT 10
''')

for row in cursor.fetchall():
    addr = row['from_address']
    short_addr = f"{addr[:10]}...{addr[-8:]}"
    print(f"\n{row['timestamp']}")
    print(f"  From: {short_addr}")
    print(f"  Swaps: {row['swap_count']}")
    print(f"  Gas: {row['gas_price_gwei']:.2f} Gwei")
    print(f"  Est. Profit: ${row['estimated_profit_usd']:,.0f}")
    print(f"  Strategy: {row['strategy_type']}")

print()
print()

# Gas price analysis
print("⛽ GAS PRICE ANALYSIS")
print("=" * 60)

cursor.execute('''
    SELECT
        CASE
            WHEN avg_gas_price_gwei < 1 THEN 'Ultra-low (<1 Gwei)'
            WHEN avg_gas_price_gwei < 5 THEN 'Low (1-5 Gwei)'
            WHEN avg_gas_price_gwei < 10 THEN 'Medium (5-10 Gwei)'
            WHEN avg_gas_price_gwei < 50 THEN 'High (10-50 Gwei)'
            ELSE 'Very High (>50 Gwei)'
        END as gas_category,
        COUNT(*) as arbitrageur_count,
        AVG(total_profit_usd) as avg_total_profit,
        AVG(win_rate * 100) as avg_win_rate
    FROM arbitrageurs
    WHERE total_trades >= 1
    GROUP BY gas_category
    ORDER BY avg_gas_price_gwei
''')

for row in cursor.fetchall():
    print(f"\n{row['gas_category']}")
    print(f"  Arbitrageurs: {row['arbitrageur_count']}")
    print(f"  Avg Total Profit: ${row['avg_total_profit']:,.0f}")
    print(f"  Avg Win Rate: {row['avg_win_rate']:.1f}%")

print()
print()

# Strategy analysis
print("🎯 STRATEGY ANALYSIS")
print("=" * 60)

cursor.execute('''
    SELECT
        strategy_type,
        COUNT(*) as count,
        AVG(estimated_profit_usd) as avg_profit
    FROM transactions
    WHERE strategy_type IS NOT NULL
    GROUP BY strategy_type
    ORDER BY count DESC
''')

for row in cursor.fetchall():
    print(f"\n{row['strategy_type']}")
    print(f"  Transactions: {row['count']}")
    print(f"  Avg Profit: ${row['avg_profit']:,.0f}")

print()
print()

# Time analysis
print("⏰ ACTIVITY TIMELINE")
print("=" * 60)

cursor.execute('''
    SELECT
        MIN(timestamp) as first_record,
        MAX(timestamp) as last_record
    FROM opportunities
''')
row = cursor.fetchone()
print(f"First Record: {row['first_record']}")
print(f"Last Record: {row['last_record']}")

if row['first_record'] and row['last_record']:
    first = datetime.fromisoformat(row['first_record'])
    last = datetime.fromisoformat(row['last_record'])
    duration_minutes = (last - first).total_seconds() / 60

    print(f"Duration: {duration_minutes:.1f} minutes")

    if duration_minutes > 0:
        opps_per_hour = (total_opps / duration_minutes) * 60
        txs_per_hour = (total_txs / duration_minutes) * 60
        print(f"Opportunities per hour: {opps_per_hour:.1f}")
        print(f"Transactions per hour: {txs_per_hour:.1f}")

print()
print("=" * 60)
print("💡 View full details in dashboard: python3 scripts/dashboard.py")
print("=" * 60)

conn.close()
