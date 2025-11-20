// Copyright 2024 The go-ethereum Authors
// This file is part of the go-ethereum library.

// Package legacypool implements the BSC Imbalance Prediction Engine
// Main Orchestrator - Integrates all components
//
// This is the main entry point for the imbalance prediction feature.
// It orchestrates the DEX filter, pool cache, CPMM simulator, and imbalance detector
// to provide end-to-end mempool-based liquidity imbalance predictions.

package legacypool

import (
	"fmt"
	"sync"
	"time"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/event"
	"github.com/ethereum/go-ethereum/log"
	"github.com/ethereum/go-ethereum/metrics"
)

// ImbalancePredictor is the main orchestrator for the BSC Imbalance Prediction Engine
// It integrates all components to provide end-to-end predictions
type ImbalancePredictor struct {
	// Core components
	filter    *DEXFilter           // DEX transaction filter
	cache     *PoolCache           // Pool state cache
	simulator *CPMMSimulator       // CPMM simulation engine
	detector  *ImbalanceDetector   // Imbalance detector

	// Configuration
	config *PredictorConfig

	// State
	mu              sync.RWMutex
	running         bool
	pendingSwaps    map[common.Address][]*PendingSwap // Pending swaps per pool
	subscriptions   map[common.Address]*Subscription   // Active subscriptions

	// Metrics
	metrics *PredictorMetrics

	// Channels
	txFeed    event.Feed          // Transaction feed from mempool
	quit      chan struct{}       // Shutdown signal
}

// PredictorConfig contains configuration for the imbalance predictor
type PredictorConfig struct {
	CacheSize         int           // Pool cache size (default: 1000)
	PredictionWindow  time.Duration // Time window for pending swaps (default: 3s)
	UpdateInterval    time.Duration // Pool state update interval (default: 1s)
	MinConfidence     float64       // Minimum confidence threshold (default: 70%)
	EnableMetrics     bool          // Enable Prometheus metrics (default: true)
}

// DefaultPredictorConfig returns the default configuration
func DefaultPredictorConfig() *PredictorConfig {
	return &PredictorConfig{
		CacheSize:        1000,
		PredictionWindow: 3 * time.Second,
		UpdateInterval:   1 * time.Second,
		MinConfidence:    70.0,
		EnableMetrics:    true,
	}
}

// PredictorMetrics tracks Prometheus metrics for the predictor
type PredictorMetrics struct {
	// Counters (pointers to concrete types)
	TransactionsProcessed *metrics.Counter // Total transactions processed
	TransactionsFiltered  *metrics.Counter // Transactions passing filter
	PredictionsGenerated  *metrics.Counter // Total predictions generated
	CacheHits             *metrics.Counter // Cache hits
	CacheMisses           *metrics.Counter // Cache misses

	// Histograms (interfaces, not pointers)
	EndToEndLatency       metrics.Histogram // Total prediction latency
	FilterLatency         metrics.Histogram // DEX filter latency
	SimulationLatency     metrics.Histogram // CPMM simulation latency
	DetectionLatency      metrics.Histogram // Imbalance detection latency

	// Gauges (pointers to concrete types)
	ActivePools           *metrics.Gauge // Number of pools being tracked
	PendingSwapsTotal     *metrics.Gauge // Total pending swaps across all pools
	CacheUtilization      *metrics.Gauge // Cache utilization percentage
}

// NewImbalancePredictor creates a new imbalance predictor with the given configuration
func NewImbalancePredictor(config *PredictorConfig) *ImbalancePredictor {
	if config == nil {
		config = DefaultPredictorConfig()
	}

	predictor := &ImbalancePredictor{
		filter:    NewDEXFilter(),
		cache:     NewPoolCache(config.CacheSize),
		simulator: NewCPMMSimulator(),
		detector:  NewImbalanceDetector(),
		config:    config,
		pendingSwaps: make(map[common.Address][]*PendingSwap),
		subscriptions: make(map[common.Address]*Subscription),
		quit:      make(chan struct{}),
	}

	if config.EnableMetrics {
		predictor.metrics = &PredictorMetrics{
			TransactionsProcessed: metrics.NewRegisteredCounter("predictor/transactions/processed", nil),
			TransactionsFiltered:  metrics.NewRegisteredCounter("predictor/transactions/filtered", nil),
			PredictionsGenerated:  metrics.NewRegisteredCounter("predictor/predictions/generated", nil),
			CacheHits:             metrics.NewRegisteredCounter("predictor/cache/hits", nil),
			CacheMisses:           metrics.NewRegisteredCounter("predictor/cache/misses", nil),
			EndToEndLatency:       metrics.NewRegisteredHistogram("predictor/latency/e2e", nil, metrics.NewExpDecaySample(1028, 0.015)),
			FilterLatency:         metrics.NewRegisteredHistogram("predictor/latency/filter", nil, metrics.NewExpDecaySample(1028, 0.015)),
			SimulationLatency:     metrics.NewRegisteredHistogram("predictor/latency/simulation", nil, metrics.NewExpDecaySample(1028, 0.015)),
			DetectionLatency:      metrics.NewRegisteredHistogram("predictor/latency/detection", nil, metrics.NewExpDecaySample(1028, 0.015)),
			ActivePools:           metrics.NewRegisteredGauge("predictor/pools/active", nil),
			PendingSwapsTotal:     metrics.NewRegisteredGauge("predictor/swaps/pending", nil),
			CacheUtilization:      metrics.NewRegisteredGauge("predictor/cache/utilization", nil),
		}
	}

	return predictor
}

// Start starts the imbalance predictor
func (p *ImbalancePredictor) Start() error {
	p.mu.Lock()
	defer p.mu.Unlock()

	if p.running {
		return nil
	}

	p.running = true

	log.Info("Starting BSC Imbalance Predictor",
		"cacheSize", p.config.CacheSize,
		"predictionWindow", p.config.PredictionWindow,
		"updateInterval", p.config.UpdateInterval)

	// Start background workers
	go p.cleanupLoop()
	go p.metricsLoop()

	return nil
}

// Stop stops the imbalance predictor
func (p *ImbalancePredictor) Stop() error {
	p.mu.Lock()
	defer p.mu.Unlock()

	if !p.running {
		return nil
	}

	p.running = false
	close(p.quit)

	log.Info("Stopped BSC Imbalance Predictor")

	return nil
}

// OnPendingTransaction processes a new pending transaction from the mempool
// This is the main entry point called by the transaction pool
func (p *ImbalancePredictor) OnPendingTransaction(tx *types.Transaction) {
	startTime := time.Now()

	if p.metrics != nil {
		p.metrics.TransactionsProcessed.Inc(1)
		defer func() {
			p.metrics.EndToEndLatency.Update(time.Since(startTime).Microseconds())
		}()
	}

	// Stage 1: DEX Filter (O(1))
	filterStart := time.Now()
	if !p.filter.IsSwapTransaction(tx) {
		return // Not a swap, ignore
	}
	if p.metrics != nil {
		p.metrics.FilterLatency.Update(time.Since(filterStart).Nanoseconds())
		p.metrics.TransactionsFiltered.Inc(1)
	}

	// Extract swap details (simplified - full implementation would parse ABI)
	poolAddr := *tx.To() // In reality, extract from transaction data
	swap := &PendingSwap{
		TxHash:      tx.Hash(),
		PoolAddress: poolAddr,
		AmountIn:    tx.Value(), // Simplified
		GasPrice:    tx.GasPrice(),
		Timestamp:   uint64(time.Now().Unix()),
	}

	// Add to pending swaps
	p.mu.Lock()
	p.pendingSwaps[poolAddr] = append(p.pendingSwaps[poolAddr], swap)
	p.mu.Unlock()

	log.Debug("Detected swap transaction",
		"tx", tx.Hash().Hex(),
		"pool", poolAddr.Hex(),
		"gasPrice", tx.GasPrice())
}

// PredictPoolImbalance generates an imbalance prediction for a specific pool
// This is the main API method called via RPC
func (p *ImbalancePredictor) PredictPoolImbalance(poolAddr common.Address) (*ImbalanceResult, error) {
	startTime := time.Now()

	// Get current pool state from cache
	currentState, found := p.cache.Get(poolAddr)
	if !found {
		if p.metrics != nil {
			p.metrics.CacheMisses.Inc(1)
		}
		// Cache miss - fetch from chain (not implemented here, would use eth_call)
		return nil, fmt.Errorf("pool state not in cache")
	}

	if p.metrics != nil {
		p.metrics.CacheHits.Inc(1)
	}

	// Get pending swaps for this pool
	p.mu.RLock()
	pendingSwaps := make([]*PendingSwap, len(p.pendingSwaps[poolAddr]))
	copy(pendingSwaps, p.pendingSwaps[poolAddr])
	p.mu.RUnlock()

	if len(pendingSwaps) == 0 {
		// No pending swaps, return current state analysis
		return p.detector.DetectImbalance(currentState, currentState, nil)
	}

	// Stage 2: CPMM Simulation
	simStart := time.Now()
	predictedState, err := p.simulator.PredictPoolState(currentState, pendingSwaps)
	if err != nil {
		return nil, fmt.Errorf("simulation failed: %w", err)
	}
	if p.metrics != nil {
		p.metrics.SimulationLatency.Update(time.Since(simStart).Microseconds())
	}

	// Stage 3: Imbalance Detection
	detStart := time.Now()
	result, err := p.detector.DetectImbalance(currentState, predictedState, pendingSwaps)
	if err != nil {
		return nil, fmt.Errorf("detection failed: %w", err)
	}
	if p.metrics != nil {
		p.metrics.DetectionLatency.Update(time.Since(detStart).Microseconds())
		p.metrics.PredictionsGenerated.Inc(1)
	}

	log.Info("Generated imbalance prediction",
		"pool", poolAddr.Hex(),
		"score", result.ImbalanceScore,
		"level", result.Level.String(),
		"confidence", result.Confidence,
		"latency", time.Since(startTime))

	return result, nil
}

// GetPoolState retrieves the current cached state for a pool
func (p *ImbalancePredictor) GetPoolState(poolAddr common.Address) (*PoolState, bool) {
	return p.cache.Get(poolAddr)
}

// UpdatePoolState updates the cached state for a pool
// This would be called periodically or on-demand to refresh pool states
func (p *ImbalancePredictor) UpdatePoolState(state *PoolState) {
	p.cache.Set(state.PoolAddress, state)
}

// cleanupLoop periodically cleans up old pending swaps
func (p *ImbalancePredictor) cleanupLoop() {
	ticker := time.NewTicker(p.config.PredictionWindow)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			p.cleanupPendingSwaps()
		case <-p.quit:
			return
		}
	}
}

// cleanupPendingSwaps removes pending swaps older than the prediction window
func (p *ImbalancePredictor) cleanupPendingSwaps() {
	p.mu.Lock()
	defer p.mu.Unlock()

	now := uint64(time.Now().Unix())
	cutoff := now - uint64(p.config.PredictionWindow.Seconds())

	for poolAddr, swaps := range p.pendingSwaps {
		// Filter out old swaps
		filtered := make([]*PendingSwap, 0, len(swaps))
		for _, swap := range swaps {
			if swap.Timestamp > cutoff {
				filtered = append(filtered, swap)
			}
		}

		if len(filtered) == 0 {
			delete(p.pendingSwaps, poolAddr)
		} else {
			p.pendingSwaps[poolAddr] = filtered
		}
	}
}

// metricsLoop periodically updates aggregate metrics
func (p *ImbalancePredictor) metricsLoop() {
	if p.metrics == nil {
		return
	}

	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			p.updateMetrics()
		case <-p.quit:
			return
		}
	}
}

// updateMetrics updates aggregate Prometheus metrics
func (p *ImbalancePredictor) updateMetrics() {
	p.mu.RLock()
	activePools := len(p.pendingSwaps)
	totalSwaps := 0
	for _, swaps := range p.pendingSwaps {
		totalSwaps += len(swaps)
	}
	p.mu.RUnlock()

	cacheSize := p.cache.Len()
	cacheMax := p.config.CacheSize
	utilization := int64(float64(cacheSize) / float64(cacheMax) * 100.0)

	p.metrics.ActivePools.Update(int64(activePools))
	p.metrics.PendingSwapsTotal.Update(int64(totalSwaps))
	p.metrics.CacheUtilization.Update(utilization)
}

// GetStats returns current predictor statistics
func (p *ImbalancePredictor) GetStats() map[string]interface{} {
	p.mu.RLock()
	defer p.mu.RUnlock()

	stats := make(map[string]interface{})
	stats["running"] = p.running
	stats["active_pools"] = len(p.pendingSwaps)
	stats["cache_size"] = p.cache.Len()
	stats["cache_hit_rate"] = p.cache.HitRate()

	filterStats := p.filter.GetStats()
	stats["filter_total_processed"] = filterStats.TotalProcessed
	stats["filter_filtered"] = filterStats.Filtered
	stats["filter_efficiency"] = p.filter.FilterEfficiency()

	return stats
}

// Subscription represents an active subscription to pool imbalance updates
type Subscription struct {
	PoolAddress common.Address
	Ch          chan *ImbalanceResult
	Created     time.Time
}
