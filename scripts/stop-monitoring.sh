#!/bin/bash

echo "⏹️  Stopping Arbitrage Monitoring System..."

# Stop tracker
if [ -f "arbitrage-data/tracker.pid" ]; then
    PID=$(cat arbitrage-data/tracker.pid)
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        echo "   ✅ Tracker stopped (PID: $PID)"
    else
        echo "   ⚠️  Tracker not running"
    fi
    rm arbitrage-data/tracker.pid
else
    echo "   ⚠️  No tracker PID file found"
fi

echo ""
echo "📊 View collected data:"
echo "   python3 scripts/dashboard.py"
echo ""
