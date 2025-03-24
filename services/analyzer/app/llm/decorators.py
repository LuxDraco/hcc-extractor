"""
Decorators for enhancing LLM client functionality.

This module provides decorators for common patterns like caching,
retry logic, and rate limiting when interacting with LLM APIs.
"""

import functools
import random
import time
from typing import Any, Callable, Dict, TypeVar, cast

# Define type variables for type hinting
F = TypeVar('F', bound=Callable[..., Any])
T = TypeVar('T')

# Simple in-memory cache
_cache: Dict[str, Dict[str, Any]] = {}


def cache(ttl_seconds: int = 3600) -> Callable[[F], F]:
    """
    Cache the result of a function call.

    Args:
        ttl_seconds: Time-to-live for cached results in seconds

    Returns:
        Decorated function with caching
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Create a cache key from the function name and arguments
            key_parts = [func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)

            # Check if result is in cache and not expired
            if cache_key in _cache:
                result_dict = _cache[cache_key]
                if result_dict["timestamp"] + ttl_seconds > time.time():
                    return result_dict["result"]

            # Call the function and cache the result
            result = func(*args, **kwargs)
            _cache[cache_key] = {
                "result": result,
                "timestamp": time.time()
            }

            return result

        return cast(F, wrapper)

    return decorator


def retry(
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
        backoff_factor: float = 2.0,
        exceptions: tuple = (Exception,),
) -> Callable[[F], F]:
    """
    Retry a function call on failure with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_factor: Factor by which to increase delay after each attempt
        exceptions: Tuple of exceptions to catch and retry

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    # Don't sleep after the last attempt
                    if attempt < max_attempts - 1:
                        # Calculate delay with jitter
                        delay = min(
                            base_delay * (backoff_factor ** attempt),
                            max_delay
                        )
                        jitter = random.uniform(0.8, 1.2)
                        sleep_time = delay * jitter

                        time.sleep(sleep_time)

            # If we get here, all attempts failed
            if last_exception:
                raise last_exception

            # This should never happen, but just in case
            raise RuntimeError("All retry attempts failed without an exception")

        return cast(F, wrapper)

    return decorator
