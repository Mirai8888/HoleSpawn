"""
Clear error types for API and pipeline failures.
"""


class ApifyError(Exception):
    """Raised when an Apify API call fails (token set but actor/run failed)."""

    pass


class ScraperError(Exception):
    """Raised when the self-hosted scraper fails (e.g. no session, auth expired)."""

    pass
