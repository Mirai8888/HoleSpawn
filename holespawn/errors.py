"""
Clear error types for API and pipeline failures.
"""


class ApifyError(Exception):
    """Raised when an Apify API call fails (token set but actor/run failed)."""
    pass
