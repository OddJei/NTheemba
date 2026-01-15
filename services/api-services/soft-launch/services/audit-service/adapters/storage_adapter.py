import os

def upload_export(local_path: str, dest_path: str) -> str:
    """Placeholder: upload a local file to object storage and return a signed URL or path."""
    # Implement S3/MinIO upload here. For now return local path.
    return f"file://{os.path.abspath(local_path)}"
