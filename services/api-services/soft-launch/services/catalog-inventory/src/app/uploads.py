from __future__ import annotations

import io
import tempfile
from typing import Optional

import boto3
from botocore.client import Config
from PIL import Image

from src.app.config import get_s3_settings


def _s3_client():
    s = get_s3_settings()
    client = boto3.client(
        "s3",
        endpoint_url=s["endpoint_url"],
        aws_access_key_id=s["access_key"],
        aws_secret_access_key=s["secret_key"],
        region_name=s["region"],
        config=Config(signature_version="s3v4"),
        use_ssl=bool(s["use_ssl"]),
    )
    return client


def generate_presigned_put_url(key: str, content_type: str, expires_in: int = 3600) -> str:
    client = _s3_client()
    bucket = get_s3_settings()["bucket"]
    url = client.generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=int(expires_in),
    )
    return url


def generate_presigned_get_url(key: str, expires_in: int = 3600) -> str:
    client = _s3_client()
    bucket = get_s3_settings()["bucket"]
    url = client.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=int(expires_in),
    )
    return url


def process_image_and_upload(source_key: str, dest_key: str, size: tuple[int, int] = (800, 800)) -> None:
    """Download object `source_key`, create a resized variant, and upload as `dest_key`.

    This uses Pillow for a minimal, portable implementation.
    """
    client = _s3_client()
    bucket = get_s3_settings()["bucket"]

    with tempfile.TemporaryFile() as tf:
        client.download_fileobj(Bucket=bucket, Key=source_key, Fileobj=tf)
        tf.seek(0)
        img = Image.open(tf)
        img = img.convert("RGB")
        img.thumbnail(size, Image.Resampling.LANCZOS)

        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85)
        out.seek(0)

        client.upload_fileobj(Fileobj=out, Bucket=bucket, Key=dest_key, ExtraArgs={"ContentType": "image/jpeg"})


def upload_bytes(key: str, data: bytes, content_type: Optional[str] = None) -> None:
    client = _s3_client()
    bucket = get_s3_settings()["bucket"]
    extra = {}
    if content_type:
        extra["ContentType"] = content_type
    client.put_object(Bucket=bucket, Key=key, Body=data, **extra)
