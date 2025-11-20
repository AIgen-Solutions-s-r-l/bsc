#!/bin/bash

# Stop persistent arbitrage tracking

echo "🛑 Stopping arbitrage tracker..."

PID=$(pgrep -f "arbitrage-tracker-persistent.py")

if [ -z "$PID" ]; then
    echo "ℹ️  No tracker running"
    exit 0
fi

kill $PID

sleep 2

if pgrep -f "arbitrage-tracker-persistent.py" > /dev/null; then
    echo "⚠️  Process still running, force killing..."
    kill -9 $PID
    sleep 1
fi

if ! pgrep -f "arbitrage-tracker-persistent.py" > /dev/null; then
    echo "✅ Tracker stopped successfully"
    echo ""
    echo "📁 Data saved in: ./arbitrage-data/"
    echo ""
    echo "View collected data:"
    echo "  ./scripts/view-tracked-data.sh"
else
    echo "❌ Failed to stop tracker"
    exit 1
fi
