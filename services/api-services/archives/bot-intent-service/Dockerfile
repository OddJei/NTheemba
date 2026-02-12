FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies if a requirements.txt exists
COPY requirements.txt ./
RUN sh -c "if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; else pip install --no-cache-dir pytest redis httpx pydantic; fi"

# Copy service code
COPY . /app

EXPOSE 5530

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5530"]
