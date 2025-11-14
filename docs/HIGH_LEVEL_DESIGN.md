# BSC Imbalance Prediction - High-Level Design (HLD)

**Project**: BSC Imbalance Prediction Mechanism
**Version**: 1.0
**Status**: Draft - Pending Architecture Review
**Date**: 2025-11-13
**Authors**: Tech Lead (Claude), Backend Engineering Team
**Reviewers**: Senior Engineers, BSC Core Team, Security Team

---

## Executive Summary

This document describes the high-level architecture for the BSC Imbalance Prediction mechanism, a system that predicts DEX liquidity imbalances before they occur by analyzing mempool transactions and simulating future pool states.

**Key Characteristics**:
- **Integration**: Embedded in BSC Go-Ethereum client fork
- **Latency**: <100ms (p95) prediction generation
- **Accuracy**: >70% predictions within 5% of actual
- **Scalability**: 1000+ pools, 100-500 tx/sec mempool throughput
- **Availability**: 99.9% uptime target

---

## Table of Contents

1. [System Context (C4 Level 1)](#1-system-context-c4-level-1)
2. [Container Architecture (C4 Level 2)](#2-container-architecture-c4-level-2)
3. [Component Design (C4 Level 3)](#3-component-design-c4-level-3)
4. [Data Flow Architecture](#4-data-flow-architecture)
5. [Deployment Architecture](#5-deployment-architecture)
6. [Security Architecture](#6-security-architecture)
7. [Observability Architecture](#7-observability-architecture)
8. [Performance & Scalability](#8-performance--scalability)
9. [Risk Matrix](#9-risk-matrix)
10. [Quality Attributes](#10-quality-attributes)

---

## 1. System Context (C4 Level 1)

### System Context Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    BSC Blockchain Ecosystem                      │
│                                                                   │
│  ┌─────────────┐                                                │
│  │   BSC P2P   │◄────── Mempool Sync                            │
│  │   Network   │                                                 │
│  └──────┬──────┘                                                 │
│         │                                                         │
│         │ Pending Transactions                                   │
│         ▼                                                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │         BSC Client (Go-Ethereum Fork)                    │   │
│  │                                                           │   │
│  │  ┌─────────────────────────────────────────────────┐   │   │
│  │  │   Imbalance Prediction Engine [NEW]             │   │   │
│  │  │   - Monitors mempool transactions               │   │   │
│  │  │   - Simulates future pool states                │   │   │
│  │  │   - Predicts price imbalances                   │   │   │
│  │  │   - Exposes predictions via RPC                 │   │   │
│  │  └─────────────────────────────────────────────────┘   │   │
│  │                                                           │   │
│  │  [Core BSC Components]                                   │   │
│  │  - TxPool, StateDB, EVM, Consensus                      │   │
│  └───────────────────────┬─────────────────────────────────┘   │
│                           │                                      │
│                           │ JSON-RPC API                         │
│                           ▼                                      │
└───────────────────────────────────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         ▼                  ▼                  ▼
  ┌────────────┐    ┌────────────┐    ┌────────────┐
  │ MEV Bots   │    │    DEX     │    │   Market   │
  │  (Searchers)│    │ Aggregators│    │   Makers   │
  └────────────┘    └────────────┘    └────────────┘
  - Flash loans     - 1inch          - Automated MM
  - Arbitrage       - ParaSwap       - Liquidity
  - Sandwich        - Matcha           providers

  ┌────────────────────────────────────────────┐
  │    Supporting Infrastructure               │
  ├────────────────────────────────────────────┤
  │  Prometheus (Metrics)                      │
  │  Grafana (Dashboards)                      │
  │  TimescaleDB (Accuracy Tracking)           │
  │  PagerDuty (Alerting)                      │
  └────────────────────────────────────────────┘
```

### External Systems & Interfaces

| System | Relationship | Protocol | Purpose |
|--------|-------------|----------|---------|
| **BSC P2P Network** | Inbound | devp2p | Mempool transaction broadcast |
| **MEV Bots** | Outbound | JSON-RPC (HTTPS/WSS) | Prediction consumers |
| **DEX Aggregators** | Outbound | JSON-RPC | Routing optimization |
| **Market Makers** | Outbound | JSON-RPC | Liquidity management |
| **Prometheus** | Outbound | HTTP | Metrics collection |
| **TimescaleDB** | Outbound | PostgreSQL | Accuracy tracking storage |
| **PagerDuty** | Outbound | HTTPS | Incident alerting |

### Key Users & Personas

1. **MEV Searchers** (Primary)
   - Need: Real-time predictions for arbitrage
   - Usage: High-frequency API calls (10-100 req/min)
   - SLA: <200ms p95 latency, >70% accuracy

2. **DEX Aggregators** (Primary)
   - Need: Pre-trade pool state predictions for routing
   - Usage: Moderate frequency (1-10 req/min per route calculation)
   - SLA: <200ms p95 latency, predictive routing

3. **Market Makers** (Secondary)
   - Need: Liquidity management signals
   - Usage: Low frequency (1 req/min) + WebSocket subscriptions
   - SLA: >99.9% uptime, real-time alerts

---

## 2. Container Architecture (C4 Level 2)

### Container Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                      BSC Client Process                             │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Core BSC Components (Existing)                             │   │
│  │  - TxPool (mempool management)                              │   │
│  │  - StateDB (blockchain state)                               │   │
│  │  - EVM (transaction execution)                              │   │
│  │  - Consensus (block validation)                             │   │
│  └────────────────────────┬───────────────────────────────────┘   │
│                            │                                        │
│                            │ Events & State Access                  │
│                            ▼                                        │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  Imbalance Prediction Engine [NEW CONTAINER]                 │ │
│  │                                                               │ │
│  │  ┌─────────────────────────────────────────────────────┐   │ │
│  │  │  Prediction Orchestrator                             │   │ │
│  │  │  - Subscribes to TxPool events                       │   │ │
│  │  │  - Coordinates prediction pipeline                   │   │ │
│  │  │  - Manages cache lifecycle                           │   │ │
│  │  └─────────────────────────────────────────────────────┘   │ │
│  │                                                               │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐        │ │
│  │  │ DEX Filter  │  │Pool State   │  │  Imbalance   │        │ │
│  │  │ (Mempool)   │→ │Simulator    │→ │  Detector    │        │ │
│  │  │             │  │ (CPMM)      │  │  (Scoring)   │        │ │
│  │  └─────────────┘  └─────────────┘  └──────────────┘        │ │
│  │         │                 │                  │               │ │
│  │         ▼                 ▼                  ▼               │ │
│  │  ┌────────────────────────────────────────────────────┐    │ │
│  │  │         Pool State Cache (In-Memory LRU)            │    │ │
│  │  │         - 1000 entry capacity                       │    │ │
│  │  │         - Thread-safe with RWMutex                  │    │ │
│  │  └────────────────────────────────────────────────────┘    │ │
│  │                                                               │ │
│  │  ┌─────────────────────────────────────────────────────┐   │ │
│  │  │  Observability Layer                                 │   │ │
│  │  │  - Prometheus metrics                                │   │ │
│  │  │  - Structured logging (zerolog)                      │   │ │
│  │  │  - Accuracy tracker                                  │   │ │
│  │  └─────────────────────────────────────────────────────┘   │ │
│  └───────────────────────────┬───────────────────────────────┘ │
│                               │                                  │
│  ┌────────────────────────────▼──────────────────────────────┐ │
│  │  RPC API Server (Existing, Extended)                       │ │
│  │                                                             │ │
│  │  [New Namespace: "imbalance"]                              │ │
│  │  - imbalance_getPoolImbalance                              │ │
│  │  - imbalance_getTopImbalances                              │ │
│  │  - imbalance_subscribe (WebSocket)                         │ │
│  │                                                             │ │
│  │  [Security Layer]                                          │ │
│  │  - Rate limiting (100 req/min per IP)                     │ │
│  │  - Input validation                                        │ │
│  │  - API key authentication (optional)                      │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                                  │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               │ HTTPS / WebSocket
                               ▼
                    ┌─────────────────────┐
                    │  External Clients   │
                    └─────────────────────┘
```

### Container Responsibilities

#### 1. BSC Core Components (Existing)
- **Responsibility**: Blockchain consensus, transaction execution, state management
- **Technology**: Go, LevelDB, devp2p
- **Modification**: Minimal (expose events to prediction engine)

#### 2. Imbalance Prediction Engine (New)
- **Responsibility**: Mempool monitoring, pool state simulation, imbalance detection
- **Technology**: Go, in-memory cache
- **Dependencies**: BSC TxPool, StateDB
- **Performance**: <2% CPU overhead, <500MB memory

#### 3. RPC API Server (Extended)
- **Responsibility**: Expose predictions via JSON-RPC
- **Technology**: Go RPC framework (existing BSC infrastructure)
- **Security**: Rate limiting, input validation, optional API keys

---

## 3. Component Design (C4 Level 3)

### Prediction Engine Components

```
┌──────────────────────────────────────────────────────────────────────┐
│                     Imbalance Prediction Engine                       │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  ImbalancePredictor (Main Orchestrator)                          │ │
│  │  ┌──────────────────────────────────────────────────────────┐  │ │
│  │  │  - Start() / Stop(): Lifecycle management                 │  │ │
│  │  │  - OnPendingTx(tx): Handle mempool events                 │  │ │
│  │  │  - PredictPoolState(pool): Main prediction logic          │  │ │
│  │  │  - GetPoolState(pool): Retrieve cached prediction         │  │ │
│  │  └──────────────────────────────────────────────────────────┘  │ │
│  └───┬──────────────────────────────────────────────────────────────┘ │
│      │                                                                 │
│      │ Uses                                                            │
│      ▼                                                                 │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │  Component Layer                                               │   │
│  │                                                                 │   │
│  │  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────┐ │   │
│  │  │   DEXFilter     │  │  PoolSimulator   │  │  Imbalance   │ │   │
│  │  │                 │  │                  │  │  Detector    │ │   │
│  │  │ - IsSwap(tx)    │  │ - Simulate()     │  │ - Detect()   │ │   │
│  │  │ - ParseSwap(tx) │  │ - CalcOutput()   │  │ - Score()    │ │   │
│  │  │ - Routers map   │  │ - ApplySwap()    │  │ - Estimate() │ │   │
│  │  └─────────────────┘  └──────────────────┘  └──────────────┘ │   │
│  │                                                                 │   │
│  │  ┌─────────────────────────────────────────────────────────┐  │   │
│  │  │   PoolCache (In-Memory LRU)                             │  │   │
│  │  │   - Get(addr): Retrieve cached state                    │  │   │
│  │  │   - Set(addr, state): Update cache                      │  │   │
│  │  │   - Evict(): LRU eviction policy                        │  │   │
│  │  │   - Stats(): Hit rate, size metrics                     │  │   │
│  │  └─────────────────────────────────────────────────────────┘  │   │
│  │                                                                 │   │
│  │  ┌─────────────────────────────────────────────────────────┐  │   │
│  │  │   PoolStateFetcher                                       │  │   │
│  │  │   - FetchReserves(pool): Query StateDB                  │  │   │
│  │  │   - GetTokenInfo(pool): Token addresses, decimals       │  │   │
│  │  └─────────────────────────────────────────────────────────┘  │   │
│  │                                                                 │   │
│  │  ┌─────────────────────────────────────────────────────────┐  │   │
│  │  │   MetricsCollector                                       │  │   │
│  │  │   - RecordPrediction()                                   │  │   │
│  │  │   - RecordLatency()                                      │  │   │
│  │  │   - UpdateAccuracy()                                     │  │   │
│  │  └─────────────────────────────────────────────────────────┘  │   │
│  │                                                                 │   │
│  │  ┌─────────────────────────────────────────────────────────┐  │   │
│  │  │   AccuracyTracker (Optional, Sprint 3)                   │  │   │
│  │  │   - RecordPrediction(pred)                               │  │   │
│  │  │   - ValidatePrediction(pred): After 3 sec               │  │   │
│  │  │   - StoreResult(db): Persist to TimescaleDB             │  │   │
│  │  └─────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
```

### Component Interfaces

#### 1. ImbalancePredictor (Orchestrator)

```go
type ImbalancePredictor struct {
    txpool       *legacypool.LegacyPool
    filter       *DEXFilter
    simulator    *PoolSimulator
    detector     *ImbalanceDetector
    cache        *PoolCache
    fetcher      *PoolStateFetcher
    metrics      *MetricsCollector
    tracker      *AccuracyTracker  // Optional
    config       *Config
}

// Lifecycle
func (ip *ImbalancePredictor) Start() error
func (ip *ImbalancePredictor) Stop() error

// Event handling
func (ip *ImbalancePredictor) OnPendingTx(tx *types.Transaction)

// Prediction API
func (ip *ImbalancePredictor) PredictPoolState(pool common.Address) (*PoolState, error)
func (ip *ImbalancePredictor) GetPoolState(pool common.Address) (*PoolState, bool)
func (ip *ImbalancePredictor) GetTopImbalances(limit int) []*PoolState
```

#### 2. DEXFilter (Transaction Filtering)

```go
type DEXFilter struct {
    routers     map[common.Address]bool
    swapSigs    map[string]bool
    metrics     *FilterMetrics
}

func (f *DEXFilter) IsSwapTransaction(tx *types.Transaction) bool
func (f *DEXFilter) ParseSwap(tx *types.Transaction) (*PendingSwap, error)
func (f *DEXFilter) UpdateRouters(routers []common.Address)
```

#### 3. PoolSimulator (CPMM Simulation)

```go
type PoolSimulator struct {
    stateDB  *state.StateDB
}

func (ps *PoolSimulator) SimulatePendingSwaps(
    pool *PoolState,
    swaps []*PendingSwap,
) (*PoolState, error)

func (ps *PoolSimulator) calculateSwapOutput(
    amountIn, reserveIn, reserveOut *big.Int,
) *big.Int
```

#### 4. ImbalanceDetector (Scoring)

```go
type ImbalanceDetector struct {
    minThreshold float64
    minProfit    *big.Int
}

func (id *ImbalanceDetector) DetectImbalance(
    current, predicted *PoolState,
) *PriceImpact

func (id *ImbalanceDetector) calculateConfidence(
    swaps []*PendingSwap,
) float64
```

#### 5. PoolCache (LRU Cache)

```go
type PoolCache struct {
    cache   *lru.Cache
    mu      sync.RWMutex
    maxSize int
}

func (pc *PoolCache) Get(pool common.Address) (*PoolState, bool)
func (pc *PoolCache) Set(pool common.Address, state *PoolState)
func (pc *PoolCache) Stats() CacheStats
```

---

## 4. Data Flow Architecture

### Prediction Generation Flow

```
┌────────────────────────────────────────────────────────────────────┐
│  1. Mempool Event                                                   │
└────────────────────────────────────────────────────────────────────┘
                              │
                              │ Swap transaction arrives
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  2. DEX Filter (100 ns)                                             │
│     - Check if tx.To() in router whitelist (O(1))                  │
│     - Check if method signature in swap list (O(1))                │
│     - Decision: PASS (is swap) / REJECT (not swap)                 │
└────────────────────────────────────────────────────────────────────┘
                              │ PASS (is swap)
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  3. Parse Swap (1 μs)                                               │
│     - Extract: pool, tokenIn, tokenOut, amountIn, gasPrice        │
│     - Store as PendingSwap struct                                  │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  4. Cache Lookup (1 μs)                                             │
│     - Check if PoolState exists in cache for pool address          │
│     - If HIT: Add PendingSwap to existing state                    │
│     - If MISS: Fetch current state from StateDB (10-50 ms)         │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  5. Pool State Simulation (10-50 μs)                                │
│     - Sort pending swaps by gasPrice descending                     │
│     - For each swap:                                                │
│       • Calculate amountOut using CPMM formula                      │
│       • Update reserves (reserve_in += amountIn, reserve_out -= amountOut) │
│     - Return predicted future state                                 │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  6. Imbalance Detection (10 μs)                                     │
│     - Calculate price: reserve1 / reserve0                          │
│     - Price change %: (predicted - current) / current              │
│     - Imbalance score: abs(priceChange) * 10 (capped at 100)      │
│     - Confidence score: f(pendingTxCount, totalGas, freshness)     │
│     - Arbitrage profit estimate: priceDiff * liquidityDepth * 0.7  │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  7. Cache Update (1 μs)                                             │
│     - Update PoolState in cache with predicted values               │
│     - Set TTL = 3 seconds (prediction window)                       │
│     - Emit metrics (prediction count, latency, score)              │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  8. RPC API Access (<1 ms)                                          │
│     - External client calls: imbalance_getPoolImbalance(pool)      │
│     - Retrieve PoolState from cache (or trigger new prediction)    │
│     - Serialize to JSON and return                                  │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ Client Receives  │
                    │  Prediction      │
                    └──────────────────┘

Total Latency: ~50-100 μs (if cache HIT), ~10-50 ms (if cache MISS)
```

### WebSocket Subscription Flow

```
┌────────────────────────────────────────────────────────────────────┐
│  1. Client Subscribes                                               │
│     eth_subscribeImbalances(minImbalanceScore: 50)                 │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  2. Subscription Created                                            │
│     - Store subscription: map[subscriptionID]chan *PoolState       │
│     - Filter: minImbalanceScore = 50                                │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  3. Prediction Pipeline (continuous)                                │
│     - For each new prediction:                                      │
│       • If imbalanceScore >= 50:                                    │
│         → Send to subscription channel                              │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  4. WebSocket Push                                                  │
│     - Serialize PoolState to JSON                                   │
│     - Push to client over WebSocket connection                      │
│     - Rate limit: Max 100 events/sec per client                     │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ Client Receives  │
                    │  Real-time Event │
                    └──────────────────┘
```

---

## 5. Deployment Architecture

### Production Deployment (Single-Node)

```
┌──────────────────────────────────────────────────────────────────────┐
│                          AWS/GCP Cloud                                │
│                                                                        │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Load Balancer (ALB/GCLB)                                       │  │
│  │  - TLS termination                                              │  │
│  │  - Health checks (RPC ping)                                     │  │
│  └───────────────────────────┬────────────────────────────────────┘  │
│                               │ HTTPS / WSS                           │
│                               ▼                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  BSC Node Instance (EC2/Compute Engine)                         │  │
│  │  Instance Type: c5.4xlarge (16 vCPU, 32 GB RAM, 2 TB NVMe)     │  │
│  │                                                                  │  │
│  │  ┌──────────────────────────────────────────────────────────┐  │  │
│  │  │  BSC Client Process                                       │  │  │
│  │  │  - Port 8545: HTTP RPC                                    │  │  │
│  │  │  - Port 8546: WebSocket RPC                               │  │  │
│  │  │  - Port 30303: devp2p (P2P)                               │  │  │
│  │  │  - Port 6060: Metrics (Prometheus)                        │  │  │
│  │  │                                                            │  │  │
│  │  │  [Imbalance Prediction Engine enabled]                    │  │  │
│  │  │  --imbalance-prediction.enabled=true                       │  │  │
│  │  │  --imbalance-prediction.rollout-percent=100                │  │  │
│  │  └──────────────────────────────────────────────────────────┘  │  │
│  │                                                                  │  │
│  │  Data Volumes:                                                   │  │
│  │  - /data/bsc: 2 TB NVMe SSD (blockchain data, fast sync)        │  │
│  │  - /logs: 100 GB (structured logs, 7-day retention)             │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                               │                                       │
│                               │ Metrics, Logs, Alerts                │
│                               ▼                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Monitoring Stack                                               │  │
│  │                                                                  │  │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────┐  │  │
│  │  │  Prometheus      │  │  Grafana         │  │ PagerDuty   │  │  │
│  │  │  (Managed)       │  │  (Managed)       │  │ (Alerting)  │  │  │
│  │  │  - Metrics DB    │→ │  - Dashboards    │→ │ - On-call   │  │  │
│  │  │  - 30-day retain │  │  - Visualizations│  │ - Escalation│  │  │
│  │  └──────────────────┘  └──────────────────┘  └─────────────┘  │  │
│  │                                                                  │  │
│  │  ┌──────────────────────────────────────────┐                   │  │
│  │  │  TimescaleDB (Optional, Sprint 3)        │                   │  │
│  │  │  - Accuracy tracking storage              │                   │  │
│  │  │  - 30-day retention                       │                   │  │
│  │  └──────────────────────────────────────────┘                   │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### High-Availability Deployment (Future)

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Multi-Region Setup                             │
│                                                                        │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Global Load Balancer (Route 53, Traffic Manager)              │  │
│  │  - Geo-routing: Americas → us-east-1, Asia → ap-southeast-1   │  │
│  │  - Health checks: Failover if region down                      │  │
│  └───────────────────────────┬────────────────────────────────────┘  │
│                               │                                       │
│            ┌──────────────────┴──────────────────┐                   │
│            │                                      │                   │
│            ▼                                      ▼                   │
│  ┌──────────────────────┐              ┌──────────────────────┐     │
│  │  Region 1: us-east-1 │              │ Region 2: ap-southeast-1 │  │
│  │                       │              │                         │  │
│  │  [3x BSC Nodes]       │              │  [3x BSC Nodes]         │  │
│  │  - Active-Active      │              │  - Active-Active        │  │
│  │  - Load balanced      │              │  - Load balanced        │  │
│  │  - Shared Redis cache │              │  - Shared Redis cache   │  │
│  └──────────────────────┘              └──────────────────────┘     │
│                                                                        │
│  Shared State: Redis ElastiCache (Global Datastore)                  │
│  - Cross-region replication                                           │
│  - Pool state cache shared across regions                             │
│  - Eventual consistency acceptable (3-sec TTL)                        │
└────────────────────────────────────────────────────────────────────────┘
```

### Deployment Configuration

```yaml
# Terraform configuration
resource "aws_instance" "bsc_prediction_node" {
  instance_type = "c5.4xlarge"  # 16 vCPU, 32 GB RAM
  ami           = "ami-ubuntu-22.04"

  block_device_mappings {
    device_name = "/dev/sda1"
    volume_size = 2048  # 2 TB NVMe SSD
    volume_type = "gp3"
    iops        = 16000
    throughput  = 1000
  }

  user_data = <<-EOF
    #!/bin/bash
    # Install BSC client
    wget https://github.com/bnb-chain/bsc/releases/download/v1.6.3/geth-linux-amd64
    chmod +x geth-linux-amd64
    mv geth-linux-amd64 /usr/local/bin/geth

    # Start BSC with prediction engine
    geth \
      --config /etc/bsc/config.toml \
      --datadir /data/bsc \
      --http \
      --http.addr 0.0.0.0 \
      --http.port 8545 \
      --http.api eth,net,web3,imbalance \
      --ws \
      --ws.addr 0.0.0.0 \
      --ws.port 8546 \
      --ws.api eth,net,web3,imbalance \
      --metrics \
      --metrics.addr 0.0.0.0 \
      --metrics.port 6060 \
      --imbalance-prediction.enabled=true \
      --imbalance-prediction.rollout-percent=100
  EOF

  tags = {
    Name = "bsc-prediction-node"
    Environment = "production"
  }
}

resource "aws_lb" "bsc_api" {
  name               = "bsc-prediction-lb"
  load_balancer_type = "application"
  subnets            = [aws_subnet.public_a.id, aws_subnet.public_b.id]

  enable_http2 = true
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.bsc_api.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = aws_acm_certificate.bsc_api.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.bsc_rpc.arn
  }
}
```

---

## 6. Security Architecture

### Security Layers

```
┌────────────────────────────────────────────────────────────────────┐
│  Layer 1: Network Security                                          │
│  - VPC isolation (private subnets for BSC nodes)                   │
│  - Security groups: Allow only 443 (HTTPS), 8546 (WSS)            │
│  - DDoS protection (AWS Shield, Cloudflare)                        │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  Layer 2: TLS/HTTPS Encryption                                      │
│  - TLS 1.2+ only (strong ciphers)                                  │
│  - Certificate from Let's Encrypt / AWS ACM                         │
│  - HSTS enabled (Strict-Transport-Security header)                 │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  Layer 3: Application Security (RPC API)                            │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Rate Limiting (Token Bucket)                                 │  │
│  │  - Public: 100 req/min per IP                                 │  │
│  │  - Premium (future): 1000 req/min with API key                │  │
│  │  - Return 429 Too Many Requests if exceeded                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Input Validation                                             │  │
│  │  - Pool address: Valid Ethereum address format                │  │
│  │  - Limit param: 1 <= limit <= 100                             │  │
│  │  - MinScore: 0.0 <= score <= 100.0                            │  │
│  │  - Sanitize all inputs (prevent injection)                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Authentication (Optional, Future)                            │  │
│  │  - X-API-Key header for premium tier                          │  │
│  │  - Keys stored encrypted (bcrypt)                             │  │
│  │  - Key rotation every 90 days                                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  Layer 4: Code Security                                             │
│  - SAST: Snyk, gosec (CI/CD gates)                                 │
│  - Dependency scanning: Dependabot                                  │
│  - Secret scanning: No credentials in code                          │
│  - Code review: 2 approvals (1 senior)                             │
└────────────────────────────────────────────────────────────────────┘
```

### Threat Model

| Threat | Attack Vector | Impact | Mitigation |
|--------|--------------|--------|------------|
| **DoS via High Request Rate** | Flood API with requests | Service degradation | Rate limiting (100 req/min), load balancer, caching |
| **Mempool Spam** | Submit fake high-gas swaps | Wrong predictions | Gas price filtering (only >5 gwei), mempool validation |
| **Information Leakage** | Scrape predictions for profit | Competitive disadvantage | Public API (no PII), rate limiting, fair access |
| **RPC Injection** | Malicious parameters | Data breach, code execution | Input validation, sanitization, parameterized queries |
| **Man-in-the-Middle** | Intercept API traffic | Data theft | TLS 1.2+, HSTS, certificate pinning |
| **Insider Threat** | Privileged access abuse | Data manipulation | Access logs, audit trails, principle of least privilege |

### Security Controls Checklist

- [ ] **Network**: VPC isolation, security groups configured
- [ ] **Encryption**: TLS 1.2+ enforced, Let's Encrypt certificate
- [ ] **Rate Limiting**: 100 req/min per IP implemented
- [ ] **Input Validation**: All parameters validated and sanitized
- [ ] **Authentication**: API key infrastructure (optional tier)
- [ ] **Audit Logging**: All API calls logged with IP, timestamp, parameters
- [ ] **Dependency Scanning**: Snyk integrated in CI/CD
- [ ] **Secret Management**: No credentials in code, use env vars
- [ ] **Incident Response**: Runbook created, on-call rotation setup
- [ ] **External Audit**: $25K budget, schedule for Sprint 3

---

## 7. Observability Architecture

### Metrics (Prometheus)

```yaml
Prediction Metrics:
  imbalance_predictions_total:
    Type: Counter
    Labels: [pool_type, dex_router]
    Description: Total predictions made

  imbalance_score_histogram:
    Type: Histogram
    Buckets: [0, 20, 40, 60, 80, 100]
    Description: Distribution of imbalance scores

  prediction_latency_seconds:
    Type: Histogram
    Buckets: [0.001, 0.01, 0.05, 0.1, 0.2, 0.5]
    Description: Time to generate prediction

  prediction_accuracy_gauge:
    Type: Gauge
    Labels: [pool, tier]
    Description: Real-time accuracy percentage

Performance Metrics:
  pool_state_update_duration_seconds:
    Type: Histogram
    Description: Pool state update time

  cache_hit_rate:
    Type: Gauge
    Description: Cache effectiveness (%)

  mempool_swaps_detected_total:
    Type: Counter
    Labels: [dex_router]
    Description: DEX swaps detected in mempool

  bsc_node_cpu_usage_percent:
    Type: Gauge
    Description: CPU overhead from prediction engine

API Metrics:
  api_requests_total:
    Type: Counter
    Labels: [method, status_code]
    Description: Total API requests

  api_response_time_seconds:
    Type: Histogram
    Labels: [method]
    Description: API latency

  api_errors_total:
    Type: Counter
    Labels: [method, error_type]
    Description: API error count

  rate_limit_hits_total:
    Type: Counter
    Labels: [ip_address]
    Description: Rate limiting triggers
```

### Grafana Dashboards

**Dashboard 1: Prediction Performance**
- Predictions per second (time series)
- Average imbalance score (gauge)
- P50/P95/P99 prediction latency (graph)
- Cache hit rate (gauge)
- Top 10 pools by prediction count (table)

**Dashboard 2: Accuracy Tracking**
- Overall accuracy % (time series)
- Accuracy by pool (heatmap)
- Accuracy by confidence bucket (histogram)
- False positive/negative rates (gauge)
- Prediction error distribution (histogram)

**Dashboard 3: API Health**
- Requests per minute (time series)
- Error rate % (time series)
- P50/P95/P99 API latency (graph)
- Rate limit hits per IP (table)
- Top API consumers (table)

**Dashboard 4: System Health**
- BSC node CPU/memory usage (time series)
- Mempool size (gauge)
- Pending swap count (gauge)
- Pool state cache size (gauge)
- Disk I/O, network bandwidth (time series)

### Logging Strategy

```go
// Structured logging with zerolog
log.Info().
    Str("pool", pool.Hex()).
    Float64("imbalance_score", score).
    Float64("confidence", confidence).
    Int("pending_swaps", len(swaps)).
    Msg("High imbalance detected")

log.Error().
    Err(err).
    Str("pool", pool.Hex()).
    Msg("Failed to simulate pool state")
```

**Log Levels**:
- **DEBUG**: Detailed prediction pipeline steps
- **INFO**: High imbalance detections, cache events
- **WARN**: Rate limiting triggered, cache misses >90%
- **ERROR**: Simulation failures, state fetch errors
- **FATAL**: Prediction engine crashes

**Log Retention**: 7 days (CloudWatch Logs, 100 GB capacity)

### Alerting Rules

```yaml
# Prometheus Alert Manager

groups:
  - name: prediction_engine
    rules:
      - alert: PredictionAccuracyLow
        expr: prediction_accuracy_gauge < 60
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Prediction accuracy below 60%"
          description: "Accuracy: {{ $value }}%. Consider upgrading to Tier 2."

      - alert: PredictionLatencyHigh
        expr: histogram_quantile(0.95, prediction_latency_seconds) > 0.2
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Prediction p95 latency >200ms"
          description: "Current: {{ $value }}s. Optimize or reduce tracked pools."

      - alert: APIDown
        expr: up{job="bsc_prediction_api"} == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Prediction API is down"
          description: "API unreachable for 5+ minutes. Page on-call."

      - alert: CacheHitRateLow
        expr: cache_hit_rate < 50
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "Cache hit rate <50%"
          description: "Excessive cache eviction. Consider increasing capacity."

      - alert: RateLimitExceeded
        expr: rate(rate_limit_hits_total[5m]) > 100
        for: 10m
        labels:
          severity: info
        annotations:
          summary: "High rate limiting activity"
          description: "Potential DoS attempt or legitimate high traffic."
```

---

## 8. Performance & Scalability

### Performance Budgets

| Component | Budget | Measurement | Target |
|-----------|--------|-------------|--------|
| **DEX Filter** | <1ms per tx | Benchmark | <1000 ns/op |
| **Pool Simulation** | <50ms for 10 swaps | Benchmark | <50ms p95 |
| **Cache Lookup** | <10ms | Histogram | <10ms p95 |
| **Total Prediction** | <100ms | Histogram | <100ms p95 |
| **RPC API** | <200ms | Histogram | <200ms p95 |
| **CPU Overhead** | <5% | Gauge | <5% of BSC node CPU |
| **Memory Usage** | <500MB | Gauge | <500MB for 1000 pools |

### Scalability Characteristics

#### Horizontal Scalability
- **Current**: Single BSC node
- **Future**: Multi-node with shared Redis cache
- **Bottleneck**: BSC node itself (blockchain sync), not prediction engine
- **Scaling**: Add more BSC nodes behind load balancer, share cache via Redis

#### Vertical Scalability
- **CPU**: Linear scaling with pool count (2% CPU per 1000 pools)
- **Memory**: Linear scaling (500 MB per 1000 pools)
- **Disk**: No significant impact (cache is in-memory)
- **Network**: Moderate (RPC API traffic)

#### Capacity Planning

| Metric | Current (MVP) | 6 Months | 12 Months |
|--------|--------------|----------|-----------|
| **Tracked Pools** | 1000 | 2000 | 5000 |
| **API Requests/Day** | 1M | 5M | 10M |
| **Mempool Throughput** | 100-500 tx/sec | 500-1000 tx/sec | 1000+ tx/sec |
| **Memory Usage** | 500 MB | 1 GB | 2.5 GB |
| **CPU Overhead** | <5% | <10% | <15% |
| **Infrastructure Cost** | $5K/month | $10K/month | $20K/month |

### Performance Optimization Strategies

1. **Caching**: LRU cache with 3-second TTL reduces state fetches by 80%+
2. **Lazy Evaluation**: Only simulate pools with pending swaps
3. **Batch Processing**: Group similar swaps for parallel simulation (future)
4. **Bloom Filters**: Fast DEX router lookup (O(1) probabilistic)
5. **Goroutine Pools**: Limit concurrent simulations to avoid CPU spikes
6. **big.Int Pooling**: Reuse big.Int allocations to reduce GC pressure

---

## 9. Risk Matrix

### Technical Risks

| Risk | Probability | Impact | Severity | Mitigation | Owner |
|------|------------|--------|----------|------------|-------|
| **Prediction accuracy <70%** | LOW | HIGH | 🟡 MEDIUM | Sprint 0 validation (10K samples) | Tech Lead |
| **BSC performance degradation >5%** | MEDIUM | CRITICAL | 🔴 HIGH | Load testing, profiling, <5% budget | Backend Eng |
| **Cache stampede** | MEDIUM | MEDIUM | 🟡 MEDIUM | Cache locking, rate limiting per pool | Backend Eng |
| **Memory leak** | LOW | MEDIUM | 🟡 MEDIUM | pprof monitoring, automated restarts | DevOps |
| **State synchronization lag** | MEDIUM | MEDIUM | 🟡 MEDIUM | StateDB caching, stale data detection | Backend Eng |

### Operational Risks

| Risk | Probability | Impact | Severity | Mitigation | Owner |
|------|------------|--------|----------|------------|-------|
| **High RPC load (>10K req/sec)** | MEDIUM | MEDIUM | 🟡 MEDIUM | Caching (1-sec TTL), rate limiting, scale horizontally | DevOps |
| **Mempool spike (1000+ tx/sec)** | MEDIUM | MEDIUM | 🟡 MEDIUM | Efficient filtering (<1ms), goroutine pools | Backend Eng |
| **Node crash during prediction** | LOW | HIGH | 🟡 MEDIUM | Graceful degradation, prediction engine in separate goroutine | Backend Eng |
| **Monitoring failure** | LOW | MEDIUM | 🟡 MEDIUM | Redundant monitoring (Prometheus + CloudWatch) | DevOps |

### Security Risks

| Risk | Probability | Impact | Severity | Mitigation | Owner |
|------|------------|--------|----------|------------|-------|
| **DoS via high request rate** | HIGH | MEDIUM | 🟡 MEDIUM | Rate limiting (100 req/min), load balancer, WAF | Security + DevOps |
| **Mempool spam attacks** | MEDIUM | LOW | 🟢 LOW | High-gas filtering (>5 gwei), mempool validation | Backend Eng |
| **Security vulnerability in audit** | MEDIUM | HIGH | 🟡 MEDIUM | External audit ($25K), internal review first | Security + Tech Lead |

---

## 10. Quality Attributes

### Quality Attribute Scenarios

#### 1. Performance
- **Scenario**: Under peak load (500 tx/sec mempool), generate prediction for top 100 pools
- **Response**: p95 latency <100ms, p99 <200ms
- **Measure**: Prometheus histogram `prediction_latency_seconds`

#### 2. Availability
- **Scenario**: Prediction engine crashes due to memory leak
- **Response**: BSC node continues normal operation, predictions unavailable but node stable
- **Measure**: BSC node uptime 99.9%, prediction uptime 99.5%

#### 3. Scalability
- **Scenario**: Pool count increases from 1000 → 5000
- **Response**: CPU overhead increases linearly (<10% for 5000 pools), memory <2.5 GB
- **Measure**: `bsc_node_cpu_usage_percent`, `pool_cache_size`

#### 4. Accuracy
- **Scenario**: High-MEV environment (many reordered transactions)
- **Response**: Tier 1 accuracy degrades to 60-65%, trigger upgrade to Tier 2
- **Measure**: `prediction_accuracy_gauge`, alert if <65% for 1 hour

#### 5. Security
- **Scenario**: Attacker floods API with 10K req/sec
- **Response**: Rate limiter blocks requests, service remains available for legitimate users
- **Measure**: `rate_limit_hits_total`, 429 error rate

#### 6. Maintainability
- **Scenario**: BSC core upgrades to new version with txpool refactoring
- **Response**: Prediction engine integration tests catch breaking changes, fix in <1 week
- **Measure**: CI test pass rate, upgrade success rate

---

## Architecture Review Sign-Off

### Design Principles Validation

| Principle | Compliance | Evidence |
|-----------|-----------|----------|
| **Simplicity over Complexity** | ✅ PASS | Start with Tier 1 (gas price), defer ML/MEV |
| **Evolutionary Architecture** | ✅ PASS | Pluggable interfaces, feature flags, cache abstraction |
| **Data Sovereignty** | ⚠️ PARTIAL | Tight coupling with BSC state (acceptable for performance) |
| **Observability First** | ✅ PASS | Prometheus metrics, structured logs, Grafana dashboards |

### Quality Gates Status

| Gate | Criteria | Status | Evidence |
|------|----------|--------|----------|
| **HLD approved** | Architecture review completed, design principles validated | ⏳ PENDING REVIEW | This document |
| **TCO within budget** | Infrastructure and operational costs estimated | ✅ PASS | $301K Year 1 |
| **Team capability aligned** | Skills gaps identified, mitigation planned | ✅ PASS | Training in Sprint 0 |
| **Observability designed** | Metrics, logs, traces defined | ✅ PASS | Section 7 |

### Reviewers

- [ ] **Tech Lead**: Overall architecture alignment
- [ ] **Senior Backend Engineer**: Go implementation feasibility, performance estimates
- [ ] **BSC Core Team**: Impact on BSC client, integration approach
- [ ] **Security Engineer**: Threat model, security controls
- [ ] **DevOps Engineer**: Deployment strategy, monitoring

### Approval Status

**Status**: ⏳ **PENDING REVIEW**
**Review Date**: November 18, 2025
**Approval Required**: Tech Lead + 2 Senior Engineers + BSC Core Team

---

## References

- **ADRs**: `docs/adr/ADR-001` through `ADR-005`
- **Technical Feasibility Report**: `docs/TECHNICAL_FEASIBILITY_REPORT.md`
- **Sprint Plan**: `TECHNICAL_SPRINT_PLAN.md`
- **Phase 1 Handoff**: `docs/PHASE_1_HANDOFF.md`
- **C4 Model**: https://c4model.com/
- **BSC Repository**: https://github.com/bnb-chain/bsc

---

**Document Version**: 1.0
**Last Updated**: 2025-11-13
**Next Review**: After Sprint 0 Go/No-Go Decision
**Status**: DRAFT - Awaiting Architecture Review

Co-Authored-By: Claude <noreply@anthropic.com>
