// Copyright 2024 The go-ethereum Authors
// Imbalance Prediction Engine - Test Client
//
// This client demonstrates how to use the Imbalance API to detect
// liquidity imbalance opportunities in real-time.

package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"math/big"
	"time"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/ethclient"
	"github.com/ethereum/go-ethereum/rpc"
)

var (
	rpcURL     = flag.String("rpc", "http://127.0.0.1:8545", "BSC RPC endpoint")
	poolAddr   = flag.String("pool", "", "Specific pool address to monitor (optional)")
	minScore   = flag.Float64("minscore", 20.0, "Minimum imbalance score to display")
	subscribe  = flag.Bool("subscribe", false, "Subscribe to real-time pool updates")
	testMode   = flag.Bool("test", false, "Run in test mode with predefined pools")
)

// ImbalanceResult mirrors the server-side struct
type ImbalanceResult struct {
	PoolAddress       string  `json:"pool_address"`
	ImbalanceScore    float64 `json:"imbalance_score"`
	Level             string  `json:"level"`
	ProfitOpportunity string  `json:"profit_opportunity"`
	Confidence        float64 `json:"confidence"`
	PendingSwaps      int     `json:"pending_swaps"`
	Timestamp         string  `json:"timestamp"`
}

// PoolState contains pool reserve information
type PoolState struct {
	PoolAddress common.Address `json:"pool_address"`
	Reserve0    *big.Int       `json:"reserve0"`
	Reserve1    *big.Int       `json:"reserve1"`
	Token0      common.Address `json:"token0"`
	Token1      common.Address `json:"token1"`
	BlockNumber uint64         `json:"block_number"`
}

// Stats contains predictor statistics
type Stats struct {
	Running              bool    `json:"running"`
	ActivePools          int     `json:"active_pools"`
	CacheSize            int     `json:"cache_size"`
	CacheHitRate         float64 `json:"cache_hit_rate"`
	FilterTotalProcessed int     `json:"filter_total_processed"`
	FilterFiltered       int     `json:"filter_filtered"`
	FilterEfficiency     float64 `json:"filter_efficiency"`
}

// Well-known BSC DEX pool addresses for testing
var testPools = []string{
	"0x58F876857a02D6762E0101bb5C46A8c1ED44Dc16", // WBNB-BUSD PancakeSwap V2
	"0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE", // WBNB-USDT PancakeSwap V2
	"0x7EFaEf62fDdCCa950418312c6C91Aef321375A00", // WBNB-USDC PancakeSwap V2
	"0x0eD7e52944161450477ee417DE9Cd3a859b14fD0", // WBNB-CAKE PancakeSwap V2
	"0x1B96B92314C44b159149f7E0303511fB2Fc4774f", // WBNB-ETH PancakeSwap V2
}

func main() {
	flag.Parse()

	fmt.Println("╔═══════════════════════════════════════════════════════════════╗")
	fmt.Println("║    BSC Imbalance Prediction Engine - Opportunity Scanner     ║")
	fmt.Println("╚═══════════════════════════════════════════════════════════════╝")
	fmt.Println()

	// Connect to BSC node
	client, err := rpc.Dial(*rpcURL)
	if err != nil {
		log.Fatalf("Failed to connect to RPC: %v", err)
	}
	defer client.Close()

	ethClient, err := ethclient.Dial(*rpcURL)
	if err != nil {
		log.Fatalf("Failed to connect to ETH client: %v", err)
	}
	defer ethClient.Close()

	fmt.Printf("✓ Connected to BSC node: %s\n", *rpcURL)

	// Get predictor stats
	stats, err := getStats(client)
	if err != nil {
		log.Fatalf("Failed to get stats: %v", err)
	}

	displayStats(stats)

	// Get current block number
	blockNumber, err := ethClient.BlockNumber(context.Background())
	if err != nil {
		log.Printf("Warning: Could not get block number: %v", err)
	} else {
		fmt.Printf("Current block: %d\n", blockNumber)
	}

	fmt.Println()
	fmt.Println("─────────────────────────────────────────────────────────────")
	fmt.Println()

	if *subscribe {
		// Real-time subscription mode
		runSubscriptionMode(client)
	} else if *testMode {
		// Test mode with known pools
		runTestMode(client, ethClient)
	} else if *poolAddr != "" {
		// Single pool monitoring
		runSinglePoolMode(client, *poolAddr)
	} else {
		// Default: monitor test pools once
		runTestMode(client, ethClient)
	}
}

func getStats(client *rpc.Client) (*Stats, error) {
	var stats Stats
	err := client.Call(&stats, "imbalance_getStats")
	return &stats, err
}

func displayStats(stats *Stats) {
	fmt.Println("Predictor Status:")
	if stats.Running {
		fmt.Println("  Status: ✓ RUNNING")
	} else {
		fmt.Println("  Status: ✗ STOPPED")
	}
	fmt.Printf("  Active Pools: %d\n", stats.ActivePools)
	fmt.Printf("  Cache Size: %d entries\n", stats.CacheSize)
	fmt.Printf("  Cache Hit Rate: %.2f%%\n", stats.CacheHitRate*100)
	fmt.Printf("  Transactions Processed: %d\n", stats.FilterTotalProcessed)
	fmt.Printf("  Swap Transactions Filtered: %d\n", stats.FilterFiltered)
	if stats.FilterTotalProcessed > 0 {
		fmt.Printf("  Filter Efficiency: %.2f%%\n", float64(stats.FilterFiltered)/float64(stats.FilterTotalProcessed)*100)
	}
}

func runSinglePoolMode(client *rpc.Client, poolAddress string) {
	fmt.Printf("Monitoring pool: %s\n\n", poolAddress)

	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for {
		result, err := getPoolImbalance(client, poolAddress)
		if err != nil {
			log.Printf("Error getting imbalance: %v", err)
			time.Sleep(5 * time.Second)
			continue
		}

		if result.ImbalanceScore >= *minScore {
			displayOpportunity(result)
		}

		<-ticker.C
	}
}

func runTestMode(client *rpc.Client, ethClient *ethclient.Client) {
	fmt.Println("Scanning known DEX pools for opportunities...\n")

	opportunities := 0

	for i, poolAddr := range testPools {
		fmt.Printf("[%d/%d] Checking pool %s...\n", i+1, len(testPools), poolAddr)

		// Try to get pool state (will fail if node not synced)
		result, err := getPoolImbalance(client, poolAddr)
		if err != nil {
			if err.Error() == "pool state not in cache" {
				fmt.Printf("  ⚠ Pool not in cache (node may still be syncing)\n\n")
				continue
			}
			log.Printf("  Error: %v\n\n", err)
			continue
		}

		if result.ImbalanceScore >= *minScore {
			opportunities++
			displayOpportunity(result)
		} else {
			fmt.Printf("  ℹ Score: %.2f%% (%s) - Below threshold\n\n",
				result.ImbalanceScore, result.Level)
		}

		// Small delay between requests
		time.Sleep(500 * time.Millisecond)
	}

	fmt.Println("─────────────────────────────────────────────────────────────")
	fmt.Printf("Scan complete. Found %d opportunities above %.1f%% threshold.\n",
		opportunities, *minScore)

	if opportunities == 0 {
		fmt.Println("\nNote: If no opportunities were found, this could mean:")
		fmt.Println("  • Pools are well-balanced (good market health)")
		fmt.Println("  • Node is still syncing and doesn't have state data yet")
		fmt.Println("  • No pending swap transactions in the mempool")
		fmt.Println("\nTry running with --subscribe flag for real-time monitoring.")
	}
}

func runSubscriptionMode(client *rpc.Client) {
	fmt.Println("📡 Real-time subscription mode")
	fmt.Println("Subscribing to pending transactions...\n")

	// Subscribe to pending transactions
	ch := make(chan *types.Transaction)

	sub, err := subscribePendingTransactions(client, ch)
	if err != nil {
		log.Fatalf("Failed to subscribe: %v", err)
	}
	defer sub.Unsubscribe()

	fmt.Println("✓ Subscribed. Monitoring mempool for swap transactions...")
	fmt.Println("  (Press Ctrl+C to stop)\n")

	// Monitor for opportunities
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	lastCheck := time.Now()

	for {
		select {
		case err := <-sub.Err():
			log.Fatalf("Subscription error: %v", err)
		case tx := <-ch:
			// New pending transaction detected
			if tx.To() != nil {
				fmt.Printf("⚡ Swap tx detected: %s → %s\n",
					tx.Hash().Hex()[:10], tx.To().Hex()[:10])

				// Check pool imbalance
				result, err := getPoolImbalance(client, tx.To().Hex())
				if err == nil && result.ImbalanceScore >= *minScore {
					displayOpportunity(result)
				}
			}
		case <-ticker.C:
			// Periodic stats update
			elapsed := time.Since(lastCheck)
			fmt.Printf("\n[%s] Still monitoring... (%.0fs elapsed)\n",
				time.Now().Format("15:04:05"), elapsed.Seconds())
			lastCheck = time.Now()
		}
	}
}

func subscribePendingTransactions(client *rpc.Client, ch chan *types.Transaction) (*rpc.ClientSubscription, error) {
	return client.EthSubscribe(context.Background(), ch, "newPendingTransactions")
}

func getPoolImbalance(client *rpc.Client, poolAddress string) (*ImbalanceResult, error) {
	var result ImbalanceResult
	err := client.Call(&result, "imbalance_getPoolImbalance", poolAddress)
	return &result, err
}

func displayOpportunity(result *ImbalanceResult) {
	// Color codes for terminal output
	const (
		colorReset  = "\033[0m"
		colorRed    = "\033[31m"
		colorGreen  = "\033[32m"
		colorYellow = "\033[33m"
		colorCyan   = "\033[36m"
	)

	// Determine severity color
	severityColor := colorGreen
	icon := "ℹ"

	switch result.Level {
	case "moderate":
		severityColor = colorYellow
		icon = "⚠"
	case "severe":
		severityColor = colorRed
		icon = "⚠"
	case "critical":
		severityColor = colorRed
		icon = "🚨"
	}

	fmt.Printf("%s%s OPPORTUNITY DETECTED%s\n", severityColor, icon, colorReset)
	fmt.Printf("  Pool: %s%s%s\n", colorCyan, result.PoolAddress, colorReset)
	fmt.Printf("  Imbalance Score: %s%.2f%%%s (%s)\n",
		severityColor, result.ImbalanceScore, colorReset, result.Level)
	fmt.Printf("  Confidence: %.1f%%\n", result.Confidence)

	// Parse profit opportunity
	profit := new(big.Int)
	profit.SetString(result.ProfitOpportunity, 10)
	profitEther := new(big.Float).Quo(
		new(big.Float).SetInt(profit),
		new(big.Float).SetInt(big.NewInt(1e18)),
	)
	fmt.Printf("  Estimated Profit: %s%.6f BNB%s (%s wei)\n",
		colorGreen, profitEther, colorReset, result.ProfitOpportunity)

	fmt.Printf("  Pending Swaps: %d\n", result.PendingSwaps)
	fmt.Printf("  Timestamp: %s\n", result.Timestamp)

	// Actionability assessment
	if result.Confidence >= 70.0 && result.ImbalanceScore >= 20.0 {
		fmt.Printf("\n  %s✓ ACTIONABLE%s - High confidence opportunity\n",
			colorGreen, colorReset)
	} else if result.Confidence < 50.0 {
		fmt.Printf("\n  %s⚠ LOW CONFIDENCE%s - More data needed\n",
			colorYellow, colorReset)
	}

	fmt.Println()
}

func prettyPrint(v interface{}) {
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		fmt.Println(v)
		return
	}
	fmt.Println(string(b))
}
