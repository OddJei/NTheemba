FROM python:3.11-slim

WORKDIR /app

# Install Python deps (copy only requirements first for layer cache)
COPY services/bot-session/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy service source and shared libs from repo root into the image
COPY services/bot-session /app
COPY libs /app/libs

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
