#!/bin/bash

# View tracked arbitrage data

DATA_DIR="./arbitrage-data"

if [ ! -d "$DATA_DIR" ]; then
    echo "❌ No data directory found. Start tracking first:"
    echo "   ./scripts/start-tracking.sh"
    exit 1
fi

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           Arbitrage Tracking Data - Summary Report          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Show session stats
if [ -f "$DATA_DIR/session.json" ]; then
    echo "📊 SESSION STATISTICS:"
    echo "─────────────────────────────────────────────────────────────"
    cat "$DATA_DIR/session.json" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f\"  Start Time: {data.get('start_time', 'N/A')}\"
      if 'start_time' in data else '')
print(f\"  Duration: {data.get('duration_seconds', 0) / 60:.1f} minutes\"
      if 'duration_seconds' in data else '')
print(f\"  Blocks Scanned: {data.get('blocks_scanned', 0):,}\")
print(f\"  Opportunities Found: {data.get('opportunities_logged', 0):,}\")
print(f\"  Arbitrage Detected: {data.get('arbitrage_detected', 0):,}\")
print(f\"  Unique Arbitrageurs: {data.get('unique_arbitrageurs', 0):,}\")
print(f\"  Total Est. Profit: \${data.get('total_estimated_profit', 0):,.0f}\")
"
    echo ""
fi

# Show top arbitrageurs
if [ -f "$DATA_DIR/arbitrageurs.csv" ]; then
    echo "🏆 TOP ARBITRAGEURS:"
    echo "─────────────────────────────────────────────────────────────"

    # Count total
    TOTAL=$(tail -n +2 "$DATA_DIR/arbitrageurs.csv" | wc -l)

    if [ "$TOTAL" -gt 0 ]; then
        echo "Total arbitrageurs tracked: $TOTAL"
        echo ""
        echo "Top 10 by profit:"
        echo ""

        tail -n +2 "$DATA_DIR/arbitrageurs.csv" | head -10 | \
        awk -F',' '{printf "  %2d. %s...%s\n      Trades: %s | Profit: %s BNB ($%s)\n      Strategies: %s\n\n",
                    NR, substr($1,1,10), substr($1,length($1)-5), $2, $3, $4, $5}'
    else
        echo "  No arbitrageurs detected yet"
    fi
    echo ""
fi

# Show recent opportunities
if [ -f "$DATA_DIR/opportunities.csv" ]; then
    echo "🎯 RECENT OPPORTUNITIES:"
    echo "─────────────────────────────────────────────────────────────"

    TOTAL_OPPS=$(tail -n +2 "$DATA_DIR/opportunities.csv" | wc -l)

    if [ "$TOTAL_OPPS" -gt 0 ]; then
        echo "Total opportunities logged: $TOTAL_OPPS"
        echo ""
        echo "Last 10:"
        echo ""

        tail -10 "$DATA_DIR/opportunities.csv" | \
        awk -F',' '{printf "  • %s - %s%% imbalance - $%s profit\n    %s\n",
                    $2, $4, $5, $1}'
    else
        echo "  No opportunities logged yet"
    fi
    echo ""
fi

# Show recent transactions
if [ -f "$DATA_DIR/transactions.csv" ]; then
    echo "💰 RECENT ARBITRAGE TRANSACTIONS:"
    echo "─────────────────────────────────────────────────────────────"

    TOTAL_TXS=$(tail -n +2 "$DATA_DIR/transactions.csv" | wc -l)

    if [ "$TOTAL_TXS" -gt 0 ]; then
        echo "Total transactions logged: $TOTAL_TXS"
        echo ""
        echo "Last 5:"
        echo ""

        tail -5 "$DATA_DIR/transactions.csv" | \
        awk -F',' '{printf "  • %s...%s - %s swaps - $%s profit\n    %s\n",
                    substr($3,1,10), substr($3,length($3)-5), $4, $7, $1}'
    else
        echo "  No transactions logged yet"
    fi
    echo ""
fi

echo "═════════════════════════════════════════════════════════════"
echo ""
echo "📁 Data Files:"
echo "   • Arbitrageurs: $DATA_DIR/arbitrageurs.csv"
echo "   • Opportunities: $DATA_DIR/opportunities.csv"
echo "   • Transactions: $DATA_DIR/transactions.csv"
echo "   • Full Log: $DATA_DIR/monitoring.log"
echo ""
echo "🔍 View in detail:"
echo "   cat $DATA_DIR/arbitrageurs.csv"
echo "   cat $DATA_DIR/opportunities.csv"
echo "   tail -f $DATA_DIR/monitoring.log"
echo ""
echo "📊 Open in spreadsheet:"
echo "   libreoffice $DATA_DIR/arbitrageurs.csv"
echo "   # Or import into Excel/Google Sheets"
echo ""
