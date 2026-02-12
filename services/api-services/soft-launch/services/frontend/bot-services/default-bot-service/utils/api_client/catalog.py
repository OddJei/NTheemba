"""Catalog service API client utilities."""

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

import requests
from requests import Response

from config.environment import config

try:
    import redis  # type: ignore
except ImportError:  # pragma: no cover - Redis optional dependency
    redis = None  # type: ignore

logger = logging.getLogger(__name__)


class CatalogApiError(Exception):
    """Raised when the catalog API request fails."""


class CatalogApiClient:
    """Lightweight client for interacting with the catalog service."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        session: Optional[requests.Session] = None,
        cache_client: Optional[Any] = None,
        cache_ttl: Optional[int] = None,
    ) -> None:
        catalog_base_url = base_url or config.get("CATALOG_SERVICE_URL")
        if not catalog_base_url:
            catalog_base_url = "http://127.0.0.1:9101" if config.is_debug() else "http://localhost:8104"
        self.base_url = catalog_base_url.rstrip("/")
        self.timeout = timeout or config.get("CATALOG_SERVICE_TIMEOUT", 15)
        self.session = session or requests.Session()
        self.default_headers = {"Accept": "application/json"}
        self.cache = cache_client
        redis_url = config.get("REDIS_URL")
        if self.cache is None and redis_url and redis:
            try:
                self.cache = redis.from_url(redis_url)
            except redis.RedisError as exc:  # type: ignore[attr-defined]
                logger.warning("Failed to initialize Redis cache", exc_info=exc)
        if redis_url and not redis:
            logger.warning("Redis URL provided but redis package not installed")
        ttl_source = cache_ttl if cache_ttl is not None else config.get("CATALOG_CACHE_TTL", 300)
        try:
            self.cache_ttl = int(ttl_source)
        except (TypeError, ValueError):
            logger.warning("Invalid catalog cache TTL; falling back to default", extra={"value": ttl_source})
            self.cache_ttl = 300
        if self.cache_ttl < 0:
            self.cache_ttl = 0
        categories_path = config.get("CATALOG_SERVICE_CATEGORIES_PATH", "/categories")
        categories_path = categories_path or "/categories"
        if not categories_path.startswith("/"):
            categories_path = f"/{categories_path}"
        self.categories_path = categories_path
        categories_all_path = config.get("CATALOG_SERVICE_CATEGORIES_ALL_PATH", "/categories/all")
        categories_all_path = categories_all_path or "/categories/all"
        if not categories_all_path.startswith("/"):
            categories_all_path = f"/{categories_all_path}"
        self.categories_all_path = categories_all_path
        use_all_config = config.get("CATALOG_SERVICE_USE_CATEGORIES_ALL")
        if isinstance(use_all_config, str):
            use_all = use_all_config.lower() in {"1", "true", "yes", "on"}
        elif isinstance(use_all_config, bool):
            use_all = use_all_config
        else:
            use_all = config.is_debug()
        self.use_categories_all = use_all

    def fetch_categories(
        self,
        *,
        filters: Optional[Dict[str, Any]] = None,
        include_inactive: bool = False,
        business_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        fetch_all: bool = False,
    ) -> List[Dict[str, Any]]:
        """Fetch product categories from catalog service."""
        use_all_endpoint = fetch_all or self.use_categories_all
        endpoint_path = self.categories_all_path if use_all_endpoint else self.categories_path
        params = self._build_query_params(
            filters,
            include_inactive,
            business_id,
            limit,
            offset,
            use_all_endpoint,
        )
        endpoint = f"{self.base_url}{endpoint_path}"
        cache_key = self._build_cache_key(params, endpoint_path)

        if self.cache is not None:
            cached = self._load_from_cache(cache_key)
            if cached is not None:
                logger.debug(
                    "Serving catalog categories from cache",
                    extra={"cache_key": cache_key},
                )
                return cached

        logger.debug("Fetching catalog categories", extra={"endpoint": endpoint, "params": params})

        try:
            response = self.session.get(
                endpoint,
                params=params,
                headers=self.default_headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            logger.error("Catalog service request timed out", exc_info=exc)
            raise CatalogApiError("Catalog service timed out") from exc
        except requests.RequestException as exc:
            logger.error("Catalog service request failed", exc_info=exc)
            raise CatalogApiError("Catalog service request failed") from exc

        categories = self._parse_categories(response)

        if self.cache is not None:
            self._store_in_cache(cache_key, categories)

        return categories

    def _build_query_params(
        self,
        filters: Optional[Dict[str, Any]],
        include_inactive: bool,
        business_id: Optional[str],
        limit: Optional[int],
        offset: Optional[int],
        use_all_endpoint: bool,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if include_inactive:
            params["include_inactive"] = "true"

        if business_id:
            params["business_id"] = business_id

        if not use_all_endpoint:
            if limit is not None:
                if limit <= 0:
                    raise CatalogApiError("limit must be a positive integer")
                params["limit"] = limit
            if offset is not None:
                if offset < 0:
                    raise CatalogApiError("offset must be a non-negative integer")
                params["offset"] = offset
        elif limit is not None or offset is not None:
            logger.debug(
                "Ignoring pagination parameters for /categories/all",
                extra={"limit": limit, "offset": offset},
            )

        if not filters:
            return params

        # Only allow simple scalar filter values to avoid leaking complex payloads.
        for key, value in filters.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                params[key] = value
        return params

    def _parse_categories(self, response: Response) -> List[Dict[str, Any]]:
        try:
            payload = response.json()
        except ValueError as exc:
            logger.error("Catalog service returned invalid JSON", exc_info=exc)
            raise CatalogApiError("Invalid catalog response") from exc

        categories: Any = (
            payload.get("categories")
            or payload.get("data")
            or payload.get("results")
            or []
        )

        if not isinstance(categories, list):
            logger.error("Unexpected catalog payload shape", extra={"payload": payload})
            raise CatalogApiError("Unexpected catalog response structure")

        normalized: List[Dict[str, Any]] = []
        for item in categories:
            if not isinstance(item, dict):
                continue

            category_id = item.get("id") or item.get("category_id")
            name = item.get("name") or item.get("title")
            description = item.get("description") or ""

            if not category_id and not name:
                continue

            normalized.append(
                {
                    "id": category_id or "",
                    "name": name or "",
                    "description": description,
                }
            )

        return normalized

    def _build_cache_key(self, params: Dict[str, Any], endpoint_path: str) -> str:
        payload = {
            "endpoint": endpoint_path,
            "params": params,
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return f"catalog:categories:{digest}"

    def _load_from_cache(self, key: str) -> Optional[List[Dict[str, Any]]]:
        if self.cache is None:
            return None
        try:
            cached = self.cache.get(key)
        except Exception as exc:  # noqa: BLE001 - broad to guard optional dependency
            logger.warning("Failed to read catalog categories from cache", exc_info=exc)
            return None
        if not cached:
            return None
        try:
            cached_payload = cached.decode("utf-8") if isinstance(cached, bytes) else cached
            if not isinstance(cached_payload, str):
                logger.warning(
                    "Unexpected cached catalog categories type",
                    extra={"type": type(cached_payload).__name__},
                )
                return None
            return json.loads(cached_payload)
        except json.JSONDecodeError as exc:
            logger.warning("Invalid cached catalog categories payload", exc_info=exc)
            return None

    def _store_in_cache(self, key: str, categories: List[Dict[str, Any]]) -> None:
        if self.cache is None:
            return
        try:
            payload = json.dumps(categories)
            if self.cache_ttl > 0:
                self.cache.setex(key, self.cache_ttl, payload)
            else:
                self.cache.set(key, payload)
        except Exception as exc:  # noqa: BLE001 - ensure failures do not break API flow
            logger.warning("Failed to write catalog categories to cache", exc_info=exc)
