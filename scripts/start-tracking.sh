#!/bin/bash

# Start persistent arbitrage tracking in background

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Starting Persistent Arbitrage Tracking System           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Create data directory
mkdir -p ./arbitrage-data

# Check if already running
if pgrep -f "arbitrage-tracker-persistent.py" > /dev/null; then
    echo "⚠️  Tracker is already running!"
    echo ""
    echo "PID: $(pgrep -f 'arbitrage-tracker-persistent.py')"
    echo ""
    echo "Options:"
    echo "  • View live: tail -f arbitrage-data/monitoring.log"
    echo "  • Stop: ./scripts/stop-tracking.sh"
    echo "  • View data: ./scripts/view-tracked-data.sh"
    exit 1
fi

# Start in background
echo "🚀 Starting tracker in background..."
nohup python3 scripts/arbitrage-tracker-persistent.py > arbitrage-data/nohup.log 2>&1 &
TRACKER_PID=$!

sleep 2

# Check if started successfully
if ps -p $TRACKER_PID > /dev/null; then
    echo "✅ Tracker started successfully!"
    echo ""
    echo "PID: $TRACKER_PID"
    echo "Data directory: ./arbitrage-data/"
    echo ""
    echo "📊 Tracking:"
    echo "   • Arbitrage opportunities (saved to CSV)"
    echo "   • Arbitrageur wallet addresses"
    echo "   • Transaction details"
    echo "   • Profit estimates"
    echo ""
    echo "📁 Output files:"
    echo "   • arbitrage-data/arbitrageurs.csv"
    echo "   • arbitrage-data/opportunities.csv"
    echo "   • arbitrage-data/transactions.csv"
    echo "   • arbitrage-data/monitoring.log"
    echo ""
    echo "🔍 Monitor progress:"
    echo "   tail -f arbitrage-data/monitoring.log"
    echo ""
    echo "📊 View collected data:"
    echo "   ./scripts/view-tracked-data.sh"
    echo ""
    echo "🛑 Stop tracking:"
    echo "   ./scripts/stop-tracking.sh"
    echo ""
    echo "✨ Tracker is now running in background!"
else
    echo "❌ Failed to start tracker"
    echo "Check arbitrage-data/nohup.log for errors"
    exit 1
fi
