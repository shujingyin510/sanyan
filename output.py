import time
import threading
from functools import wraps
from typing import Callable, Optional


class TokenBucketRateLimiter:
    """Token bucket rate limiter for API calls.

    Allows a certain number of requests per time window, with burst support.
    Thread-safe.
    """

    def __init__(self, rate: float, capacity: int, burst: Optional[int] = None):
        """
        Initialize the token bucket rate limiter.

        Args:
            rate: Sustained request rate (tokens per second).
            capacity: Maximum number of tokens the bucket can hold.
            burst: Maximum burst size (if None, defaults to capacity).
        """
        if rate <= 0:
            raise ValueError('rate must be positive')
        if capacity <= 0:
            raise ValueError('capacity must be positive')
        self.rate = rate
        self.capacity = capacity
        self.burst = burst if burst is not None else capacity
        self.tokens = float(self.burst)
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        new_tokens = elapsed * self.rate
        if new_tokens > 0:
            self.tokens = min(self.capacity, self.tokens + new_tokens)
            self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume (default 1).

        Returns:
            True if tokens were consumed, False if not enough tokens.
        """
        if tokens <= 0:
            raise ValueError('tokens must be positive')
        with self.lock:
            self._refill()
            if tokens <= self.tokens:
                self.tokens -= tokens
                return True
            return False

    def wait_for_token(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """
        Wait until tokens become available or timeout expires.

        Args:
            tokens: Number of tokens to consume.
            timeout: Maximum seconds to wait (None means wait indefinitely).

        Returns:
            True if tokens obtained, False on timeout.
        """
        if tokens > self.capacity:
            raise ValueError('tokens cannot exceed capacity')
        deadline = time.monotonic() + timeout if timeout is not None else None
        while True:
            if self.consume(tokens):
                return True
            if deadline is not None and time.monotonic() >= deadline:
                return False
            # Sleep for roughly the time needed to get one token
            time.sleep(1.0 / self.rate)

    def decorate(self, tokens: int = 1, block: bool = False, timeout: Optional[float] = None):
        """
        Decorator for applying rate limiting to a function.

        Args:
            tokens: Number of tokens to consume per call.
            block: If True, wait for token instead of raising an error.
            timeout: Maximum wait time if blocking.

        Returns:
            Decorated function.
        """

        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if block:
                    if not self.wait_for_token(tokens, timeout):
                        raise RateLimitExceeded('Rate limit exceeded and timeout reached')
                else:
                    if not self.consume(tokens):
                        raise RateLimitExceeded('Rate limit exceeded')
                return func(*args, **kwargs)

            return wrapper

        return decorator


class RateLimitExceeded(Exception):
    """Raised when the rate limit is exceeded."""

    pass


# Example usage
if __name__ == '__main__':
    # Create a rate limiter: 5 requests per second, bucket size 10, burst 10.
    limiter = TokenBucketRateLimiter(rate=5.0, capacity=10)

    @limiter.decorate(tokens=1, block=False)
    def api_endpoint(data):
        # Simulate API processing
        return f'Processed: {data}'

    # Test: make several rapid calls
    for i in range(15):
        try:
            result = api_endpoint(f'request {i}')
            print(result)
        except RateLimitExceeded:
            print(f'Request {i} blocked by rate limiter')
        time.sleep(0.1)  # small delay to see effect
