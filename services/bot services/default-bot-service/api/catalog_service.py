"""Catalog service API client."""

import logging
import requests
from typing import Dict, Any, List, Optional
from config.environment import config

logger = logging.getLogger(__name__)

class CatalogServiceClient:
    """Client for catalog service"""
    
    def __init__(self):
        self.base_url = config.get_service_url("CATALOG_SERVICE")
        self.timeout = config.get_service_timeout("CATALOG_SERVICE")
        self.api_key = config.get("API_KEY_VALUE")
    
    def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to catalog service"""
        try:
            url = f"{self.base_url}{endpoint}"
            headers = {
                "Content-Type": "application/json",
                config.get("API_KEY_HEADER"): self.api_key
            }
            
            response = requests.request(
                method=method,
                url=url,
                json=data,
                headers=headers,
                params=params,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Catalog service request failed: {e}")
            return {"error": f"Catalog service error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in catalog service: {e}")
            return {"error": f"Unexpected error: {str(e)}"}
    
    def get_categories(self, parent_id: str = None) -> Dict[str, Any]:
        """Get product categories"""
        try:
            params = {}
            if parent_id:
                params["parent_id"] = parent_id
            
            result = self._make_request("GET", "/catalog/categories", params=params)
            
            if "error" not in result:
                logger.info("Categories retrieved from catalog service")
            else:
                logger.warning("Failed to get categories from catalog service")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return {"error": f"Categories error: {str(e)}"}
    
    def get_products(self, category_id: str = None, search_query: str = None, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Get products with optional filtering"""
        try:
            params = {
                "limit": limit,
                "offset": offset
            }
            if category_id:
                params["category_id"] = category_id
            if search_query:
                params["search"] = search_query
            
            result = self._make_request("GET", "/catalog/products", params=params)
            
            if "error" not in result:
                logger.info(f"Products retrieved from catalog service: {len(result.get('products', []))} products")
            else:
                logger.warning("Failed to get products from catalog service")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting products: {e}")
            return {"error": f"Products error: {str(e)}"}
    
    def get_product_details(self, product_id: str) -> Dict[str, Any]:
        """Get detailed product information"""
        try:
            result = self._make_request("GET", f"/catalog/products/{product_id}")
            
            if "error" not in result:
                logger.info(f"Product details retrieved: {product_id}")
            else:
                logger.warning(f"Failed to get product details: {product_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting product details: {e}")
            return {"error": f"Product details error: {str(e)}"}
    
    def search_products(self, query: str, filters: Dict[str, Any] = None, limit: int = 50) -> Dict[str, Any]:
        """Search products with query and filters"""
        try:
            data = {
                "query": query,
                "filters": filters or {},
                "limit": limit
            }
            
            result = self._make_request("POST", "/catalog/search", data)
            
            if "error" not in result:
                logger.info(f"Product search completed: {query}")
            else:
                logger.warning(f"Failed to search products: {query}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return {"error": f"Product search error: {str(e)}"}
    
    def get_product_reviews(self, product_id: str, limit: int = 20) -> Dict[str, Any]:
        """Get product reviews"""
        try:
            params = {"limit": limit}
            result = self._make_request("GET", f"/catalog/products/{product_id}/reviews", params=params)
            
            if "error" not in result:
                logger.info(f"Product reviews retrieved: {product_id}")
            else:
                logger.warning(f"Failed to get product reviews: {product_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting product reviews: {e}")
            return {"error": f"Product reviews error: {str(e)}"}
    
    def add_product_review(self, product_id: str, user_id: str, rating: int, review_text: str) -> Dict[str, Any]:
        """Add product review"""
        try:
            data = {
                "product_id": product_id,
                "user_id": user_id,
                "rating": rating,
                "review_text": review_text
            }
            
            result = self._make_request("POST", f"/catalog/products/{product_id}/reviews", data)
            
            if "error" not in result:
                logger.info(f"Product review added: {product_id}")
            else:
                logger.warning(f"Failed to add product review: {product_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error adding product review: {e}")
            return {"error": f"Add review error: {str(e)}"}
    
    def get_featured_products(self, limit: int = 10) -> Dict[str, Any]:
        """Get featured products"""
        try:
            params = {"limit": limit}
            result = self._make_request("GET", "/catalog/featured", params=params)
            
            if "error" not in result:
                logger.info("Featured products retrieved")
            else:
                logger.warning("Failed to get featured products")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting featured products: {e}")
            return {"error": f"Featured products error: {str(e)}"}
    
    def get_related_products(self, product_id: str, limit: int = 5) -> Dict[str, Any]:
        """Get related products"""
        try:
            params = {"limit": limit}
            result = self._make_request("GET", f"/catalog/products/{product_id}/related", params=params)
            
            if "error" not in result:
                logger.info(f"Related products retrieved: {product_id}")
            else:
                logger.warning(f"Failed to get related products: {product_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting related products: {e}")
            return {"error": f"Related products error: {str(e)}"}
    
    def get_product_availability(self, product_id: str) -> Dict[str, Any]:
        """Check product availability"""
        try:
            result = self._make_request("GET", f"/catalog/products/{product_id}/availability")
            
            if "error" not in result:
                logger.info(f"Product availability checked: {product_id}")
            else:
                logger.warning(f"Failed to check product availability: {product_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking product availability: {e}")
            return {"error": f"Product availability error: {str(e)}"}
    
    def get_product_pricing(self, product_id: str, quantity: int = 1) -> Dict[str, Any]:
        """Get product pricing information"""
        try:
            params = {"quantity": quantity}
            result = self._make_request("GET", f"/catalog/products/{product_id}/pricing", params=params)
            
            if "error" not in result:
                logger.info(f"Product pricing retrieved: {product_id}")
            else:
                logger.warning(f"Failed to get product pricing: {product_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting product pricing: {e}")
            return {"error": f"Product pricing error: {str(e)}"}
    
    def get_catalog_analytics(self, business_id: str = None) -> Dict[str, Any]:
        """Get catalog analytics"""
        try:
            params = {}
            if business_id:
                params["business_id"] = business_id
            
            result = self._make_request("GET", "/catalog/analytics", params=params)
            
            if "error" not in result:
                logger.info("Catalog analytics retrieved")
            else:
                logger.warning("Failed to get catalog analytics")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting catalog analytics: {e}")
            return {"error": f"Catalog analytics error: {str(e)}"}

