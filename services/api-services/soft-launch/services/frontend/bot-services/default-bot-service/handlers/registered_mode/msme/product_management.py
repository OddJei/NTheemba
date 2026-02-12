"""MSME product management handlers."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

def add_product(session_id: str, payload: Dict[str, Any], business_id: str = None, **kwargs) -> Dict[str, Any]:
    """Add new product to MSME catalog"""
    try:
        if not business_id:
            return {"error": "Business ID is required for MSME operations"}
        
        product_data = payload.get("data", {})
        name = product_data.get("name")
        description = product_data.get("description")
        price = product_data.get("price")
        category = product_data.get("category")
        
        if not all([name, description, price, category]):
            return {"error": "Product name, description, price, and category are required"}
        
        # Generate product ID
        product_id = f"PROD-{business_id}-{str(uuid.uuid4())[:8].upper()}"
        
        # Mock product creation - in real implementation, this would save to database
        product = {
            "product_id": product_id,
            "business_id": business_id,
            "name": name,
            "description": description,
            "price": float(price),
            "category": category,
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "session_id": session_id
        }
        
        response = {
            "message": f"Product '{name}' added successfully!",
            "product": product,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Product added for business {business_id} in session {session_id}: {product_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error adding product: {e}")
        return {"error": f"Failed to add product: {str(e)}"}

def edit_product(session_id: str, payload: Dict[str, Any], business_id: str = None, **kwargs) -> Dict[str, Any]:
    """Edit existing product"""
    try:
        if not business_id:
            return {"error": "Business ID is required for MSME operations"}
        
        product_id = payload.get("data", {}).get("product_id")
        if not product_id:
            return {"error": "Product ID is required"}
        
        # Mock product update - in real implementation, this would update database
        updated_fields = payload.get("data", {}).get("updated_fields", {})
        
        product = {
            "product_id": product_id,
            "business_id": business_id,
            "updated_fields": updated_fields,
            "updated_at": datetime.now().isoformat(),
            "session_id": session_id
        }
        
        response = {
            "message": f"Product {product_id} updated successfully!",
            "product": product,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Product {product_id} edited for business {business_id} in session {session_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error editing product: {e}")
        return {"error": f"Failed to edit product: {str(e)}"}

def remove_product(session_id: str, payload: Dict[str, Any], business_id: str = None, **kwargs) -> Dict[str, Any]:
    """Remove product from catalog"""
    try:
        if not business_id:
            return {"error": "Business ID is required for MSME operations"}
        
        product_id = payload.get("data", {}).get("product_id")
        if not product_id:
            return {"error": "Product ID is required"}
        
        # Mock product removal - in real implementation, this would update database
        response = {
            "message": f"Product {product_id} removed from catalog",
            "product_id": product_id,
            "business_id": business_id,
            "removed_at": datetime.now().isoformat(),
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Product {product_id} removed for business {business_id} in session {session_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error removing product: {e}")
        return {"error": f"Failed to remove product: {str(e)}"}

def view_product_list(session_id: str, payload: Dict[str, Any], business_id: str = None, **kwargs) -> Dict[str, Any]:
    """View all products for MSME business"""
    try:
        if not business_id:
            return {"error": "Business ID is required for MSME operations"}
        
        # Mock product list - in real implementation, this would fetch from database
        products = [
            {
                "product_id": f"PROD-{business_id}-001",
                "name": "Sample Product 1",
                "price": 29.99,
                "category": "Electronics",
                "status": "active",
                "created_at": "2024-01-15T10:00:00Z"
            },
            {
                "product_id": f"PROD-{business_id}-002",
                "name": "Sample Product 2",
                "price": 49.99,
                "category": "Clothing",
                "status": "active",
                "created_at": "2024-01-16T14:30:00Z"
            }
        ]
        
        response = {
            "message": f"Your product catalog ({len(products)} products):",
            "products": products,
            "business_id": business_id,
            "total_products": len(products),
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Product list viewed for business {business_id} in session {session_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error viewing product list: {e}")
        return {"error": f"Failed to view product list: {str(e)}"}

def update_product_status(session_id: str, payload: Dict[str, Any], business_id: str = None, **kwargs) -> Dict[str, Any]:
    """Update product status (active/inactive)"""
    try:
        if not business_id:
            return {"error": "Business ID is required for MSME operations"}
        
        product_id = payload.get("data", {}).get("product_id")
        new_status = payload.get("data", {}).get("status")
        
        if not product_id or not new_status:
            return {"error": "Product ID and status are required"}
        
        valid_statuses = ["active", "inactive", "draft"]
        if new_status not in valid_statuses:
            return {"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}
        
        response = {
            "message": f"Product {product_id} status updated to {new_status}",
            "product_id": product_id,
            "status": new_status,
            "business_id": business_id,
            "updated_at": datetime.now().isoformat(),
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Product {product_id} status updated to {new_status} for business {business_id} in session {session_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error updating product status: {e}")
        return {"error": f"Failed to update product status: {str(e)}"}

def bulk_update_products(session_id: str, payload: Dict[str, Any], business_id: str = None, **kwargs) -> Dict[str, Any]:
    """Bulk update multiple products"""
    try:
        if not business_id:
            return {"error": "Business ID is required for MSME operations"}
        
        product_updates = payload.get("data", {}).get("product_updates", [])
        if not product_updates:
            return {"error": "Product updates are required"}
        
        # Mock bulk update - in real implementation, this would update database
        updated_count = len(product_updates)
        
        response = {
            "message": f"Bulk update completed: {updated_count} products updated",
            "updated_count": updated_count,
            "business_id": business_id,
            "updated_at": datetime.now().isoformat(),
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Bulk update completed for business {business_id} in session {session_id}: {updated_count} products")
        return response
        
    except Exception as e:
        logger.error(f"Error bulk updating products: {e}")
        return {"error": f"Failed to bulk update products: {str(e)}"}

def duplicate_product(session_id: str, payload: Dict[str, Any], business_id: str = None, **kwargs) -> Dict[str, Any]:
    """Duplicate existing product"""
    try:
        if not business_id:
            return {"error": "Business ID is required for MSME operations"}
        
        source_product_id = payload.get("data", {}).get("source_product_id")
        new_name = payload.get("data", {}).get("new_name")
        
        if not source_product_id or not new_name:
            return {"error": "Source product ID and new name are required"}
        
        # Generate new product ID
        new_product_id = f"PROD-{business_id}-{str(uuid.uuid4())[:8].upper()}"
        
        response = {
            "message": f"Product duplicated successfully! New product: {new_product_id}",
            "source_product_id": source_product_id,
            "new_product_id": new_product_id,
            "new_name": new_name,
            "business_id": business_id,
            "created_at": datetime.now().isoformat(),
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Product {source_product_id} duplicated for business {business_id} in session {session_id}: {new_product_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error duplicating product: {e}")
        return {"error": f"Failed to duplicate product: {str(e)}"}