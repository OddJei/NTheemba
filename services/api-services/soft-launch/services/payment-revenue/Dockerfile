FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (small, but helps some wheels)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY services/payment-revenue/requirements.txt ./requirements.txt
COPY services/payment-revenue/requirements-prod.txt ./requirements-prod.txt
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy shared libraries from the repository root so `import libs` works in the container
COPY libs ./libs

# Copy the service source
COPY services/payment-revenue/src ./src

# Service listens on 8590 in this stack.
EXPOSE 8590

CMD ["python", "-m", "uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8590"]
