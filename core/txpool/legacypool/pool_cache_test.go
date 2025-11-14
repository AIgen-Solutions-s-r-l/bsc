// Copyright 2024 The go-ethereum Authors
// This file is part of the go-ethereum library.

package legacypool

import (
	"math/big"
	"testing"
	"time"

	"github.com/ethereum/go-ethereum/common"
)

// TestNewPoolCache tests cache initialization
func TestNewPoolCache(t *testing.T) {
	cache := NewPoolCache(100)

	if cache == nil {
		t.Fatal("NewPoolCache returned nil")
	}

	if cache.maxSize != 100 {
		t.Errorf("Expected maxSize 100, got %d", cache.maxSize)
	}

	if cache.Len() != 0 {
		t.Error("New cache should be empty")
	}
}

// TestPoolCache_SetAndGet tests basic cache operations
func TestPoolCache_SetAndGet(t *testing.T) {
	cache := NewPoolCache(10)

	poolAddr := common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f")
	state := &PoolState{
		PoolAddress: poolAddr,
		Token0:      common.HexToAddress("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"),
		Token1:      common.HexToAddress("0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56"),
		Reserve0:    big.NewInt(1000000),
		Reserve1:    big.NewInt(2000000),
		BlockNumber: 30000000,
		Timestamp:   uint64(time.Now().Unix()),
	}

	// Set
	cache.Set(poolAddr, state)

	if cache.Len() != 1 {
		t.Errorf("Expected cache length 1, got %d", cache.Len())
	}

	// Get
	retrieved, found := cache.Get(poolAddr)
	if !found {
		t.Fatal("Pool state should be found in cache")
	}

	if retrieved.PoolAddress != poolAddr {
		t.Error("Retrieved state has wrong pool address")
	}

	if retrieved.Reserve0.Cmp(state.Reserve0) != 0 {
		t.Error("Retrieved state has wrong Reserve0")
	}
}

// TestPoolCache_Miss tests cache miss
func TestPoolCache_Miss(t *testing.T) {
	cache := NewPoolCache(10)

	poolAddr := common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f")

	retrieved, found := cache.Get(poolAddr)
	if found {
		t.Error("Should not find non-existent entry")
	}

	if retrieved != nil {
		t.Error("Retrieved value should be nil for cache miss")
	}

	stats := cache.GetStats()
	if stats.Misses != 1 {
		t.Errorf("Expected 1 miss, got %d", stats.Misses)
	}
}

// TestPoolCache_Update tests updating existing entry
func TestPoolCache_Update(t *testing.T) {
	cache := NewPoolCache(10)

	poolAddr := common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f")

	// Initial state
	state1 := &PoolState{
		PoolAddress: poolAddr,
		Reserve0:    big.NewInt(1000000),
		Reserve1:    big.NewInt(2000000),
		BlockNumber: 30000000,
	}
	cache.Set(poolAddr, state1)

	// Updated state
	state2 := &PoolState{
		PoolAddress: poolAddr,
		Reserve0:    big.NewInt(1100000),
		Reserve1:    big.NewInt(2100000),
		BlockNumber: 30000001,
	}
	cache.Set(poolAddr, state2)

	// Cache should still have 1 entry (updated, not added)
	if cache.Len() != 1 {
		t.Errorf("Expected cache length 1, got %d", cache.Len())
	}

	// Retrieve updated state
	retrieved, found := cache.Get(poolAddr)
	if !found {
		t.Fatal("Pool state should be found")
	}

	if retrieved.Reserve0.Cmp(state2.Reserve0) != 0 {
		t.Error("State should be updated to new values")
	}
}

// TestPoolCache_LRUEviction tests LRU eviction policy
func TestPoolCache_LRUEviction(t *testing.T) {
	cache := NewPoolCache(3) // Small cache for testing eviction

	addr1 := common.HexToAddress("0x0000000000000000000000000000000000000001")
	addr2 := common.HexToAddress("0x0000000000000000000000000000000000000002")
	addr3 := common.HexToAddress("0x0000000000000000000000000000000000000003")
	addr4 := common.HexToAddress("0x0000000000000000000000000000000000000004")

	// Fill cache to capacity
	cache.Set(addr1, &PoolState{PoolAddress: addr1, Reserve0: big.NewInt(1)})
	time.Sleep(time.Millisecond) // Ensure different timestamps
	cache.Set(addr2, &PoolState{PoolAddress: addr2, Reserve0: big.NewInt(2)})
	time.Sleep(time.Millisecond)
	cache.Set(addr3, &PoolState{PoolAddress: addr3, Reserve0: big.NewInt(3)})

	if cache.Len() != 3 {
		t.Errorf("Expected cache length 3, got %d", cache.Len())
	}

	// Add 4th entry - should evict addr1 (oldest)
	cache.Set(addr4, &PoolState{PoolAddress: addr4, Reserve0: big.NewInt(4)})

	if cache.Len() != 3 {
		t.Errorf("Expected cache length 3, got %d", cache.Len())
	}

	// addr1 should be evicted
	_, found := cache.Get(addr1)
	if found {
		t.Error("addr1 should have been evicted")
	}

	// addr2, addr3, addr4 should still be present
	if _, found := cache.Get(addr2); !found {
		t.Error("addr2 should still be in cache")
	}
	if _, found := cache.Get(addr3); !found {
		t.Error("addr3 should still be in cache")
	}
	if _, found := cache.Get(addr4); !found {
		t.Error("addr4 should be in cache")
	}

	stats := cache.GetStats()
	if stats.Evictions != 1 {
		t.Errorf("Expected 1 eviction, got %d", stats.Evictions)
	}
}

// TestPoolCache_LRUOrdering tests that access updates LRU order
func TestPoolCache_LRUOrdering(t *testing.T) {
	cache := NewPoolCache(3)

	addr1 := common.HexToAddress("0x0000000000000000000000000000000000000001")
	addr2 := common.HexToAddress("0x0000000000000000000000000000000000000002")
	addr3 := common.HexToAddress("0x0000000000000000000000000000000000000003")
	addr4 := common.HexToAddress("0x0000000000000000000000000000000000000004")

	// Fill cache
	cache.Set(addr1, &PoolState{PoolAddress: addr1})
	time.Sleep(time.Millisecond)
	cache.Set(addr2, &PoolState{PoolAddress: addr2})
	time.Sleep(time.Millisecond)
	cache.Set(addr3, &PoolState{PoolAddress: addr3})

	// Access addr1 (makes it most recently used)
	cache.Get(addr1)

	// Add addr4 - should evict addr2 (now oldest), not addr1
	cache.Set(addr4, &PoolState{PoolAddress: addr4})

	// addr1 should still be present (was accessed)
	if _, found := cache.Get(addr1); !found {
		t.Error("addr1 should still be in cache after access")
	}

	// addr2 should be evicted
	if _, found := cache.Get(addr2); found {
		t.Error("addr2 should have been evicted")
	}
}

// TestPoolCache_Delete tests entry deletion
func TestPoolCache_Delete(t *testing.T) {
	cache := NewPoolCache(10)

	addr := common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f")
	state := &PoolState{PoolAddress: addr, Reserve0: big.NewInt(1000000)}

	cache.Set(addr, state)

	if cache.Len() != 1 {
		t.Fatal("Cache should have 1 entry")
	}

	cache.Delete(addr)

	if cache.Len() != 0 {
		t.Error("Cache should be empty after delete")
	}

	_, found := cache.Get(addr)
	if found {
		t.Error("Entry should not be found after delete")
	}
}

// TestPoolCache_Clear tests clearing all entries
func TestPoolCache_Clear(t *testing.T) {
	cache := NewPoolCache(10)

	// Add multiple entries
	for i := 0; i < 5; i++ {
		addr := common.BigToAddress(big.NewInt(int64(i)))
		cache.Set(addr, &PoolState{PoolAddress: addr})
	}

	if cache.Len() != 5 {
		t.Fatalf("Expected 5 entries, got %d", cache.Len())
	}

	cache.Clear()

	if cache.Len() != 0 {
		t.Error("Cache should be empty after clear")
	}
}

// TestPoolCache_HitRate tests hit rate calculation
func TestPoolCache_HitRate(t *testing.T) {
	cache := NewPoolCache(10)

	addr1 := common.HexToAddress("0x0000000000000000000000000000000000000001")
	addr2 := common.HexToAddress("0x0000000000000000000000000000000000000002")

	// Add addr1
	cache.Set(addr1, &PoolState{PoolAddress: addr1})

	// 2 hits on addr1
	cache.Get(addr1)
	cache.Get(addr1)

	// 1 miss on addr2
	cache.Get(addr2)

	hitRate := cache.HitRate()
	expected := 66.66 // 2 hits out of 3 total accesses
	if hitRate < expected-1 || hitRate > expected+1 {
		t.Errorf("Expected hit rate ~%.2f%%, got %.2f%%", expected, hitRate)
	}
}

// TestPoolCache_Contains tests the Contains method
func TestPoolCache_Contains(t *testing.T) {
	cache := NewPoolCache(10)

	addr := common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f")

	if cache.Contains(addr) {
		t.Error("Cache should not contain addr before adding")
	}

	cache.Set(addr, &PoolState{PoolAddress: addr})

	if !cache.Contains(addr) {
		t.Error("Cache should contain addr after adding")
	}

	cache.Delete(addr)

	if cache.Contains(addr) {
		t.Error("Cache should not contain addr after deleting")
	}
}

// TestPoolCache_GetAll tests retrieving all entries
func TestPoolCache_GetAll(t *testing.T) {
	cache := NewPoolCache(10)

	// Add 3 entries
	for i := 1; i <= 3; i++ {
		addr := common.BigToAddress(big.NewInt(int64(i)))
		cache.Set(addr, &PoolState{PoolAddress: addr, Reserve0: big.NewInt(int64(i * 1000))})
	}

	all := cache.GetAll()

	if len(all) != 3 {
		t.Errorf("Expected 3 entries, got %d", len(all))
	}

	// Check that most recent is first (addr3)
	if all[0].Reserve0.Int64() != 3000 {
		t.Error("GetAll should return entries in LRU order (most recent first)")
	}
}

// TestPoolCache_GetOldestNewest tests oldest/newest entry retrieval
func TestPoolCache_GetOldestNewest(t *testing.T) {
	cache := NewPoolCache(10)

	addr1 := common.HexToAddress("0x0000000000000000000000000000000000000001")
	addr2 := common.HexToAddress("0x0000000000000000000000000000000000000002")
	addr3 := common.HexToAddress("0x0000000000000000000000000000000000000003")

	cache.Set(addr1, &PoolState{PoolAddress: addr1, Reserve0: big.NewInt(1000)})
	time.Sleep(time.Millisecond)
	cache.Set(addr2, &PoolState{PoolAddress: addr2, Reserve0: big.NewInt(2000)})
	time.Sleep(time.Millisecond)
	cache.Set(addr3, &PoolState{PoolAddress: addr3, Reserve0: big.NewInt(3000)})

	oldest := cache.GetOldestEntry()
	if oldest == nil || oldest.PoolAddress != addr1 {
		t.Error("Oldest entry should be addr1")
	}

	newest := cache.GetNewestEntry()
	if newest == nil || newest.PoolAddress != addr3 {
		t.Error("Newest entry should be addr3")
	}
}

// TestPoolCache_ConcurrentAccess tests thread-safe concurrent operations
func TestPoolCache_ConcurrentAccess(t *testing.T) {
	cache := NewPoolCache(100)

	const numGoroutines = 10
	const operationsPerGoroutine = 100

	done := make(chan bool, numGoroutines)

	for g := 0; g < numGoroutines; g++ {
		go func(goroutineID int) {
			for i := 0; i < operationsPerGoroutine; i++ {
				addr := common.BigToAddress(big.NewInt(int64(goroutineID*1000 + i)))
				state := &PoolState{
					PoolAddress: addr,
					Reserve0:    big.NewInt(int64(i)),
				}

				// Mix of operations
				cache.Set(addr, state)
				cache.Get(addr)
				if i%10 == 0 {
					cache.Delete(addr)
				}
			}
			done <- true
		}(g)
	}

	// Wait for all goroutines
	for g := 0; g < numGoroutines; g++ {
		<-done
	}

	// No panics = success
}

// TestPoolCache_ResetStats tests statistics reset
func TestPoolCache_ResetStats(t *testing.T) {
	cache := NewPoolCache(10)

	addr := common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f")
	cache.Set(addr, &PoolState{PoolAddress: addr})
	cache.Get(addr)
	cache.Get(common.HexToAddress("0x0000000000000000000000000000000000000002")) // miss

	stats := cache.GetStats()
	if stats.Hits == 0 || stats.Misses == 0 {
		t.Fatal("Stats should be non-zero before reset")
	}

	cache.ResetStats()

	stats = cache.GetStats()
	if stats.Hits != 0 || stats.Misses != 0 || stats.Sets != 0 {
		t.Error("Stats should be zero after reset")
	}
}

// BenchmarkPoolCache_Set benchmarks cache write performance
func BenchmarkPoolCache_Set(b *testing.B) {
	cache := NewPoolCache(1000)

	state := &PoolState{
		PoolAddress: common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f"),
		Reserve0:    big.NewInt(1000000),
		Reserve1:    big.NewInt(2000000),
		BlockNumber: 30000000,
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		addr := common.BigToAddress(big.NewInt(int64(i)))
		cache.Set(addr, state)
	}
}

// BenchmarkPoolCache_Get benchmarks cache read performance
func BenchmarkPoolCache_Get(b *testing.B) {
	cache := NewPoolCache(1000)

	// Populate cache
	for i := 0; i < 1000; i++ {
		addr := common.BigToAddress(big.NewInt(int64(i)))
		cache.Set(addr, &PoolState{PoolAddress: addr, Reserve0: big.NewInt(int64(i))})
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		addr := common.BigToAddress(big.NewInt(int64(i % 1000)))
		cache.Get(addr)
	}
}

// BenchmarkPoolCache_Concurrent benchmarks concurrent access performance
func BenchmarkPoolCache_Concurrent(b *testing.B) {
	cache := NewPoolCache(1000)

	// Populate cache
	for i := 0; i < 1000; i++ {
		addr := common.BigToAddress(big.NewInt(int64(i)))
		cache.Set(addr, &PoolState{PoolAddress: addr, Reserve0: big.NewInt(int64(i))})
	}

	b.ResetTimer()
	b.RunParallel(func(pb *testing.PB) {
		i := 0
		for pb.Next() {
			addr := common.BigToAddress(big.NewInt(int64(i % 1000)))
			cache.Get(addr)
			i++
		}
	})
}
