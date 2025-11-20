#!/usr/bin/env python3
"""Final comprehensive analysis with insights"""

import sqlite3

db_path = 'arbitrage-data/arbitrage.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("╔══════════════════════════════════════════════════════════════╗")
print("║        COMPREHENSIVE ANALYSIS & INSIGHTS                     ║")
print("╚══════════════════════════════════════════════════════════════╝")
print()

print("📊 WHAT THE DATA TELLS US")
print("=" * 60)
print()

# Get basic stats
cursor.execute('SELECT COUNT(*) as count FROM opportunities')
total_opps = cursor.fetchone()['count']

cursor.execute('SELECT COUNT(*) as count FROM transactions')
total_txs = cursor.fetchone()['count']

cursor.execute('SELECT COUNT(*) as count FROM arbitrageurs')
total_arbs = cursor.fetchone()['count']

print(f"Data collected: {total_opps} opportunities, {total_txs} transactions, {total_arbs} arbitrageurs")
print()

# 1. Pool Health Check
print("1️⃣  POOL HEALTH ANALYSIS")
print("-" * 60)

cursor.execute('''
    SELECT
        pool_name,
        AVG(imbalance_pct) as avg_imbalance,
        AVG(reserve0) as avg_r0,
        AVG(reserve1) as avg_r1
    FROM opportunities
    GROUP BY pool_name
''')

print()
for row in cursor.fetchall():
    ratio = row['avg_r0'] / row['avg_r1'] if row['avg_r1'] > 0 else 0
    print(f"Pool: {row['pool_name']}")
    print(f"  Avg Imbalance: {row['avg_imbalance']:.1f}%")
    print(f"  Reserve Ratio: {ratio:.1f}:1")

    if row['avg_imbalance'] > 1000:
        print(f"  ⚠️  SEVERELY IMBALANCED - This is NOT a healthy trading pool")
    elif row['avg_imbalance'] > 100:
        print(f"  ⚠️  HIGHLY IMBALANCED - Low liquidity or abandoned pool")
    elif row['avg_imbalance'] > 20:
        print(f"  ⚠️  MODERATELY IMBALANCED - Opportunity exists but risky")
    else:
        print(f"  ✅ HEALTHY - Normal market conditions")
    print()

print()

# 2. Profit Estimate Reliability
print("2️⃣  PROFIT ESTIMATE RELIABILITY")
print("-" * 60)

cursor.execute('''
    SELECT
        COUNT(DISTINCT estimated_profit_usd) as unique_values,
        COUNT(*) as total_txs
    FROM transactions
''')
row = cursor.fetchone()

diversity = (row['unique_values'] / row['total_txs']) * 100

print(f"\nProfit value diversity: {diversity:.2f}%")
print(f"  ({row['unique_values']} unique values across {row['total_txs']} transactions)")
print()

if diversity < 1:
    print("❌ CRITICAL: Profit estimates are VERY rough approximations")
    print("   • Currently using: profit = swap_count × $1000")
    print("   • Real profits require parsing transaction logs")
    print("   • These numbers are for COMPARISON only, not accuracy")
elif diversity < 10:
    print("⚠️  WARNING: Profit estimates are rough")
    print("   • Limited precision in calculations")
else:
    print("✅ Good diversity in profit estimates")

print()
print()

# 3. Competition Analysis
print("3️⃣  COMPETITION LANDSCAPE")
print("-" * 60)

cursor.execute('''
    SELECT
        CASE
            WHEN total_trades = 1 THEN 'One-hit wonders'
            WHEN total_trades <= 10 THEN 'Occasional traders'
            WHEN total_trades <= 50 THEN 'Active traders'
            ELSE 'Power traders'
        END as trader_type,
        COUNT(*) as count,
        AVG(total_trades) as avg_trades,
        AVG(avg_gas_price_gwei) as avg_gas
    FROM arbitrageurs
    GROUP BY trader_type
    ORDER BY MIN(total_trades)
''')

print()
total_arbs_check = 0
for row in cursor.fetchall():
    total_arbs_check += row['count']
    pct = (row['count'] / total_arbs) * 100
    print(f"{row['trader_type']}")
    print(f"  Count: {row['count']} ({pct:.1f}%)")
    print(f"  Avg Trades: {row['avg_trades']:.1f}")
    print(f"  Avg Gas: {row['avg_gas']:.2f} Gwei")
    print()

print()

# 4. Block Competition
cursor.execute('''
    SELECT
        AVG(tx_count) as avg_txs_per_block,
        MAX(tx_count) as max_txs_per_block,
        SUM(CASE WHEN tx_count >= 10 THEN 1 ELSE 0 END) as highly_competitive_blocks,
        COUNT(*) as total_blocks
    FROM (
        SELECT block_number, COUNT(*) as tx_count
        FROM transactions
        GROUP BY block_number
    )
''')
row = cursor.fetchone()

print("Block-level competition:")
print(f"  Avg transactions per block: {row['avg_txs_per_block']:.1f}")
print(f"  Max transactions in one block: {row['max_txs_per_block']}")
print(f"  Highly competitive blocks (≥10 txs): {row['highly_competitive_blocks']}/{row['total_blocks']}")

if row['avg_txs_per_block'] > 5:
    print("\n  ⚠️  EXTREME COMPETITION - Most blocks have multiple arbitrage attempts")
else:
    print("\n  ✅ Moderate competition")

print()
print()

# 5. Gas Price Reality Check
print("4️⃣  GAS PRICE REALITY CHECK")
print("-" * 60)

cursor.execute('''
    SELECT
        AVG(avg_gas_price_gwei) as avg_gas,
        MIN(avg_gas_price_gwei) as min_gas,
        MAX(avg_gas_price_gwei) as max_gas
    FROM arbitrageurs
''')
row = cursor.fetchone()

print(f"\nGas price statistics:")
print(f"  Average: {row['avg_gas']:.2f} Gwei")
print(f"  Range: {row['min_gas']:.2f} - {row['max_gas']:.2f} Gwei")
print()

if row['avg_gas'] < 1:
    print("❌ ULTRA-COMPETITIVE: Average gas is <1 Gwei")
    print("   • This is institutional/whale territory")
    print("   • Small traders cannot compete at these gas prices")
    print("   • Suggests MEV bots with special infrastructure")
elif row['avg_gas'] < 5:
    print("⚠️  VERY COMPETITIVE: Average gas is <5 Gwei")
    print("   • Professional arbitrage bots")
    print("   • Difficult for small traders to compete")
else:
    print("✅ ACCESSIBLE: Gas prices are reasonable for small traders")

print()
print()

# 6. The Small Opportunity Question
print("5️⃣  THE $10K-$100K OPPORTUNITY QUESTION")
print("-" * 60)

cursor.execute('''
    SELECT
        COUNT(*) as count,
        AVG(estimated_profit_usd) as avg_profit
    FROM opportunities
    WHERE estimated_profit_usd BETWEEN 10000 AND 100000
''')
row = cursor.fetchone()

print(f"\nOpportunities in target range ($10K-$100K): {row['count']}")

if row['count'] == 0:
    print()
    print("❌ ZERO opportunities detected in your target range")
    print()
    print("Possible reasons:")
    print("  1. Pool imbalances are TOO LARGE (whale-sized only)")
    print("  2. Small opportunities get captured TOO FAST (<60 sec scan)")
    print("  3. Profit estimates are ROUGH (actual might be different)")
    print("  4. These specific pools don't have small opportunities")
    print()
    print("What this means:")
    print("  • The pools we're monitoring are dominated by whales")
    print("  • May need to monitor different pools (higher volume DEXes)")
    print("  • May need faster scanning (<60 second intervals)")
    print("  • May need to target different chains (less competitive)")
else:
    print(f"✅ Found {row['count']} opportunities with avg ${row['avg_profit']:,.0f}")

print()
print()

# 7. Final Verdict
print("6️⃣  VERDICT FOR SMALL TRADERS")
print("-" * 60)
print()

# Calculate competitiveness score
score = 0
reasons = []

# Check gas prices
if row['avg_gas'] < 1:
    score += 3
    reasons.append("Ultra-low gas prices (whale territory)")

# Check competition
cursor.execute('SELECT AVG(tx_count) as avg FROM (SELECT COUNT(*) as tx_count FROM transactions GROUP BY block_number)')
avg_tx_per_block = cursor.fetchone()['avg']
if avg_tx_per_block > 10:
    score += 3
    reasons.append("Extreme competition (many txs per block)")
elif avg_tx_per_block > 5:
    score += 2
    reasons.append("High competition")

# Check small opportunities
if row['count'] == 0:
    score += 3
    reasons.append("Zero small opportunities detected")

# Check pool health
cursor.execute('SELECT AVG(imbalance_pct) as avg FROM opportunities')
avg_imbalance = cursor.fetchone()['avg']
if avg_imbalance > 1000:
    score += 2
    reasons.append("Abnormal pool states (very high imbalances)")

print(f"Difficulty Score: {score}/11")
print()

if score >= 8:
    verdict = "❌ EXTREMELY DIFFICULT"
    advice = """
    Based on the data, competing for arbitrage on these BSC pools appears
    EXTREMELY DIFFICULT for small traders:

    • Whale-dominated market (ultra-low gas prices)
    • Extreme competition (high transaction density)
    • No small opportunities in your target range
    • Abnormal pool states suggest low liquidity/abandoned pools

    RECOMMENDATIONS:
    1. Monitor DIFFERENT pools (high-volume DEX pairs)
    2. Consider DIFFERENT strategies (liquidations, flash loans)
    3. Try DIFFERENT chains (Polygon, Arbitrum, etc.)
    4. Increase capital range if possible ($100K-$500K)
    5. Focus on learning from whale strategies first
    """
elif score >= 5:
    verdict = "⚠️  DIFFICULT BUT POSSIBLE"
    advice = """
    Competing for arbitrage is challenging but not impossible:

    • High competition but not insurmountable
    • May need faster execution and better gas strategy
    • Continue monitoring for 24 hours to find patterns

    RECOMMENDATIONS:
    1. Let tracker run for 24 hours
    2. Analyze timing patterns (when is competition lower?)
    3. Study successful traders in detail
    4. Consider niche strategies (specific pools/times)
    """
else:
    verdict = "✅ FEASIBLE"
    advice = """
    The data suggests small trader arbitrage is feasible:

    • Competition exists but is manageable
    • Opportunities in your size range detected
    • Reasonable gas prices

    RECOMMENDATIONS:
    1. Continue data collection
    2. Develop execution bot
    3. Start with small capital to test
    """

print(verdict)
print()
print("Key factors:")
for i, reason in enumerate(reasons, 1):
    print(f"  {i}. {reason}")

print()
print(advice)

print()
print("=" * 60)
print("📈 NEXT STEPS")
print("=" * 60)
print()
print("1. Let tracker run for 24 HOURS to get comprehensive data")
print("2. Launch DASHBOARD to explore specific arbitrageurs:")
print("   python3 scripts/dashboard.py")
print("3. Study the TOP PERFORMERS to learn their strategies")
print("4. Re-evaluate after 24 hours of data collection")
print()

conn.close()
