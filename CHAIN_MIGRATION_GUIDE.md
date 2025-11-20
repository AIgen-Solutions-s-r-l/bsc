# Chain Migration Guide

## 🌐 Alternative Chains Configuration

After monitoring BSC for 3-5 days, if results show it's not viable for small traders, here are the prepared configurations to quickly switch to alternative chains.

---

## 🟣 Option 1: Polygon (RECOMMENDED)

### Why Polygon?
- ✅ Lower gas costs (fractions of a cent)
- ✅ Less MEV competition than BSC
- ✅ Large DeFi ecosystem
- ✅ Fast block times (2 seconds)
- ✅ Similar to BSC (easy migration)

### RPC Endpoints
```python
# Public RPCs (Free)
EXTERNAL_RPC = "https://polygon-rpc.com"
# or
EXTERNAL_RPC = "https://rpc-mainnet.matic.network"
# or
EXTERNAL_RPC = "https://polygon-bor-rpc.publicnode.com"
```

### Major DEXes & Pools

**QuickSwap (Uniswap V2 fork)**
```python
POOLS = {
    "WMATIC-USDC": "0x6e7a5FAFcec6BB1e78bAE2A1F0B612012BF14827",
    "WMATIC-USDT": "0x604229c960e5CACF2aaEAc8Be68Ac07BA9dF81c3",
    "WMATIC-DAI": "0x4A35582a710E1F4b2030A3F826DA20BfB6703C09",
    "WMATIC-WETH": "0xadbF1854e5883eB8aa7BAf50705338739e558E5b",
}

DEX_ROUTERS = {
    "QuickSwap": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
}
```

**SushiSwap on Polygon**
```python
POOLS = {
    "WMATIC-USDC": "0xcd353F79d9FADe311fC3119B841e1f456b54e858",
    "WMATIC-USDT": "0xc2755915a85C6f6c1C0F3a86ac8C058F11Caa9C9",
    "WMATIC-WETH": "0xc4e595acDD7d12feC385E5dA5D43160e8A0bAC0E",
}

DEX_ROUTERS = {
    "SushiSwap": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
}
```

### Token Price
```python
MATIC_USD = 0.90  # Update with current price
```

### Configuration Changes

1. Update `scripts/enhanced_tracker.py`:
```python
EXTERNAL_RPC = "https://polygon-rpc.com"
LOCAL_RPC = "http://localhost:8545"  # If running local Polygon node

POOLS = {
    "WMATIC-USDC": "0x6e7a5FAFcec6BB1e78bAE2A1F0B612012BF14827",
    "WMATIC-USDT": "0x604229c960e5CACF2aaEAc8Be68Ac07BA9dF81c3",
    "WMATIC-DAI": "0x4A35582a710E1F4b2030A3F826DA20BfB6703C09",
    "WMATIC-WETH": "0xadbF1854e5883eB8aa7BAf50705338739e558E5b",
}

DEX_ROUTERS = {
    "QuickSwap": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
    "SushiSwap": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
}

MATIC_USD = 0.90
```

---

## 🔵 Option 2: Arbitrum

### Why Arbitrum?
- ✅ True Layer 2 scaling
- ✅ Lower fees than mainnet
- ✅ Growing DeFi ecosystem
- ✅ Ethereum-compatible

### RPC Endpoints
```python
EXTERNAL_RPC = "https://arb1.arbitrum.io/rpc"
# or
EXTERNAL_RPC = "https://arbitrum-one-rpc.publicnode.com"
```

### Major DEXes & Pools

**Uniswap V3 on Arbitrum**
```python
# Note: Uniswap V3 uses different pool structure
# Would need to adapt code for concentrated liquidity

POOLS = {
    "WETH-USDC": "0xC31E54c7a869B9FcBEcc14363CF510d1c41fa443",  # 0.05% fee
    "WETH-USDT": "0x641C00A822e8b671738d32a431a4Fb6074E5c79d",  # 0.05% fee
    "WETH-ARB": "0xC6F780497A95e246EB9449f5e4770916DCd6396A",   # 0.05% fee
}

DEX_ROUTERS = {
    "Uniswap V3": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
}
```

**Camelot (Native Arbitrum DEX)**
```python
POOLS = {
    "WETH-USDC": "0x84652bb2539513BAf36e225c930Fdd8eaa63CE27",
    "WETH-ARB": "0xa6c5c7d189fa4eb5af8ba34e63dcdd3a635d433f",
}

DEX_ROUTERS = {
    "Camelot": "0xc873fEcbd354f5A56E00E710B90EF4201db2448d",
}
```

### Token Price
```python
ETH_USD = 3500  # Update with current price
ARB_USD = 0.75
```

---

## 🔵 Option 3: Base (Coinbase L2)

### Why Base?
- ✅ Newest major L2 (less competition)
- ✅ Coinbase backing
- ✅ Fast growing
- ✅ Low fees

### RPC Endpoints
```python
EXTERNAL_RPC = "https://mainnet.base.org"
# or
EXTERNAL_RPC = "https://base-rpc.publicnode.com"
```

### Major DEXes & Pools

**Uniswap V3 on Base**
```python
POOLS = {
    "WETH-USDC": "0xd0b53D9277642d899DF5C87A3966A349A798F224",  # 0.05% fee
    "WETH-USDbC": "0x88A43bbDF9D098eEC7bCEda4e2494615dfD9bB9C", # 0.05% fee
}

DEX_ROUTERS = {
    "Uniswap V3": "0x2626664c2603336E57B271c5C0b26F421741e481",
}
```

**Aerodrome (Native Base DEX)**
```python
POOLS = {
    "WETH-USDC": "0xcDAC0d6c6C59727a65F871236188350531885C43",
}

DEX_ROUTERS = {
    "Aerodrome": "0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43",
}
```

### Token Price
```python
ETH_USD = 3500  # Update with current price
```

---

## 🔴 Option 4: Optimism

### Why Optimism?
- ✅ Mature L2
- ✅ Unique DEXes (Velodrome)
- ✅ Good liquidity
- ✅ Low fees

### RPC Endpoints
```python
EXTERNAL_RPC = "https://mainnet.optimism.io"
# or
EXTERNAL_RPC = "https://optimism-rpc.publicnode.com"
```

### Major DEXes & Pools

**Velodrome (Native Optimism DEX)**
```python
POOLS = {
    "WETH-USDC": "0x0493Bf8b6DBB159Ce2Db2E0E8403E753Abd1235b",
    "WETH-OP": "0xd25711EdfBf747efCE181442Cc1D8F5F8fc8a0D3",
}

DEX_ROUTERS = {
    "Velodrome": "0xa062aE8A9c5e11aaA026fc2670B0D65cCc8B2858",
}
```

**Uniswap V3 on Optimism**
```python
POOLS = {
    "WETH-USDC": "0x85149247691df622eaF1a8Bd0CaFd40BC45154a9",  # 0.05% fee
}

DEX_ROUTERS = {
    "Uniswap V3": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
}
```

### Token Price
```python
ETH_USD = 3500  # Update with current price
OP_USD = 2.50
```

---

## 🛠️ Migration Steps

### 1. Stop Current Monitoring

```bash
./scripts/stop-monitoring.sh
```

### 2. Archive BSC Data

```bash
# Create archive directory
mkdir -p chain-archives

# Move BSC data
mv arbitrage-data chain-archives/bsc-data-$(date +%Y%m%d)

# Create fresh data directory
mkdir arbitrage-data
```

### 3. Update Configuration

Edit `scripts/enhanced_tracker.py`:

```python
# Line ~15-20: Update RPC endpoint
EXTERNAL_RPC = "https://polygon-rpc.com"  # Example for Polygon

# Line ~25-35: Update pools (use configurations above)
POOLS = {
    "WMATIC-USDC": "0x6e7a5FAFcec6BB1e78bAE2A1F0B612012BF14827",
    # ... other pools
}

# Line ~40-45: Update DEX routers
DEX_ROUTERS = {
    "QuickSwap": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
    # ... other routers
}

# Line ~55: Update token price variable name and value
MATIC_USD = 0.90  # Replace BNB_USD with appropriate token
```

### 4. Update Database Manager (Optional)

If changing token symbol in display:

Edit `scripts/db_manager.py` and other scripts to replace "BNB" references with new chain token.

### 5. Initialize New Database

```bash
python3 scripts/db_manager.py
```

### 6. Start Monitoring on New Chain

```bash
./scripts/start-monitoring.sh
```

### 7. Verify

```bash
# Check logs
tail -f arbitrage-data/tracker.log

# Should see new chain activity
# Example: "Scanning Polygon pools..."
```

---

## 📊 Chain Comparison Table

| Feature | BSC | Polygon | Arbitrum | Base | Optimism |
|---------|-----|---------|----------|------|----------|
| **Gas Cost** | Low | Very Low | Low | Very Low | Low |
| **Competition** | ❌ Extreme | ⚠️ Moderate | ⚠️ Moderate | ✅ Low | ⚠️ Moderate |
| **Liquidity** | High | High | High | Medium | Medium |
| **Block Time** | 3s | 2s | 0.25s | 2s | 2s |
| **MEV Intensity** | ❌ Very High | ⚠️ Moderate | ⚠️ Moderate | ✅ Low | ⚠️ Moderate |
| **Ease of Setup** | ✅ Easy | ✅ Easy | ⚠️ Medium | ✅ Easy | ✅ Easy |
| **Recommendation** | ❌ Not viable | ✅ Try first | ✅ Good option | ✅ Good option | ⚠️ Consider |

---

## 🎯 Recommended Migration Path

Based on current BSC results, here's the recommended order to try chains:

### Phase 1: Polygon (Week 1)
- **Why First:** Most similar to BSC, easy migration, good liquidity
- **Monitor:** 3-5 days
- **Decision Point:** If <10 small opportunities, move to Phase 2

### Phase 2: Base (Week 2)
- **Why Second:** Newest L2, less competition, growing ecosystem
- **Monitor:** 3-5 days
- **Decision Point:** If <10 small opportunities, move to Phase 3

### Phase 3: Arbitrum (Week 3)
- **Why Third:** Mature L2, good liquidity, different DEX landscape
- **Monitor:** 3-5 days
- **Decision Point:** Final evaluation

### Phase 4: Alternative Strategy
If all three chains show <10 small opportunities:
- Consider different DeFi strategies (liquidations, etc.)
- Or accept that $10K-$100K arbitrage requires different approach
- Or increase capital range to $100K-$500K

---

## 🔧 Code Adaptations Needed

### For Uniswap V3 Chains (Arbitrum, Base, Optimism)

Uniswap V3 uses **concentrated liquidity** instead of constant product formula. Need to adapt:

1. **Pool Reserve Calculation**
   - V3 doesn't have simple `getReserves()`
   - Need to query `slot0()` for current price
   - Calculate liquidity in active range

2. **Imbalance Calculation**
   - Different math for concentrated liquidity
   - Need to understand tick ranges
   - More complex profit estimation

3. **Pool Addresses**
   - V3 pools are created per fee tier
   - Need to specify fee tier in address

**Note:** Initial migration should focus on **V2-style DEXes** (QuickSwap, SushiSwap, Camelot, Aerodrome) which use same math as PancakeSwap V2. V3 adaptation can come later.

---

## 📝 Migration Checklist

Before switching chains:

- [ ] Review BSC data (5 days minimum)
- [ ] Confirm BSC is not viable (<10 small opportunities)
- [ ] Choose target chain (recommend Polygon first)
- [ ] Get RPC endpoint (from configurations above)
- [ ] Get pool addresses (from configurations above)
- [ ] Update token price variable
- [ ] Archive BSC data
- [ ] Update `enhanced_tracker.py`
- [ ] Initialize fresh database
- [ ] Start monitoring
- [ ] Verify logs show new chain activity
- [ ] Run daily summaries for 3-5 days
- [ ] Compare results with BSC

---

## 💡 Pro Tips

### 1. Test RPC Endpoint First
```bash
curl -X POST https://polygon-rpc.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

### 2. Verify Pool Addresses
Check on block explorer before adding:
- Polygon: https://polygonscan.com
- Arbitrum: https://arbiscan.io
- Base: https://basescan.org
- Optimism: https://optimistic.etherscan.io

### 3. Monitor Gas Prices
Each chain has different gas dynamics:
- Polygon: 30-100 Gwei typical
- Arbitrum: Check L1 + L2 fees
- Base: Usually <0.01 Gwei
- Optimism: Check L1 + L2 fees

### 4. Pool Liquidity Check
Before monitoring a pool, verify it has >$100K liquidity:
- Use DEX analytics (dexscreener.com)
- Avoid low-liquidity pools (same problem as BSC)

---

## 🚀 Quick Migration Commands

When ready to switch (e.g., to Polygon):

```bash
# 1. Stop and archive
./scripts/stop-monitoring.sh
mkdir -p chain-archives
mv arbitrage-data chain-archives/bsc-$(date +%Y%m%d)
mkdir arbitrage-data

# 2. Update config (manual edit)
nano scripts/enhanced_tracker.py
# - Change EXTERNAL_RPC
# - Change POOLS
# - Change DEX_ROUTERS
# - Change BNB_USD to MATIC_USD

# 3. Initialize and start
python3 scripts/db_manager.py
./scripts/start-monitoring.sh

# 4. Verify
tail -f arbitrage-data/tracker.log
```

**Migration time: ~15-30 minutes**

---

## 📞 Support & Resources

### Block Explorers
- Polygon: https://polygonscan.com
- Arbitrum: https://arbiscan.io
- Base: https://basescan.org
- Optimism: https://optimistic.etherscan.io

### DEX Analytics
- https://dexscreener.com
- https://www.geckoterminal.com
- https://dune.com

### RPC Providers (If public RPCs are slow)
- Alchemy (free tier)
- Infura (free tier)
- QuickNode (paid)
- GetBlock (paid)

---

**Ready to migrate whenever BSC monitoring period concludes!**
