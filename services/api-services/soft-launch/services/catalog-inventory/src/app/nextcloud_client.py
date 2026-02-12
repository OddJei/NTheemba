"""
Nextcloud WebDAV client for media uploads.
"""
import os
import io
from typing import BinaryIO
from webdav3.client import Client


class NextcloudClient:
    """WebDAV client for Nextcloud file operations."""
    
    def __init__(self):
        self.base_url = os.getenv("NEXTCLOUD_URL", "http://nextcloud")
        self.username = os.getenv("NEXTCLOUD_USER", "admin")
        self.password = os.getenv("NEXTCLOUD_PASSWORD", "admin123")
        
        self.client = Client({
            'webdav_hostname': f"{self.base_url}/remote.php/dav/files/{self.username}/",
            'webdav_login': self.username,
            'webdav_password': self.password,
            'disable_check': True  # Disable SSL verification for local dev
        })
    
    def upload_product_media(
        self,
        business_id: str,
        product_id: str,
        filename: str,
        file_content: bytes | BinaryIO
    ) -> str:
        """
        Upload media file to Nextcloud.
        
        Args:
            business_id: Business UUID
            product_id: Product UUID
            filename: Original filename
            file_content: File bytes or file-like object
        
        Returns:
            Public URL to the uploaded file
        """
        # Create directory structure: /products/{business_id}/{product_id}/
        remote_dir = f"products/{business_id}/{product_id}/"
        remote_path = f"{remote_dir}{filename}"
        
        print(f"[MEDIA] Uploading to: {remote_path}")
        
        # Ensure directory exists - create all levels
        print(f"[MEDIA] Ensuring directory: {remote_dir}")
        self._ensure_directory(remote_dir)
        print(f"[MEDIA] Directory ensured")
        
        # Upload file
        if isinstance(file_content, bytes):
            file_content = io.BytesIO(file_content)
        
        print(f"[MEDIA] Uploading file...")
        self.client.upload_to(file_content, remote_path)
        print(f"[MEDIA] Upload complete")
        
        # Return public URL (adjust based on your Nextcloud sharing setup)
        # For now, return WebDAV path - in production, generate share link
        return f"{self.base_url}/remote.php/dav/files/{self.username}/{remote_path}"
    
    def delete_product_media(self, business_id: str, product_id: str, filename: str) -> bool:
        """Delete a media file from Nextcloud."""
        remote_path = f"products/{business_id}/{product_id}/{filename}"
        
        try:
            self.client.clean(remote_path)
            return True
        except Exception:
            return False
    
    def list_product_media(self, business_id: str, product_id: str) -> list[str]:
        """List all media files for a product."""
        remote_dir = f"products/{business_id}/{product_id}/"
        
        try:
            return self.client.list(remote_dir)
        except Exception:
            return []
    
    def _ensure_directory(self, remote_dir: str):
        """Create directory structure if it doesn't exist."""
        parts = remote_dir.strip("/").split("/")
        current_path = ""

        for part in parts:
            current_path += f"{part}/"
            try:
                self.client.mkdir(current_path)
            except Exception as e:
                # Ignore errors for existing directories
                message = str(e).lower()
                if "method not allowed" in message or "405" in message or "exists" in message:
                    continue
                raise


# Global instance
nextcloud_client = NextcloudClient()
