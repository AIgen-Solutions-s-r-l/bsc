#!/bin/bash
# Demo script showing what the Imbalance API would return when opportunities are detected

cat << 'EOF'
╔═══════════════════════════════════════════════════════════════╗
║    BSC Imbalance Prediction Engine - Demo Opportunities      ║
╚═══════════════════════════════════════════════════════════════╝

This demonstrates what the client would display when the node has
synced and opportunities are detected in real-time.

─────────────────────────────────────────────────────────────

SCENARIO 1: Moderate Imbalance Detected
─────────────────────────────────────────────────────────────

[32m⚠ OPPORTUNITY DETECTED[0m
  Pool: [36m0x58F876857a02D6762E0101bb5C46A8c1ED44Dc16[0m
  Imbalance Score: [33m25.40%[0m (moderate)
  Confidence: 82.5%
  Estimated Profit: [32m0.124500 BNB[0m (124500000000000000 wei)
  Pending Swaps: 3
  Timestamp: 2025-11-14T12:15:30Z

  [32m✓ ACTIONABLE[0m - High confidence opportunity

─────────────────────────────────────────────────────────────

SCENARIO 2: Severe Imbalance - Large Opportunity
─────────────────────────────────────────────────────────────

[31m⚠ OPPORTUNITY DETECTED[0m
  Pool: [36m0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE[0m
  Imbalance Score: [31m48.75%[0m (severe)
  Confidence: 91.2%
  Estimated Profit: [32m0.876300 BNB[0m (876300000000000000 wei)
  Pending Swaps: 7
  Timestamp: 2025-11-14T12:15:32Z

  [32m✓ ACTIONABLE[0m - High confidence opportunity

─────────────────────────────────────────────────────────────

SCENARIO 3: Critical Imbalance - Flash Loan Opportunity
─────────────────────────────────────────────────────────────

[31m🚨 OPPORTUNITY DETECTED[0m
  Pool: [36m0x7EFaEf62fDdCCa950418312c6C91Aef321375A00[0m
  Imbalance Score: [31m72.18%[0m (critical)
  Confidence: 95.8%
  Estimated Profit: [32m2.451200 BNB[0m (2451200000000000000 wei)
  Pending Swaps: 12
  Timestamp: 2025-11-14T12:15:35Z

  [32m✓ ACTIONABLE[0m - High confidence opportunity

─────────────────────────────────────────────────────────────

SCENARIO 4: Slight Imbalance - Low Confidence
─────────────────────────────────────────────────────────────

[32mℹ OPPORTUNITY DETECTED[0m
  Pool: [36m0x0eD7e52944161450477ee417DE9Cd3a859b14fD0[0m
  Imbalance Score: [32m15.20%[0m (slight)
  Confidence: 45.0%
  Estimated Profit: [32m0.015600 BNB[0m (15600000000000000 wei)
  Pending Swaps: 18
  Timestamp: 2025-11-14T12:15:38Z

  [33m⚠ LOW CONFIDENCE[0m - More data needed

─────────────────────────────────────────────────────────────

SUMMARY
─────────────────────────────────────────────────────────────

Total Opportunities Found: 4
Actionable Opportunities: 3
Total Estimated Profit: 3.467600 BNB (~$1,040 USD at $300/BNB)

HOW TO EXECUTE:
1. Deploy arbitrage contract with flash loan capability
2. Monitor for severe/critical imbalances (>40%)
3. Execute multi-hop arbitrage when confidence >80%
4. Account for gas costs and slippage

The prediction engine processes transactions in the mempool BEFORE
they are mined, giving you a time advantage to execute arbitrage.

EOF
