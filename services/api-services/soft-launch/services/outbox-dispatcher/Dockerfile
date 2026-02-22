FROM python:3.11-slim

WORKDIR /app

# Copy source and install runtime dependencies; this image is intentionally minimal
COPY . .

ENV PIP_DEFAULT_TIMEOUT=100
# Retry installs a few times to mitigate transient network timeouts during build
RUN for i in 1 2 3; do \
	pip install --no-cache-dir fastapi uvicorn httpx asyncpg && break || \
	(echo "pip install failed, retrying... ($i)" && sleep 5); \
	done

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8550"]
