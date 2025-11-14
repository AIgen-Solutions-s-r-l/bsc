// Copyright 2024 The go-ethereum Authors
// This file is part of the go-ethereum library.

// Package legacypool implements the BSC Imbalance Prediction Engine
// Imbalance Detector - Issue #7
//
// This detector analyzes predicted pool states to identify liquidity imbalances
// and calculate imbalance scores for user consumption via RPC API.
//
// Imbalance Score: |Reserve0 - Reserve1| / (Reserve0 + Reserve1) × 100%
//
// Classification:
//   0-10%:   Balanced
//   10-20%:  Slight imbalance
//   20-40%:  Moderate imbalance
//   40-60%:  Severe imbalance
//   60-100%: Critical imbalance

package legacypool

import (
	"fmt"
	"math/big"
	"sync"
	"time"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/log"
	"github.com/ethereum/go-ethereum/metrics"
)

// ImbalanceLevel represents the severity of a pool imbalance
type ImbalanceLevel int

const (
	Balanced       ImbalanceLevel = iota // 0-10%
	SlightImbalance                      // 10-20%
	ModerateImbalance                    // 20-40%
	SevereImbalance                      // 40-60%
	CriticalImbalance                    // 60-100%
)

func (level ImbalanceLevel) String() string {
	switch level {
	case Balanced:
		return "balanced"
	case SlightImbalance:
		return "slight"
	case ModerateImbalance:
		return "moderate"
	case SevereImbalance:
		return "severe"
	case CriticalImbalance:
		return "critical"
	default:
		return "unknown"
	}
}

// ImbalanceResult contains the detected imbalance information
type ImbalanceResult struct {
	PoolAddress     common.Address // Pool contract address
	CurrentState    *PoolState     // Current pool state
	PredictedState  *PoolState     // Predicted pool state after pending swaps
	ImbalanceScore  float64        // Imbalance score (0-100%)
	Level           ImbalanceLevel // Imbalance severity level
	ProfitOpportunity *big.Int     // Estimated arbitrage profit (in wei)
	Confidence      float64        // Prediction confidence (0-100%)
	Timestamp       time.Time      // When prediction was made
	PendingSwaps    int            // Number of pending swaps considered
}

// ImbalanceDetector detects and scores liquidity pool imbalances
type ImbalanceDetector struct {
	mu      sync.RWMutex
	metrics *ImbalanceMetrics
}

// ImbalanceMetrics tracks Prometheus metrics for the imbalance detector
type ImbalanceMetrics struct {
	// Counters
	PredictionsTotal      *metrics.Counter   // Total predictions made
	SwapSimulationsTotal  *metrics.Counter   // Total swaps simulated
	ErrorsTotal           *metrics.Counter   // Total errors encountered

	// Histograms (interfaces, not pointers)
	ImbalanceScoreHist    metrics.Histogram // Distribution of imbalance scores
	PredictionLatency     metrics.Histogram // Prediction latency

	// Gauges (per pool)
	ImbalanceScoreGauge   *metrics.Gauge     // Current imbalance score
	PredictionAccuracy    *metrics.Gauge     // Prediction accuracy
	ConfidenceGauge       *metrics.Gauge     // Prediction confidence
}

// NewImbalanceDetector creates a new imbalance detector with Prometheus metrics
func NewImbalanceDetector() *ImbalanceDetector {
	return &ImbalanceDetector{
		metrics: &ImbalanceMetrics{
			PredictionsTotal:     metrics.NewRegisteredCounter("imbalance/predictions/total", nil),
			SwapSimulationsTotal: metrics.NewRegisteredCounter("imbalance/swaps/simulated", nil),
			ErrorsTotal:          metrics.NewRegisteredCounter("imbalance/errors/total", nil),
			ImbalanceScoreHist:   metrics.NewRegisteredHistogram("imbalance/score/distribution", nil, metrics.NewExpDecaySample(1028, 0.015)),
			PredictionLatency:    metrics.NewRegisteredHistogram("imbalance/prediction/latency", nil, metrics.NewExpDecaySample(1028, 0.015)),
			ImbalanceScoreGauge:  metrics.NewRegisteredGauge("imbalance/score/current", nil),
			PredictionAccuracy:   metrics.NewRegisteredGauge("imbalance/prediction/accuracy", nil),
			ConfidenceGauge:      metrics.NewRegisteredGauge("imbalance/prediction/confidence", nil),
		},
	}
}

// DetectImbalance analyzes current and predicted pool states to detect imbalances
func (d *ImbalanceDetector) DetectImbalance(
	currentState *PoolState,
	predictedState *PoolState,
	pendingSwaps []*PendingSwap,
) (*ImbalanceResult, error) {
	startTime := time.Now()
	defer func() {
		d.metrics.PredictionsTotal.Inc(1)
		d.metrics.PredictionLatency.Update(time.Since(startTime).Microseconds())
	}()

	if currentState == nil || predictedState == nil {
		d.metrics.ErrorsTotal.Inc(1)
		return nil, ErrInvalidReserves
	}

	// Calculate imbalance score for predicted state
	score := d.calculateImbalanceScore(predictedState)
	level := d.classifyImbalance(score)

	// Calculate confidence based on number of pending swaps and reserve sizes
	confidence := d.calculateConfidence(currentState, len(pendingSwaps))

	// Estimate profit opportunity (arbitrage between imbalanced reserves)
	profit := d.estimateProfitOpportunity(predictedState, score)

	result := &ImbalanceResult{
		PoolAddress:       predictedState.PoolAddress,
		CurrentState:      currentState,
		PredictedState:    predictedState,
		ImbalanceScore:    score,
		Level:             level,
		ProfitOpportunity: profit,
		Confidence:        confidence,
		Timestamp:         time.Now(),
		PendingSwaps:      len(pendingSwaps),
	}

	// Update metrics
	d.metrics.ImbalanceScoreHist.Update(int64(score * 100))
	d.metrics.ImbalanceScoreGauge.Update(int64(score * 100))
	d.metrics.ConfidenceGauge.Update(int64(confidence * 100))
	d.metrics.SwapSimulationsTotal.Inc(int64(len(pendingSwaps)))

	log.Debug("Imbalance detected",
		"pool", result.PoolAddress.Hex(),
		"score", score,
		"level", level.String(),
		"confidence", confidence,
		"swaps", len(pendingSwaps))

	return result, nil
}

// calculateImbalanceScore computes the imbalance score using the formula:
// Score = |Reserve0 - Reserve1| / (Reserve0 + Reserve1) × 100%
func (d *ImbalanceDetector) calculateImbalanceScore(state *PoolState) float64 {
	if state.Reserve0.Sign() == 0 || state.Reserve1.Sign() == 0 {
		return 100.0 // Critical imbalance if either reserve is zero
	}

	// |Reserve0 - Reserve1|
	diff := new(big.Int).Sub(state.Reserve0, state.Reserve1)
	diff.Abs(diff)

	// Reserve0 + Reserve1
	sum := new(big.Int).Add(state.Reserve0, state.Reserve1)

	// Avoid division by zero
	if sum.Sign() == 0 {
		return 100.0
	}

	// diff / sum × 100
	diffFloat := new(big.Float).SetInt(diff)
	sumFloat := new(big.Float).SetInt(sum)
	ratio := new(big.Float).Quo(diffFloat, sumFloat)
	ratio.Mul(ratio, big.NewFloat(100.0))

	score, _ := ratio.Float64()
	return score
}

// classifyImbalance classifies the imbalance severity based on score
func (d *ImbalanceDetector) classifyImbalance(score float64) ImbalanceLevel {
	switch {
	case score < 10.0:
		return Balanced
	case score < 20.0:
		return SlightImbalance
	case score < 40.0:
		return ModerateImbalance
	case score < 60.0:
		return SevereImbalance
	default:
		return CriticalImbalance
	}
}

// calculateConfidence estimates prediction confidence based on:
// - Pool reserve sizes (larger = more confident)
// - Number of pending swaps (fewer = more confident)
// - Historical accuracy (if available)
func (d *ImbalanceDetector) calculateConfidence(state *PoolState, numSwaps int) float64 {
	// Base confidence: 100%
	confidence := 100.0

	// Reduce confidence for many pending swaps (complexity)
	// Each swap reduces confidence by 2%, minimum 50%
	swapPenalty := float64(numSwaps) * 2.0
	if swapPenalty > 50.0 {
		swapPenalty = 50.0
	}
	confidence -= swapPenalty

	// Reduce confidence for small reserves (higher slippage risk)
	// Reserves < 100 ETH equivalent = -20% confidence
	minReserve := state.Reserve0
	if state.Reserve1.Cmp(minReserve) < 0 {
		minReserve = state.Reserve1
	}

	// Assuming 1e18 = 1 token, 100e18 = 100 tokens
	hundredTokens := new(big.Int).Mul(big.NewInt(100), big.NewInt(1e18))
	if minReserve.Cmp(hundredTokens) < 0 {
		confidence -= 20.0
	}

	// Confidence cannot be negative
	if confidence < 0 {
		confidence = 0
	}

	return confidence
}

// estimateProfitOpportunity estimates potential arbitrage profit from imbalance
// This is a simplified estimate: actual profit depends on execution and fees
func (d *ImbalanceDetector) estimateProfitOpportunity(state *PoolState, score float64) *big.Int {
	if score < 10.0 {
		// Balanced pools have minimal arbitrage opportunity
		return big.NewInt(0)
	}

	// Simple estimate: profit proportional to imbalance and smaller reserve
	minReserve := state.Reserve0
	if state.Reserve1.Cmp(minReserve) < 0 {
		minReserve = state.Reserve1
	}

	// Profit ≈ (score / 100) × minReserve × 0.003 (accounting for 0.3% LP fee)
	profitFloat := new(big.Float).SetInt(minReserve)
	profitFloat.Mul(profitFloat, big.NewFloat(score/100.0))
	profitFloat.Mul(profitFloat, big.NewFloat(0.003)) // 0.3% of imbalanced amount

	profit, _ := profitFloat.Int(nil)
	return profit
}

// GetImbalanceLevel returns the severity level for a given score
func GetImbalanceLevel(score float64) ImbalanceLevel {
	switch {
	case score < 10.0:
		return Balanced
	case score < 20.0:
		return SlightImbalance
	case score < 40.0:
		return ModerateImbalance
	case score < 60.0:
		return SevereImbalance
	default:
		return CriticalImbalance
	}
}

// ShouldAlert determines if an imbalance warrants an alert
// Alerts are triggered for moderate or higher imbalances
func (result *ImbalanceResult) ShouldAlert() bool {
	return result.Level >= ModerateImbalance
}

// IsActionable determines if the imbalance represents an actionable opportunity
// Actionable if: moderate+ imbalance AND high confidence AND non-zero profit
func (result *ImbalanceResult) IsActionable() bool {
	return result.Level >= ModerateImbalance &&
		result.Confidence >= 70.0 &&
		result.ProfitOpportunity.Sign() > 0
}

// String returns a human-readable representation of the imbalance result
func (result *ImbalanceResult) String() string {
	return fmt.Sprintf(
		"Pool %s: Score=%.2f%% (%s), Confidence=%.1f%%, Profit=%s wei, Swaps=%d",
		result.PoolAddress.Hex()[:10],
		result.ImbalanceScore,
		result.Level.String(),
		result.Confidence,
		result.ProfitOpportunity.String(),
		result.PendingSwaps,
	)
}
