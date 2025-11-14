// Copyright 2024 The go-ethereum Authors
// This file is part of the go-ethereum library.

package legacypool

import (
	"math/big"
	"testing"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
)

// TestNewDEXFilter tests filter initialization
func TestNewDEXFilter(t *testing.T) {
	filter := NewDEXFilter()

	if filter == nil {
		t.Fatal("NewDEXFilter returned nil")
	}

	if len(filter.routers) == 0 {
		t.Error("Filter should be initialized with known routers")
	}

	if len(filter.swapSigs) == 0 {
		t.Error("Filter should be initialized with known swap signatures")
	}

	if filter.stats == nil {
		t.Error("Filter stats should be initialized")
	}
}

// TestIsSwapTransaction_ValidSwap tests detection of valid swap transactions
func TestIsSwapTransaction_ValidSwap(t *testing.T) {
	filter := NewDEXFilter()

	// PancakeSwap V2 Router address
	routerAddr := common.HexToAddress("0x10ED43C718714eb63d5aA57B78B54704E256024E")

	// swapExactTokensForTokens method signature (0x38ed1739)
	// Followed by dummy parameters
	data := common.Hex2Bytes("38ed1739" +
		"0000000000000000000000000000000000000000000000000de0b6b3a7640000" + // amountIn
		"0000000000000000000000000000000000000000000000000000000000000000" + // amountOutMin
		"0000000000000000000000000000000000000000000000000000000000000080" + // path offset
		"000000000000000000000000000000000000000000000000000000000000dead" + // to
		"0000000000000000000000000000000000000000000000000000000063a1e5e0") // deadline

	tx := types.NewTransaction(
		0,                   // nonce
		routerAddr,          // to
		big.NewInt(0),       // value
		300000,              // gas limit
		big.NewInt(5e9),     // gas price (5 Gwei)
		data,                // data
	)

	if !filter.IsSwapTransaction(tx) {
		t.Error("Valid swap transaction should be detected")
	}

	// Verify stats
	stats := filter.GetStats()
	if stats.TotalProcessed != 1 {
		t.Errorf("Expected 1 processed, got %d", stats.TotalProcessed)
	}
	if stats.Filtered != 1 {
		t.Errorf("Expected 1 filtered, got %d", stats.Filtered)
	}
}

// TestIsSwapTransaction_InvalidRouter tests rejection of non-DEX transactions
func TestIsSwapTransaction_InvalidRouter(t *testing.T) {
	filter := NewDEXFilter()

	// Random non-DEX address
	randomAddr := common.HexToAddress("0x1234567890123456789012345678901234567890")

	// Valid swap method signature but wrong router
	data := common.Hex2Bytes("38ed1739" + "00000000000000000000000000000000000000000000000000000000000000")

	tx := types.NewTransaction(0, randomAddr, big.NewInt(0), 300000, big.NewInt(5e9), data)

	if filter.IsSwapTransaction(tx) {
		t.Error("Transaction to non-DEX router should be rejected")
	}

	stats := filter.GetStats()
	if stats.RouterMatches != 0 {
		t.Errorf("Expected 0 router matches, got %d", stats.RouterMatches)
	}
}

// TestIsSwapTransaction_InvalidMethodSignature tests rejection of non-swap methods
func TestIsSwapTransaction_InvalidMethodSignature(t *testing.T) {
	filter := NewDEXFilter()

	// PancakeSwap V2 Router address (valid)
	routerAddr := common.HexToAddress("0x10ED43C718714eb63d5aA57B78B54704E256024E")

	// Invalid method signature (not a swap)
	// Using transfer(address,uint256) signature: 0xa9059cbb
	data := common.Hex2Bytes("a9059cbb" + "00000000000000000000000000000000000000000000000000000000000000")

	tx := types.NewTransaction(0, routerAddr, big.NewInt(0), 300000, big.NewInt(5e9), data)

	if filter.IsSwapTransaction(tx) {
		t.Error("Transaction with non-swap method should be rejected")
	}

	stats := filter.GetStats()
	if stats.RouterMatches != 1 {
		t.Errorf("Expected 1 router match, got %d", stats.RouterMatches)
	}
	if stats.SignatureMatches != 0 {
		t.Errorf("Expected 0 signature matches, got %d", stats.SignatureMatches)
	}
}

// TestIsSwapTransaction_ContractCreation tests rejection of contract creation
func TestIsSwapTransaction_ContractCreation(t *testing.T) {
	filter := NewDEXFilter()

	// Contract creation (to = nil)
	data := common.Hex2Bytes("38ed1739")

	tx := types.NewContractCreation(0, big.NewInt(0), 300000, big.NewInt(5e9), data)

	if filter.IsSwapTransaction(tx) {
		t.Error("Contract creation should be rejected")
	}
}

// TestIsSwapTransaction_ShortData tests rejection of transactions with insufficient data
func TestIsSwapTransaction_ShortData(t *testing.T) {
	filter := NewDEXFilter()

	routerAddr := common.HexToAddress("0x10ED43C718714eb63d5aA57B78B54704E256024E")

	// Data too short (less than 4 bytes)
	data := common.Hex2Bytes("38ed17")

	tx := types.NewTransaction(0, routerAddr, big.NewInt(0), 300000, big.NewInt(5e9), data)

	if filter.IsSwapTransaction(tx) {
		t.Error("Transaction with short data should be rejected")
	}
}

// TestMultipleDEXRouters tests filtering for different DEX routers
func TestMultipleDEXRouters(t *testing.T) {
	filter := NewDEXFilter()

	routers := []common.Address{
		common.HexToAddress("0x10ED43C718714eb63d5aA57B78B54704E256024E"), // PancakeSwap V2
		common.HexToAddress("0x3a6d8cA21D1CF76F653A67577FA0D27453350dD8"), // BiSwap
		common.HexToAddress("0xCDe540d7eAFE93aC5fE6233Bee57E1270D3E330F"), // BakerySwap
	}

	// Valid swap method signature
	data := common.Hex2Bytes("38ed1739" + "00000000000000000000000000000000000000000000000000000000000000")

	for i, router := range routers {
		tx := types.NewTransaction(uint64(i), router, big.NewInt(0), 300000, big.NewInt(5e9), data)

		if !filter.IsSwapTransaction(tx) {
			t.Errorf("Valid swap on router %s should be detected", router.Hex())
		}

		name := filter.GetRouterName(router)
		if name == "" {
			t.Errorf("Router %s should have a name", router.Hex())
		}
	}

	stats := filter.GetStats()
	if stats.Filtered != 3 {
		t.Errorf("Expected 3 filtered transactions, got %d", stats.Filtered)
	}
}

// TestMultipleSwapMethods tests filtering for different swap method signatures
func TestMultipleSwapMethods(t *testing.T) {
	filter := NewDEXFilter()

	routerAddr := common.HexToAddress("0x10ED43C718714eb63d5aA57B78B54704E256024E")

	methods := []string{
		"38ed1739", // swapExactTokensForTokens
		"8803dbee", // swapTokensForExactTokens
		"7ff36ab5", // swapExactETHForTokens
		"18cbafe5", // swapExactTokensForETH
		"5c11d795", // swapExactTokensForTokensSupportingFeeOnTransferTokens
		"414bf389", // exactInputSingle (V3)
	}

	for i, methodSig := range methods {
		data := common.Hex2Bytes(methodSig + "00000000000000000000000000000000000000000000000000000000000000")

		tx := types.NewTransaction(uint64(i), routerAddr, big.NewInt(0), 300000, big.NewInt(5e9), data)

		if !filter.IsSwapTransaction(tx) {
			t.Errorf("Swap with method 0x%s should be detected", methodSig)
		}

		methodName := filter.GetMethodName("0x" + methodSig)
		if methodName == "" {
			t.Errorf("Method 0x%s should have a name", methodSig)
		}
	}

	stats := filter.GetStats()
	if stats.Filtered != 6 {
		t.Errorf("Expected 6 filtered transactions, got %d", stats.Filtered)
	}
}

// TestAddRouter tests runtime router addition
func TestAddRouter(t *testing.T) {
	filter := NewDEXFilter()

	newRouter := common.HexToAddress("0x9999999999999999999999999999999999999999")
	filter.AddRouter(newRouter, "TestDEX")

	name := filter.GetRouterName(newRouter)
	if name != "TestDEX" {
		t.Errorf("Expected router name 'TestDEX', got '%s'", name)
	}

	// Test transaction filtering with new router
	data := common.Hex2Bytes("38ed1739" + "00000000000000000000000000000000000000000000000000000000000000")
	tx := types.NewTransaction(0, newRouter, big.NewInt(0), 300000, big.NewInt(5e9), data)

	if !filter.IsSwapTransaction(tx) {
		t.Error("Transaction to newly added router should be detected")
	}
}

// TestRemoveRouter tests runtime router removal
func TestRemoveRouter(t *testing.T) {
	filter := NewDEXFilter()

	routerAddr := common.HexToAddress("0x10ED43C718714eb63d5aA57B78B54704E256024E")

	// Verify router exists
	if filter.GetRouterName(routerAddr) == "" {
		t.Fatal("Router should exist before removal")
	}

	// Remove router
	filter.RemoveRouter(routerAddr)

	// Verify router removed
	if filter.GetRouterName(routerAddr) != "" {
		t.Error("Router should be removed")
	}

	// Test transaction filtering after removal
	data := common.Hex2Bytes("38ed1739" + "00000000000000000000000000000000000000000000000000000000000000")
	tx := types.NewTransaction(0, routerAddr, big.NewInt(0), 300000, big.NewInt(5e9), data)

	if filter.IsSwapTransaction(tx) {
		t.Error("Transaction to removed router should not be detected")
	}
}

// TestAddMethodSignature tests runtime method signature addition
func TestAddMethodSignature(t *testing.T) {
	filter := NewDEXFilter()

	newSig := "0x12345678"
	filter.AddMethodSignature(newSig, "testMethod")

	name := filter.GetMethodName(newSig)
	if name != "testMethod" {
		t.Errorf("Expected method name 'testMethod', got '%s'", name)
	}
}

// TestFilterEfficiency tests efficiency calculation
func TestFilterEfficiency(t *testing.T) {
	filter := NewDEXFilter()

	// Before any transactions
	if filter.FilterEfficiency() != 0.0 {
		t.Error("Efficiency should be 0.0 when no transactions processed")
	}

	routerAddr := common.HexToAddress("0x10ED43C718714eb63d5aA57B78B54704E256024E")
	validData := common.Hex2Bytes("38ed1739" + "00000000000000000000000000000000000000000000000000000000000000")
	invalidData := common.Hex2Bytes("a9059cbb" + "00000000000000000000000000000000000000000000000000000000000000")

	// 1 valid swap
	tx1 := types.NewTransaction(0, routerAddr, big.NewInt(0), 300000, big.NewInt(5e9), validData)
	filter.IsSwapTransaction(tx1)

	// 1 invalid (wrong method)
	tx2 := types.NewTransaction(1, routerAddr, big.NewInt(0), 300000, big.NewInt(5e9), invalidData)
	filter.IsSwapTransaction(tx2)

	// Efficiency should be 50% (1 filtered out of 2 processed)
	efficiency := filter.FilterEfficiency()
	if efficiency != 50.0 {
		t.Errorf("Expected 50%% efficiency, got %.2f%%", efficiency)
	}

	// Noise reduction should be 50%
	noise := filter.NoiseReduction()
	if noise != 50.0 {
		t.Errorf("Expected 50%% noise reduction, got %.2f%%", noise)
	}
}

// TestResetStats tests statistics reset
func TestResetStats(t *testing.T) {
	filter := NewDEXFilter()

	routerAddr := common.HexToAddress("0x10ED43C718714eb63d5aA57B78B54704E256024E")
	data := common.Hex2Bytes("38ed1739" + "00000000000000000000000000000000000000000000000000000000000000")

	// Process some transactions
	for i := 0; i < 10; i++ {
		tx := types.NewTransaction(uint64(i), routerAddr, big.NewInt(0), 300000, big.NewInt(5e9), data)
		filter.IsSwapTransaction(tx)
	}

	stats := filter.GetStats()
	if stats.TotalProcessed != 10 {
		t.Errorf("Expected 10 processed, got %d", stats.TotalProcessed)
	}

	// Reset stats
	filter.ResetStats()

	stats = filter.GetStats()
	if stats.TotalProcessed != 0 {
		t.Error("Stats should be reset to 0")
	}
	if stats.Filtered != 0 {
		t.Error("Filtered stats should be reset to 0")
	}
}

// TestConcurrentFiltering tests thread-safe concurrent filtering
func TestConcurrentFiltering(t *testing.T) {
	filter := NewDEXFilter()

	routerAddr := common.HexToAddress("0x10ED43C718714eb63d5aA57B78B54704E256024E")
	data := common.Hex2Bytes("38ed1739" + "00000000000000000000000000000000000000000000000000000000000000")

	const numGoroutines = 10
	const transactionsPerGoroutine = 100

	done := make(chan bool, numGoroutines)

	for g := 0; g < numGoroutines; g++ {
		go func(goroutineID int) {
			for i := 0; i < transactionsPerGoroutine; i++ {
				nonce := uint64(goroutineID*transactionsPerGoroutine + i)
				tx := types.NewTransaction(nonce, routerAddr, big.NewInt(0), 300000, big.NewInt(5e9), data)
				filter.IsSwapTransaction(tx)
			}
			done <- true
		}(g)
	}

	// Wait for all goroutines
	for g := 0; g < numGoroutines; g++ {
		<-done
	}

	stats := filter.GetStats()
	expected := uint64(numGoroutines * transactionsPerGoroutine)
	if stats.TotalProcessed != expected {
		t.Errorf("Expected %d processed transactions, got %d", expected, stats.TotalProcessed)
	}
	if stats.Filtered != expected {
		t.Errorf("Expected %d filtered transactions, got %d", expected, stats.Filtered)
	}
}

// BenchmarkIsSwapTransaction benchmarks filter performance
func BenchmarkIsSwapTransaction(b *testing.B) {
	filter := NewDEXFilter()

	routerAddr := common.HexToAddress("0x10ED43C718714eb63d5aA57B78B54704E256024E")
	data := common.Hex2Bytes("38ed1739" +
		"0000000000000000000000000000000000000000000000000de0b6b3a7640000" +
		"0000000000000000000000000000000000000000000000000000000000000000")

	tx := types.NewTransaction(0, routerAddr, big.NewInt(0), 300000, big.NewInt(5e9), data)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		filter.IsSwapTransaction(tx)
	}
}

// BenchmarkIsSwapTransaction_Parallel benchmarks concurrent filter performance
func BenchmarkIsSwapTransaction_Parallel(b *testing.B) {
	filter := NewDEXFilter()

	routerAddr := common.HexToAddress("0x10ED43C718714eb63d5aA57B78B54704E256024E")
	data := common.Hex2Bytes("38ed1739" +
		"0000000000000000000000000000000000000000000000000de0b6b3a7640000")

	tx := types.NewTransaction(0, routerAddr, big.NewInt(0), 300000, big.NewInt(5e9), data)

	b.ResetTimer()
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			filter.IsSwapTransaction(tx)
		}
	})
}
