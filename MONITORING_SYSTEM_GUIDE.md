# Comprehensive Arbitrage Monitoring System

## 🎯 Overview

This is a complete arbitrage monitoring and analysis system for BSC (Binance Smart Chain). It tracks pool imbalances, monitors actual arbitrage transactions, profiles competing arbitrageurs, and provides a web dashboard for in-depth analysis.

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Enhanced Tracker                            │
│  • Scans pool imbalances every 60 seconds                   │
│  • Monitors new blocks for arbitrage transactions           │
│  • Analyzes transaction details                             │
│  • Tracks timing and competition                            │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                SQLite Database                               │
│  • opportunities: Pool imbalances detected                  │
│  • transactions: Actual arbitrage executions                │
│  • arbitrageurs: Wallet profiles                            │
│  • competition: Multiple attempts at same opportunity       │
│  • timing_analysis: Speed metrics                           │
│  • pool_stats: Aggregated pool statistics                   │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                 Web Dashboard (Flask)                        │
│  • Real-time statistics                                     │
│  • Opportunity browser with filters                         │
│  • Transaction analysis                                     │
│  • Arbitrageur profiles                                     │
│  • Pool statistics                                          │
└─────────────────────────────────────────────────────────────┘
```

## 📊 Database Schema

### opportunities
Tracks every pool imbalance detected by the system.

**Key Fields:**
- `timestamp`: When the opportunity was detected
- `pool_name` / `pool_address`: Which pool (e.g., "WBNB-USDT")
- `imbalance_pct`: How imbalanced the pool is (%)
- `estimated_profit_usd`: Estimated arbitrage profit
- `was_captured`: Whether someone captured this opportunity
- `captured_by`: Address that captured it
- `capture_delay_ms`: Time from detection to capture

### transactions
Records actual arbitrage transactions observed on-chain.

**Key Fields:**
- `tx_hash`: Transaction hash
- `from_address`: Arbitrageur wallet address
- `gas_price_gwei`: Gas price used
- `swap_count`: Number of swaps in transaction
- `estimated_profit_usd`: Estimated profit
- `strategy_type`: Type of arbitrage (2-hop, 3-hop, etc.)

### arbitrageurs
Profiles of wallets executing arbitrage.

**Key Fields:**
- `address`: Wallet address
- `total_trades` / `successful_trades` / `failed_trades`: Performance metrics
- `total_profit_usd`: Cumulative profit
- `avg_gas_price_gwei`: Average gas price strategy
- `win_rate`: Success percentage
- `strategies_used`: Types of arbitrage used

### competition
Tracks multiple attempts at the same opportunity.

**Key Fields:**
- `opportunity_id`: Link to opportunity
- `from_address`: Competing arbitrageur
- `gas_price_gwei`: Gas price bid
- `won`: Whether this attempt won

## 🚀 Quick Start

### 1. Start the Monitoring System

```bash
chmod +x scripts/start-monitoring.sh
./scripts/start-monitoring.sh
```

This will:
- Initialize the database (if needed)
- Start the enhanced tracker in background
- Begin collecting data

### 2. Launch the Dashboard

```bash
python3 scripts/dashboard.py
```

Then open http://localhost:5000 in your browser.

### 3. View Live Logs

```bash
tail -f arbitrage-data/tracker.log
```

### 4. Stop the System

```bash
chmod +x scripts/stop-monitoring.sh
./scripts/stop-monitoring.sh
```

## 📈 Dashboard Features

### Overview Statistics
- **Total Opportunities**: All imbalances detected
- **Small Opportunities (10K-100K)**: Your target range
- **Total Value Detected**: Sum of all opportunity values
- **Arbitrage Transactions**: Actual executions observed
- **Unique Arbitrageurs**: Number of competing wallets
- **Capture Rate**: % of opportunities that were captured

### Opportunities Tab
Browse and filter detected opportunities:
- **Filters**: Min/max profit range, time window
- **View**: Pool name, imbalance %, estimated profit, capture status
- **Analysis**: Which opportunities are getting captured vs. missed

### Transactions Tab
Analyze actual arbitrage executions:
- **Details**: From address, swap count, gas price, profit
- **Strategy**: Type of arbitrage (2-hop, 3-hop, etc.)
- **Timing**: When transactions occurred

### Arbitrageurs Tab
Study competing wallets:
- **Performance**: Total trades, win rate, total profit
- **Strategy**: Average gas price, preferred strategies
- **Activity**: First seen, last seen

### Pool Stats Tab
Aggregate statistics by pool:
- **Frequency**: How often opportunities appear
- **Profitability**: Average, min, max profits
- **Competition**: Capture rates per pool

## 🎯 Using the System to Win Opportunities

### Step 1: Identify Your Target Pools

Run the dashboard and check the **Pool Stats** tab. Look for:
- Pools with frequent opportunities (high count)
- Opportunities in your capital range ($10K-$100K)
- Lower capture rates (less competition)

**Example:**
```
WBNB-USDT: 45 opportunities, avg $15,817, 23% capture rate
WBNB-BUSD: 12 opportunities, avg $35,241, 67% capture rate
```

➡️ **WBNB-USDT is better** - more frequent, right size, less competition

### Step 2: Study Successful Arbitrageurs

In the **Arbitrageurs** tab, filter for wallets with:
- High win rates (>80%)
- Operating in your profit range
- Reasonable gas prices (not ultra-low like whales)

Click on an address to see:
- Their typical gas price strategy
- Which pools they target
- What strategies they use (2-hop, 3-hop, cross-DEX)

### Step 3: Analyze Timing

Look at the **Opportunities** tab and note:
- What time of day opportunities appear most
- How long they stay available before capture
- What gas prices winning transactions use

### Step 4: Develop Your Strategy

Based on the data:
1. **Target specific pools** (e.g., WBNB-USDT)
2. **Set appropriate gas prices** (e.g., 3-5 Gwei if competitors use 0.05-10 Gwei range)
3. **Focus on timing** (if opportunities last 5-10 seconds, you need fast execution)
4. **Choose strategy type** (2-hop vs 3-hop based on success rates)

### Step 5: Monitor Competition

Use the **Competition** feature to see:
- How many others attempted the same opportunity
- What gas prices they used
- Who won and why

This helps you understand:
- Do you need faster execution?
- Higher gas prices?
- Better MEV protection?

## 📊 Analysis Queries

The database supports direct SQL queries for advanced analysis:

### Find best times for opportunities
```sql
SELECT
    strftime('%H', timestamp) as hour,
    COUNT(*) as opportunity_count,
    AVG(estimated_profit_usd) as avg_profit
FROM opportunities
WHERE estimated_profit_usd BETWEEN 10000 AND 100000
GROUP BY hour
ORDER BY opportunity_count DESC;
```

### Analyze gas price strategies
```sql
SELECT
    ROUND(avg_gas_price_gwei, 1) as gas_price,
    COUNT(*) as trades,
    AVG(total_profit_usd) as avg_profit,
    AVG(win_rate * 100) as win_rate_pct
FROM arbitrageurs
WHERE total_trades >= 5
GROUP BY ROUND(avg_gas_price_gwei, 1)
ORDER BY win_rate_pct DESC;
```

### Find uncaptured opportunities in your range
```sql
SELECT
    pool_name,
    COUNT(*) as count,
    AVG(estimated_profit_usd) as avg_profit
FROM opportunities
WHERE was_captured = 0
    AND estimated_profit_usd BETWEEN 10000 AND 100000
GROUP BY pool_name
ORDER BY count DESC;
```

## 🔧 Customization

### Adjust Scan Interval

Edit `scripts/enhanced_tracker.py`:
```python
time.sleep(60)  # Change from 60 seconds to your preference
```

### Add More Pools

Edit `scripts/enhanced_tracker.py`:
```python
POOLS = {
    "WBNB-BUSD": "0x58F876857a02D6762E0101bb5C46A8c1ED44Dc16",
    "YOUR-POOL": "0xYOUR_POOL_ADDRESS",
    # Add more...
}
```

### Change Profit Range Filter

Edit `scripts/enhanced_tracker.py`:
```python
if imbalance > 5.0:  # Change threshold (currently 5%)
```

## 📁 File Structure

```
scripts/
├── db_manager.py              # Database manager class
├── database_schema.sql        # Database schema definition
├── enhanced_tracker.py        # Main tracker with analysis
├── dashboard.py               # Flask web dashboard
├── templates/
│   └── dashboard.html         # Dashboard UI
├── start-monitoring.sh        # Start system
└── stop-monitoring.sh         # Stop system

arbitrage-data/
├── arbitrage.db               # SQLite database
├── tracker.log                # Tracker logs
└── tracker.pid                # Tracker process ID
```

## 🎓 Learning from the Data

### Question: "Can I win $10K-$100K opportunities?"

**Answer from data:**
1. Check **Pool Stats** → How many opportunities in this range?
2. Check **Arbitrageurs** → What gas prices do winners use?
3. Check **Opportunities** → What's the capture rate?

If:
- Frequent opportunities (>10/hour)
- Low capture rate (<50%)
- Winners use moderate gas (3-10 Gwei)

➡️ **YES, you have a chance!**

### Question: "What pool should I focus on?"

**Answer from data:**
1. **Opportunities Tab** → Filter to your profit range
2. **Pool Stats** → Sort by opportunity count
3. Choose pool with:
   - High frequency
   - Your profit range
   - Lower capture rate

### Question: "How fast do I need to be?"

**Answer from data:**
1. Look at `capture_delay_ms` in opportunities table
2. If most captures are <1000ms, you need very fast execution
3. If captures are 5000-10000ms, you have more time

## 🚨 Important Notes

### Data Collection Period

- Let the system run for **6-24 hours** to collect meaningful data
- First hour: Limited data, patterns unclear
- After 12 hours: Good statistical significance
- After 24 hours: Comprehensive competitive landscape

### Limitations

1. **Profit estimates are approximate** - actual profit requires log parsing
2. **Not all arbitrage is detected** - only DEX router transactions
3. **Gas costs not included** - factor in gas when calculating real profit

### Privacy

- All data is local (SQLite database)
- No external reporting
- Your analysis stays on your machine

## 🆘 Troubleshooting

### Tracker Not Detecting Opportunities

1. Check logs: `tail -f arbitrage-data/tracker.log`
2. Verify RPC is working: Test EXTERNAL_RPC endpoint
3. Check pool addresses are correct

### Dashboard Shows No Data

1. Ensure tracker is running: `cat arbitrage-data/tracker.pid`
2. Check database has data: `python3 scripts/db_manager.py`
3. Wait for tracker to complete first scan cycle

### High Memory Usage

1. Reduce scan interval (less frequent scans)
2. Limit opportunity cache size
3. Purge old data from database periodically

## 📞 Support

For issues or questions:
1. Check tracker logs: `arbitrage-data/tracker.log`
2. Verify database: `sqlite3 arbitrage-data/arbitrage.db ".tables"`
3. Review this guide

## 🎯 Next Steps

After collecting 24 hours of data:
1. **Analyze patterns** using the dashboard
2. **Identify your niche** (specific pools, times, strategies)
3. **Develop execution bot** based on insights
4. **Start small** and iterate based on results

Remember: The goal is to **learn from the data** to understand if and how you can compete for small arbitrage opportunities!
