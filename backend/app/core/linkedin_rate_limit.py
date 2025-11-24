"""
LinkedIn API rate limiting configuration.

Provides configurable delay settings for paginated LinkedIn API calls
to avoid rate limiting and suspicious behavior detection.
"""
import random
import asyncio
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Default delay range in seconds (can be overridden per request)
DEFAULT_MIN_DELAY_SECONDS = 2.0
DEFAULT_MAX_DELAY_SECONDS = 5.0


async def apply_pagination_delay(
    min_delay: Optional[float] = None,
    max_delay: Optional[float] = None,
    operation_name: str = "pagination"
) -> float:
    """
    Apply a random delay between paginated LinkedIn API calls.
    
    Args:
        min_delay: Minimum delay in seconds (defaults to DEFAULT_MIN_DELAY_SECONDS)
        max_delay: Maximum delay in seconds (defaults to DEFAULT_MAX_DELAY_SECONDS)
        operation_name: Name of the operation for logging purposes
        
    Returns:
        The actual delay applied in seconds
        
    Raises:
        ValueError: If min_delay > max_delay or if delays are negative
    """
    # Use defaults if not specified
    min_val = min_delay if min_delay is not None else DEFAULT_MIN_DELAY_SECONDS
    max_val = max_delay if max_delay is not None else DEFAULT_MAX_DELAY_SECONDS
    
    # Validation
    if min_val < 0 or max_val < 0:
        raise ValueError(f"Delays must be non-negative (min={min_val}, max={max_val})")
    
    if min_val > max_val:
        raise ValueError(f"min_delay ({min_val}) cannot be greater than max_delay ({max_val})")
    
    # Calculate random delay
    delay = random.uniform(min_val, max_val)
    
    logger.info(f"[{operation_name}] Applying rate limit delay: {delay:.2f}s (range: {min_val}-{max_val}s)")
    await asyncio.sleep(delay)
    
    return delay

