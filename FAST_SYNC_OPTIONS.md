# Fast Sync Options for BSC Imbalance Engine

## The Problem

Full sync from genesis takes days/weeks and downloads ~4TB of data. Here are 3 better alternatives:

---

## ⚡ OPTION 1: Use BSC Snapshot (RECOMMENDED - 1TB, ~3 hours)

Download a recent state snapshot instead of syncing from genesis.

### Step-by-Step

```bash
# Stop current node
pkill -f "geth --config"

# Install aria2 for fast downloads
sudo apt-get install -y aria2

# Download the snapshot fetch script
wget https://raw.githubusercontent.com/bnb-chain/bsc-snapshots/main/dist/fetch-snapshot.sh
chmod +x fetch-snapshot.sh

# Download PRUNED snapshot (~1TB vs ~3.8TB full)
# Latest: mainnet-geth-pbss-20250906-pruneancient
bash fetch-snapshot.sh -d -c -D ./bsc-data mainnet-geth-pbss-20250906-pruneancient

# Once download completes, restart node
./build/bin/geth --config config.toml --datadir ./bsc-data --http --cache 4096 --http.addr 127.0.0.1 >> geth.log 2>&1 &
```

**Benefits:**
- ✅ Full mempool access (required for imbalance engine)
- ✅ Only ~1TB storage (vs ~4TB full snapshot)
- ✅ Ready in hours, not days
- ✅ All state data available immediately

**Download Time:** ~3-6 hours (depending on internet speed)

---

## 🌐 OPTION 2: Hybrid - External RPC + Local Mempool (FASTEST - 10 minutes)

Use public BSC RPC for state queries, run minimal local node just for mempool monitoring.

### Architecture

```
┌─────────────────┐        ┌──────────────────┐
│  Public BSC RPC │◄───────┤  Pool State Data │
│  (BscScan/etc)  │        │  eth_call        │
└─────────────────┘        └──────────────────┘
                                    ▲
                                    │
                            ┌───────┴────────┐
                            │ Imbalance      │
                            │ Engine         │
                            └───────┬────────┘
                                    │
                                    ▼
┌─────────────────┐        ┌──────────────────┐
│  Local BSC Node │◄───────┤  Mempool Data    │
│  (Minimal Sync) │        │  Pending Txs     │
└─────────────────┘        └──────────────────┘
```

### Implementation

1. **Use Public RPC Endpoints:**
   - BscScan: https://bsc-dataseed.bnbchain.org
   - QuickNode: https://docs.bnbchain.org/bnb-smart-chain/developers/rpc
   - Ankr: https://rpc.ankr.com/bsc

2. **Modify Imbalance Engine** to use external RPC for `eth_call` (pool reserves)

3. **Run Local Node** with minimal sync just for mempool access

**Benefits:**
- ✅ No sync required for state data
- ✅ Minimal storage (<10GB)
- ✅ Ready in minutes
- ✅ Still get mempool access

**Limitations:**
- ⚠️ Depends on external RPC availability
- ⚠️ May have rate limits
- ⚠️ Slight latency increase for state queries

---

## 🔄 OPTION 3: Pruned Mode (Current - Reduces storage by 70%)

Continue current sync but enable aggressive pruning to reduce storage.

### Stop Node and Enable Pruning

```bash
# Stop node
pkill -f "geth --config"

# Restart with pruning enabled
./build/bin/geth \
  --config config.toml \
  --datadir ./bsc-data \
  --http \
  --syncmode snap \
  --cache 4096 \
  --gcmode full \
  --state.scheme path \
  --http.addr 127.0.0.1 \
  >> geth.log 2>&1 &
```

**Storage Comparison:**
- Archive mode: ~4TB
- Full mode: ~1.5TB
- Pruned mode: ~800GB

**Benefits:**
- ✅ Reduces storage by 70%
- ✅ Full mempool access
- ✅ No external dependencies

**Limitations:**
- ⚠️ Still takes days to sync
- ⚠️ Only keeps recent state

---

## 📊 Comparison Table

| Option | Storage | Sync Time | Mempool | State Data | Best For |
|--------|---------|-----------|---------|------------|----------|
| **Snapshot** | ~1TB | 3-6 hours | ✅ Full | ✅ Full | Production |
| **Hybrid RPC** | <10GB | 10 mins | ✅ Full | ⚠️ External | Testing |
| **Pruned Sync** | ~800GB | Days | ✅ Full | ✅ Full | Long-term |

---

## 🎯 Recommended Approach

**For immediate testing:**
→ **Use OPTION 2** (Hybrid - External RPC)

**For production:**
→ **Use OPTION 1** (BSC Snapshot)

---

## Implementation: Hybrid Mode (OPTION 2)

Here's how to quickly set up the hybrid mode:

### 1. Stop Current Node
```bash
pkill -f "geth --config"
```

### 2. Modify Imbalance Engine to Use External RPC

Create a dual-client setup:
- **Local node**: Mempool access only
- **External RPC**: State queries (pool reserves)

### 3. Update Client Configuration

Add environment variable support:

```bash
export BSC_STATE_RPC="https://bsc-dataseed.bnbchain.org"
export BSC_MEMPOOL_RPC="http://127.0.0.1:8545"
```

### 4. Start Minimal Local Node (No Sync Required)

```bash
# Start node with mempool enabled but minimal sync
./build/bin/geth \
  --datadir ./bsc-data-minimal \
  --http \
  --http.api eth,net,web3,txpool,imbalance \
  --http.addr 127.0.0.1 \
  --http.port 8545 \
  --maxpeers 50 \
  --syncmode snap \
  >> geth-minimal.log 2>&1 &
```

### 5. Test Immediately

```bash
# The engine will:
# - Query mempool from local node (fast)
# - Query pool states from external RPC (reliable)
./build/bin/imbalance-client --test
```

---

## Public BSC RPC Endpoints (Free)

```bash
# BNB Chain Official (Rate limit: varies)
https://bsc-dataseed.bnbchain.org
https://bsc-dataseed1.bnbchain.org
https://bsc-dataseed2.bnbchain.org

# Ankr (Rate limit: 500 req/sec)
https://rpc.ankr.com/bsc

# Chainstack (Free tier)
https://bsc-mainnet.core.chainstack.com

# Public Node
https://bsc-rpc.publicnode.com
```

---

## Next Steps

Choose your preferred option and let me know - I can help implement any of these approaches!
