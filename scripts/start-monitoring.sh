#!/bin/bash

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     COMPREHENSIVE ARBITRAGE MONITORING SYSTEM                ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check if database exists
if [ ! -f "arbitrage-data/arbitrage.db" ]; then
    echo "📊 Initializing database..."
    python3 scripts/db_manager.py
    echo ""
fi

# Stop old tracker if running
if [ -f "arbitrage-data/tracker.pid" ]; then
    OLD_PID=$(cat arbitrage-data/tracker.pid)
    if kill -0 $OLD_PID 2>/dev/null; then
        echo "⏹️  Stopping old tracker (PID: $OLD_PID)..."
        kill $OLD_PID
        sleep 2
    fi
    rm arbitrage-data/tracker.pid
fi

# Start enhanced tracker in background
echo "🚀 Starting Enhanced Arbitrage Tracker..."
nohup python3 scripts/enhanced_tracker.py > arbitrage-data/tracker.log 2>&1 &
TRACKER_PID=$!
echo $TRACKER_PID > arbitrage-data/tracker.pid
echo "   ✅ Tracker running (PID: $TRACKER_PID)"
echo "   📝 Logs: arbitrage-data/tracker.log"
echo ""

echo "💾 Database: arbitrage-data/arbitrage.db"
echo ""

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    NEXT STEPS                                ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "1. VIEW DASHBOARD:"
echo "   python3 scripts/dashboard.py"
echo "   Then open: http://localhost:5000"
echo ""
echo "2. VIEW TRACKER LOGS:"
echo "   tail -f arbitrage-data/tracker.log"
echo ""
echo "3. STOP TRACKER:"
echo "   ./scripts/stop-monitoring.sh"
echo ""
echo "🎯 The tracker is now scanning for arbitrage opportunities"
echo "   and logging everything to the database!"
echo ""
