# Catalog + Inventory (Soft Launch)

Fused **Catalog + Inventory** implementation for soft launch.

## Run

```bash
pip install -r requirements.txt
uvicorn src.app.main:app --reload --port 8520 --host 127.0.0.1
```

## Headers

- `X-Correlation-Id` (optional): echoed back in responses
- `X-Idempotency-Key` (optional): idempotent writes for POST/PUT/DELETE

## Core Routes

### Health
- `GET /health`

### Catalog
- `POST /catalog/category`
- `GET /catalog/category/{id}`
- `GET /catalog/categories`
- `PUT /catalog/category/{id}`
- `DELETE /catalog/category/{id}`

- `POST /catalog/product`
- `GET /catalog/product/{id}`
- `PUT /catalog/product/{id}`
- `DELETE /catalog/product/{id}`
- `POST /catalog/product/{id}/variant`
- `GET /catalog/business/{id}`

- `POST /catalog/reindex/{business_id}`

### Inventory
- `POST /inventory/update`
- `GET /inventory/{variant_id}`

### Events (outbox)
- `GET /events` (optional debug)

## Media (Nextcloud)

Media files are stored in Nextcloud using WebDAV. Files are uploaded to:

`/remote.php/dav/files/{NEXTCLOUD_USER}/products/{business_id}/{product_id}/{filename}`

The product record stores media metadata in the `media_urls` JSONB column. Each entry is shaped like:

```json
{
	"url": "http://nextcloud/remote.php/dav/files/admin/products/{business_id}/{product_id}/{filename}",
	"filename": "image.png",
	"uploaded_at": "2026-02-01T20:17:37.621838+00:00",
	"content_type": "image/png",
	"size": 285,
	"is_default": true
}
```

### Media Endpoints

- `POST /catalog/product/{id}/media`
	- **Purpose**: Upload multiple media files for a product.
	- **Form data**:
		- `files`: list of files (required)
		- `set_default_index`: integer (optional, default: `0`). Index of the uploaded file to mark as default.
	- **Behavior**:
		- Unsets any previous defaults.
		- Uploads each file to Nextcloud.
		- Writes metadata to `media_urls` and marks the chosen file as default.
	- **Audit**: Emits `media_uploaded` per file.

- `PATCH /catalog/product/{id}/media/{filename}/set-default`
	- **Purpose**: Change which existing media file is the default (no re-upload).
	- **Behavior**:
		- Sets `is_default=true` on the target file.
		- Sets `is_default=false` on all other files.
	- **Audit**: Emits `media_default_set`.

- `DELETE /catalog/product/{id}/media/{filename}`
	- **Purpose**: Delete a media file from Nextcloud and the product record.
	- **Behavior**:
		- Removes the file from Nextcloud.
		- Removes the metadata entry from `media_urls`.
		- If the deleted file was default, assigns the first remaining file as default.
	- **Audit**: Emits `media_deleted`.

### Nextcloud Configuration

Environment variables used by the client (see `src/app/nextcloud_client.py`):

- `NEXTCLOUD_URL` (default: `http://nextcloud`)
- `NEXTCLOUD_USER` (default: `admin`)
- `NEXTCLOUD_PASSWORD` (default: `admin123`)

The WebDAV base is composed as:

`{NEXTCLOUD_URL}/remote.php/dav/files/{NEXTCLOUD_USER}/`

## Migrations (Alembic)

```bash
# autogenerate new revision
alembic revision --autogenerate -m "change"

# apply migrations
alembic upgrade head
```

## Outbox dispatcher

```bash
# requires EVENT_SINK_URL
python -m src.app.outbox_dispatcher
```
