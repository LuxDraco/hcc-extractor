FROM python:3.12-slim

WORKDIR /app

# Install Poetry
RUN pip install poetry && \
    poetry config virtualenvs.create false

# Copy Poetry configuration files
COPY pyproject.toml poetry.lock* ./

# Install dependencies
RUN poetry install --no-interaction --no-ansi

# Copy application code
COPY ./app /app/app

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default config (override with docker-compose or command line)
ENV STORAGE_TYPE=local
ENV WATCH_PATH=/data
ENV RABBITMQ_HOST=rabbitmq
ENV RABBITMQ_PORT=5672
ENV RABBITMQ_USER=guest
ENV RABBITMQ_PASSWORD=guest
ENV RABBITMQ_QUEUE=document-events
ENV WATCH_INTERVAL=10.0
ENV FILE_PATTERNS="*.txt,*.pdf"

# Expose port if needed (for future HTTP API or metrics)
EXPOSE 8000

# Set entry point
CMD ["python", "-m", "app.main"]