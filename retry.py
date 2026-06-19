import time
import functools

def retry_on_failure(max_retries=3, initial_delay=1, backoff_factor=2, max_delay=None, exceptions=(Exception,)):
    """
    Decorator that retries a function on specified exceptions with exponential backoff.
    Can be used with or without arguments:
        @retry_on_failure
        @retry_on_failure(max_retries=5, initial_delay=0.5)
    """
    if callable(max_retries):
        # Used without parentheses: @retry_on_failure
        f, max_retries = max_retries, 3
        return retry_on_failure(
            max_retries=max_retries,
            initial_delay=initial_delay,
            backoff_factor=backoff_factor,
            max_delay=max_delay,
            exceptions=exceptions
        )(f)

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        raise
                    delay = initial_delay * (backoff_factor ** attempt)
                    if max_delay is not None:
                        delay = min(delay, max_delay)
                    time.sleep(delay)
            raise last_exception
        return wrapper

    return decorator