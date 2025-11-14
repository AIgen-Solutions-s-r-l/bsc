// Copyright 2024 The go-ethereum Authors
// This file is part of the go-ethereum library.

// Integration tests for BSC Imbalance Prediction Engine
// Tests the complete end-to-end prediction pipeline

package legacypool

import (
	"math/big"
	"testing"
	"time"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
)

// TestEndToEndPrediction tests the complete prediction pipeline
// mempool → filter → simulate → detect
func TestEndToEndPrediction(t *testing.T) {
	// Setup: Create predictor with default config
	config := DefaultPredictorConfig()
	config.EnableMetrics = false // Disable metrics for test
	predictor := NewImbalancePredictor(config)

	err := predictor.Start()
	if err != nil {
		t.Fatalf("Failed to start predictor: %v", err)
	}
	defer predictor.Stop()

	// Pool address (WBNB-BUSD on PancakeSwap)
	poolAddr := common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f")

	// Setup initial pool state
	initialState := &PoolState{
		PoolAddress: poolAddr,
		Token0:      common.HexToAddress("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"), // WBNB
		Token1:      common.HexToAddress("0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56"), // BUSD
		Reserve0:    new(big.Int).Mul(big.NewInt(1000000), big.NewInt(1e18)),            // 1M WBNB
		Reserve1:    new(big.Int).Mul(big.NewInt(300000000), big.NewInt(1e18)),          // 300M BUSD
		BlockNumber: 30000000,
		Timestamp:   uint64(time.Now().Unix()),
	}

	predictor.UpdatePoolState(initialState)

	// Simulate incoming swap transactions
	routerAddr := common.HexToAddress("0x10ED43C718714eb63d5aA57B78B54704E256024E") // PancakeSwap router

	// Create 3 swap transactions with different gas prices
	swaps := []struct {
		gasPrice int64
		amountIn int64
	}{
		{10e9, 100e18},  // 10 Gwei, 100 WBNB
		{15e9, 50e18},   // 15 Gwei, 50 WBNB
		{5e9, 200e18},   // 5 Gwei, 200 WBNB
	}

	for i, swap := range swaps {
		// Create transaction with swapExactTokensForTokens method signature
		data := common.Hex2Bytes("38ed1739" + // method signature
			"0000000000000000000000000000000000000000000000000de0b6b3a7640000") // dummy params

		tx := types.NewTransaction(
			uint64(i),
			routerAddr,
			big.NewInt(swap.amountIn),
			300000,
			big.NewInt(swap.gasPrice),
			data,
		)

		// Process transaction through predictor
		predictor.OnPendingTransaction(tx)
	}

	// Wait for transactions to be processed
	time.Sleep(100 * time.Millisecond)

	// Generate prediction
	result, err := predictor.PredictPoolImbalance(poolAddr)
	if err != nil {
		t.Fatalf("Prediction failed: %v", err)
	}

	// Validate result
	if result == nil {
		t.Fatal("Prediction result should not be nil")
	}

	if result.PoolAddress != poolAddr {
		t.Error("Result pool address mismatch")
	}

	if result.ImbalanceScore < 0 || result.ImbalanceScore > 100 {
		t.Errorf("Imbalance score out of range: %.2f", result.ImbalanceScore)
	}

	if result.Confidence < 0 || result.Confidence > 100 {
		t.Errorf("Confidence out of range: %.2f", result.Confidence)
	}

	if result.PendingSwaps != 3 {
		t.Errorf("Expected 3 pending swaps, got %d", result.PendingSwaps)
	}

	t.Logf("Prediction successful: Score=%.2f%%, Level=%s, Confidence=%.1f%%",
		result.ImbalanceScore, result.Level.String(), result.Confidence)
}

// TestMultiPoolPrediction tests predictions across multiple pools
func TestMultiPoolPrediction(t *testing.T) {
	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     100,
		EnableMetrics: false,
	})

	predictor.Start()
	defer predictor.Stop()

	// Setup 3 different pools
	pools := []common.Address{
		common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f"), // WBNB-BUSD
		common.HexToAddress("0x58f876857a02d6762e0101bb5c46a8c1ed44dc16"), // WBNB-USDT
		common.HexToAddress("0x7efaef62fddcca950418312c6c91aef321375a00"), // WBNB-ETH
	}

	for _, poolAddr := range pools {
		state := &PoolState{
			PoolAddress: poolAddr,
			Token0:      common.HexToAddress("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"),
			Token1:      common.HexToAddress("0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56"),
			Reserve0:    new(big.Int).Mul(big.NewInt(1000000), big.NewInt(1e18)),
			Reserve1:    new(big.Int).Mul(big.NewInt(2000000), big.NewInt(1e18)),
			BlockNumber: 30000000,
			Timestamp:   uint64(time.Now().Unix()),
		}
		predictor.UpdatePoolState(state)
	}

	// Generate predictions for all pools
	results := make([]*ImbalanceResult, len(pools))
	for i, poolAddr := range pools {
		result, err := predictor.PredictPoolImbalance(poolAddr)
		if err != nil {
			t.Fatalf("Prediction failed for pool %d: %v", i, err)
		}
		results[i] = result
	}

	// Validate all predictions succeeded
	if len(results) != len(pools) {
		t.Errorf("Expected %d results, got %d", len(pools), len(results))
	}

	for i, result := range results {
		if result.PoolAddress != pools[i] {
			t.Errorf("Result %d: pool address mismatch", i)
		}
	}
}

// TestCacheBehavior tests cache hit/miss scenarios
func TestCacheBehavior(t *testing.T) {
	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     10,
		EnableMetrics: false,
	})

	poolAddr := common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f")

	// Cache miss scenario
	_, found := predictor.GetPoolState(poolAddr)
	if found {
		t.Error("Should be cache miss before state is added")
	}

	// Add state to cache
	state := &PoolState{
		PoolAddress: poolAddr,
		Reserve0:    big.NewInt(1000000),
		Reserve1:    big.NewInt(2000000),
	}
	predictor.UpdatePoolState(state)

	// Cache hit scenario
	retrieved, found := predictor.GetPoolState(poolAddr)
	if !found {
		t.Fatal("Should be cache hit after state is added")
	}

	if retrieved.PoolAddress != poolAddr {
		t.Error("Retrieved state has wrong pool address")
	}

	// Verify cache statistics
	stats := predictor.GetStats()
	cacheSize, ok := stats["cache_size"].(int)
	if !ok || cacheSize != 1 {
		t.Errorf("Expected cache size 1, got %v", stats["cache_size"])
	}
}

// TestHighThroughput tests predictor under high transaction load
func TestHighThroughput(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping high-throughput test in short mode")
	}

	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     1000,
		EnableMetrics: false,
	})

	predictor.Start()
	defer predictor.Stop()

	// Setup pool
	poolAddr := common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f")
	state := &PoolState{
		PoolAddress: poolAddr,
		Token0:      common.HexToAddress("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"),
		Token1:      common.HexToAddress("0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56"),
		Reserve0:    new(big.Int).Mul(big.NewInt(1000000), big.NewInt(1e18)),
		Reserve1:    new(big.Int).Mul(big.NewInt(2000000), big.NewInt(1e18)),
		BlockNumber: 30000000,
	}
	predictor.UpdatePoolState(state)

	routerAddr := common.HexToAddress("0x10ED43C718714eb63d5aA57B78B54704E256024E")
	data := common.Hex2Bytes("38ed1739" + "0000000000000000000000000000000000000000000000000de0b6b3a7640000")

	// Process 1000 transactions
	startTime := time.Now()
	const numTxs = 1000

	for i := 0; i < numTxs; i++ {
		tx := types.NewTransaction(
			uint64(i),
			routerAddr,
			big.NewInt(1e18),
			300000,
			big.NewInt(5e9),
			data,
		)
		predictor.OnPendingTransaction(tx)
	}

	duration := time.Since(startTime)
	throughput := float64(numTxs) / duration.Seconds()

	t.Logf("Processed %d transactions in %v (%.0f tx/s)",
		numTxs, duration, throughput)

	// Verify throughput is acceptable (target: >1000 tx/s)
	if throughput < 1000 {
		t.Errorf("Throughput %.0f tx/s is below target (1000 tx/s)", throughput)
	}

	// Generate final prediction
	result, err := predictor.PredictPoolImbalance(poolAddr)
	if err != nil {
		t.Fatalf("Prediction failed: %v", err)
	}

	t.Logf("Final prediction after %d swaps: Score=%.2f%%, Confidence=%.1f%%",
		numTxs, result.ImbalanceScore, result.Confidence)
}

// TestConcurrentPredictions tests concurrent prediction requests
func TestConcurrentPredictions(t *testing.T) {
	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     100,
		EnableMetrics: false,
	})

	predictor.Start()
	defer predictor.Stop()

	// Setup multiple pools
	numPools := 10
	pools := make([]common.Address, numPools)
	for i := 0; i < numPools; i++ {
		pools[i] = common.BigToAddress(big.NewInt(int64(i + 1)))
		state := &PoolState{
			PoolAddress: pools[i],
			Token0:      common.HexToAddress("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"),
			Token1:      common.HexToAddress("0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56"),
			Reserve0:    new(big.Int).Mul(big.NewInt(1000000), big.NewInt(1e18)),
			Reserve1:    new(big.Int).Mul(big.NewInt(2000000), big.NewInt(1e18)),
		}
		predictor.UpdatePoolState(state)
	}

	// Launch concurrent predictions
	const numGoroutines = 10
	const predictionsPerGoroutine = 100

	done := make(chan bool, numGoroutines)
	errors := make(chan error, numGoroutines*predictionsPerGoroutine)

	for g := 0; g < numGoroutines; g++ {
		go func(goroutineID int) {
			for i := 0; i < predictionsPerGoroutine; i++ {
				poolIdx := (goroutineID + i) % numPools
				_, err := predictor.PredictPoolImbalance(pools[poolIdx])
				if err != nil {
					errors <- err
				}
			}
			done <- true
		}(g)
	}

	// Wait for all goroutines
	for g := 0; g < numGoroutines; g++ {
		<-done
	}
	close(errors)

	// Check for errors
	errorCount := 0
	for range errors {
		errorCount++
	}

	if errorCount > 0 {
		t.Errorf("Encountered %d errors during concurrent predictions", errorCount)
	}

	totalPredictions := numGoroutines * predictionsPerGoroutine
	t.Logf("Successfully completed %d concurrent predictions", totalPredictions)
}

// TestPredictionLatency tests end-to-end latency
func TestPredictionLatency(t *testing.T) {
	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     1000,
		EnableMetrics: false,
	})

	predictor.Start()
	defer predictor.Stop()

	// Setup pool
	poolAddr := common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f")
	state := &PoolState{
		PoolAddress: poolAddr,
		Token0:      common.HexToAddress("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"),
		Token1:      common.HexToAddress("0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56"),
		Reserve0:    new(big.Int).Mul(big.NewInt(1000000), big.NewInt(1e18)),
		Reserve1:    new(big.Int).Mul(big.NewInt(2000000), big.NewInt(1e18)),
	}
	predictor.UpdatePoolState(state)

	// Measure latency over 100 predictions
	const numPredictions = 100
	latencies := make([]time.Duration, numPredictions)

	for i := 0; i < numPredictions; i++ {
		start := time.Now()
		_, err := predictor.PredictPoolImbalance(poolAddr)
		latencies[i] = time.Since(start)

		if err != nil {
			t.Fatalf("Prediction %d failed: %v", i, err)
		}
	}

	// Calculate statistics
	var total time.Duration
	for _, lat := range latencies {
		total += lat
	}
	avgLatency := total / time.Duration(numPredictions)

	// Find p95
	sorted := make([]time.Duration, len(latencies))
	copy(sorted, latencies)
	// Simple sort for test
	for i := 0; i < len(sorted); i++ {
		for j := i + 1; j < len(sorted); j++ {
			if sorted[i] > sorted[j] {
				sorted[i], sorted[j] = sorted[j], sorted[i]
			}
		}
	}
	p95Index := int(float64(numPredictions) * 0.95)
	p95Latency := sorted[p95Index]

	t.Logf("Prediction latency: avg=%v, p95=%v", avgLatency, p95Latency)

	// Verify latency meets target (<100ms p95)
	target := 100 * time.Millisecond
	if p95Latency > target {
		t.Errorf("p95 latency %v exceeds target %v", p95Latency, target)
	}
}

// BenchmarkEndToEndPrediction benchmarks complete prediction pipeline
func BenchmarkEndToEndPrediction(b *testing.B) {
	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     1000,
		EnableMetrics: false,
	})

	predictor.Start()
	defer predictor.Stop()

	poolAddr := common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f")
	state := &PoolState{
		PoolAddress: poolAddr,
		Token0:      common.HexToAddress("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"),
		Token1:      common.HexToAddress("0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56"),
		Reserve0:    new(big.Int).Mul(big.NewInt(1000000), big.NewInt(1e18)),
		Reserve1:    new(big.Int).Mul(big.NewInt(2000000), big.NewInt(1e18)),
	}
	predictor.UpdatePoolState(state)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		predictor.PredictPoolImbalance(poolAddr)
	}
}
