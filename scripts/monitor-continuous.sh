#!/bin/bash

# Continuous BSC Imbalance Monitoring
# Scans every 10 seconds and alerts on opportunities

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║        BSC Imbalance Engine - Continuous Monitoring         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 Monitoring PancakeSwap V2 pools for arbitrage opportunities"
echo "🔄 Scan interval: 10 seconds"
echo "⏹️  Press Ctrl+C to stop"
echo ""
echo "──────────────────────────────────────────────────────────────────────"
echo ""

SCAN_COUNT=0
TOTAL_OPPORTUNITIES=0

while true; do
    SCAN_COUNT=$((SCAN_COUNT + 1))
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

    echo "[$TIMESTAMP] Scan #$SCAN_COUNT"
    echo ""

    # Run the scanner and capture output
    OUTPUT=$(python3 scripts/imbalance-hybrid-demo.py 2>&1)

    # Count opportunities detected
    OPPS=$(echo "$OUTPUT" | grep "OPPORTUNITIES DETECTED:" | grep -oP '\d+' || echo "0")

    if [ "$OPPS" -gt 0 ]; then
        TOTAL_OPPORTUNITIES=$((TOTAL_OPPORTUNITIES + OPPS))

        # Show detected opportunities
        echo "$OUTPUT" | grep -A 100 "OPPORTUNITIES DETECTED:"

        # Alert sound (if terminal supports it)
        echo -e "\a"

        echo ""
        echo "🔔 ALERT: $OPPS opportunities detected!"
    else
        echo "✅ All pools balanced (no opportunities above threshold)"
    fi

    echo ""
    echo "📊 Session Stats:"
    echo "   Total Scans: $SCAN_COUNT"
    echo "   Total Opportunities: $TOTAL_OPPORTUNITIES"
    echo ""
    echo "──────────────────────────────────────────────────────────────────────"
    echo ""

    # Wait 10 seconds
    sleep 10
done
