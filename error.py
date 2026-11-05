"""Custom exceptions for GEO_Visual."""


class QueryTooLargeError(Exception):
    """Raised when a query returns more rows than the configured limit."""
