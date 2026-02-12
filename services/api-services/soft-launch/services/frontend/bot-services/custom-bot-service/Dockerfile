# Dockerfile placeholder for custom-bot-service
FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN python -m pip install --upgrade pip setuptools wheel \
	&& pip install --no-cache-dir -r requirements.txt
CMD ["python", "-m", "services.stream_worker"]
