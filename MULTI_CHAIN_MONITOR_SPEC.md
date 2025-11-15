# Multi-Chain Arbitrage Monitor Specification

## Overview

A production-ready arbitrage monitoring system that tracks real multi-hop arbitrage opportunities and transactions across multiple EVM chains (BSC and Polygon), designed for small traders ($10K-$100K capital) to assess market viability.

## 1. Core Objectives

### Primary Goals
- **Accurate Detection**: Track ONLY real multi-hop arbitrage (2+ swaps per transaction)
- **Multi-Chain Support**: Monitor BSC and Polygon simultaneously
- **Competition Analysis**: Identify who captures opportunities and their success patterns
- **Opportunity Assessment**: Determine if small traders can compete effectively
- **Real-Time Monitoring**: Sub-second opportunity detection and logging

### Success Criteria
- Zero false positives (no single-swap trades counted as arbitrage)
- <2 second latency from block to opportunity detection
- 99.9% uptime per chain
- Complete transaction analysis with real profit calculations

## 2. Technical Architecture

### 2.1 System Components

```
┌─────────────────────────────────────────────────────────┐
│                    Multi-Chain Monitor                   │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────┐         ┌──────────────┐              │
│  │ BSC Monitor  │         │ Polygon      │              │
│  │              │         │ Monitor      │              │
│  │ - Pool Scan  │         │ - Pool Scan  │              │
│  │ - Block Mon  │         │ - Block Mon  │              │
│  │ - TX Analyze │         │ - TX Analyze │              │
│  └──────┬───────┘         └──────┬───────┘              │
│         │                        │                       │
│         └────────┬───────────────┘                       │
│                  │                                       │
│         ┌────────▼────────┐                             │
│         │  Unified DB     │                             │
│         │  (PostgreSQL)   │                             │
│         └────────┬────────┘                             │
│                  │                                       │
│         ┌────────▼────────┐                             │
│         │   REST API      │                             │
│         └────────┬────────┘                             │
│                  │                                       │
│         ┌────────▼────────┐                             │
│         │   Dashboard     │                             │
│         │   (Real-time)   │                             │
│         └─────────────────┘                             │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Chain Configurations

#### BSC (Binance Smart Chain)
- **Network**: Mainnet
- **RPC**: Primary: `https://bsc-dataseed.bnbchain.org`, Fallback: `https://bsc-dataseed1.binance.org`
- **Block Time**: ~3 seconds
- **Native Token**: BNB (~$620 USD)
- **Target DEXs**: PancakeSwap V2/V3, BiSwap, ApeSwap, THENA
- **Pool Focus**: WBNB pairs (BUSD, USDT, USDC, CAKE, ETH)

#### Polygon
- **Network**: Mainnet
- **RPC**: Primary: `https://polygon-rpc.com`, Fallback: `https://rpc-mainnet.matic.network`
- **Block Time**: ~2 seconds
- **Native Token**: MATIC (~$0.90 USD)
- **Target DEXs**: QuickSwap, SushiSwap, Uniswap V3, Balancer
- **Pool Focus**: WMATIC pairs (USDC, USDT, DAI, WETH, WBTC)

## 3. Arbitrage Detection Specification

### 3.1 Critical Requirements (Lessons Learned)

**MUST USE PROPER EVENT SIGNATURE DETECTION**

❌ **WRONG** (Previous Bug):
```python
# This counts ALL events (Transfer, Sync, Approval, etc.)
swap_count = len([log for log in receipt.get('logs', [])])
```

✅ **CORRECT**:
```python
from web3 import Web3

web3 = Web3()
SWAP_EVENT_SIGNATURE = web3.keccak(
    text="Swap(address,uint256,uint256,uint256,uint256,address)"
).hex()

# Count ONLY Swap events
swap_count = 0
for log in receipt.get('logs', []):
    if len(log.get('topics', [])) > 0:
        if log['topics'][0] == SWAP_EVENT_SIGNATURE:
            swap_count += 1
```

### 3.2 Arbitrage Transaction Criteria

A transaction is arbitrage **IF AND ONLY IF**:

1. **Multi-Hop Requirement**: `swap_count >= 2` (minimum 2 swaps in single transaction)
2. **DEX Router Target**: Transaction sent to known DEX router contract
3. **Swap Method**: Uses swap function (swapExactTokensForTokens, etc.)
4. **Circular Path**: Ideally starts and ends with same token (A → B → C → A)

### 3.3 DEX Router Addresses

#### BSC Routers
```python
BSC_DEX_ROUTERS = {
    "PancakeSwap V2": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
    "PancakeSwap V3": "0x13f4EA83D0bd40E75C8222255bc855a974568Dd4",
    "BiSwap": "0x3a6d8cA21D1CF76F653A67577FA0D27453350dD8",
    "ApeSwap": "0xcF0feBd3f17CEf5b47b0cD257aCf6025c5BFf3b7",
    "THENA": "0xd4ae6eCA985340Dd434D38F470aCCce4DC78D109",
}
```

#### Polygon Routers
```python
POLYGON_DEX_ROUTERS = {
    "QuickSwap": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
    "SushiSwap": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
    "Uniswap V3": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
    "Balancer": "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
}
```

### 3.4 Swap Method Signatures

```python
SWAP_METHOD_SIGNATURES = {
    "0x38ed1739": "swapExactTokensForTokens",
    "0x8803dbee": "swapTokensForExactTokens",
    "0x7ff36ab5": "swapExactETHForTokens",
    "0x18cbafe5": "swapExactTokensForETH",
    "0xfb3bdb41": "swapETHForExactTokens",
    "0x4a25d94a": "swapTokensForExactETH",
    "0x5c11d795": "swapExactTokensForTokensSupportingFeeOnTransferTokens",
    "0xb6f9de95": "swapExactETHForTokensSupportingFeeOnTransferTokens",
}
```

## 4. Pool Imbalance Detection

### 4.1 Constant Product Market Maker (CPMM) Formula

For Uniswap V2 style pools:

```python
def calculate_imbalance(reserve0: int, reserve1: int) -> Tuple[float, float]:
    """
    Calculate pool imbalance using CPMM invariant: k = x * y

    Returns:
        imbalance_pct: Percentage deviation from optimal balance
        profit_potential_usd: Estimated profit from rebalancing
    """
    if reserve0 == 0 or reserve1 == 0:
        return 0.0, 0.0

    # Invariant
    k = reserve0 * reserve1

    # Optimal reserves (both equal when balanced)
    optimal_x = k ** 0.5
    optimal_y = k ** 0.5

    # Imbalance percentage
    imbalance_x = abs(reserve0 - optimal_x) / optimal_x * 100
    imbalance_y = abs(reserve1 - optimal_y) / optimal_y * 100
    imbalance = max(imbalance_x, imbalance_y)

    # Profit estimation (accounting for 0.3% fee)
    if reserve0 > optimal_x:
        excess = reserve0 - optimal_x
        profit = (excess * reserve1) / (reserve0 + excess)
        profit_after_fees = profit * 0.997  # 0.3% fee
    else:
        excess = reserve1 - optimal_y
        profit = (excess * reserve0) / (reserve1 + excess)
        profit_after_fees = profit * 0.997

    # Convert to USD (assume token1 is stablecoin)
    profit_usd = profit_after_fees / 1e18

    return imbalance, profit_usd
```

### 4.2 Target Pools

#### BSC Pools (PancakeSwap V2)
```python
BSC_POOLS = {
    "WBNB-BUSD": "0x58F876857a02D6762E0101bb5C46A8c1ED44Dc16",
    "WBNB-USDT": "0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE",
    "WBNB-USDC": "0x7EFaEf62fDdCCa950418312c6C91Aef321375A00",
    "WBNB-CAKE": "0x0eD7e52944161450477ee417DE9Cd3a859b14fD0",
    "WBNB-ETH": "0x1B96B92314C44b159149f7E0303511fB2Fc4774f",
    "BUSD-USDT": "0x7EFaEf62fDdCCa950418312c6C91Aef321375A00",
}
```

#### Polygon Pools (QuickSwap)
```python
POLYGON_POOLS = {
    "WMATIC-USDC": "0x6e7a5FAFcec6BB1e78bAA2A0430e3B1B64B5c0D7",
    "WMATIC-USDT": "0x604229c960e5CACF2aaEAc8Be68Ac07BA9dF81c3",
    "WMATIC-DAI": "0x4A35582a710E1F4b2030A3F826DA20BfB6703C09",
    "WMATIC-WETH": "0xadbF1854e5883eB8aa7BAf50705338739e558E5b",
    "USDC-USDT": "0x2cF7252e74036d1Da831d11089D326296e64a728",
}
```

## 5. Database Schema

### 5.1 PostgreSQL Schema

```sql
-- Chains table
CREATE TABLE chains (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    chain_id INTEGER NOT NULL UNIQUE,
    rpc_url VARCHAR(255) NOT NULL,
    block_time_seconds DECIMAL(4,2) NOT NULL,
    native_token VARCHAR(10) NOT NULL,
    native_token_usd DECIMAL(10,2),
    last_synced_block BIGINT,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Opportunities table
CREATE TABLE opportunities (
    id SERIAL PRIMARY KEY,
    chain_id INTEGER REFERENCES chains(id),
    pool_name VARCHAR(100) NOT NULL,
    pool_address VARCHAR(42) NOT NULL,
    imbalance_pct DECIMAL(10,4) NOT NULL,
    profit_usd DECIMAL(18,8) NOT NULL,
    profit_native DECIMAL(18,8) NOT NULL,
    reserve0 DECIMAL(30,18) NOT NULL,
    reserve1 DECIMAL(30,18) NOT NULL,
    block_number BIGINT NOT NULL,
    detected_at TIMESTAMP DEFAULT NOW(),
    captured BOOLEAN DEFAULT FALSE,
    captured_by VARCHAR(42),
    capture_tx_hash VARCHAR(66),
    INDEX idx_pool_block (chain_id, pool_address, block_number),
    INDEX idx_profit (chain_id, profit_usd DESC),
    INDEX idx_detected (detected_at DESC)
);

-- Transactions table (arbitrage executions)
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    chain_id INTEGER REFERENCES chains(id),
    tx_hash VARCHAR(66) NOT NULL UNIQUE,
    from_address VARCHAR(42) NOT NULL,
    block_number BIGINT NOT NULL,
    block_timestamp TIMESTAMP NOT NULL,
    gas_price_gwei DECIMAL(18,9) NOT NULL,
    gas_used INTEGER NOT NULL,
    gas_cost_native DECIMAL(18,8) NOT NULL,
    gas_cost_usd DECIMAL(18,8) NOT NULL,
    swap_count INTEGER NOT NULL,
    strategy VARCHAR(50) NOT NULL,
    profit_gross_usd DECIMAL(18,8),
    profit_net_usd DECIMAL(18,8),
    pools_involved TEXT[],
    tokens_involved TEXT[],
    detected_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_chain_block (chain_id, block_number DESC),
    INDEX idx_arbitrageur (from_address, detected_at DESC),
    INDEX idx_profit_net (profit_net_usd DESC),
    INDEX idx_tx_hash (tx_hash)
);

-- Arbitrageurs table (traders executing arbitrage)
CREATE TABLE arbitrageurs (
    id SERIAL PRIMARY KEY,
    address VARCHAR(42) NOT NULL,
    chain_id INTEGER REFERENCES chains(id),
    first_seen TIMESTAMP DEFAULT NOW(),
    last_seen TIMESTAMP DEFAULT NOW(),
    total_transactions INTEGER DEFAULT 0,
    successful_transactions INTEGER DEFAULT 0,
    failed_transactions INTEGER DEFAULT 0,
    total_profit_usd DECIMAL(18,8) DEFAULT 0,
    total_gas_spent_usd DECIMAL(18,8) DEFAULT 0,
    avg_gas_price_gwei DECIMAL(18,9),
    preferred_strategy VARCHAR(50),
    is_bot BOOLEAN DEFAULT TRUE,
    contract_address BOOLEAN DEFAULT FALSE,
    UNIQUE(address, chain_id),
    INDEX idx_address (address),
    INDEX idx_profit (total_profit_usd DESC),
    INDEX idx_last_seen (last_seen DESC)
);

-- Chain statistics (aggregated metrics)
CREATE TABLE chain_stats (
    id SERIAL PRIMARY KEY,
    chain_id INTEGER REFERENCES chains(id),
    date DATE NOT NULL,
    hour INTEGER NOT NULL CHECK (hour BETWEEN 0 AND 23),
    total_opportunities INTEGER DEFAULT 0,
    total_captured INTEGER DEFAULT 0,
    capture_rate DECIMAL(5,2),
    total_arbitrageurs INTEGER DEFAULT 0,
    total_transactions INTEGER DEFAULT 0,
    total_volume_usd DECIMAL(18,8) DEFAULT 0,
    avg_profit_usd DECIMAL(18,8),
    median_profit_usd DECIMAL(18,8),
    small_opps_count INTEGER DEFAULT 0,  -- 10K-100K USD
    small_opps_captured INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(chain_id, date, hour),
    INDEX idx_chain_date (chain_id, date DESC, hour DESC)
);
```

### 5.2 Database Indexes Strategy

- **High-Frequency Queries**: Index on (chain_id, block_number DESC)
- **Arbitrageur Analysis**: Index on (address, detected_at DESC)
- **Profit Filtering**: Index on (profit_usd DESC)
- **Time-Series Analysis**: Index on (detected_at DESC)

## 6. Real Profit Calculation

### 6.1 Token Flow Parsing

**Requirement**: Parse actual token amounts from Swap events to calculate REAL profit

```python
def parse_swap_event(log: dict) -> dict:
    """
    Parse Swap event from transaction log

    Event signature:
    Swap(address indexed sender, uint amount0In, uint amount1In,
         uint amount0Out, uint amount1Out, address indexed to)
    """
    # Verify this is a Swap event
    if log['topics'][0] != SWAP_EVENT_SIGNATURE:
        return None

    # Parse indexed parameters
    sender = '0x' + log['topics'][1][-40:]
    to = '0x' + log['topics'][2][-40:]

    # Parse data (non-indexed parameters)
    data = log['data'][2:]  # Remove '0x'

    amount0In = int(data[0:64], 16)
    amount1In = int(data[64:128], 16)
    amount0Out = int(data[128:192], 16)
    amount1Out = int(data[192:256], 16)

    return {
        'pool': log['address'],
        'sender': sender,
        'to': to,
        'amount0In': amount0In,
        'amount1In': amount1In,
        'amount0Out': amount0Out,
        'amount1Out': amount1Out
    }

def calculate_arbitrage_profit(receipt: dict, swaps: list) -> dict:
    """
    Calculate real profit from arbitrage transaction

    For circular arbitrage (e.g., USDC -> WBNB -> CAKE -> USDC):
    - First swap: Input is the capital
    - Last swap: Output is the result
    - Profit = Output - Input (same token)
    """
    if len(swaps) < 2:
        return {'profit_gross': 0, 'profit_net': 0}

    first_swap = swaps[0]
    last_swap = swaps[-1]

    # Determine input amount (first non-zero input)
    input_amount = first_swap['amount0In'] if first_swap['amount0In'] > 0 else first_swap['amount1In']

    # Determine output amount (last non-zero output)
    output_amount = last_swap['amount0Out'] if last_swap['amount0Out'] > 0 else last_swap['amount1Out']

    # Gross profit (before gas)
    profit_gross = output_amount - input_amount

    # Gas cost
    gas_used = int(receipt['gasUsed'], 16)
    gas_price = int(receipt.get('effectiveGasPrice', receipt.get('gasPrice', '0')), 16)
    gas_cost = gas_used * gas_price

    # Net profit
    profit_net = profit_gross - gas_cost

    return {
        'profit_gross': profit_gross,
        'profit_net': profit_net,
        'gas_cost': gas_cost,
        'input_amount': input_amount,
        'output_amount': output_amount,
        'roi_pct': (profit_net / input_amount * 100) if input_amount > 0 else 0
    }
```

## 7. API Specification

### 7.1 REST API Endpoints

#### Chain Status
```
GET /api/v1/chains
Response:
{
  "chains": [
    {
      "id": 1,
      "name": "BSC",
      "chain_id": 56,
      "status": "active",
      "last_synced_block": 68286234,
      "blocks_behind": 2,
      "uptime_pct": 99.97
    },
    {
      "id": 2,
      "name": "Polygon",
      "chain_id": 137,
      "status": "active",
      "last_synced_block": 52847123,
      "blocks_behind": 1,
      "uptime_pct": 99.95
    }
  ]
}
```

#### Opportunities
```
GET /api/v1/opportunities?chain=bsc&min_profit=10000&max_profit=100000&limit=100
Response:
{
  "opportunities": [
    {
      "id": 12345,
      "chain": "BSC",
      "pool_name": "WBNB-BUSD",
      "pool_address": "0x58F876857a02D6762E0101bb5C46A8c1ED44Dc16",
      "imbalance_pct": 7.82,
      "profit_usd": 45230.50,
      "block_number": 68286234,
      "detected_at": "2025-11-15T15:30:45Z",
      "captured": true,
      "captured_by": "0x1234...5678",
      "capture_tx_hash": "0xabc...def"
    }
  ],
  "total": 1523,
  "page": 1,
  "per_page": 100
}
```

#### Transactions
```
GET /api/v1/transactions?chain=polygon&min_profit=5000&limit=50
Response:
{
  "transactions": [
    {
      "id": 789,
      "chain": "Polygon",
      "tx_hash": "0x123...abc",
      "from_address": "0x9876...5432",
      "block_number": 52847120,
      "timestamp": "2025-11-15T15:28:12Z",
      "swap_count": 3,
      "strategy": "3-hop",
      "profit_gross_usd": 12450.00,
      "profit_net_usd": 12430.25,
      "gas_cost_usd": 19.75,
      "pools_involved": ["WMATIC-USDC", "USDC-DAI", "DAI-WMATIC"],
      "roi_pct": 24.86
    }
  ],
  "total": 234,
  "page": 1,
  "per_page": 50
}
```

#### Arbitrageurs
```
GET /api/v1/arbitrageurs?chain=bsc&min_transactions=10&sort=profit_desc
Response:
{
  "arbitrageurs": [
    {
      "address": "0x1234567890abcdef1234567890abcdef12345678",
      "chain": "BSC",
      "total_transactions": 1523,
      "successful_transactions": 1498,
      "success_rate": 98.36,
      "total_profit_usd": 4523450.75,
      "total_gas_spent_usd": 45230.25,
      "avg_profit_per_tx": 2970.12,
      "avg_gas_price_gwei": 3.5,
      "preferred_strategy": "3-hop",
      "is_bot": true,
      "first_seen": "2025-11-01T08:00:00Z",
      "last_seen": "2025-11-15T15:30:00Z"
    }
  ],
  "total": 89,
  "page": 1,
  "per_page": 20
}
```

#### Statistics
```
GET /api/v1/stats?chain=bsc&period=24h
Response:
{
  "chain": "BSC",
  "period": "24h",
  "total_opportunities": 25630,
  "total_captured": 1523,
  "capture_rate": 5.94,
  "total_transactions": 1523,
  "unique_arbitrageurs": 89,
  "total_volume_usd": 45234567.89,
  "small_opportunities": {
    "count": 15234,
    "captured": 234,
    "capture_rate": 1.54,
    "avg_profit": 45230.50
  },
  "profit_distribution": {
    "min": 10050.00,
    "max": 523400.00,
    "avg": 29705.34,
    "median": 18450.00,
    "p95": 125400.00
  },
  "gas_stats": {
    "avg_price_gwei": 3.2,
    "avg_cost_usd": 15.75,
    "total_spent_usd": 23987.25
  }
}
```

### 7.2 WebSocket API (Real-Time)

```javascript
// Connect
ws://api.example.com/ws/v1/stream

// Subscribe to opportunities
{
  "action": "subscribe",
  "channel": "opportunities",
  "filters": {
    "chains": ["bsc", "polygon"],
    "min_profit": 10000,
    "max_profit": 100000
  }
}

// Receive updates
{
  "type": "opportunity",
  "chain": "BSC",
  "data": {
    "pool_name": "WBNB-BUSD",
    "imbalance_pct": 8.5,
    "profit_usd": 52300,
    "block_number": 68286245,
    "detected_at": "2025-11-15T15:31:02Z"
  }
}

// Subscribe to transactions
{
  "action": "subscribe",
  "channel": "transactions",
  "filters": {
    "chains": ["polygon"],
    "min_swaps": 2
  }
}

// Receive transaction alerts
{
  "type": "arbitrage_executed",
  "chain": "Polygon",
  "data": {
    "tx_hash": "0x789...xyz",
    "from": "0x1234...5678",
    "swap_count": 4,
    "estimated_profit_usd": 18500,
    "block_number": 52847135
  }
}
```

## 8. Dashboard Requirements

### 8.1 Real-Time Dashboard Pages

#### Overview Page
- **Multi-Chain Summary**: Side-by-side BSC vs Polygon metrics
- **Live Statistics**: Opportunities detected, captured, arbitrageurs active
- **Profit Charts**: Hourly/daily profit distribution
- **Competition Heatmap**: Capture rate by profit range
- **Chain Health**: Block sync status, RPC latency, uptime

#### Opportunities Page
- **Live Feed**: Real-time opportunities with filtering (chain, profit range)
- **Capture Status**: Show which opportunities were captured and by whom
- **Pool Analysis**: Imbalance trends per pool
- **Time-to-Capture**: How fast are opportunities captured

#### Transactions Page
- **Arbitrage Feed**: All detected multi-hop arbitrage transactions
- **Strategy Breakdown**: 2-hop, 3-hop, 4-hop distribution
- **Profitability Analysis**: Gross vs net profit after gas
- **Gas Price Trends**: What gas prices are competitive arbitrageurs using

#### Arbitrageurs Page
- **Leaderboard**: Top arbitrageurs by profit, transaction count, success rate
- **Bot Analysis**: Identify bot patterns (consistent gas price, fast execution)
- **Competition Level**: How many active arbitrageurs per hour
- **Entry Barriers**: Minimum capital observed for successful arbitrage

#### Analytics Page
- **Small Trader Viability**: Focus on $10K-$100K opportunities
- **Capture Rate by Size**: Are small opportunities harder/easier to capture?
- **Time Analysis**: Best/worst hours for opportunities
- **Chain Comparison**: BSC vs Polygon - which is better for small traders?

### 8.2 Dashboard Technology Stack

```
Frontend:
  - Framework: React 18+ with TypeScript
  - UI Library: TailwindCSS + shadcn/ui
  - Charts: Recharts or Chart.js
  - Real-time: WebSocket client
  - State: Zustand or Redux Toolkit

Backend:
  - API: FastAPI (Python) or Express (Node.js)
  - Database: PostgreSQL 15+
  - Cache: Redis for real-time data
  - WebSocket: Socket.IO or native WS

Deployment:
  - Containerization: Docker + Docker Compose
  - Reverse Proxy: Nginx
  - SSL: Let's Encrypt
  - Monitoring: Prometheus + Grafana
```

## 9. Performance Requirements

### 9.1 Latency Targets

- **Block Detection**: <1 second from block creation
- **Opportunity Detection**: <2 seconds from pool state change
- **Transaction Analysis**: <3 seconds from transaction inclusion
- **API Response**: <200ms for queries, <50ms for cached data
- **WebSocket Broadcast**: <100ms from detection to client

### 9.2 Throughput Requirements

- **BSC**: Handle 200+ TPS (transactions per second)
- **Polygon**: Handle 300+ TPS
- **Pool Scanning**: 20+ pools per chain per minute
- **Database Writes**: 1000+ inserts per minute sustained
- **API Requests**: 100+ concurrent connections

### 9.3 Data Retention

- **Opportunities**: 30 days rolling window
- **Transactions**: Permanent (with archival after 90 days)
- **Arbitrageurs**: Permanent
- **Chain Stats**: Permanent (hourly aggregates)
- **Logs**: 7 days

## 10. Monitoring & Alerting

### 10.1 System Health Metrics

```python
METRICS_TO_TRACK = {
    # Chain Health
    "chain.blocks_behind": "Gauge - blocks behind latest",
    "chain.rpc_latency_ms": "Histogram - RPC call latency",
    "chain.rpc_errors_total": "Counter - RPC errors",
    "chain.uptime_pct": "Gauge - uptime percentage",

    # Detection Performance
    "detector.opportunities_detected_total": "Counter - opportunities found",
    "detector.transactions_detected_total": "Counter - arbitrage txs found",
    "detector.false_positives_total": "Counter - incorrectly flagged txs",
    "detector.latency_ms": "Histogram - detection latency",

    # Database Performance
    "db.connection_pool_size": "Gauge - active connections",
    "db.query_latency_ms": "Histogram - query latency",
    "db.write_errors_total": "Counter - write failures",

    # API Performance
    "api.requests_total": "Counter - total requests",
    "api.response_latency_ms": "Histogram - response time",
    "api.errors_total": "Counter - API errors",

    # Business Metrics
    "business.total_profit_usd": "Counter - cumulative profit detected",
    "business.active_arbitrageurs": "Gauge - unique arbitrageurs in last hour",
    "business.small_opportunities_pct": "Gauge - % of opps in 10K-100K range",
}
```

### 10.2 Alert Rules

```yaml
alerts:
  - name: ChainSyncLagging
    condition: chain.blocks_behind > 100
    severity: critical
    message: "Chain {{ chain }} is {{ blocks_behind }} blocks behind"

  - name: HighRPCLatency
    condition: chain.rpc_latency_ms.p95 > 2000
    severity: warning
    message: "RPC latency for {{ chain }} is {{ latency }}ms"

  - name: DatabaseConnectionPoolExhausted
    condition: db.connection_pool_size > 80% capacity
    severity: critical
    message: "Database connection pool at {{ usage }}% capacity"

  - name: HighFalsePositiveRate
    condition: detector.false_positives_total / detector.transactions_detected_total > 0.01
    severity: warning
    message: "False positive rate at {{ rate }}%"

  - name: NoOpportunitiesDetected
    condition: rate(detector.opportunities_detected_total[5m]) == 0
    severity: warning
    message: "No opportunities detected in last 5 minutes on {{ chain }}"
```

## 11. Implementation Phases

### Phase 1: Core Detection (Week 1-2)
- ✅ Set up project structure
- ✅ Implement BSC chain connector
- ✅ Implement proper Swap event detection
- ✅ Create PostgreSQL schema
- ✅ Build pool scanner for BSC
- ✅ Build transaction analyzer for BSC
- ✅ Implement real profit calculation
- ✅ Unit tests for detection logic

### Phase 2: Polygon Support (Week 3)
- Add Polygon chain connector
- Configure Polygon DEX routers
- Add Polygon pool addresses
- Test multi-chain coordination
- Validate cross-chain data consistency

### Phase 3: API & Database (Week 4)
- Build REST API endpoints
- Implement WebSocket streaming
- Add database indexes
- Implement caching layer (Redis)
- API documentation (OpenAPI/Swagger)
- Load testing

### Phase 4: Dashboard (Week 5-6)
- Build React frontend
- Implement real-time updates
- Create all dashboard pages
- Add filtering and search
- Mobile responsive design
- Performance optimization

### Phase 5: Production Hardening (Week 7)
- Monitoring setup (Prometheus + Grafana)
- Alerting configuration
- Error tracking (Sentry)
- Backup strategy
- Disaster recovery plan
- Security audit
- Load testing
- Documentation

### Phase 6: Deployment & Testing (Week 8)
- Docker containerization
- Production deployment
- 72-hour burn-in test
- Performance tuning
- Final validation
- Handoff documentation

## 12. Testing Requirements

### 12.1 Unit Tests (>80% Coverage)

```python
# test_swap_detection.py
def test_swap_event_signature():
    """Verify Swap event signature is correct"""
    assert SWAP_EVENT_SIGNATURE == "0xd78ad95f..."

def test_count_swaps_correctly():
    """Ensure only Swap events are counted, not all events"""
    # Test case from bug: transaction with 5 total events, 1 Swap
    receipt = load_test_receipt("single_swap_tx.json")
    swap_count = count_swap_events(receipt)
    assert swap_count == 1, "Should only count Swap events"

def test_multi_hop_arbitrage_detection():
    """Verify multi-hop arbitrage is detected"""
    receipt = load_test_receipt("3hop_arbitrage.json")
    is_arb = is_arbitrage(receipt)
    assert is_arb == True
    assert get_swap_count(receipt) == 3

def test_single_swap_not_arbitrage():
    """Single swap should NOT be flagged as arbitrage"""
    receipt = load_test_receipt("regular_swap.json")
    is_arb = is_arbitrage(receipt)
    assert is_arb == False

def test_profit_calculation():
    """Verify profit calculation accuracy"""
    swaps = [
        {'amount0In': 100000, 'amount1Out': 150000},
        {'amount0In': 150000, 'amount1Out': 110000}
    ]
    profit = calculate_profit(swaps)
    assert profit == 10000  # 110K - 100K
```

### 12.2 Integration Tests

- Test BSC RPC connectivity and fallback
- Test Polygon RPC connectivity
- Test database writes under load
- Test API endpoint responses
- Test WebSocket broadcasting
- Test concurrent chain monitoring

### 12.3 End-to-End Tests

- Deploy to staging environment
- Inject known arbitrage transactions
- Verify detection accuracy
- Verify profit calculations
- Verify database persistence
- Verify dashboard display

## 13. Security Considerations

### 13.1 RPC Security
- Rate limiting per RPC endpoint
- Automatic failover to backup RPCs
- No private keys stored (read-only monitoring)
- HTTPS only for RPC calls

### 13.2 API Security
- API key authentication
- Rate limiting (100 req/min per key)
- CORS configuration
- Input validation and sanitization
- SQL injection prevention (parameterized queries)
- XSS prevention

### 13.3 Data Security
- PostgreSQL authentication
- Database connection encryption
- Backup encryption at rest
- PII minimization (only public blockchain addresses)
- Audit logging for sensitive operations

## 14. Deliverables

### 14.1 Code Repositories
```
multi-chain-monitor/
├── backend/
│   ├── src/
│   │   ├── chains/
│   │   │   ├── bsc/
│   │   │   │   ├── connector.py
│   │   │   │   ├── pools.py
│   │   │   │   └── routers.py
│   │   │   ├── polygon/
│   │   │   │   ├── connector.py
│   │   │   │   ├── pools.py
│   │   │   │   └── routers.py
│   │   │   └── base.py
│   │   ├── detectors/
│   │   │   ├── opportunity_detector.py
│   │   │   ├── transaction_analyzer.py
│   │   │   └── profit_calculator.py
│   │   ├── database/
│   │   │   ├── models.py
│   │   │   ├── schema.sql
│   │   │   └── migrations/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   ├── websocket.py
│   │   │   └── middleware.py
│   │   └── utils/
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── api/
│   ├── public/
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── .env.example
└── README.md
```

### 14.2 Documentation
- Architecture diagram
- API documentation (OpenAPI spec)
- Database schema diagram
- Deployment guide
- Operations runbook
- Troubleshooting guide

### 14.3 Monitoring Dashboards
- Grafana dashboard JSON exports
- Alert rule configurations
- Metrics dictionary

## 15. Success Metrics (Post-Deployment)

### 15.1 Technical Metrics
- ✅ 99.9% uptime per chain
- ✅ <2 second average detection latency
- ✅ 0% false positive rate
- ✅ <100ms API response time (p95)

### 15.2 Business Metrics
- Number of small opportunities ($10K-$100K) detected per day
- Capture rate for small opportunities
- Number of unique arbitrageurs competing
- Average competition level (arbitrageurs per opportunity)
- Viability assessment: Can small traders compete? (Yes/No + evidence)

## 16. Budget Estimate

### 16.1 Infrastructure (Monthly)
- VPS (8 CPU, 16GB RAM): $50-100
- PostgreSQL managed instance: $50-150
- Redis cache: $20-50
- Domain + SSL: $15
- Monitoring (Grafana Cloud): $0-50
- **Total**: ~$150-350/month

### 16.2 Development (One-time)
- 8 weeks @ 40 hours/week = 320 hours
- Estimate: $15,000 - $40,000 (depending on developer rates)

## 17. Future Enhancements (Post-MVP)

- Add more chains (Ethereum, Arbitrum, Optimism, Base)
- MEV bot integration (execute opportunities, not just monitor)
- Machine learning for opportunity prediction
- Telegram/Discord notifications
- Historical data analysis and reports
- Competition forecasting
- Gas price optimization recommendations
- Multi-DEX aggregator integration
- Flash loan simulation
