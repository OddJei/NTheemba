"""HTTP client helpers for external service integrations."""

from .catalog import CatalogApiClient, CatalogApiError

__all__ = ["CatalogApiClient", "CatalogApiError"]
