-- Comprehensive Arbitrage Monitoring Database Schema

-- Opportunities detected by our system
CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    pool_name TEXT NOT NULL,
    pool_address TEXT NOT NULL,
    token0_address TEXT,
    token1_address TEXT,
    reserve0 REAL,
    reserve1 REAL,
    imbalance_pct REAL NOT NULL,
    estimated_profit_usd REAL NOT NULL,
    estimated_profit_bnb REAL,
    block_number INTEGER,
    was_captured BOOLEAN DEFAULT 0,
    captured_by TEXT,
    capture_delay_ms INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Actual arbitrage transactions we observe
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tx_hash TEXT UNIQUE NOT NULL,
    block_number INTEGER NOT NULL,
    timestamp DATETIME NOT NULL,
    from_address TEXT NOT NULL,
    to_address TEXT,
    value_bnb REAL,
    gas_price_gwei REAL,
    gas_used INTEGER,
    gas_cost_bnb REAL,
    swap_count INTEGER,
    pools_involved TEXT,
    tokens_involved TEXT,
    estimated_profit_bnb REAL,
    estimated_profit_usd REAL,
    strategy_type TEXT,
    success BOOLEAN,
    opportunity_id INTEGER,
    execution_time_ms INTEGER,
    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id)
);

-- Arbitrageur wallet tracking
CREATE TABLE IF NOT EXISTS arbitrageurs (
    address TEXT PRIMARY KEY,
    first_seen DATETIME NOT NULL,
    last_seen DATETIME NOT NULL,
    total_trades INTEGER DEFAULT 0,
    successful_trades INTEGER DEFAULT 0,
    failed_trades INTEGER DEFAULT 0,
    total_profit_bnb REAL DEFAULT 0,
    total_profit_usd REAL DEFAULT 0,
    avg_profit_usd REAL,
    avg_gas_price_gwei REAL,
    strategies_used TEXT,
    capital_level TEXT,
    win_rate REAL,
    avg_execution_time_ms INTEGER
);

-- Competition tracking - multiple attempts at same opportunity
CREATE TABLE IF NOT EXISTS competition (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL,
    tx_hash TEXT NOT NULL,
    from_address TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    time_offset_ms INTEGER,
    gas_price_gwei REAL,
    won BOOLEAN,
    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id)
);

-- Timing analysis - how fast opportunities get captured
CREATE TABLE IF NOT EXISTS timing_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL,
    detection_time DATETIME NOT NULL,
    first_attempt_time DATETIME,
    capture_time DATETIME,
    detection_to_attempt_ms INTEGER,
    detection_to_capture_ms INTEGER,
    competitors_count INTEGER,
    winner_address TEXT,
    winner_gas_gwei REAL,
    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id)
);

-- Pool statistics
CREATE TABLE IF NOT EXISTS pool_stats (
    pool_address TEXT PRIMARY KEY,
    pool_name TEXT,
    total_opportunities INTEGER DEFAULT 0,
    total_captured INTEGER DEFAULT 0,
    avg_imbalance_pct REAL,
    avg_profit_usd REAL,
    min_profit_usd REAL,
    max_profit_usd REAL,
    last_opportunity DATETIME,
    opportunities_per_hour REAL
);

-- Create indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_opportunities_timestamp ON opportunities(timestamp);
CREATE INDEX IF NOT EXISTS idx_opportunities_pool ON opportunities(pool_address);
CREATE INDEX IF NOT EXISTS idx_opportunities_captured ON opportunities(was_captured);
CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_transactions_from ON transactions(from_address);
CREATE INDEX IF NOT EXISTS idx_transactions_block ON transactions(block_number);
CREATE INDEX IF NOT EXISTS idx_competition_opportunity ON competition(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_timing_opportunity ON timing_analysis(opportunity_id);
