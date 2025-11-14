// Copyright 2024 The go-ethereum Authors
// This file is part of the go-ethereum library.

// Package legacypool implements the BSC Imbalance Prediction Engine
// Pool State Cache - Issue #5
//
// This cache implements an LRU (Least Recently Used) caching strategy (ADR-002)
// for storing liquidity pool states with O(1) access time.
//
// Design Goals:
// - <1μs cache lookup latency
// - <500MB memory footprint for 1000 pools
// - Thread-safe concurrent access
// - Automatic eviction of least-used pools

package legacypool

import (
	containerlist "container/list"
	"math/big"
	"sync"
	"time"

	"github.com/ethereum/go-ethereum/common"
)

// PoolState represents the state of a liquidity pool at a given time
type PoolState struct {
	PoolAddress  common.Address // Pool contract address
	Token0       common.Address // First token address
	Token1       common.Address // Second token address
	Reserve0     *big.Int       // Reserve of token0
	Reserve1     *big.Int       // Reserve of token1
	BlockNumber  uint64         // Block number when state was fetched
	Timestamp    uint64         // Unix timestamp when state was fetched
	LastAccessed time.Time      // Last time this state was accessed (for LRU)
}

// cacheEntry wraps a PoolState with its list element for LRU tracking
type cacheEntry struct {
	key   common.Address
	value *PoolState
}

// PoolCache implements an LRU cache for pool states
// Thread-safe for concurrent access from multiple goroutines
type PoolCache struct {
	maxSize  int                            // Maximum number of entries
	cache    map[common.Address]*containerlist.Element // Map for O(1) lookup
	lruList  *containerlist.List                     // Doubly-linked list for LRU tracking
	mu       sync.RWMutex                   // Protects concurrent access
	stats    *CacheStats                    // Performance statistics
}

// CacheStats tracks cache performance metrics
type CacheStats struct {
	Hits        uint64 // Number of cache hits
	Misses      uint64 // Number of cache misses
	Evictions   uint64 // Number of evicted entries
	Sets        uint64 // Number of set operations
	mu          sync.Mutex
}

// NewPoolCache creates a new LRU pool state cache with the specified maximum size
// Recommended size: 1000 pools (approximately 500MB memory)
func NewPoolCache(maxSize int) *PoolCache {
	if maxSize <= 0 {
		maxSize = 1000 // Default size
	}

	return &PoolCache{
		maxSize:  maxSize,
		cache:    make(map[common.Address]*containerlist.Element, maxSize),
		lruList:  containerlist.New(),
		stats:    &CacheStats{},
	}
}

// Get retrieves a pool state from the cache
// Returns (state, true) if found, (nil, false) if not found
// Updates LRU position on access (O(1) operation)
func (c *PoolCache) Get(poolAddr common.Address) (*PoolState, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()

	elem, found := c.cache[poolAddr]
	if !found {
		c.stats.incrementMisses()
		return nil, false
	}

	// Move to front of LRU list (most recently used)
	c.lruList.MoveToFront(elem)

	entry := elem.Value.(*cacheEntry)
	entry.value.LastAccessed = time.Now()

	c.stats.incrementHits()
	return entry.value, true
}

// Set adds or updates a pool state in the cache
// If cache is full, evicts the least recently used entry (O(1) operation)
func (c *PoolCache) Set(poolAddr common.Address, state *PoolState) {
	c.mu.Lock()
	defer c.mu.Unlock()

	state.LastAccessed = time.Now()

	// Check if entry already exists
	if elem, found := c.cache[poolAddr]; found {
		// Update existing entry and move to front
		c.lruList.MoveToFront(elem)
		entry := elem.Value.(*cacheEntry)
		entry.value = state
		c.stats.incrementSets()
		return
	}

	// Add new entry
	entry := &cacheEntry{
		key:   poolAddr,
		value: state,
	}
	elem := c.lruList.PushFront(entry)
	c.cache[poolAddr] = elem

	// Evict least recently used if over capacity
	if c.lruList.Len() > c.maxSize {
		c.evictOldest()
	}

	c.stats.incrementSets()
}

// evictOldest removes the least recently used entry from the cache
// Must be called with lock held
func (c *PoolCache) evictOldest() {
	elem := c.lruList.Back()
	if elem == nil {
		return
	}

	c.lruList.Remove(elem)
	entry := elem.Value.(*cacheEntry)
	delete(c.cache, entry.key)

	c.stats.incrementEvictions()
}

// Delete removes a pool state from the cache
func (c *PoolCache) Delete(poolAddr common.Address) {
	c.mu.Lock()
	defer c.mu.Unlock()

	elem, found := c.cache[poolAddr]
	if !found {
		return
	}

	c.lruList.Remove(elem)
	delete(c.cache, poolAddr)
}

// Clear removes all entries from the cache
func (c *PoolCache) Clear() {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.cache = make(map[common.Address]*containerlist.Element, c.maxSize)
	c.lruList = containerlist.New()
}

// Len returns the current number of entries in the cache
func (c *PoolCache) Len() int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.lruList.Len()
}

// HitRate returns the cache hit rate as a percentage (0-100)
func (c *PoolCache) HitRate() float64 {
	stats := c.GetStats()
	total := stats.Hits + stats.Misses
	if total == 0 {
		return 0.0
	}
	return float64(stats.Hits) / float64(total) * 100.0
}

// GetStats returns a snapshot of cache performance statistics
func (c *PoolCache) GetStats() CacheStats {
	c.stats.mu.Lock()
	defer c.stats.mu.Unlock()

	return CacheStats{
		Hits:      c.stats.Hits,
		Misses:    c.stats.Misses,
		Evictions: c.stats.Evictions,
		Sets:      c.stats.Sets,
	}
}

// ResetStats resets cache performance statistics
func (c *PoolCache) ResetStats() {
	c.stats.mu.Lock()
	defer c.stats.mu.Unlock()

	c.stats.Hits = 0
	c.stats.Misses = 0
	c.stats.Evictions = 0
	c.stats.Sets = 0
}

// GetOldestEntry returns the least recently used entry without removing it
// Returns nil if cache is empty
func (c *PoolCache) GetOldestEntry() *PoolState {
	c.mu.RLock()
	defer c.mu.RUnlock()

	elem := c.lruList.Back()
	if elem == nil {
		return nil
	}

	entry := elem.Value.(*cacheEntry)
	return entry.value
}

// GetNewestEntry returns the most recently used entry
// Returns nil if cache is empty
func (c *PoolCache) GetNewestEntry() *PoolState {
	c.mu.RLock()
	defer c.mu.RUnlock()

	elem := c.lruList.Front()
	if elem == nil {
		return nil
	}

	entry := elem.Value.(*cacheEntry)
	return entry.value
}

// GetAll returns all pool states in the cache (snapshot)
// Returned slice is ordered from most to least recently used
func (c *PoolCache) GetAll() []*PoolState {
	c.mu.RLock()
	defer c.mu.RUnlock()

	states := make([]*PoolState, 0, c.lruList.Len())
	for elem := c.lruList.Front(); elem != nil; elem = elem.Next() {
		entry := elem.Value.(*cacheEntry)
		states = append(states, entry.value)
	}

	return states
}

// Contains checks if a pool address exists in the cache
func (c *PoolCache) Contains(poolAddr common.Address) bool {
	c.mu.RLock()
	defer c.mu.RUnlock()

	_, found := c.cache[poolAddr]
	return found
}

// Stats helper methods

func (s *CacheStats) incrementHits() {
	s.mu.Lock()
	s.Hits++
	s.mu.Unlock()
}

func (s *CacheStats) incrementMisses() {
	s.mu.Lock()
	s.Misses++
	s.mu.Unlock()
}

func (s *CacheStats) incrementEvictions() {
	s.mu.Lock()
	s.Evictions++
	s.mu.Unlock()
}

func (s *CacheStats) incrementSets() {
	s.mu.Lock()
	s.Sets++
	s.mu.Unlock()
}
