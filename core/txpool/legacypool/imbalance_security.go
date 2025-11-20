// Copyright 2024 The go-ethereum Authors
// This file is part of the go-ethereum library.

// BSC Imbalance Prediction Engine - Security Controls
// Issue #9: Rate limiting, API keys, input validation
//
// This implements security middleware for the RPC API:
// 1. Rate limiting (per-IP and global)
// 2. API key authentication
// 3. Input validation
// 4. Request throttling

package legacypool

import (
	"errors"
	"strings"
	"sync"
	"time"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/log"
	"github.com/ethereum/go-ethereum/metrics"
)

var (
	// ErrRateLimitExceeded is returned when rate limit is exceeded
	ErrRateLimitExceeded = errors.New("rate limit exceeded")

	// ErrInvalidAPIKey is returned for invalid API keys
	ErrInvalidAPIKey = errors.New("invalid API key")

	// ErrUnauthorized is returned for unauthorized requests
	ErrUnauthorized = errors.New("unauthorized")

	// ErrRequestThrottled is returned when requests are throttled
	ErrRequestThrottled = errors.New("request throttled due to system load")
)

// SecurityConfig contains security configuration
type SecurityConfig struct {
	// Rate limiting
	EnableRateLimiting  bool          // Enable rate limiting (default: true)
	MaxRequestsPerMin   int           // Max requests per minute per IP (default: 60)
	GlobalMaxRPS        int           // Global max requests per second (default: 1000)
	RateLimitWindow     time.Duration // Rate limit window (default: 1 minute)

	// Authentication
	EnableAPIKeys       bool          // Require API keys (default: false for public nodes)
	AllowedAPIKeys      []string      // List of valid API keys
	RequireAuth         bool          // Require authentication for all methods (default: false)

	// Throttling
	EnableThrottling    bool          // Enable request throttling (default: true)
	MaxConcurrentReqs   int           // Max concurrent requests (default: 100)
	MaxSubscriptions    int           // Max active subscriptions per IP (default: 10)

	// Validation
	MaxPoolsPerQuery    int           // Max pools per batch query (default: 50)
	QueryTimeout        time.Duration // Query timeout (default: 30s)
}

// DefaultSecurityConfig returns default security configuration
func DefaultSecurityConfig() *SecurityConfig {
	return &SecurityConfig{
		EnableRateLimiting:  true,
		MaxRequestsPerMin:   60,
		GlobalMaxRPS:        1000,
		RateLimitWindow:     1 * time.Minute,
		EnableAPIKeys:       false,
		AllowedAPIKeys:      []string{},
		RequireAuth:         false,
		EnableThrottling:    true,
		MaxConcurrentReqs:   100,
		MaxSubscriptions:    10,
		MaxPoolsPerQuery:    50,
		QueryTimeout:        30 * time.Second,
	}
}

// SecurityMiddleware provides security controls for the RPC API
type SecurityMiddleware struct {
	config          *SecurityConfig
	rateLimiter     *RateLimiter
	authValidator   *AuthValidator
	throttler       *RequestThrottler
	inputValidator  *InputValidator
	metrics         *SecurityMetrics
}

// SecurityMetrics tracks security-related metrics
type SecurityMetrics struct {
	RequestsTotal      *metrics.Counter // Total requests
	RequestsAllowed    *metrics.Counter // Allowed requests
	RequestsBlocked    *metrics.Counter // Blocked requests
	RateLimitHits      *metrics.Counter // Rate limit violations
	AuthFailures       *metrics.Counter // Authentication failures
	ThrottledRequests  *metrics.Counter // Throttled requests
	ValidationErrors   *metrics.Counter // Validation errors
	ActiveRequests     *metrics.Gauge   // Currently active requests
	ActiveSubscriptions *metrics.Gauge  // Currently active subscriptions
}

// NewSecurityMiddleware creates a new security middleware
func NewSecurityMiddleware(config *SecurityConfig) *SecurityMiddleware {
	if config == nil {
		config = DefaultSecurityConfig()
	}

	sm := &SecurityMiddleware{
		config:         config,
		rateLimiter:    NewRateLimiter(config),
		authValidator:  NewAuthValidator(config),
		throttler:      NewRequestThrottler(config),
		inputValidator: NewInputValidator(config),
		metrics: &SecurityMetrics{
			RequestsTotal:       metrics.NewRegisteredCounter("security/requests/total", nil),
			RequestsAllowed:     metrics.NewRegisteredCounter("security/requests/allowed", nil),
			RequestsBlocked:     metrics.NewRegisteredCounter("security/requests/blocked", nil),
			RateLimitHits:       metrics.NewRegisteredCounter("security/ratelimit/hits", nil),
			AuthFailures:        metrics.NewRegisteredCounter("security/auth/failures", nil),
			ThrottledRequests:   metrics.NewRegisteredCounter("security/throttled/requests", nil),
			ValidationErrors:    metrics.NewRegisteredCounter("security/validation/errors", nil),
			ActiveRequests:      metrics.NewRegisteredGauge("security/requests/active", nil),
			ActiveSubscriptions: metrics.NewRegisteredGauge("security/subscriptions/active", nil),
		},
	}

	return sm
}

// ValidateRequest validates an incoming RPC request
func (sm *SecurityMiddleware) ValidateRequest(clientIP string, apiKey string, method string) error {
	sm.metrics.RequestsTotal.Inc(1)

	// Step 1: Rate limiting
	if sm.config.EnableRateLimiting {
		if err := sm.rateLimiter.CheckLimit(clientIP); err != nil {
			sm.metrics.RateLimitHits.Inc(1)
			sm.metrics.RequestsBlocked.Inc(1)
			log.Warn("Rate limit exceeded", "ip", clientIP, "method", method)
			return ErrRateLimitExceeded
		}
	}

	// Step 2: Authentication
	if sm.config.RequireAuth || sm.config.EnableAPIKeys {
		if err := sm.authValidator.ValidateAPIKey(apiKey); err != nil {
			sm.metrics.AuthFailures.Inc(1)
			sm.metrics.RequestsBlocked.Inc(1)
			log.Warn("Authentication failed", "ip", clientIP, "method", method)
			return ErrUnauthorized
		}
	}

	// Step 3: Throttling
	if sm.config.EnableThrottling {
		if err := sm.throttler.AcquireSlot(); err != nil {
			sm.metrics.ThrottledRequests.Inc(1)
			sm.metrics.RequestsBlocked.Inc(1)
			log.Warn("Request throttled", "ip", clientIP, "method", method)
			return ErrRequestThrottled
		}
	}

	sm.metrics.RequestsAllowed.Inc(1)
	sm.metrics.ActiveRequests.Inc(1)

	return nil
}

// ReleaseRequest releases resources after request completion
func (sm *SecurityMiddleware) ReleaseRequest() {
	if sm.config.EnableThrottling {
		sm.throttler.ReleaseSlot()
	}
	sm.metrics.ActiveRequests.Dec(1)
}

// ValidatePoolAddress validates a pool address
func (sm *SecurityMiddleware) ValidatePoolAddress(addr common.Address) error {
	return sm.inputValidator.ValidatePoolAddress(addr)
}

// RateLimiter implements token bucket rate limiting
type RateLimiter struct {
	config  *SecurityConfig
	buckets map[string]*tokenBucket
	mu      sync.RWMutex
	global  *tokenBucket
}

// tokenBucket implements a token bucket for rate limiting
type tokenBucket struct {
	tokens         int
	maxTokens      int
	refillRate     int           // Tokens per second
	lastRefill     time.Time
	mu             sync.Mutex
}

// NewRateLimiter creates a new rate limiter
func NewRateLimiter(config *SecurityConfig) *RateLimiter {
	return &RateLimiter{
		config:  config,
		buckets: make(map[string]*tokenBucket),
		global: &tokenBucket{
			tokens:     config.GlobalMaxRPS,
			maxTokens:  config.GlobalMaxRPS,
			refillRate: config.GlobalMaxRPS,
			lastRefill: time.Now(),
		},
	}
}

// CheckLimit checks if request is within rate limit
func (rl *RateLimiter) CheckLimit(clientIP string) error {
	// Check global rate limit
	if !rl.global.tryConsume() {
		return ErrRateLimitExceeded
	}

	// Check per-IP rate limit
	rl.mu.Lock()
	bucket, exists := rl.buckets[clientIP]
	if !exists {
		bucket = &tokenBucket{
			tokens:     rl.config.MaxRequestsPerMin,
			maxTokens:  rl.config.MaxRequestsPerMin,
			refillRate: rl.config.MaxRequestsPerMin / 60, // Per second
			lastRefill: time.Now(),
		}
		rl.buckets[clientIP] = bucket
	}
	rl.mu.Unlock()

	if !bucket.tryConsume() {
		return ErrRateLimitExceeded
	}

	return nil
}

// tryConsume attempts to consume a token from the bucket
func (tb *tokenBucket) tryConsume() bool {
	tb.mu.Lock()
	defer tb.mu.Unlock()

	// Refill tokens based on elapsed time
	now := time.Now()
	elapsed := now.Sub(tb.lastRefill).Seconds()
	tokensToAdd := int(elapsed * float64(tb.refillRate))

	if tokensToAdd > 0 {
		tb.tokens += tokensToAdd
		if tb.tokens > tb.maxTokens {
			tb.tokens = tb.maxTokens
		}
		tb.lastRefill = now
	}

	// Try to consume a token
	if tb.tokens > 0 {
		tb.tokens--
		return true
	}

	return false
}

// AuthValidator validates API keys
type AuthValidator struct {
	config      *SecurityConfig
	apiKeys     map[string]bool
	mu          sync.RWMutex
}

// NewAuthValidator creates a new auth validator
func NewAuthValidator(config *SecurityConfig) *AuthValidator {
	apiKeys := make(map[string]bool)
	for _, key := range config.AllowedAPIKeys {
		apiKeys[key] = true
	}

	return &AuthValidator{
		config:  config,
		apiKeys: apiKeys,
	}
}

// ValidateAPIKey validates an API key
func (av *AuthValidator) ValidateAPIKey(apiKey string) error {
	if !av.config.EnableAPIKeys {
		return nil // API keys not required
	}

	if apiKey == "" {
		return ErrInvalidAPIKey
	}

	av.mu.RLock()
	valid := av.apiKeys[apiKey]
	av.mu.RUnlock()

	if !valid {
		return ErrInvalidAPIKey
	}

	return nil
}

// AddAPIKey adds an API key to the allow list
func (av *AuthValidator) AddAPIKey(apiKey string) {
	av.mu.Lock()
	av.apiKeys[apiKey] = true
	av.mu.Unlock()
}

// RemoveAPIKey removes an API key from the allow list
func (av *AuthValidator) RemoveAPIKey(apiKey string) {
	av.mu.Lock()
	delete(av.apiKeys, apiKey)
	av.mu.Unlock()
}

// RequestThrottler limits concurrent requests
type RequestThrottler struct {
	config       *SecurityConfig
	semaphore    chan struct{}
	activeCount  int
	mu           sync.Mutex
}

// NewRequestThrottler creates a new request throttler
func NewRequestThrottler(config *SecurityConfig) *RequestThrottler {
	return &RequestThrottler{
		config:    config,
		semaphore: make(chan struct{}, config.MaxConcurrentReqs),
	}
}

// AcquireSlot attempts to acquire a slot for request processing
func (rt *RequestThrottler) AcquireSlot() error {
	select {
	case rt.semaphore <- struct{}{}:
		rt.mu.Lock()
		rt.activeCount++
		rt.mu.Unlock()
		return nil
	default:
		return ErrRequestThrottled
	}
}

// ReleaseSlot releases a slot after request completion
func (rt *RequestThrottler) ReleaseSlot() {
	<-rt.semaphore
	rt.mu.Lock()
	rt.activeCount--
	rt.mu.Unlock()
}

// GetActiveCount returns the number of active requests
func (rt *RequestThrottler) GetActiveCount() int {
	rt.mu.Lock()
	defer rt.mu.Unlock()
	return rt.activeCount
}

// InputValidator validates RPC input parameters
type InputValidator struct {
	config *SecurityConfig
}

// NewInputValidator creates a new input validator
func NewInputValidator(config *SecurityConfig) *InputValidator {
	return &InputValidator{
		config: config,
	}
}

// ValidatePoolAddress validates a pool address
func (iv *InputValidator) ValidatePoolAddress(addr common.Address) error {
	// Check for zero address
	if addr == (common.Address{}) {
		return ErrInvalidPoolAddress
	}

	// Check for valid Ethereum address format (already validated by common.Address)
	// Additional checks can be added here:
	// - Whitelist of known pool addresses
	// - Blacklist of suspicious addresses
	// - Contract existence verification

	return nil
}

// ValidatePoolAddresses validates multiple pool addresses
func (iv *InputValidator) ValidatePoolAddresses(addresses []common.Address) error {
	if len(addresses) == 0 {
		return errors.New("no pool addresses provided")
	}

	if len(addresses) > iv.config.MaxPoolsPerQuery {
		return errors.New("too many pool addresses")
	}

	for _, addr := range addresses {
		if err := iv.ValidatePoolAddress(addr); err != nil {
			return err
		}
	}

	return nil
}

// SanitizeString sanitizes string input to prevent injection attacks
func (iv *InputValidator) SanitizeString(input string) string {
	// Remove control characters
	input = strings.Map(func(r rune) rune {
		if r < 32 || r == 127 {
			return -1
		}
		return r
	}, input)

	// Trim whitespace
	input = strings.TrimSpace(input)

	return input
}

// GetSecurityStats returns current security statistics
func (sm *SecurityMiddleware) GetSecurityStats() map[string]interface{} {
	stats := make(map[string]interface{})

	stats["requests_total"] = sm.metrics.RequestsTotal.Snapshot().Count()
	stats["requests_allowed"] = sm.metrics.RequestsAllowed.Snapshot().Count()
	stats["requests_blocked"] = sm.metrics.RequestsBlocked.Snapshot().Count()
	stats["rate_limit_hits"] = sm.metrics.RateLimitHits.Snapshot().Count()
	stats["auth_failures"] = sm.metrics.AuthFailures.Snapshot().Count()
	stats["throttled_requests"] = sm.metrics.ThrottledRequests.Snapshot().Count()
	stats["validation_errors"] = sm.metrics.ValidationErrors.Snapshot().Count()
	stats["active_requests"] = sm.throttler.GetActiveCount()

	// Calculate block rate
	total := sm.metrics.RequestsTotal.Snapshot().Count()
	blocked := sm.metrics.RequestsBlocked.Snapshot().Count()
	if total > 0 {
		stats["block_rate_percent"] = float64(blocked) / float64(total) * 100.0
	} else {
		stats["block_rate_percent"] = 0.0
	}

	return stats
}
