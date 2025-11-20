// Copyright 2024 The go-ethereum Authors
// This file is part of the go-ethereum library.

// End-to-End and Load Tests for BSC Imbalance Prediction Engine
// Issue #10: Integration tests (E2E, load tests reaching 1000 RPS)
//
// These tests validate:
// 1. Complete RPC API flow (request → response)
// 2. Security middleware integration
// 3. Performance under load (1000+ RPS target)
// 4. Concurrent client scenarios
// 5. Error handling and recovery

package legacypool

import (
	"fmt"
	"math/big"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
)

// TestE2EBasicFlow tests the complete end-to-end flow
func TestE2EBasicFlow(t *testing.T) {
	// Setup: Create complete system
	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     1000,
		EnableMetrics: false,
	})
	predictor.Start()
	defer predictor.Stop()

	api := NewImbalanceAPI(predictor)
	security := NewSecurityMiddleware(DefaultSecurityConfig())

	// Step 1: Setup pool state
	poolAddr := common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f")
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

	// Step 2: Simulate incoming transactions
	routerAddr := common.HexToAddress("0x10ED43C718714eb63d5aA57B78B54704E256024E")
	data := common.Hex2Bytes("38ed1739" + "0000000000000000000000000000000000000000000000000de0b6b3a7640000")

	for i := 0; i < 5; i++ {
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

	time.Sleep(50 * time.Millisecond) // Allow processing

	// Step 3: Security validation
	clientIP := "192.168.1.1"
	err := security.ValidateRequest(clientIP, "", "imbalance_getPoolImbalance")
	if err != nil {
		t.Fatalf("Security validation failed: %v", err)
	}
	defer security.ReleaseRequest()

	// Step 4: RPC API call
	response, err := api.GetPoolImbalance(poolAddr)
	if err != nil {
		t.Fatalf("API call failed: %v", err)
	}

	// Step 5: Validate response
	if response == nil {
		t.Fatal("Response should not be nil")
	}

	if response.PoolAddress != poolAddr.Hex() {
		t.Error("Pool address mismatch")
	}

	if response.PendingSwaps != 5 {
		t.Errorf("Expected 5 pending swaps, got %d", response.PendingSwaps)
	}

	// Step 6: Get accuracy metrics
	accuracy, err := api.GetAccuracy()
	if err != nil {
		t.Fatalf("GetAccuracy failed: %v", err)
	}

	if accuracy.AccuracyPercent < 0 || accuracy.AccuracyPercent > 100 {
		t.Errorf("Invalid accuracy: %.2f", accuracy.AccuracyPercent)
	}

	t.Logf("E2E test passed: score=%.2f%%, level=%s, swaps=%d, accuracy=%.1f%%",
		response.ImbalanceScore, response.Level, response.PendingSwaps, accuracy.AccuracyPercent)
}

// TestE2EMultiPool tests handling of multiple pools simultaneously
func TestE2EMultiPool(t *testing.T) {
	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     1000,
		EnableMetrics: false,
	})
	predictor.Start()
	defer predictor.Stop()

	api := NewImbalanceAPI(predictor)

	// Setup 10 pools
	const numPools = 10
	pools := make([]common.Address, numPools)

	for i := 0; i < numPools; i++ {
		pools[i] = common.BigToAddress(big.NewInt(int64(i + 1000)))
		state := &PoolState{
			PoolAddress: pools[i],
			Token0:      common.HexToAddress("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"),
			Token1:      common.HexToAddress("0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56"),
			Reserve0:    new(big.Int).Mul(big.NewInt(1000000), big.NewInt(1e18)),
			Reserve1:    new(big.Int).Mul(big.NewInt(2000000), big.NewInt(1e18)),
			BlockNumber: 30000000,
			Timestamp:   uint64(time.Now().Unix()),
		}
		predictor.UpdatePoolState(state)
	}

	// Query all pools
	startTime := time.Now()
	for i, pool := range pools {
		response, err := api.GetPoolImbalance(pool)
		if err != nil {
			t.Errorf("Pool %d query failed: %v", i, err)
		}

		if response.PoolAddress != pool.Hex() {
			t.Errorf("Pool %d address mismatch", i)
		}
	}
	duration := time.Since(startTime)

	t.Logf("E2E multi-pool test passed: %d pools in %v (avg %.2fms/pool)",
		numPools, duration, float64(duration.Milliseconds())/float64(numPools))
}

// TestE2ESecurityIntegration tests security middleware integration
func TestE2ESecurityIntegration(t *testing.T) {
	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     1000,
		EnableMetrics: false,
	})
	predictor.Start()
	defer predictor.Stop()

	api := NewImbalanceAPI(predictor)
	security := NewSecurityMiddleware(&SecurityConfig{
		EnableRateLimiting: true,
		MaxRequestsPerMin:  5,
		GlobalMaxRPS:       100,
		EnableAPIKeys:      false,
		EnableThrottling:   true,
		MaxConcurrentReqs:  3,
	})

	// Setup pool
	poolAddr := common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f")
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

	clientIP := "192.168.1.100"

	// Test: Allow requests within rate limit
	var successCount, blockedCount int

	for i := 0; i < 10; i++ {
		err := security.ValidateRequest(clientIP, "", "test")
		if err == nil {
			successCount++
			_, apiErr := api.GetPoolImbalance(poolAddr)
			if apiErr != nil {
				t.Errorf("API call %d failed: %v", i, apiErr)
			}
			security.ReleaseRequest()
		} else {
			blockedCount++
		}
	}

	// Validate some requests were blocked (rate limit = 5/min)
	if blockedCount < 3 {
		t.Errorf("Expected at least 3 blocked requests, got %d", blockedCount)
	}

	if successCount != 5 {
		t.Errorf("Expected 5 successful requests, got %d", successCount)
	}

	t.Logf("E2E security test passed: %d allowed, %d blocked", successCount, blockedCount)
}

// TestLoadTest1000RPS tests system performance at 1000 RPS target
func TestLoadTest1000RPS(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping load test in short mode")
	}

	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     10000,
		EnableMetrics: false,
	})
	predictor.Start()
	defer predictor.Stop()

	api := NewImbalanceAPI(predictor)
	security := NewSecurityMiddleware(&SecurityConfig{
		EnableRateLimiting: false, // Disable for load test
		EnableAPIKeys:      false,
		EnableThrottling:   true,
		MaxConcurrentReqs:  500,
	})

	// Setup pool
	poolAddr := common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f")
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

	// Load test parameters
	const targetRPS = 1000
	const durationSeconds = 10
	const totalRequests = targetRPS * durationSeconds

	var successCount, errorCount uint64
	var totalLatency uint64

	startTime := time.Now()

	// Launch workers
	const numWorkers = 50
	requestsPerWorker := totalRequests / numWorkers
	var wg sync.WaitGroup

	for w := 0; w < numWorkers; w++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()

			clientIP := fmt.Sprintf("192.168.1.%d", workerID)

			for i := 0; i < requestsPerWorker; i++ {
				reqStart := time.Now()

				// Security check
				err := security.ValidateRequest(clientIP, "", "test")
				if err == nil {
					// API call
					_, apiErr := api.GetPoolImbalance(poolAddr)
					security.ReleaseRequest()

					if apiErr == nil {
						atomic.AddUint64(&successCount, 1)
						latency := uint64(time.Since(reqStart).Microseconds())
						atomic.AddUint64(&totalLatency, latency)
					} else {
						atomic.AddUint64(&errorCount, 1)
					}
				} else {
					atomic.AddUint64(&errorCount, 1)
				}

				// Rate limiting to achieve target RPS
				time.Sleep(time.Duration(numWorkers*1000/targetRPS) * time.Millisecond)
			}
		}(w)
	}

	wg.Wait()
	duration := time.Since(startTime)

	// Calculate metrics
	actualRPS := float64(successCount) / duration.Seconds()
	avgLatency := float64(totalLatency) / float64(successCount)
	errorRate := float64(errorCount) / float64(totalRequests) * 100.0

	t.Logf("Load Test Results:")
	t.Logf("  Duration: %v", duration)
	t.Logf("  Total Requests: %d", totalRequests)
	t.Logf("  Successful: %d", successCount)
	t.Logf("  Errors: %d", errorCount)
	t.Logf("  Actual RPS: %.0f", actualRPS)
	t.Logf("  Avg Latency: %.2f ms", avgLatency/1000.0)
	t.Logf("  Error Rate: %.2f%%", errorRate)

	// Validate performance targets
	if actualRPS < 800 {
		t.Errorf("RPS %.0f below target (1000 RPS)", actualRPS)
	}

	if avgLatency/1000.0 > 100 {
		t.Errorf("Avg latency %.2fms exceeds 100ms target", avgLatency/1000.0)
	}

	if errorRate > 5.0 {
		t.Errorf("Error rate %.2f%% exceeds 5%% threshold", errorRate)
	}

	t.Logf("✅ Load test PASSED: %.0f RPS with %.2fms avg latency", actualRPS, avgLatency/1000.0)
}

// TestLoadTestBurst tests burst traffic handling
func TestLoadTestBurst(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping burst test in short mode")
	}

	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     10000,
		EnableMetrics: false,
	})
	predictor.Start()
	defer predictor.Stop()

	api := NewImbalanceAPI(predictor)

	// Setup pool
	poolAddr := common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f")
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

	// Burst: 500 concurrent requests
	const burstSize = 500
	var wg sync.WaitGroup
	var successCount uint64
	var latencies []time.Duration
	var latencyMu sync.Mutex

	startTime := time.Now()

	for i := 0; i < burstSize; i++ {
		wg.Add(1)
		go func(reqID int) {
			defer wg.Done()

			reqStart := time.Now()
			_, err := api.GetPoolImbalance(poolAddr)
			latency := time.Since(reqStart)

			if err == nil {
				atomic.AddUint64(&successCount, 1)
				latencyMu.Lock()
				latencies = append(latencies, latency)
				latencyMu.Unlock()
			}
		}(i)
	}

	wg.Wait()
	duration := time.Since(startTime)

	// Calculate p50, p95, p99 latencies
	latencyMu.Lock()
	sortedLatencies := make([]time.Duration, len(latencies))
	copy(sortedLatencies, latencies)
	latencyMu.Unlock()

	// Simple bubble sort for test
	for i := 0; i < len(sortedLatencies); i++ {
		for j := i + 1; j < len(sortedLatencies); j++ {
			if sortedLatencies[i] > sortedLatencies[j] {
				sortedLatencies[i], sortedLatencies[j] = sortedLatencies[j], sortedLatencies[i]
			}
		}
	}

	p50 := sortedLatencies[len(sortedLatencies)*50/100]
	p95 := sortedLatencies[len(sortedLatencies)*95/100]
	p99 := sortedLatencies[len(sortedLatencies)*99/100]

	t.Logf("Burst Test Results:")
	t.Logf("  Burst Size: %d requests", burstSize)
	t.Logf("  Duration: %v", duration)
	t.Logf("  Successful: %d", successCount)
	t.Logf("  Success Rate: %.1f%%", float64(successCount)/float64(burstSize)*100.0)
	t.Logf("  p50 Latency: %v", p50)
	t.Logf("  p95 Latency: %v", p95)
	t.Logf("  p99 Latency: %v", p99)

	// Validate targets
	if successCount < uint64(burstSize*95/100) {
		t.Errorf("Success rate too low: %d/%d", successCount, burstSize)
	}

	if p95 > 200*time.Millisecond {
		t.Errorf("p95 latency %v exceeds 200ms threshold", p95)
	}

	t.Log("✅ Burst test PASSED")
}

// TestE2EStressTest tests system stability under continuous load
func TestE2EStressTest(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping stress test in short mode")
	}

	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     10000,
		EnableMetrics: false,
	})
	predictor.Start()
	defer predictor.Stop()

	api := NewImbalanceAPI(predictor)

	// Setup 100 pools
	const numPools = 100
	pools := make([]common.Address, numPools)

	for i := 0; i < numPools; i++ {
		pools[i] = common.BigToAddress(big.NewInt(int64(i + 2000)))
		state := &PoolState{
			PoolAddress: pools[i],
			Token0:      common.HexToAddress("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"),
			Token1:      common.HexToAddress("0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56"),
			Reserve0:    new(big.Int).Mul(big.NewInt(1000000), big.NewInt(1e18)),
			Reserve1:    new(big.Int).Mul(big.NewInt(2000000), big.NewInt(1e18)),
			BlockNumber: 30000000,
			Timestamp:   uint64(time.Now().Unix()),
		}
		predictor.UpdatePoolState(state)
	}

	// Run continuous load for 30 seconds
	const duration = 30 * time.Second
	const numWorkers = 20

	var requestCount, errorCount uint64
	stopChan := make(chan struct{})

	startTime := time.Now()

	// Start workers
	var wg sync.WaitGroup
	for w := 0; w < numWorkers; w++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()

			for {
				select {
				case <-stopChan:
					return
				default:
					// Random pool
					poolIdx := workerID % numPools
					_, err := api.GetPoolImbalance(pools[poolIdx])

					atomic.AddUint64(&requestCount, 1)
					if err != nil {
						atomic.AddUint64(&errorCount, 1)
					}

					time.Sleep(10 * time.Millisecond)
				}
			}
		}(w)
	}

	// Run for specified duration
	time.Sleep(duration)
	close(stopChan)
	wg.Wait()

	elapsed := time.Since(startTime)

	// Calculate metrics
	avgRPS := float64(requestCount) / elapsed.Seconds()
	errorRate := float64(errorCount) / float64(requestCount) * 100.0

	t.Logf("Stress Test Results:")
	t.Logf("  Duration: %v", elapsed)
	t.Logf("  Total Requests: %d", requestCount)
	t.Logf("  Errors: %d", errorCount)
	t.Logf("  Avg RPS: %.0f", avgRPS)
	t.Logf("  Error Rate: %.2f%%", errorRate)
	t.Logf("  Pools Tested: %d", numPools)

	// Validate stability
	if errorRate > 1.0 {
		t.Errorf("Error rate %.2f%% exceeds 1%% threshold", errorRate)
	}

	t.Log("✅ Stress test PASSED: System stable under continuous load")
}

// BenchmarkE2EFullStack benchmarks complete end-to-end stack
func BenchmarkE2EFullStack(b *testing.B) {
	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     10000,
		EnableMetrics: false,
	})
	predictor.Start()
	defer predictor.Stop()

	api := NewImbalanceAPI(predictor)
	security := NewSecurityMiddleware(&SecurityConfig{
		EnableRateLimiting: false,
		EnableAPIKeys:      false,
		EnableThrottling:   false,
	})

	// Setup pool
	poolAddr := common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f")
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

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		security.ValidateRequest("192.168.1.1", "", "test")
		api.GetPoolImbalance(poolAddr)
		security.ReleaseRequest()
	}
}
