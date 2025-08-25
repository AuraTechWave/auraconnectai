// Generate a UUID v4
export const generateUUID = () => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
};

// Store for pending idempotency keys
const pendingRequests = new Map();

// Create idempotent request wrapper
export const idempotentRequest = async (key, requestFn, options = {}) => {
  const { ttl = 300000 } = options; // Default 5 minutes TTL
  
  // Check if request is already pending
  if (pendingRequests.has(key)) {
    console.log(`Request with key ${key} is already pending, returning existing promise`);
    return pendingRequests.get(key).promise;
  }
  
  // Check localStorage for recent successful request
  const cachedResult = checkRecentRequest(key, ttl);
  if (cachedResult) {
    console.log(`Returning cached result for key ${key}`);
    return Promise.resolve(cachedResult);
  }
  
  // Create new request
  const requestPromise = requestFn()
    .then(result => {
      // Store successful result
      storeSuccessfulRequest(key, result);
      pendingRequests.delete(key);
      return result;
    })
    .catch(error => {
      pendingRequests.delete(key);
      throw error;
    });
  
  // Store pending request
  pendingRequests.set(key, {
    promise: requestPromise,
    timestamp: Date.now()
  });
  
  return requestPromise;
};

// Check for recent successful request
const checkRecentRequest = (key, ttl) => {
  try {
    const stored = localStorage.getItem(`idempotent_${key}`);
    if (!stored) return null;
    
    const { result, timestamp } = JSON.parse(stored);
    
    // Check if within TTL
    if (Date.now() - timestamp < ttl) {
      return result;
    }
    
    // Expired, remove it
    localStorage.removeItem(`idempotent_${key}`);
    return null;
  } catch (error) {
    console.error('Error checking recent request:', error);
    return null;
  }
};

// Store successful request result
const storeSuccessfulRequest = (key, result) => {
  try {
    localStorage.setItem(`idempotent_${key}`, JSON.stringify({
      result,
      timestamp: Date.now()
    }));
  } catch (error) {
    console.error('Error storing request result:', error);
  }
};

// Clean up old idempotency keys
export const cleanupIdempotencyKeys = (maxAge = 86400000) => { // Default 24 hours
  try {
    const now = Date.now();
    const keysToRemove = [];
    
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith('idempotent_')) {
        try {
          const { timestamp } = JSON.parse(localStorage.getItem(key));
          if (now - timestamp > maxAge) {
            keysToRemove.push(key);
          }
        } catch (error) {
          // Invalid entry, remove it
          keysToRemove.push(key);
        }
      }
    }
    
    keysToRemove.forEach(key => localStorage.removeItem(key));
    console.log(`Cleaned up ${keysToRemove.length} old idempotency keys`);
  } catch (error) {
    console.error('Error cleaning up idempotency keys:', error);
  }
};

// Create idempotency key for checkout
export const createCheckoutIdempotencyKey = (cartItems, customerId, timestamp) => {
  // Create deterministic key based on cart contents and customer
  const cartSignature = cartItems
    .sort((a, b) => a.id - b.id)
    .map(item => `${item.id}-${item.quantity}`)
    .join('|');
  
  return `checkout_${customerId}_${cartSignature}_${timestamp}`;
};

// Rate limiting helper
const rateLimitMap = new Map();

export const rateLimit = (key, limit = 3, windowMs = 60000) => {
  const now = Date.now();
  const windowStart = now - windowMs;
  
  // Get or create rate limit entry
  let entry = rateLimitMap.get(key);
  if (!entry) {
    entry = { attempts: [], blocked: false };
    rateLimitMap.set(key, entry);
  }
  
  // Remove old attempts outside the window
  entry.attempts = entry.attempts.filter(timestamp => timestamp > windowStart);
  
  // Check if currently blocked
  if (entry.blocked && entry.blockedUntil > now) {
    const remainingMs = entry.blockedUntil - now;
    return {
      allowed: false,
      retryAfter: Math.ceil(remainingMs / 1000),
      message: `Too many attempts. Please try again in ${Math.ceil(remainingMs / 1000)} seconds.`
    };
  }
  
  // Reset blocked status if block period expired
  if (entry.blocked && entry.blockedUntil <= now) {
    entry.blocked = false;
    entry.blockedUntil = null;
  }
  
  // Check current attempts
  if (entry.attempts.length >= limit) {
    // Block for progressively longer periods
    const blockDuration = Math.min(windowMs * Math.pow(2, entry.blockCount || 0), 300000); // Max 5 minutes
    entry.blocked = true;
    entry.blockedUntil = now + blockDuration;
    entry.blockCount = (entry.blockCount || 0) + 1;
    
    return {
      allowed: false,
      retryAfter: Math.ceil(blockDuration / 1000),
      message: `Too many attempts. Please try again in ${Math.ceil(blockDuration / 1000)} seconds.`
    };
  }
  
  // Allow the attempt
  entry.attempts.push(now);
  return { allowed: true };
};

// Clear rate limit for a key (e.g., after successful login)
export const clearRateLimit = (key) => {
  rateLimitMap.delete(key);
};

// Setup periodic cleanup
if (typeof window !== 'undefined') {
  // Clean up idempotency keys every hour
  setInterval(() => {
    cleanupIdempotencyKeys();
  }, 3600000);
  
  // Clean up rate limit map every 5 minutes
  setInterval(() => {
    const now = Date.now();
    for (const [key, entry] of rateLimitMap.entries()) {
      if (entry.blockedUntil && entry.blockedUntil < now - 300000) {
        rateLimitMap.delete(key);
      }
    }
  }, 300000);
}