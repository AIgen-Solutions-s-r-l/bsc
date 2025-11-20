# BSC Arbitrage Monitoring - Critical Findings Report

**Analysis Date**: November 15, 2025
**Runtime**: ~5.5 hours (15:06 - 20:36 UTC)
**Tracker Version**: Fixed (proper Swap event signature detection)

---

## Executive Summary

### 🔴 CRITICAL FINDING

**ZERO real multi-hop arbitrage transactions detected on BSC in 26,000+ blocks (~5.5 hours of monitoring)**

This is the most important finding after fixing the tracker's Swap event detection bug.

---

## Monitoring Statistics

| Metric | Value |
|--------|-------|
| **Blocks Scanned** | 68,285,950 → 68,311,985 (26,035 blocks) |
| **Time Period** | ~5.5 hours |
| **Block Scans** | 118 iterations |
| **Avg Blocks/Scan** | ~220 blocks (~11 minutes per scan) |
| **Opportunities Detected** | 484 pool imbalances |
| **Arbitrage Transactions** | **0 (ZERO)** |
| **Unique Arbitrageurs** | **0 (ZERO)** |
| **Opportunities Captured** | 0 |

---

## Pool Imbalance Analysis

### Distribution (484 total opportunities)

| Pool | Count | Percentage |
|------|-------|------------|
| WBNB-USDT | 121 | 25.0% |
| WBNB-ETH | 121 | 25.0% |
| WBNB-CAKE | 121 | 25.0% |
| WBNB-BUSD | 121 | 25.0% |

### Average Metrics by Pool

| Pool | Avg Imbalance | Avg Estimated Profit |
|------|---------------|---------------------|
| WBNB-USDT | 2,963% | ~$4.86M |
| WBNB-ETH | 2,961% | ~$350K |
| WBNB-CAKE | 1,872% | ~$3.70M |
| WBNB-BUSD | 2,961% | ~$1.69M |

---

## Opportunity Size Distribution

| Size Range | Count | Percentage |
|------------|-------|------------|
| **$10K - $100K** (Target) | **0** | **0.0%** |
| **>$100K** | 484 | 100% |

**Profit Range**:
- MIN: $348,779
- MAX: $4,870,320
- AVG: ~$2.9M

---

## Critical Findings

### 1. NO REAL ARBITRAGE DETECTED ❌

Despite detecting 484 profitable pool imbalances, **ZERO multi-hop arbitrage transactions** were executed in 26,000 blocks.

**Possible Explanations**:
- ✗ Imbalance calculations are incorrect
- ✗ Arbitrageurs use different strategies (not multi-hop DEX routing)
- ✗ Profit estimates are completely unrealistic
- ✗ Flash loan/MEV arbitrage is invisible to public mempool
- ✗ Real arbitrage happens through private channels (Flashbots-style)

### 2. NO SMALL OPPORTUNITIES ❌

**ALL** detected opportunities are >$348K profit.
**ZERO** opportunities in the $10K-$100K target range for small traders.

**This Suggests**:
- ✗ Imbalance calculation formula is fundamentally flawed
- ✗ Profit estimates are orders of magnitude too high
- ✗ Real arbitrage opportunities are much smaller than detected

### 3. UNREALISTIC IMBALANCE PERCENTAGES ❌

Average imbalances of **1,872% - 2,963%** are completely unrealistic for active liquidity pools on PancakeSwap (the largest BSC DEX).

**Indicates**:
- ✗ Formula error in imbalance calculation
- ✗ Reserve parsing/decimal issue
- ✗ Wrong assumption about Uniswap V2 CPMM mechanics

### 4. COMPARISON: Flawed vs Fixed Tracker

| Metric | OLD (Buggy) Tracker | NEW (Fixed) Tracker | Change |
|--------|---------------------|---------------------|--------|
| Runtime | 1 hour | 5.5 hours | +450% |
| Arbitrage TXs | 25,628 | **0** | **-100%** |
| Arbitrageurs | 4,347 | **0** | **-100%** |
| TX Rate | 16,682/hour | 0/hour | **-100%** |

**This 100% drop confirms the old tracker was completely wrong** - it was counting regular single-swap DEX trades as arbitrage.

---

## Root Cause Analysis

### The Pool Imbalance Detection Has Fundamental Issues

#### 1. **CPMM Formula Assumption Error**

**Current Code Assumes**:
```python
k = reserve0 * reserve1
optimal_x = sqrt(k)
optimal_y = sqrt(k)
# Assumes optimal balance: reserve0 == reserve1
```

**This is WRONG** for pools with different token prices!

**For WBNB-USDT**:
- WBNB ≈ $620
- USDT ≈ $1
- **Optimal ratio is NOT 1:1, it's approximately 1:620**

The code assumes equal reserves mean balance, but in reality:
- Balanced WBNB-USDT pool has ~1 WBNB per 620 USDT
- Current formula treats 1 WBNB : 1 USDT as "optimal" (completely wrong)

#### 2. **Reserve Interpretation Issues**

Potential problems:
- Not accounting for token decimal differences (WBNB=18, USDT=18 but prices differ)
- Misinterpreting reserve values from `getReserves()` call
- Not normalizing to USD properly

#### 3. **Profit Calculation Error**

Estimated profits of **$4.8M** from a single pool arbitrage are absurd.

Real arbitrage profits are typically:
- **0.1% - 3%** of trade size
- Not **2,900%** (which current calculations suggest)

**The Formula**:
```python
excess = reserve0 - optimal_x
profit = (excess * reserve1) / (reserve0 + excess)
```

This doesn't account for:
- Token price differences
- 0.3% swap fees (PancakeSwap V2)
- Slippage
- Gas costs
- Realistic trade sizes

---

## Recommendations

### IMMEDIATE (Before Continuing Monitoring)

#### 1. FIX IMBALANCE CALCULATION
- **Account for token price differences** using price oracles or reserve ratios
- Use **correct optimal reserve ratio** based on token prices
- **Validate against known pool states** from BSCScan/DexTools

Example fix:
```python
# Get token prices
price0_usd = get_token_price(token0)
price1_usd = get_token_price(token1)

# Calculate USD values
value0_usd = reserve0 * price0_usd
value1_usd = reserve1 * price1_usd

# Optimal balance: 50/50 USD split
total_value = value0_usd + value1_usd
optimal_value_each = total_value / 2

imbalance = abs(value0_usd - optimal_value_each) / optimal_value_each * 100
```

#### 2. FIX PROFIT ESTIMATION
- Use **realistic slippage calculations** (x*y=k formula)
- **Account for 0.3% swap fees** (PancakeSwap V2)
- **Include gas costs** (~3-5 Gwei × 300K gas = ~0.0015 BNB = $0.93)
- **Verify against real arbitrage examples** from BSCScan

#### 3. EXPAND TRANSACTION SCANNING
- Scan **ALL transactions**, not just DEX router calls
- Look for **flash loan arbitrage** (direct pool interactions)
- Check for **MEV bot patterns** (bundle transactions)
- Analyze **failed transactions** (reveal attempted arbitrage)
- Monitor **contract deployments** (one-time arbitrage contracts)

### MEDIUM TERM

#### 4. VALIDATE WITH KNOWN DATA
- Find **confirmed arbitrage transactions** on BSCScan
- Verify tracker **detects them correctly**
- **Backtest profit calculations** against known results

Example sources:
- BSCScan transaction tags (arbitrage bots)
- EigenPhi arbitrage analytics
- MistTrack bot tracking

#### 5. EXPAND DETECTION METHODS
- **Flash loan detection** (Aave, Venus, PancakeSwap)
- **MEV bundle detection** (if BSC supports it)
- **Cross-DEX price monitoring** (detect price differences)
- **Mempool monitoring** (if accessible via node)

---

## Technical Deep Dive: Why Multi-Hop Arbitrage is Rare

### Possible Reasons for 0 Detections

1. **Flash Loans Dominate**
   - Arbitrageurs use flash loans to borrow capital
   - Execute through direct pool calls, not router
   - Single atomic transaction with loan + swaps + repayment
   - May not look like "multi-hop" to our detector

2. **MEV Bots Use Private Channels**
   - Transactions submitted via private RPCs (BSC MEV relayers)
   - Never appear in public mempool
   - Only visible after inclusion in block

3. **Cross-DEX is Preferred**
   - Real arbitrage is between DIFFERENT DEXs (PancakeSwap vs BiSwap)
   - Single-hop on each DEX (A→B on Pancake, B→A on BiSwap)
   - Looks like 2 separate swaps, not one multi-hop

4. **Just-in-Time (JIT) Arbitrage**
   - Arbitrage happens within same block as price-moving trade
   - Extremely fast execution
   - May use custom contracts, not standard routers

---

## Conclusion

### What We Learned

1. ✅ **Bug Fix Successful**: Eliminated false positives (regular swaps counted as arbitrage)
2. ❌ **Pool Imbalance Calculation Broken**: Fundamentally flawed assumptions about CPMM mechanics
3. ❌ **Profit Estimates 1000x Too High**: Need complete rewrite of profit calculation
4. ❌ **Real Arbitrage Much Rarer**: Multi-hop DEX routing may not be the dominant strategy
5. ❌ **Detection Strategy Incomplete**: Missing flash loans, MEV bundles, cross-DEX arbitrage

### Current Assessment

**BSC viability for small traders ($10K-$100K) CANNOT be determined with current monitoring implementation.**

The tracker successfully detects transactions (Swap event logic is correct), but:
- Pool analysis is completely wrong
- Profit calculations are meaningless
- Detection scope is too narrow

### Recommendation

**⏸️ PAUSE 3-5 DAY MONITORING** until critical issues are fixed:

1. Rewrite imbalance calculation with proper price accounting
2. Implement realistic profit estimation
3. Add flash loan detection
4. Validate against known arbitrage transactions
5. Expand to cross-DEX monitoring

**ALTERNATIVE**: Shift focus to **transaction analysis approach**:
- Stop trying to predict opportunities
- Focus on **detecting arbitrage after execution**
- Analyze successful arbitrage transactions
- Reverse-engineer their strategies
- Measure actual competition levels

---

## Next Steps

### Option A: Fix Current Approach
- Estimated time: 1-2 weeks
- Risk: May still miss majority of arbitrage activity

### Option B: Transaction Analysis Approach
- Find known arbitrage bots on BSCScan
- Monitor their transactions
- Analyze patterns and profitability
- Estimated time: 3-5 days
- Lower risk, more accurate results

### Option C: Use Existing Tools
- Integrate with EigenPhi API (arbitrage analytics)
- Use DexTools/DexScreener for pool monitoring
- Focus on execution strategy, not detection
- Estimated time: 1 week

---

## Appendix: Sample Data

### Latest Opportunities (Last 10 Scans)

All opportunities show similar patterns:
- Extremely high imbalance (>1800%)
- Extremely high profit estimates (>$300K)
- No captures (0 arbitrage transactions)
- Consistent across all WBNB pairs

This consistency suggests a **systematic error in the calculation formula**, not random variance.

---

**Report Generated**: 2025-11-15 20:36 UTC
**Database**: `arbitrage-data/arbitrage.db`
**Tracker Log**: `tracker-fixed.log`
**Tracker Status**: Running (PID 4131835)
