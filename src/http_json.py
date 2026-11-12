"""GET a URL and decode JSON, retrying transient failures with exponential backoff."""

import json
import logging
import time
from collections.abc import Callable
from urllib.error import HTTPError
from urllib.request import urlopen

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class HttpJsonError(Exception):
    """Raised when a request still fails after its retries, or fails in a way retries cannot fix."""


def get_json(
    url: str,
    timeout: float = 60,
    attempts: int = 3,
    base_delay: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> dict | list:
    """Return the decoded JSON body; wait base_delay, 2x, 4x... between attempts."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(url, timeout=timeout) as response:  # noqa: S310 (https URL from callers)
                return json.load(response)
        except HTTPError as error:
            retryable = error.code in RETRYABLE_STATUS_CODES
            reason = f"HTTP {error.code}"
        except OSError as error:
            retryable = True
            reason = str(error)
        except ValueError as error:
            raise HttpJsonError(f"Response is not valid JSON: {error}") from error
        if not retryable or attempt == attempts:
            logger.error("Giving up after %d attempt(s): %s (%s)", attempt, reason, url)
            raise HttpJsonError(f"Request failed after {attempt} attempt(s): {reason}")
        delay = base_delay * 2 ** (attempt - 1)
        logger.warning("Attempt %d failed (%s); retrying in %.0f s", attempt, reason, delay)
        sleep(delay)
