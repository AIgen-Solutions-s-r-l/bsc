// Copyright 2024 The go-ethereum Authors
// This file is part of the go-ethereum library.

// Package legacypool implements the BSC Imbalance Prediction Engine
// CPMM Simulator - Issue #6
//
// This simulator implements the Uniswap V2 Constant Product Market Maker formula
// for simulating swap transactions and predicting pool states.
//
// Formula: x * y = k (constant product)
// With 0.3% LP fee: amountOut = (amountIn × 9970 × reserveOut) / (reserveIn × 10000 + amountIn × 9970)
//
// Target Performance: <50μs per swap simulation

package legacypool

import (
	"errors"
	"math/big"
	"sort"
	"time"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
)

var (
	// ErrInsufficientLiquidity is returned when a pool has insufficient liquidity for a swap
	ErrInsufficientLiquidity = errors.New("insufficient liquidity")

	// ErrInvalidAmountIn is returned when swap amount is zero or negative
	ErrInvalidAmountIn = errors.New("invalid amount in")

	// ErrInvalidReserves is returned when pool reserves are invalid
	ErrInvalidReserves = errors.New("invalid reserves")
)

// PendingSwap represents a swap transaction extracted from the mempool
type PendingSwap struct {
	TxHash      common.Hash    // Transaction hash
	PoolAddress common.Address // Pool being swapped on
	TokenIn     common.Address // Input token address
	TokenOut    common.Address // Output token address
	AmountIn    *big.Int       // Input amount
	AmountOutMin *big.Int      // Minimum output amount (slippage tolerance)
	GasPrice    *big.Int       // Gas price for ordering
	Timestamp   uint64         // Timestamp when added to mempool
}

// SimulationResult represents the result of simulating a swap
type SimulationResult struct {
	AmountOut       *big.Int   // Calculated output amount
	NewReserve0     *big.Int   // New reserve of token0 after swap
	NewReserve1     *big.Int   // New reserve of token1 after swap
	PriceImpact     float64    // Price impact percentage
	EffectivePrice  *big.Float // Effective price (amountOut / amountIn)
	ExecutionPath   string     // "token0->token1" or "token1->token0"
}

// CPMMSimulator implements Uniswap V2 constant product market maker simulation
type CPMMSimulator struct {
	feeNumerator   *big.Int // 9970 (0.3% fee)
	feeDenominator *big.Int // 10000
}

// NewCPMMSimulator creates a new CPMM simulator with 0.3% fee
func NewCPMMSimulator() *CPMMSimulator {
	return &CPMMSimulator{
		feeNumerator:   big.NewInt(9970), // 100% - 0.3% = 99.70%
		feeDenominator: big.NewInt(10000),
	}
}

// SimulateSwap simulates a single swap and returns the new pool state
// Uses the Uniswap V2 formula: amountOut = (amountIn × 9970 × reserveOut) / (reserveIn × 10000 + amountIn × 9970)
//
// Parameters:
//   - currentState: Current pool state (reserves)
//   - swap: Pending swap transaction details
//
// Returns:
//   - SimulationResult with amountOut and new reserves
//   - error if simulation fails
func (sim *CPMMSimulator) SimulateSwap(currentState *PoolState, swap *PendingSwap) (*SimulationResult, error) {
	if currentState == nil {
		return nil, ErrInvalidReserves
	}

	if swap.AmountIn == nil || swap.AmountIn.Sign() <= 0 {
		return nil, ErrInvalidAmountIn
	}

	// Determine swap direction
	var reserveIn, reserveOut *big.Int
	var isToken0ToToken1 bool

	if swap.TokenIn == currentState.Token0 {
		// Swapping token0 for token1
		reserveIn = currentState.Reserve0
		reserveOut = currentState.Reserve1
		isToken0ToToken1 = true
	} else if swap.TokenIn == currentState.Token1 {
		// Swapping token1 for token0
		reserveIn = currentState.Reserve1
		reserveOut = currentState.Reserve0
		isToken0ToToken1 = false
	} else {
		return nil, errors.New("token not in pool")
	}

	// Validate reserves
	if reserveIn == nil || reserveOut == nil || reserveIn.Sign() <= 0 || reserveOut.Sign() <= 0 {
		return nil, ErrInvalidReserves
	}

	// Calculate amountOut using CPMM formula with fee
	// amountOut = (amountIn × 9970 × reserveOut) / (reserveIn × 10000 + amountIn × 9970)

	// Step 1: amountIn × 9970
	amountInWithFee := new(big.Int).Mul(swap.AmountIn, sim.feeNumerator)

	// Step 2: amountInWithFee × reserveOut
	numerator := new(big.Int).Mul(amountInWithFee, reserveOut)

	// Step 3: reserveIn × 10000
	denominator := new(big.Int).Mul(reserveIn, sim.feeDenominator)

	// Step 4: denominator + amountInWithFee
	denominator.Add(denominator, amountInWithFee)

	// Step 5: numerator / denominator
	amountOut := new(big.Int).Div(numerator, denominator)

	// Check if output exceeds reserve (shouldn't happen with valid CPMM)
	if amountOut.Cmp(reserveOut) >= 0 {
		return nil, ErrInsufficientLiquidity
	}

	// Calculate new reserves
	var newReserve0, newReserve1 *big.Int
	if isToken0ToToken1 {
		newReserve0 = new(big.Int).Add(reserveIn, swap.AmountIn)
		newReserve1 = new(big.Int).Sub(reserveOut, amountOut)
	} else {
		newReserve1 = new(big.Int).Add(reserveIn, swap.AmountIn)
		newReserve0 = new(big.Int).Sub(reserveOut, amountOut)
	}

	// Calculate price impact
	// Price impact = |1 - (amountOut / expectedAmountOut)| × 100%
	// Where expectedAmountOut = amountIn × (reserveOut / reserveIn)
	priceImpact := calculatePriceImpact(swap.AmountIn, amountOut, reserveIn, reserveOut)

	// Calculate effective price
	effectivePrice := new(big.Float).Quo(
		new(big.Float).SetInt(amountOut),
		new(big.Float).SetInt(swap.AmountIn),
	)

	executionPath := "token0->token1"
	if !isToken0ToToken1 {
		executionPath = "token1->token0"
	}

	return &SimulationResult{
		AmountOut:      amountOut,
		NewReserve0:    newReserve0,
		NewReserve1:    newReserve1,
		PriceImpact:    priceImpact,
		EffectivePrice: effectivePrice,
		ExecutionPath:  executionPath,
	}, nil
}

// SimulateBatch simulates multiple pending swaps in order (sorted by gas price)
// Implements Tier 1 ordering strategy: highest gas price first
//
// Parameters:
//   - initialState: Initial pool state before any swaps
//   - swaps: List of pending swaps (will be sorted by gas price)
//
// Returns:
//   - Final pool state after all swaps
//   - Slice of individual simulation results
//   - error if any simulation fails
func (sim *CPMMSimulator) SimulateBatch(initialState *PoolState, swaps []*PendingSwap) (*PoolState, []*SimulationResult, error) {
	if initialState == nil {
		return nil, nil, ErrInvalidReserves
	}

	if len(swaps) == 0 {
		// No swaps, return initial state
		return initialState, nil, nil
	}

	// Sort swaps by gas price (descending - highest first)
	// This implements the Tier 1 ordering strategy from ADR-005
	sortedSwaps := make([]*PendingSwap, len(swaps))
	copy(sortedSwaps, swaps)
	sort.Slice(sortedSwaps, func(i, j int) bool {
		return sortedSwaps[i].GasPrice.Cmp(sortedSwaps[j].GasPrice) > 0
	})

	// Simulate each swap sequentially
	currentState := &PoolState{
		PoolAddress: initialState.PoolAddress,
		Token0:      initialState.Token0,
		Token1:      initialState.Token1,
		Reserve0:    new(big.Int).Set(initialState.Reserve0),
		Reserve1:    new(big.Int).Set(initialState.Reserve1),
		BlockNumber: initialState.BlockNumber,
		Timestamp:   initialState.Timestamp,
	}

	results := make([]*SimulationResult, 0, len(sortedSwaps))

	for _, swap := range sortedSwaps {
		result, err := sim.SimulateSwap(currentState, swap)
		if err != nil {
			// Skip failed swaps (e.g., insufficient liquidity, slippage exceeded)
			continue
		}

		// Check slippage tolerance
		if swap.AmountOutMin != nil && result.AmountOut.Cmp(swap.AmountOutMin) < 0 {
			// Slippage exceeded, transaction would revert
			continue
		}

		// Update current state for next swap
		currentState.Reserve0 = result.NewReserve0
		currentState.Reserve1 = result.NewReserve1

		results = append(results, result)
	}

	return currentState, results, nil
}

// PredictPoolState predicts the final pool state after processing all pending swaps
// This is the main prediction method used by the imbalance detector
func (sim *CPMMSimulator) PredictPoolState(initialState *PoolState, pendingSwaps []*PendingSwap) (*PoolState, error) {
	finalState, _, err := sim.SimulateBatch(initialState, pendingSwaps)
	return finalState, err
}

// ValidateInvariant checks that the constant product invariant holds after a swap
// k_before ≤ k_after (due to fees, k should increase slightly)
func (sim *CPMMSimulator) ValidateInvariant(stateBefore, stateAfter *PoolState) bool {
	if stateBefore == nil || stateAfter == nil {
		return false
	}

	// k_before = reserve0 × reserve1
	kBefore := new(big.Int).Mul(stateBefore.Reserve0, stateBefore.Reserve1)

	// k_after = reserve0 × reserve1
	kAfter := new(big.Int).Mul(stateAfter.Reserve0, stateAfter.Reserve1)

	// k should remain constant or increase (due to fees)
	// Allow for small rounding errors (0.01%)
	tolerance := new(big.Int).Div(kBefore, big.NewInt(10000))
	minAcceptable := new(big.Int).Sub(kBefore, tolerance)

	return kAfter.Cmp(minAcceptable) >= 0
}

// ExtractSwapFromTx extracts swap parameters from a transaction
// Parses the transaction data to extract amountIn, amountOutMin, and path
func ExtractSwapFromTx(tx *types.Transaction, poolAddr common.Address) (*PendingSwap, error) {
	data := tx.Data()
	if len(data) < 4 {
		return nil, errors.New("invalid transaction data")
	}

	// Extract method signature
	methodSig := common.Bytes2Hex(data[:4])

	// For simplicity, we'll implement a basic parser for swapExactTokensForTokens (0x38ed1739)
	// Full implementation would handle all swap method signatures
	if methodSig != "38ed1739" {
		return nil, errors.New("unsupported swap method")
	}

	// Parse ABI-encoded parameters
	// swapExactTokensForTokens(uint amountIn, uint amountOutMin, address[] path, address to, uint deadline)
	if len(data) < 164 { // 4 + 32*5 = minimum length
		return nil, errors.New("insufficient data length")
	}

	// Extract amountIn (offset 4, length 32)
	amountIn := new(big.Int).SetBytes(data[4:36])

	// Extract amountOutMin (offset 36, length 32)
	amountOutMin := new(big.Int).SetBytes(data[36:68])

	// Note: Full implementation would parse the path array to extract tokenIn/tokenOut
	// For now, return a simplified PendingSwap structure

	return &PendingSwap{
		TxHash:       tx.Hash(),
		PoolAddress:  poolAddr,
		AmountIn:     amountIn,
		AmountOutMin: amountOutMin,
		GasPrice:     tx.GasPrice(),
		Timestamp:    uint64(time.Now().Unix()),
	}, nil
}

// calculatePriceImpact calculates the price impact of a swap
// Price impact = |(actualPrice - expectedPrice) / expectedPrice| × 100%
func calculatePriceImpact(amountIn, amountOut, reserveIn, reserveOut *big.Int) float64 {
	// Expected price without slippage: reserveOut / reserveIn
	expectedPrice := new(big.Float).Quo(
		new(big.Float).SetInt(reserveOut),
		new(big.Float).SetInt(reserveIn),
	)

	// Actual price: amountOut / amountIn
	actualPrice := new(big.Float).Quo(
		new(big.Float).SetInt(amountOut),
		new(big.Float).SetInt(amountIn),
	)

	// Price impact = |1 - (actualPrice / expectedPrice)| × 100
	ratio := new(big.Float).Quo(actualPrice, expectedPrice)
	impact := new(big.Float).Sub(big.NewFloat(1.0), ratio)
	impact.Abs(impact)
	impact.Mul(impact, big.NewFloat(100.0))

	result, _ := impact.Float64()
	return result
}
