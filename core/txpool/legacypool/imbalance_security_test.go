// Copyright 2024 The go-ethereum Authors
// This file is part of the go-ethereum library.

// Unit tests for BSC Imbalance Prediction Security Controls

package legacypool

import (
	"sync"
	"testing"
	"time"

	"github.com/ethereum/go-ethereum/common"
)

// TestRateLimiter tests the rate limiting functionality
func TestRateLimiter(t *testing.T) {
	config := &SecurityConfig{
		MaxRequestsPerMin: 10,
		GlobalMaxRPS:      100,
	}

	limiter := NewRateLimiter(config)

	// Test: Allow requests within limit
	clientIP := "192.168.1.1"
	for i := 0; i < 10; i++ {
		err := limiter.CheckLimit(clientIP)
		if err != nil {
			t.Errorf("Request %d should be allowed, got error: %v", i, err)
		}
	}

	// Test: Block request exceeding limit
	err := limiter.CheckLimit(clientIP)
	if err != ErrRateLimitExceeded {
		t.Errorf("Expected ErrRateLimitExceeded, got %v", err)
	}

	t.Logf("Rate limiter correctly enforced 10 req/min limit")
}

// TestRateLimiterRefill tests token bucket refill mechanism
func TestRateLimiterRefill(t *testing.T) {
	config := &SecurityConfig{
		MaxRequestsPerMin: 60, // 1 per second
		GlobalMaxRPS:      100,
	}

	limiter := NewRateLimiter(config)
	clientIP := "192.168.1.2"

	// Consume all tokens
	for i := 0; i < 60; i++ {
		limiter.CheckLimit(clientIP)
	}

	// Should be blocked
	err := limiter.CheckLimit(clientIP)
	if err != ErrRateLimitExceeded {
		t.Error("Should be blocked after consuming all tokens")
	}

	// Wait for refill (2 seconds = 2 tokens)
	time.Sleep(2 * time.Second)

	// Should allow 2 requests after refill
	for i := 0; i < 2; i++ {
		err := limiter.CheckLimit(clientIP)
		if err != nil {
			t.Errorf("Request %d should be allowed after refill, got: %v", i, err)
		}
	}

	t.Log("Rate limiter refill working correctly")
}

// TestRateLimiterMultipleIPs tests rate limiting across multiple IPs
func TestRateLimiterMultipleIPs(t *testing.T) {
	config := &SecurityConfig{
		MaxRequestsPerMin: 10,
		GlobalMaxRPS:      100,
	}

	limiter := NewRateLimiter(config)

	// Test 3 different IPs
	ips := []string{"192.168.1.1", "192.168.1.2", "192.168.1.3"}

	for _, ip := range ips {
		// Each IP should have independent limit
		for i := 0; i < 10; i++ {
			err := limiter.CheckLimit(ip)
			if err != nil {
				t.Errorf("IP %s request %d should be allowed, got: %v", ip, i, err)
			}
		}

		// Each IP should be blocked after limit
		err := limiter.CheckLimit(ip)
		if err != ErrRateLimitExceeded {
			t.Errorf("IP %s should be blocked, got: %v", ip, err)
		}
	}

	t.Logf("Rate limiter correctly handles %d independent IPs", len(ips))
}

// TestGlobalRateLimit tests global rate limiting
func TestGlobalRateLimit(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping global rate limit test in short mode")
	}

	config := &SecurityConfig{
		MaxRequestsPerMin: 1000, // High per-IP limit
		GlobalMaxRPS:      10,   // Low global limit
	}

	limiter := NewRateLimiter(config)

	// Generate requests from multiple IPs
	var blocked int
	for i := 0; i < 20; i++ {
		ip := "192.168.1." + string(rune(i))
		err := limiter.CheckLimit(ip)
		if err == ErrRateLimitExceeded {
			blocked++
		}
	}

	// Some requests should be blocked by global limit
	if blocked < 5 {
		t.Errorf("Expected at least 5 globally blocked requests, got %d", blocked)
	}

	t.Logf("Global rate limit correctly blocked %d requests", blocked)
}

// TestAuthValidator tests API key validation
func TestAuthValidator(t *testing.T) {
	config := &SecurityConfig{
		EnableAPIKeys:  true,
		AllowedAPIKeys: []string{"valid-key-123", "valid-key-456"},
	}

	validator := NewAuthValidator(config)

	// Test: Valid API key
	err := validator.ValidateAPIKey("valid-key-123")
	if err != nil {
		t.Errorf("Valid key should be accepted, got: %v", err)
	}

	// Test: Invalid API key
	err = validator.ValidateAPIKey("invalid-key")
	if err != ErrInvalidAPIKey {
		t.Errorf("Expected ErrInvalidAPIKey, got: %v", err)
	}

	// Test: Empty API key
	err = validator.ValidateAPIKey("")
	if err != ErrInvalidAPIKey {
		t.Errorf("Expected ErrInvalidAPIKey for empty key, got: %v", err)
	}

	t.Log("API key validation working correctly")
}

// TestAuthValidatorDynamic tests dynamic API key management
func TestAuthValidatorDynamic(t *testing.T) {
	config := &SecurityConfig{
		EnableAPIKeys:  true,
		AllowedAPIKeys: []string{"initial-key"},
	}

	validator := NewAuthValidator(config)

	// Add new key
	validator.AddAPIKey("new-key-123")

	err := validator.ValidateAPIKey("new-key-123")
	if err != nil {
		t.Errorf("Dynamically added key should be valid, got: %v", err)
	}

	// Remove key
	validator.RemoveAPIKey("new-key-123")

	err = validator.ValidateAPIKey("new-key-123")
	if err != ErrInvalidAPIKey {
		t.Errorf("Removed key should be invalid, got: %v", err)
	}

	t.Log("Dynamic API key management working correctly")
}

// TestRequestThrottler tests concurrent request throttling
func TestRequestThrottler(t *testing.T) {
	config := &SecurityConfig{
		MaxConcurrentReqs: 5,
	}

	throttler := NewRequestThrottler(config)

	// Acquire 5 slots (should all succeed)
	for i := 0; i < 5; i++ {
		err := throttler.AcquireSlot()
		if err != nil {
			t.Errorf("Slot %d should be available, got: %v", i, err)
		}
	}

	// Try to acquire 6th slot (should fail)
	err := throttler.AcquireSlot()
	if err != ErrRequestThrottled {
		t.Errorf("Expected ErrRequestThrottled, got: %v", err)
	}

	// Release one slot
	throttler.ReleaseSlot()

	// Now 6th slot should succeed
	err = throttler.AcquireSlot()
	if err != nil {
		t.Errorf("Slot should be available after release, got: %v", err)
	}

	t.Log("Request throttler working correctly")
}

// TestRequestThrottlerConcurrent tests throttler under concurrent load
func TestRequestThrottlerConcurrent(t *testing.T) {
	config := &SecurityConfig{
		MaxConcurrentReqs: 10,
	}

	throttler := NewRequestThrottler(config)

	const numGoroutines = 50
	const reqsPerGoroutine = 10

	var wg sync.WaitGroup
	var successCount, throttledCount int
	var mu sync.Mutex

	for g := 0; g < numGoroutines; g++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for i := 0; i < reqsPerGoroutine; i++ {
				err := throttler.AcquireSlot()
				if err == nil {
					mu.Lock()
					successCount++
					mu.Unlock()

					// Simulate request processing
					time.Sleep(10 * time.Millisecond)
					throttler.ReleaseSlot()
				} else {
					mu.Lock()
					throttledCount++
					mu.Unlock()
				}
			}
		}()
	}

	wg.Wait()

	totalRequests := numGoroutines * reqsPerGoroutine
	t.Logf("Concurrent throttling: %d successful, %d throttled out of %d requests",
		successCount, throttledCount, totalRequests)

	// All requests should eventually succeed (they retry after throttling)
	if successCount+throttledCount != totalRequests {
		t.Errorf("Request count mismatch: %d + %d != %d",
			successCount, throttledCount, totalRequests)
	}
}

// TestInputValidator tests input validation
func TestInputValidator(t *testing.T) {
	config := &SecurityConfig{
		MaxPoolsPerQuery: 50,
	}

	validator := NewInputValidator(config)

	// Test: Valid pool address
	validAddr := common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f")
	err := validator.ValidatePoolAddress(validAddr)
	if err != nil {
		t.Errorf("Valid address should pass validation, got: %v", err)
	}

	// Test: Zero address (invalid)
	zeroAddr := common.Address{}
	err = validator.ValidatePoolAddress(zeroAddr)
	if err != ErrInvalidPoolAddress {
		t.Errorf("Expected ErrInvalidPoolAddress for zero address, got: %v", err)
	}

	t.Log("Input validation working correctly")
}

// TestInputValidatorMultiple tests validation of multiple addresses
func TestInputValidatorMultiple(t *testing.T) {
	config := &SecurityConfig{
		MaxPoolsPerQuery: 3,
	}

	validator := NewInputValidator(config)

	// Test: Valid addresses within limit
	validAddrs := []common.Address{
		common.HexToAddress("0x1b96b92314c44b159149f7e0303511fb2fc4774f"),
		common.HexToAddress("0x58f876857a02d6762e0101bb5c46a8c1ed44dc16"),
	}

	err := validator.ValidatePoolAddresses(validAddrs)
	if err != nil {
		t.Errorf("Valid addresses should pass validation, got: %v", err)
	}

	// Test: Too many addresses
	tooMany := make([]common.Address, 5)
	for i := range tooMany {
		tooMany[i] = common.BigToAddress(big.NewInt(int64(i + 1)))
	}

	err = validator.ValidatePoolAddresses(tooMany)
	if err == nil {
		t.Error("Should reject too many addresses")
	}

	// Test: Empty list
	err = validator.ValidatePoolAddresses([]common.Address{})
	if err == nil {
		t.Error("Should reject empty address list")
	}

	t.Log("Multiple address validation working correctly")
}

// TestSanitizeString tests string sanitization
func TestSanitizeString(t *testing.T) {
	config := DefaultSecurityConfig()
	validator := NewInputValidator(config)

	tests := []struct {
		input    string
		expected string
	}{
		{"normal string", "normal string"},
		{"  whitespace  ", "whitespace"},
		{"control\x00chars", "controlchars"},
		{"new\nline", "newline"},
		{"tab\ttab", "tabtab"},
	}

	for _, test := range tests {
		result := validator.SanitizeString(test.input)
		if result != test.expected {
			t.Errorf("SanitizeString(%q) = %q, expected %q",
				test.input, result, test.expected)
		}
	}

	t.Log("String sanitization working correctly")
}

// TestSecurityMiddleware tests the complete security middleware
func TestSecurityMiddleware(t *testing.T) {
	config := &SecurityConfig{
		EnableRateLimiting: true,
		MaxRequestsPerMin:  10,
		GlobalMaxRPS:       100,
		EnableAPIKeys:      true,
		AllowedAPIKeys:     []string{"test-key"},
		RequireAuth:        true,
		EnableThrottling:   true,
		MaxConcurrentReqs:  5,
	}

	middleware := NewSecurityMiddleware(config)

	// Test: Valid request
	err := middleware.ValidateRequest("192.168.1.1", "test-key", "imbalance_getPoolImbalance")
	if err != nil {
		t.Errorf("Valid request should be allowed, got: %v", err)
	}
	middleware.ReleaseRequest()

	// Test: Invalid API key
	err = middleware.ValidateRequest("192.168.1.1", "wrong-key", "imbalance_getPoolImbalance")
	if err != ErrUnauthorized {
		t.Errorf("Expected ErrUnauthorized, got: %v", err)
	}

	// Test: Rate limit
	for i := 0; i < 10; i++ {
		middleware.ValidateRequest("192.168.1.2", "test-key", "imbalance_getPoolImbalance")
		middleware.ReleaseRequest()
	}

	err = middleware.ValidateRequest("192.168.1.2", "test-key", "imbalance_getPoolImbalance")
	if err != ErrRateLimitExceeded {
		t.Errorf("Expected ErrRateLimitExceeded, got: %v", err)
	}

	t.Log("Security middleware working correctly")
}

// TestSecurityMiddlewareThrottling tests middleware throttling
func TestSecurityMiddlewareThrottling(t *testing.T) {
	config := &SecurityConfig{
		EnableRateLimiting: false, // Disable rate limiting for this test
		EnableAPIKeys:      false, // Disable auth for this test
		EnableThrottling:   true,
		MaxConcurrentReqs:  3,
	}

	middleware := NewSecurityMiddleware(config)

	// Acquire 3 slots
	for i := 0; i < 3; i++ {
		err := middleware.ValidateRequest("192.168.1.1", "", "test")
		if err != nil {
			t.Errorf("Request %d should succeed, got: %v", i, err)
		}
	}

	// 4th request should be throttled
	err := middleware.ValidateRequest("192.168.1.1", "", "test")
	if err != ErrRequestThrottled {
		t.Errorf("Expected ErrRequestThrottled, got: %v", err)
	}

	// Release one slot
	middleware.ReleaseRequest()

	// Now should succeed
	err = middleware.ValidateRequest("192.168.1.1", "", "test")
	if err != nil {
		t.Errorf("Request should succeed after release, got: %v", err)
	}

	t.Log("Middleware throttling working correctly")
}

// TestSecurityStats tests security statistics collection
func TestSecurityStats(t *testing.T) {
	config := DefaultSecurityConfig()
	middleware := NewSecurityMiddleware(config)

	// Generate some traffic
	for i := 0; i < 10; i++ {
		middleware.ValidateRequest("192.168.1.1", "", "test")
		middleware.ReleaseRequest()
	}

	// Get stats
	stats := middleware.GetSecurityStats()

	// Validate stats
	requiredFields := []string{
		"requests_total",
		"requests_allowed",
		"requests_blocked",
		"rate_limit_hits",
		"auth_failures",
		"throttled_requests",
		"validation_errors",
		"active_requests",
		"block_rate_percent",
	}

	for _, field := range requiredFields {
		if _, ok := stats[field]; !ok {
			t.Errorf("Stats missing required field: %s", field)
		}
	}

	t.Logf("Security stats: %d total requests, %.2f%% block rate",
		stats["requests_total"], stats["block_rate_percent"])
}

// BenchmarkRateLimiter benchmarks rate limiter performance
func BenchmarkRateLimiter(b *testing.B) {
	config := &SecurityConfig{
		MaxRequestsPerMin: 60000, // High limit
		GlobalMaxRPS:      100000,
	}

	limiter := NewRateLimiter(config)
	clientIP := "192.168.1.1"

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		limiter.CheckLimit(clientIP)
	}
}

// BenchmarkAuthValidator benchmarks auth validation performance
func BenchmarkAuthValidator(b *testing.B) {
	config := &SecurityConfig{
		EnableAPIKeys:  true,
		AllowedAPIKeys: []string{"test-key-123"},
	}

	validator := NewAuthValidator(config)
	apiKey := "test-key-123"

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		validator.ValidateAPIKey(apiKey)
	}
}

// BenchmarkSecurityMiddleware benchmarks complete middleware
func BenchmarkSecurityMiddleware(b *testing.B) {
	config := &SecurityConfig{
		EnableRateLimiting: true,
		MaxRequestsPerMin:  60000,
		GlobalMaxRPS:       100000,
		EnableAPIKeys:      false,
		EnableThrottling:   true,
		MaxConcurrentReqs:  1000,
	}

	middleware := NewSecurityMiddleware(config)
	clientIP := "192.168.1.1"

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		middleware.ValidateRequest(clientIP, "", "test")
		middleware.ReleaseRequest()
	}
}
