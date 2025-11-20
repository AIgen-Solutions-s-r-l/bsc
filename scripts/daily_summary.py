#!/usr/bin/env python3
"""Generate daily summary report"""

import sqlite3
from datetime import datetime, timedelta

db_path = 'arbitrage-data/arbitrage.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("╔══════════════════════════════════════════════════════════════╗")
print("║              DAILY MONITORING SUMMARY                        ║")
print("╚══════════════════════════════════════════════════════════════╝")
print()

# Overall stats
cursor.execute('SELECT COUNT(*) as count FROM opportunities')
total_opps = cursor.fetchone()['count']

cursor.execute('SELECT COUNT(*) as count FROM transactions')
total_txs = cursor.fetchone()['count']

cursor.execute('SELECT COUNT(*) as count FROM arbitrageurs')
total_arbs = cursor.fetchone()['count']

cursor.execute('SELECT SUM(estimated_profit_usd) as total FROM opportunities')
total_value = cursor.fetchone()['total'] or 0

print(f"📊 CUMULATIVE STATISTICS")
print("=" * 60)
print(f"Total Opportunities: {total_opps:,}")
print(f"Total Transactions: {total_txs:,}")
print(f"Unique Arbitrageurs: {total_arbs:,}")
print(f"Total Value Detected: ${total_value:,.2f}")
print()

# Small opportunities check
cursor.execute('''
    SELECT
        COUNT(*) as count,
        AVG(estimated_profit_usd) as avg,
        MIN(estimated_profit_usd) as min,
        MAX(estimated_profit_usd) as max
    FROM opportunities
    WHERE estimated_profit_usd BETWEEN 10000 AND 100000
''')
row = cursor.fetchone()

print(f"🎯 SMALL OPPORTUNITIES ($10K-$100K)")
print("=" * 60)
if row['count'] > 0:
    print(f"✅ Found: {row['count']} opportunities")
    print(f"   Average: ${row['avg']:,.0f}")
    print(f"   Range: ${row['min']:,.0f} - ${row['max']:,.0f}")
else:
    print(f"❌ Still ZERO opportunities in target range")
print()

# Last 24 hours activity
cursor.execute('''
    SELECT
        MIN(timestamp) as first,
        MAX(timestamp) as last
    FROM opportunities
''')
row = cursor.fetchone()

if row['first'] and row['last']:
    first = datetime.fromisoformat(row['first'])
    last = datetime.fromisoformat(row['last'])
    duration_hours = (last - first).total_seconds() / 3600

    print(f"⏰ MONITORING DURATION")
    print("=" * 60)
    print(f"Started: {first.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Latest: {last.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration: {duration_hours:.1f} hours ({duration_hours/24:.1f} days)")
    print()

    # Activity rates
    if duration_hours > 0:
        opps_per_hour = total_opps / duration_hours
        txs_per_hour = total_txs / duration_hours

        print(f"📈 ACTIVITY RATES")
        print("=" * 60)
        print(f"Opportunities per hour: {opps_per_hour:.1f}")
        print(f"Transactions per hour: {txs_per_hour:,.1f}")
        print()

# Pool distribution
print(f"🏊 POOL BREAKDOWN")
print("=" * 60)
cursor.execute('''
    SELECT
        pool_name,
        COUNT(*) as count,
        AVG(estimated_profit_usd) as avg_profit
    FROM opportunities
    GROUP BY pool_name
    ORDER BY count DESC
''')

for row in cursor.fetchall():
    print(f"{row['pool_name']}: {row['count']} opps, avg ${row['avg_profit']:,.0f}")
print()

# Top performers today
print(f"🏆 TOP 10 ARBITRAGEURS (All Time)")
print("=" * 60)
cursor.execute('''
    SELECT
        address,
        total_trades,
        total_profit_usd,
        avg_gas_price_gwei
    FROM arbitrageurs
    ORDER BY total_profit_usd DESC
    LIMIT 10
''')

for i, row in enumerate(cursor.fetchall(), 1):
    addr = row['address']
    short = f"{addr[:10]}...{addr[-8:]}"
    print(f"{i:2d}. {short} - {row['total_trades']:4d} trades - ${row['total_profit_usd']:10,.0f} - {row['avg_gas_price_gwei']:.2f} Gwei")
print()

# Competition analysis
cursor.execute('''
    SELECT AVG(tx_count) as avg, MAX(tx_count) as max
    FROM (
        SELECT block_number, COUNT(*) as tx_count
        FROM transactions
        GROUP BY block_number
    )
''')
row = cursor.fetchone()

print(f"⚔️  COMPETITION LEVEL")
print("=" * 60)
print(f"Avg transactions per block: {row['avg']:.1f}")
print(f"Max transactions in one block: {row['max']}")

if row['avg'] >= 10:
    print(f"Status: ❌ EXTREME competition")
elif row['avg'] >= 5:
    print(f"Status: ⚠️  HIGH competition")
else:
    print(f"Status: ✅ MODERATE competition")
print()

# Gas price trends
cursor.execute('''
    SELECT
        AVG(avg_gas_price_gwei) as avg_gas,
        MIN(avg_gas_price_gwei) as min_gas,
        MAX(avg_gas_price_gwei) as max_gas
    FROM arbitrageurs
''')
row = cursor.fetchone()

print(f"⛽ GAS PRICE ANALYSIS")
print("=" * 60)
print(f"Average: {row['avg_gas']:.2f} Gwei")
print(f"Range: {row['min_gas']:.2f} - {row['max_gas']:.2f} Gwei")

if row['avg_gas'] < 1:
    print(f"Status: ❌ Ultra-low (whale territory)")
elif row['avg_gas'] < 5:
    print(f"Status: ⚠️  Low (professional bots)")
else:
    print(f"Status: ✅ Accessible for small traders")
print()

# Decision helper
print("=" * 60)
print("💡 DECISION HELPER")
print("=" * 60)
print()

score = 0
if row['count'] == 0:
    score += 3
    print("❌ No small opportunities detected")
else:
    print(f"✅ {row['count']} small opportunities found")

if row['avg_gas'] < 1:
    score += 2
    print("❌ Gas prices in whale territory")
else:
    print("✅ Gas prices accessible")

if row['avg'] >= 10:
    score += 2
    print("❌ Extreme competition (>10 txs/block)")
else:
    print("✅ Competition manageable")

print()
if score >= 5:
    print("🚨 RECOMMENDATION: Consider switching chain")
    print("   • BSC appears too competitive for small traders")
    print("   • Try Polygon, Arbitrum, Base, or other L2s")
elif score >= 3:
    print("⚠️  RECOMMENDATION: Continue monitoring")
    print("   • Some challenges but potentially viable")
    print("   • Collect more data before deciding")
else:
    print("✅ RECOMMENDATION: Develop execution strategy")
    print("   • Opportunities exist in your range")
    print("   • Competition is manageable")

print()
print("=" * 60)
print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

conn.close()
