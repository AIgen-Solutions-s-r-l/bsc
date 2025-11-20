# BSC Imbalance Prediction Engine - Integration Guide

**Version:** 1.0.0
**Last Updated:** December 6, 2025

This guide helps developers integrate the Imbalance Prediction Engine into their BSC node and applications.

---

## Table of Contents

1. [Node Integration](#node-integration)
2. [Application Integration](#application-integration)
3. [Trading Bot Integration](#trading-bot-integration)
4. [Monitoring & Alerts](#monitoring--alerts)
5. [Troubleshooting](#troubleshooting)

---

## Node Integration

### Step 1: Enable the Imbalance Predictor

Edit your BSC node configuration (`config.toml`):

```toml
[Imbalance]
# Enable the imbalance predictor
Enabled = true

# Cache configuration
CacheSize = 1000

# Prediction window (in seconds)
PredictionWindow = 3

# Pool state update interval (in seconds)
UpdateInterval = 1

# Minimum confidence threshold (percentage)
MinConfidence = 70.0

# Enable Prometheus metrics
EnableMetrics = true

# Security settings
[Imbalance.Security]
EnableRateLimiting = true
MaxRequestsPerMin = 60
GlobalMaxRPS = 1000
EnableAPIKeys = false
EnableThrottling = true
MaxConcurrentReqs = 100
MaxSubscriptions = 10
```

### Step 2: Enable RPC/WebSocket APIs

Start your BSC node with the imbalance namespace:

**HTTP RPC**:
```bash
./geth --config config.toml \
  --http \
  --http.api eth,net,web3,imbalance \
  --http.port 8545 \
  --http.addr 0.0.0.0 \
  --http.corsdomain "*"
```

**WebSocket** (for subscriptions):
```bash
./geth --config config.toml \
  --ws \
  --ws.api eth,net,web3,imbalance \
  --ws.port 8546 \
  --ws.addr 0.0.0.0 \
  --ws.origins "*"
```

**Both**:
```bash
./geth --config config.toml \
  --http --http.api eth,net,web3,imbalance --http.port 8545 \
  --ws --ws.api eth,net,web3,imbalance --ws.port 8546
```

### Step 3: Verify Installation

Check that the API is accessible:

```bash
curl -X POST http://localhost:8545 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "imbalance_getAccuracy",
    "params": [],
    "id": 1
  }'
```

Expected response:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "totalPredictions": 1000,
    "successfulPredictions": 724,
    "accuracyPercent": 72.4,
    ...
  }
}
```

### Step 4: Monitor Metrics

Access Prometheus metrics at:
```
http://localhost:6060/debug/metrics/prometheus
```

Key metrics to monitor:
- `predictor_latency_e2e`: End-to-end latency
- `predictor_cache_hits`: Cache hit rate
- `imbalance_predictions_total`: Total predictions
- `security_requests_blocked`: Blocked requests

---

## Application Integration

### JavaScript/TypeScript

**Installation**:
```bash
npm install web3
```

**Basic Usage**:
```typescript
import Web3 from 'web3';

const web3 = new Web3('http://localhost:8545');

// Get pool imbalance
async function getPoolImbalance(poolAddress: string) {
  const result = await web3.eth.extend({
    methods: [{
      name: 'getPoolImbalance',
      call: 'imbalance_getPoolImbalance',
      params: 1,
      inputFormatter: [null],
      outputFormatter: null
    }]
  }).getPoolImbalance(poolAddress);

  console.log('Imbalance Score:', result.imbalanceScore + '%');
  console.log('Level:', result.level);
  console.log('Confidence:', result.confidence + '%');

  return result;
}

// Usage
const WBNB_BUSD_POOL = '0x1b96b92314c44b159149f7e0303511fb2fc4774f';
getPoolImbalance(WBNB_BUSD_POOL);
```

**WebSocket Subscription**:
```typescript
const ws = new Web3('ws://localhost:8546');

async function subscribeToPool(poolAddress: string) {
  const subscription = await ws.eth.subscribe('imbalance', {
    poolAddress: poolAddress
  });

  subscription.on('data', (data: any) => {
    console.log('Update:', {
      score: data.imbalanceScore,
      level: data.level,
      actionable: data.isActionable
    });
  });

  subscription.on('error', console.error);

  return subscription;
}

// Usage
subscribeToPool(WBNB_BUSD_POOL);
```

### Python

**Installation**:
```bash
pip install web3
```

**Basic Usage**:
```python
from web3 import Web3

w3 = Web3(Web3.HTTPProvider('http://localhost:8545'))

def get_pool_imbalance(pool_address):
    result = w3.provider.make_request(
        'imbalance_getPoolImbalance',
        [pool_address]
    )

    data = result['result']
    print(f"Imbalance Score: {data['imbalanceScore']}%")
    print(f"Level: {data['level']}")
    print(f"Confidence: {data['confidence']}%")

    return data

# Usage
WBNB_BUSD_POOL = '0x1b96b92314c44b159149f7e0303511fb2fc4774f'
get_pool_imbalance(WBNB_BUSD_POOL)
```

**WebSocket Subscription**:
```python
import asyncio
import websockets
import json

async def subscribe_to_pool(pool_address):
    uri = "ws://localhost:8546"

    async with websockets.connect(uri) as websocket:
        # Subscribe
        subscribe_msg = {
            "jsonrpc": "2.0",
            "method": "imbalance_subscribe",
            "params": ["imbalance", pool_address],
            "id": 1
        }

        await websocket.send(json.dumps(subscribe_msg))

        # Get subscription ID
        response = await websocket.recv()
        print(f"Subscribed: {response}")

        # Listen for updates
        while True:
            message = await websocket.recv()
            data = json.loads(message)

            if 'params' in data:
                result = data['params']['result']
                print(f"Update: {result['imbalanceScore']}% ({result['level']})")

# Usage
WBNB_BUSD_POOL = '0x1b96b92314c44b159149f7e0303511fb2fc4774f'
asyncio.run(subscribe_to_pool(WBNB_BUSD_POOL))
```

### Go

**Basic Usage**:
```go
package main

import (
    "context"
    "fmt"
    "math/big"

    "github.com/ethereum/go-ethereum/common"
    "github.com/ethereum/go-ethereum/rpc"
)

type ImbalanceResponse struct {
    PoolAddress       string   `json:"poolAddress"`
    ImbalanceScore    float64  `json:"imbalanceScore"`
    Level             string   `json:"level"`
    Confidence        float64  `json:"confidence"`
    PendingSwaps      int      `json:"pendingSwaps"`
    IsActionable      bool     `json:"isActionable"`
}

func main() {
    client, err := rpc.Dial("http://localhost:8545")
    if err != nil {
        panic(err)
    }

    poolAddr := "0x1b96b92314c44b159149f7e0303511fb2fc4774f"

    var result ImbalanceResponse
    err = client.Call(&result, "imbalance_getPoolImbalance", poolAddr)
    if err != nil {
        panic(err)
    }

    fmt.Printf("Pool: %s\n", result.PoolAddress)
    fmt.Printf("Score: %.2f%%\n", result.ImbalanceScore)
    fmt.Printf("Level: %s\n", result.Level)
    fmt.Printf("Confidence: %.1f%%\n", result.Confidence)
    fmt.Printf("Actionable: %v\n", result.IsActionable)
}
```

---

## Trading Bot Integration

### Example: Simple Arbitrage Bot

```javascript
const Web3 = require('web3');
const web3 = new Web3('ws://localhost:8546');

const CONFIG = {
  MIN_PROFIT: web3.utils.toWei('0.1', 'ether'), // 0.1 BNB
  MIN_CONFIDENCE: 80, // 80%
  MIN_IMBALANCE: 20, // 20%
};

class ArbitrageBot {
  constructor(poolAddress) {
    this.poolAddress = poolAddress;
    this.subscription = null;
  }

  async start() {
    console.log(`🤖 Starting arbitrage bot for ${this.poolAddress}`);

    this.subscription = await web3.eth.subscribe('imbalance', {
      poolAddress: this.poolAddress
    });

    this.subscription.on('data', this.handleUpdate.bind(this));
    this.subscription.on('error', this.handleError.bind(this));
  }

  async handleUpdate(data) {
    // Check if opportunity meets criteria
    if (!this.isOpportunity(data)) {
      return;
    }

    console.log('\n🚨 OPPORTUNITY DETECTED!');
    console.log('Pool:', data.poolAddress);
    console.log('Score:', data.imbalanceScore + '%');
    console.log('Profit:', web3.utils.fromWei(data.profitOpportunity, 'ether'), 'BNB');
    console.log('Confidence:', data.confidence + '%');

    // Execute arbitrage
    try {
      await this.executeArbitrage(data);
    } catch (error) {
      console.error('Arbitrage execution failed:', error);
    }
  }

  isOpportunity(data) {
    const profit = BigInt(data.profitOpportunity);
    const minProfit = BigInt(CONFIG.MIN_PROFIT);

    return (
      data.isActionable &&
      profit >= minProfit &&
      data.confidence >= CONFIG.MIN_CONFIDENCE &&
      data.imbalanceScore >= CONFIG.MIN_IMBALANCE
    );
  }

  async executeArbitrage(data) {
    // Implement your arbitrage strategy here
    console.log('Executing arbitrage...');

    // Example: Flash loan + swap + repay
    // 1. Get flash loan
    // 2. Swap on imbalanced pool
    // 3. Swap back on another DEX
    // 4. Repay flash loan + keep profit
  }

  handleError(error) {
    console.error('Subscription error:', error);
  }

  stop() {
    if (this.subscription) {
      this.subscription.unsubscribe();
    }
  }
}

// Usage
const bot = new ArbitrageBot('0x1b96b92314c44b159149f7e0303511fb2fc4774f');
bot.start();

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('\n⏹️  Stopping bot...');
  bot.stop();
  process.exit(0);
});
```

---

## Monitoring & Alerts

### Grafana Dashboard

**Step 1: Configure Prometheus**

`prometheus.yml`:
```yaml
scrape_configs:
  - job_name: 'bsc-imbalance'
    static_configs:
      - targets: ['localhost:6060']
    metrics_path: '/debug/metrics/prometheus'
    scrape_interval: 10s
```

**Step 2: Import Dashboard**

Use the following queries in Grafana:

**Prediction Rate**:
```promql
rate(imbalance_predictions_total[1m])
```

**Accuracy**:
```promql
(imbalance_predictions_successful / imbalance_predictions_total) * 100
```

**Latency p95**:
```promql
histogram_quantile(0.95, rate(predictor_latency_e2e_bucket[5m]))
```

**Cache Hit Rate**:
```promql
rate(predictor_cache_hits[1m]) / (rate(predictor_cache_hits[1m]) + rate(predictor_cache_misses[1m])) * 100
```

### Alerting

**Prometheus Alert Rules** (`alerts.yml`):

```yaml
groups:
  - name: imbalance_predictor
    interval: 30s
    rules:
      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(predictor_latency_e2e_bucket[5m])) > 100
        for: 5m
        annotations:
          summary: "Imbalance predictor latency is high"
          description: "p95 latency is {{ $value }}ms (threshold: 100ms)"

      - alert: LowAccuracy
        expr: (imbalance_predictions_successful / imbalance_predictions_total) * 100 < 70
        for: 10m
        annotations:
          summary: "Prediction accuracy below threshold"
          description: "Accuracy is {{ $value }}% (threshold: 70%)"

      - alert: HighErrorRate
        expr: rate(imbalance_errors_total[5m]) > 10
        for: 5m
        annotations:
          summary: "High error rate in imbalance predictor"
          description: "Error rate is {{ $value }} errors/sec"
```

### Slack Alerts

```javascript
const Web3 = require('web3');
const axios = require('axios');

const SLACK_WEBHOOK = 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL';

async function sendSlackAlert(data) {
  await axios.post(SLACK_WEBHOOK, {
    text: `⚠️ *Imbalance Alert*`,
    attachments: [{
      color: data.level === 'critical' ? 'danger' : 'warning',
      fields: [
        { title: 'Pool', value: data.poolAddress, short: false },
        { title: 'Score', value: `${data.imbalanceScore}%`, short: true },
        { title: 'Level', value: data.level.toUpperCase(), short: true },
        { title: 'Confidence', value: `${data.confidence}%`, short: true },
        { title: 'Profit', value: web3.utils.fromWei(data.profitOpportunity, 'ether') + ' BNB', short: true }
      ]
    }]
  });
}

// Subscribe and alert
const ws = new Web3('ws://localhost:8546');
const subscription = await ws.eth.subscribe('imbalance', {
  poolAddress: '0x1b96b92314c44b159149f7e0303511fb2fc4774f'
});

subscription.on('data', (data) => {
  if (data.shouldAlert) {
    sendSlackAlert(data);
  }
});
```

---

## Troubleshooting

### Issue: "predictor not running"

**Cause**: Imbalance predictor is not enabled or failed to start.

**Solution**:
1. Check `config.toml` has `Enabled = true`
2. Check node logs for startup errors
3. Verify RPC namespace includes `imbalance`

### Issue: "pool state not found"

**Cause**: Pool state not yet synced or pool address invalid.

**Solutions**:
1. Wait a few seconds for initial sync
2. Verify pool address is correct
3. Check if pool exists on BSC
4. Increase `CacheSize` in config

### Issue: "rate limit exceeded"

**Cause**: Too many requests from the same IP.

**Solutions**:
1. Implement exponential backoff
2. Use WebSocket subscriptions instead of polling
3. Increase `MaxRequestsPerMin` in config
4. Distribute load across multiple IPs

### Issue: High latency

**Causes**: System overload, low cache hit rate, or network issues.

**Solutions**:
1. Check cache hit rate (target >90%)
2. Increase `CacheSize`
3. Check CPU and memory usage
4. Optimize queries (batch when possible)
5. Check network latency to node

### Issue: Low accuracy

**Causes**: Volatile market conditions, insufficient data, or misconfiguration.

**Solutions**:
1. Check `MinConfidence` setting
2. Wait for more data collection (>1000 predictions)
3. Verify DEX router addresses are correct
4. Check if mempool is properly synchronized

---

## Best Practices

1. **Use WebSocket subscriptions** for real-time monitoring
2. **Implement proper error handling** with exponential backoff
3. **Monitor key metrics** (latency, accuracy, cache hit rate)
4. **Set up alerts** for critical events
5. **Test in testnet first** before production deployment
6. **Keep node updated** to latest BSC version
7. **Secure your API** with rate limiting and API keys
8. **Log all arbitrage attempts** for post-analysis

---

## Support

- **GitHub**: [https://github.com/bnb-chain/bsc](https://github.com/bnb-chain/bsc)
- **Discord**: [https://discord.gg/bnbchain](https://discord.gg/bnbchain)
- **Forum**: [https://forum.bnbchain.org](https://forum.bnbchain.org)

---

**© 2025 BSC Development Team. Licensed under LGPL-3.0.**
