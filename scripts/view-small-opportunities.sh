#!/bin/bash

# View opportunities in the $10K-$100K range (accessible to small traders)

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║      SMALL TRADER OPPORTUNITIES ($10K-$100K Range)          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

if [ ! -f "arbitrage-data/opportunities.csv" ]; then
    echo "❌ No opportunities data yet. Let tracker run longer."
    exit 1
fi

echo "🎯 YOUR SIZE RANGE: $10,000 - $100,000 per opportunity"
echo ""
echo "These are perfect for:"
echo "  • Retail traders with $10K-$50K capital"
echo "  • Small DeFi funds"
echo "  • Individual arbitrage bots"
echo "  • Less whale competition"
echo ""
echo "─────────────────────────────────────────────────────────────"
echo ""

# Filter and display
python3 << 'PYEOF'
import csv
from datetime import datetime

with open('arbitrage-data/opportunities.csv', 'r') as f:
    reader = csv.DictReader(f)
    opportunities = list(reader)

# Filter for $10K-$100K range
small_opps = [
    opp for opp in opportunities
    if 10000 <= float(opp['profit_usd']) <= 100000
]

if not small_opps:
    print("ℹ️  No opportunities in $10K-$100K range yet")
    print("   Try running tracker for longer or check back later")
else:
    print(f"Found {len(small_opps)} opportunities in your range:")
    print()

    # Group by pool
    by_pool = {}
    for opp in small_opps:
        pool = opp['pool_name']
        if pool not in by_pool:
            by_pool[pool] = []
        by_pool[pool].append(opp)

    # Show by pool
    for pool, opps in sorted(by_pool.items(), key=lambda x: len(x[1]), reverse=True):
        count = len(opps)
        avg_profit = sum(float(o['profit_usd']) for o in opps) / count
        total_profit = sum(float(o['profit_usd']) for o in opps)
        avg_imbalance = sum(float(o['imbalance_pct']) for o in opps) / count

        print(f"📊 {pool}")
        print(f"   Opportunities: {count}")
        print(f"   Avg Profit: ${avg_profit:,.0f}")
        print(f"   Total Value: ${total_profit:,.0f}")
        print(f"   Avg Imbalance: {avg_imbalance:.1f}%")

        # Show most recent
        latest = opps[-1]
        print(f"   Latest: {latest['timestamp'][:19]} - ${float(latest['profit_usd']):,.0f}")
        print()

    # Summary stats
    total_value = sum(float(o['profit_usd']) for o in small_opps)
    avg_profit = total_value / len(small_opps)

    print("═════════════════════════════════════════════════════════════")
    print()
    print(f"📈 SUMMARY:")
    print(f"   Total Opportunities: {len(small_opps)}")
    print(f"   Average Profit: ${avg_profit:,.0f}")
    print(f"   Total Value Available: ${total_value:,.0f}")
    print()

    # Frequency
    if len(small_opps) > 1:
        first_time = datetime.fromisoformat(small_opps[0]['timestamp'])
        last_time = datetime.fromisoformat(small_opps[-1]['timestamp'])
        duration = (last_time - first_time).total_seconds() / 60

        if duration > 0:
            freq = len(small_opps) / (duration / 60)
            print(f"   Frequency: {freq:.1f} opportunities/hour")
            print(f"   Duration Tracked: {duration:.0f} minutes")
            print()

PYEOF

echo "─────────────────────────────────────────────────────────────"
echo ""
echo "💡 NEXT STEPS FOR SMALL TRADERS:"
echo ""
echo "1. CAPITAL REQUIREMENTS:"
echo "   • $10K-$50K is enough to capture these"
echo "   • Don't need millions like the whales"
echo ""
echo "2. FOCUS ON THESE POOLS:"
echo "   • WBNB-USDT (most frequent in this range)"
echo "   • WBNB-BUSD"
echo "   • Other stablecoin pairs"
echo ""
echo "3. STRATEGY:"
echo "   • Monitor these specific pools"
echo "   • Use moderate gas (3-5 Gwei, not 0.05 like whales)"
echo "   • Execute quickly but don't compete with whales"
echo "   • Target 0.5-1% profit margins"
echo ""
echo "4. COMPETITION:"
echo "   • Less competition than whale trades"
echo "   • More opportunities available"
echo "   • Better for learning and testing"
echo ""
echo "═════════════════════════════════════════════════════════════"
echo ""
