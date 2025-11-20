// Copyright 2024 The go-ethereum Authors
// This file is part of the go-ethereum library.
//
// The go-ethereum library is free software: you can redistribute it and/or modify
// it under the terms of the GNU Lesser General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

// Package legacypool implements the BSC Imbalance Prediction Engine
// DEX Transaction Filter - Issue #4
//
// This filter implements a two-stage filtering strategy (ADR-004) to efficiently
// identify swap transactions from the mempool with O(1) performance:
//
// Stage 1: Address whitelist (router addresses)
// Stage 2: Method signature check (swap method signatures)
//
// Target Performance: <1ms per transaction, 99.9% noise reduction

package legacypool

import (
	"sync"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
)

// DEXFilter filters transactions from known DEX router addresses
// and validates swap method signatures for efficient mempool monitoring
type DEXFilter struct {
	// routers maps DEX router addresses to their names for quick O(1) lookup
	routers map[common.Address]string

	// swapSigs maps method signatures (first 4 bytes) to method names
	swapSigs map[string]string

	// mu protects concurrent access to the filter configuration
	mu sync.RWMutex

	// stats tracks filter performance metrics
	stats *FilterStats
}

// FilterStats tracks DEX filter performance and accuracy metrics
type FilterStats struct {
	TotalProcessed   uint64 // Total transactions processed
	RouterMatches    uint64 // Transactions matching router whitelist
	SignatureMatches uint64 // Transactions matching swap signatures
	Filtered         uint64 // Transactions passing both stages
	mu               sync.Mutex
}

// KnownDEXRouters returns a map of known BSC DEX router addresses
// Updated as of November 2025 with top BSC DEXes
func KnownDEXRouters() map[common.Address]string {
	return map[common.Address]string{
		// PancakeSwap V2 Router
		common.HexToAddress("0x10ED43C718714eb63d5aA57B78B54704E256024E"): "PancakeSwap V2",

		// PancakeSwap V3 Router
		common.HexToAddress("0x1b81D678ffb9C0263b24A97847620C99d213eB14"): "PancakeSwap V3",

		// BiSwap Router
		common.HexToAddress("0x3a6d8cA21D1CF76F653A67577FA0D27453350dD8"): "BiSwap",

		// BakerySwap Router
		common.HexToAddress("0xCDe540d7eAFE93aC5fE6233Bee57E1270D3E330F"): "BakerySwap",

		// ApeSwap Router
		common.HexToAddress("0xcF0feBd3f17CEf5b47b0cD257aCf6025c5BFf3b7"): "ApeSwap",

		// MDEX Router
		common.HexToAddress("0x7DAe51BD3E3376B8c7c4900E9107f12Be3AF1bA8"): "MDEX",

		// SushiSwap Router (BSC)
		common.HexToAddress("0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506"): "SushiSwap",

		// BabySwap Router
		common.HexToAddress("0x325E343f1dE602396E256B67eFd1F61C3A6B38Bd"): "BabySwap",
	}
}

// SwapMethodSignatures returns known swap method signatures
// These are the first 4 bytes of keccak256(methodSignature)
func SwapMethodSignatures() map[string]string {
	return map[string]string{
		// Uniswap V2 / PancakeSwap V2 style
		"0x38ed1739": "swapExactTokensForTokens",
		"0x8803dbee": "swapTokensForExactTokens",
		"0x7ff36ab5": "swapExactETHForTokens",
		"0x4a25d94a": "swapTokensForExactETH",
		"0x18cbafe5": "swapExactTokensForETH",
		"0xfb3bdb41": "swapETHForExactTokens",

		// Supporting fee-on-transfer tokens
		"0x5c11d795": "swapExactTokensForTokensSupportingFeeOnTransferTokens",
		"0xb6f9de95": "swapExactETHForTokensSupportingFeeOnTransferTokens",
		"0x791ac947": "swapExactTokensForETHSupportingFeeOnTransferTokens",

		// Uniswap V3 / PancakeSwap V3 style
		"0x414bf389": "exactInputSingle",
		"0xc04b8d59": "exactInput",
		"0xdb3e2198": "exactOutputSingle",
		"0x09b81346": "exactOutput",

		// Multi-hop swaps
		"0x472b43f3": "swapExactIn",
		"0x42712a67": "swapExactOut",
	}
}

// NewDEXFilter creates a new DEX transaction filter with known routers and signatures
func NewDEXFilter() *DEXFilter {
	return &DEXFilter{
		routers:  KnownDEXRouters(),
		swapSigs: SwapMethodSignatures(),
		stats:    &FilterStats{},
	}
}

// IsSwapTransaction checks if a transaction is a swap on a known DEX
// Returns true if the transaction passes both stages:
// 1. Router address whitelist (O(1))
// 2. Method signature validation (O(1))
//
// Performance: <1μs per call, suitable for high-throughput mempool filtering
func (f *DEXFilter) IsSwapTransaction(tx *types.Transaction) bool {
	f.stats.incrementProcessed()

	// Stage 1: Router address whitelist check
	to := tx.To()
	if to == nil {
		// Contract creation transaction, not a swap
		return false
	}

	f.mu.RLock()
	_, isRouter := f.routers[*to]
	f.mu.RUnlock()

	if !isRouter {
		// Not sent to a known DEX router
		return false
	}

	f.stats.incrementRouterMatches()

	// Stage 2: Method signature validation
	data := tx.Data()
	if len(data) < 4 {
		// Invalid transaction data (must have at least 4-byte method signature)
		return false
	}

	// Extract method signature (first 4 bytes)
	methodSig := common.Bytes2Hex(data[:4])
	methodSig = "0x" + methodSig

	f.mu.RLock()
	_, isSwap := f.swapSigs[methodSig]
	f.mu.RUnlock()

	if isSwap {
		f.stats.incrementSignatureMatches()
		f.stats.incrementFiltered()
	}

	return isSwap
}

// GetRouterName returns the name of the DEX router for a given address
// Returns empty string if the address is not a known router
func (f *DEXFilter) GetRouterName(addr common.Address) string {
	f.mu.RLock()
	defer f.mu.RUnlock()
	return f.routers[addr]
}

// GetMethodName returns the method name for a given method signature
// Returns empty string if the signature is not known
func (f *DEXFilter) GetMethodName(sig string) string {
	f.mu.RLock()
	defer f.mu.RUnlock()
	return f.swapSigs[sig]
}

// AddRouter adds a new DEX router address to the whitelist
// Thread-safe for runtime configuration updates
func (f *DEXFilter) AddRouter(addr common.Address, name string) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.routers[addr] = name
}

// RemoveRouter removes a DEX router address from the whitelist
func (f *DEXFilter) RemoveRouter(addr common.Address) {
	f.mu.Lock()
	defer f.mu.Unlock()
	delete(f.routers, addr)
}

// AddMethodSignature adds a new swap method signature
func (f *DEXFilter) AddMethodSignature(sig string, name string) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.swapSigs[sig] = name
}

// GetStats returns a snapshot of the filter's performance statistics
func (f *DEXFilter) GetStats() FilterStats {
	f.stats.mu.Lock()
	defer f.stats.mu.Unlock()

	return FilterStats{
		TotalProcessed:   f.stats.TotalProcessed,
		RouterMatches:    f.stats.RouterMatches,
		SignatureMatches: f.stats.SignatureMatches,
		Filtered:         f.stats.Filtered,
	}
}

// ResetStats resets the filter's performance statistics
func (f *DEXFilter) ResetStats() {
	f.stats.mu.Lock()
	defer f.stats.mu.Unlock()

	f.stats.TotalProcessed = 0
	f.stats.RouterMatches = 0
	f.stats.SignatureMatches = 0
	f.stats.Filtered = 0
}

// FilterEfficiency returns the percentage of transactions that passed the filter
// Returns 0 if no transactions have been processed
func (f *DEXFilter) FilterEfficiency() float64 {
	stats := f.GetStats()
	if stats.TotalProcessed == 0 {
		return 0.0
	}
	return float64(stats.Filtered) / float64(stats.TotalProcessed) * 100.0
}

// NoiseReduction returns the percentage of transactions rejected by the filter
func (f *DEXFilter) NoiseReduction() float64 {
	return 100.0 - f.FilterEfficiency()
}

// incrementProcessed atomically increments the processed counter
func (s *FilterStats) incrementProcessed() {
	s.mu.Lock()
	s.TotalProcessed++
	s.mu.Unlock()
}

// incrementRouterMatches atomically increments the router matches counter
func (s *FilterStats) incrementRouterMatches() {
	s.mu.Lock()
	s.RouterMatches++
	s.mu.Unlock()
}

// incrementSignatureMatches atomically increments the signature matches counter
func (s *FilterStats) incrementSignatureMatches() {
	s.mu.Lock()
	s.SignatureMatches++
	s.mu.Unlock()
}

// incrementFiltered atomically increments the filtered counter
func (s *FilterStats) incrementFiltered() {
	s.mu.Lock()
	s.Filtered++
	s.mu.Unlock()
}
