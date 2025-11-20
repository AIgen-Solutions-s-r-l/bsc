// Copyright 2024 The go-ethereum Authors
// This file is part of the go-ethereum library.

// Unit tests for BSC Imbalance Prediction RPC API

package legacypool

import (
	"context"
	"math/big"
	"testing"
	"time"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/rpc"
)

// TestGetPoolImbalance tests the GetPoolImbalance RPC method
func TestGetPoolImbalance(t *testing.T) {
	// Setup predictor
	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     100,
		EnableMetrics: false,
	})
	predictor.Start()
	defer predictor.Stop()

	// Setup API
	api := NewImbalanceAPI(predictor)

	// Setup pool state
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

	// Test successful query
	response, err := api.GetPoolImbalance(poolAddr)
	if err != nil {
		t.Fatalf("GetPoolImbalance failed: %v", err)
	}

	// Validate response
	if response == nil {
		t.Fatal("Response should not be nil")
	}

	if response.PoolAddress != poolAddr.Hex() {
		t.Errorf("Expected pool address %s, got %s", poolAddr.Hex(), response.PoolAddress)
	}

	if response.ImbalanceScore < 0 || response.ImbalanceScore > 100 {
		t.Errorf("Imbalance score out of range: %.2f", response.ImbalanceScore)
	}

	if response.Confidence < 0 || response.Confidence > 100 {
		t.Errorf("Confidence out of range: %.2f", response.Confidence)
	}

	if response.Timestamp == 0 {
		t.Error("Timestamp should not be zero")
	}

	validLevels := map[string]bool{
		"balanced": true, "slight": true, "moderate": true,
		"severe": true, "critical": true,
	}
	if !validLevels[response.Level] {
		t.Errorf("Invalid level: %s", response.Level)
	}

	t.Logf("GetPoolImbalance successful: score=%.2f%%, level=%s, confidence=%.1f%%",
		response.ImbalanceScore, response.Level, response.Confidence)
}

// TestGetPoolImbalanceInvalidAddress tests error handling for invalid addresses
func TestGetPoolImbalanceInvalidAddress(t *testing.T) {
	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     100,
		EnableMetrics: false,
	})
	predictor.Start()
	defer predictor.Stop()

	api := NewImbalanceAPI(predictor)

	// Test with zero address
	_, err := api.GetPoolImbalance(common.Address{})
	if err != ErrInvalidPoolAddress {
		t.Errorf("Expected ErrInvalidPoolAddress, got %v", err)
	}
}

// TestGetPoolImbalancePoolNotFound tests error when pool is not in cache
func TestGetPoolImbalancePoolNotFound(t *testing.T) {
	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     100,
		EnableMetrics: false,
	})
	predictor.Start()
	defer predictor.Stop()

	api := NewImbalanceAPI(predictor)

	// Query non-existent pool
	poolAddr := common.HexToAddress("0x0000000000000000000000000000000000000001")
	_, err := api.GetPoolImbalance(poolAddr)
	if err == nil {
		t.Error("Expected error for non-existent pool")
	}
}

// TestGetPoolImbalancePredictorNotRunning tests error when predictor is stopped
func TestGetPoolImbalancePredictorNotRunning(t *testing.T) {
	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     100,
		EnableMetrics: false,
	})
	// Don't start predictor

	api := NewImbalanceAPI(predictor)

	poolAddr := common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f")
	_, err := api.GetPoolImbalance(poolAddr)
	if err != ErrPredictorNotRunning {
		t.Errorf("Expected ErrPredictorNotRunning, got %v", err)
	}
}

// TestGetAccuracy tests the GetAccuracy RPC method
func TestGetAccuracy(t *testing.T) {
	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     100,
		EnableMetrics: false,
	})
	predictor.Start()
	defer predictor.Stop()

	api := NewImbalanceAPI(predictor)

	// Get accuracy metrics
	response, err := api.GetAccuracy()
	if err != nil {
		t.Fatalf("GetAccuracy failed: %v", err)
	}

	// Validate response
	if response == nil {
		t.Fatal("Response should not be nil")
	}

	if response.AccuracyPercent < 0 || response.AccuracyPercent > 100 {
		t.Errorf("Accuracy out of range: %.2f", response.AccuracyPercent)
	}

	if response.MeanErrorPercent < 0 {
		t.Errorf("Mean error should be positive: %.2f", response.MeanErrorPercent)
	}

	if response.CacheHitRate < 0 || response.CacheHitRate > 100 {
		t.Errorf("Cache hit rate out of range: %.2f", response.CacheHitRate)
	}

	if response.FilterEfficiency < 0 || response.FilterEfficiency > 100 {
		t.Errorf("Filter efficiency out of range: %.2f", response.FilterEfficiency)
	}

	if response.LastUpdated == 0 {
		t.Error("LastUpdated should not be zero")
	}

	t.Logf("GetAccuracy successful: accuracy=%.1f%%, mean_error=%.2f%%, cache_hit_rate=%.1f%%",
		response.AccuracyPercent, response.MeanErrorPercent, response.CacheHitRate)
}

// TestGetAccuracyPredictorNotRunning tests error when predictor is stopped
func TestGetAccuracyPredictorNotRunning(t *testing.T) {
	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     100,
		EnableMetrics: false,
	})
	// Don't start predictor

	api := NewImbalanceAPI(predictor)

	_, err := api.GetAccuracy()
	if err != ErrPredictorNotRunning {
		t.Errorf("Expected ErrPredictorNotRunning, got %v", err)
	}
}

// TestGetStats tests the GetStats utility method
func TestGetStats(t *testing.T) {
	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     100,
		EnableMetrics: false,
	})
	predictor.Start()
	defer predictor.Stop()

	api := NewImbalanceAPI(predictor)

	// Get stats
	stats, err := api.GetStats()
	if err != nil {
		t.Fatalf("GetStats failed: %v", err)
	}

	// Validate stats
	if stats == nil {
		t.Fatal("Stats should not be nil")
	}

	// Check required fields
	requiredFields := []string{
		"running", "active_pools", "cache_size",
		"cache_hit_rate", "filter_efficiency",
		"active_subscriptions",
	}

	for _, field := range requiredFields {
		if _, ok := stats[field]; !ok {
			t.Errorf("Stats missing required field: %s", field)
		}
	}

	if running, ok := stats["running"].(bool); !ok || !running {
		t.Error("Predictor should be running")
	}

	t.Logf("GetStats successful: %d fields returned", len(stats))
}

// TestMultiplePoolQueries tests querying multiple pools in sequence
func TestMultiplePoolQueries(t *testing.T) {
	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     100,
		EnableMetrics: false,
	})
	predictor.Start()
	defer predictor.Stop()

	api := NewImbalanceAPI(predictor)

	// Setup 3 pools
	pools := []common.Address{
		common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f"),
		common.HexToAddress("0x58f876857a02d6762e0101bb5c46a8c1ed44dc16"),
		common.HexToAddress("0x7efaef62fddcca950418312c6c91aef321375a00"),
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

	// Query all pools
	for i, poolAddr := range pools {
		response, err := api.GetPoolImbalance(poolAddr)
		if err != nil {
			t.Fatalf("Query %d failed: %v", i, err)
		}

		if response.PoolAddress != poolAddr.Hex() {
			t.Errorf("Query %d: pool address mismatch", i)
		}
	}

	t.Logf("Successfully queried %d pools", len(pools))
}

// TestConcurrentQueries tests concurrent RPC queries
func TestConcurrentQueries(t *testing.T) {
	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     100,
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

	// Launch concurrent queries
	const numGoroutines = 10
	const queriesPerGoroutine = 50

	done := make(chan bool, numGoroutines)
	errors := make(chan error, numGoroutines*queriesPerGoroutine)

	for g := 0; g < numGoroutines; g++ {
		go func(goroutineID int) {
			for i := 0; i < queriesPerGoroutine; i++ {
				_, err := api.GetPoolImbalance(poolAddr)
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
		t.Errorf("Encountered %d errors during concurrent queries", errorCount)
	}

	totalQueries := numGoroutines * queriesPerGoroutine
	t.Logf("Successfully completed %d concurrent queries", totalQueries)
}

// TestSubscribeImbalance tests subscription creation and handling
func TestSubscribeImbalance(t *testing.T) {
	// Note: Full subscription testing requires a real RPC server
	// This test validates the basic subscription setup

	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     100,
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

	// Test subscription with invalid address
	ctx := context.Background()
	_, err := api.SubscribeImbalance(ctx, common.Address{})
	if err != ErrInvalidPoolAddress {
		t.Errorf("Expected ErrInvalidPoolAddress, got %v", err)
	}

	t.Log("Subscription validation successful")
}

// TestResponseFormat tests that response fields are correctly populated
func TestResponseFormat(t *testing.T) {
	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     100,
		EnableMetrics: false,
	})
	predictor.Start()
	defer predictor.Stop()

	api := NewImbalanceAPI(predictor)

	// Setup pool with known imbalance
	poolAddr := common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f")
	state := &PoolState{
		PoolAddress: poolAddr,
		Token0:      common.HexToAddress("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"),
		Token1:      common.HexToAddress("0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56"),
		Reserve0:    new(big.Int).Mul(big.NewInt(100000), big.NewInt(1e18)),  // 100K
		Reserve1:    new(big.Int).Mul(big.NewInt(500000), big.NewInt(1e18)),  // 500K (5x imbalance)
		BlockNumber: 30000000,
		Timestamp:   uint64(time.Now().Unix()),
	}
	predictor.UpdatePoolState(state)

	// Get prediction
	response, err := api.GetPoolImbalance(poolAddr)
	if err != nil {
		t.Fatalf("GetPoolImbalance failed: %v", err)
	}

	// Validate all fields are populated
	if response.PoolAddress == "" {
		t.Error("PoolAddress should not be empty")
	}

	if response.CurrentReserve0 == nil {
		t.Error("CurrentReserve0 should not be nil")
	}

	if response.CurrentReserve1 == nil {
		t.Error("CurrentReserve1 should not be nil")
	}

	if response.PredictedReserve0 == nil {
		t.Error("PredictedReserve0 should not be nil")
	}

	if response.PredictedReserve1 == nil {
		t.Error("PredictedReserve1 should not be nil")
	}

	if response.ProfitOpportunity == nil {
		t.Error("ProfitOpportunity should not be nil")
	}

	// This pool has significant imbalance (80%)
	if response.ImbalanceScore < 60 {
		t.Errorf("Expected high imbalance score, got %.2f", response.ImbalanceScore)
	}

	if response.Level != "critical" {
		t.Errorf("Expected critical level, got %s", response.Level)
	}

	t.Logf("Response format valid: all fields populated correctly")
}

// BenchmarkGetPoolImbalance benchmarks RPC query performance
func BenchmarkGetPoolImbalance(b *testing.B) {
	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     1000,
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

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		api.GetPoolImbalance(poolAddr)
	}
}

// BenchmarkGetAccuracy benchmarks accuracy query performance
func BenchmarkGetAccuracy(b *testing.B) {
	predictor := NewImbalancePredictor(&PredictorConfig{
		CacheSize:     1000,
		EnableMetrics: false,
	})
	predictor.Start()
	defer predictor.Stop()

	api := NewImbalanceAPI(predictor)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		api.GetAccuracy()
	}
}

// mockNotifier is a mock implementation of rpc.Notifier for testing
type mockNotifier struct {
	notifications []interface{}
}

func (m *mockNotifier) CreateSubscription() *rpc.Subscription {
	return &rpc.Subscription{
		ID: rpc.ID("test-sub-123"),
	}
}

func (m *mockNotifier) Notify(id rpc.ID, data interface{}) error {
	m.notifications = append(m.notifications, data)
	return nil
}

func (m *mockNotifier) Closed() <-chan interface{} {
	ch := make(chan interface{})
	return ch
}
