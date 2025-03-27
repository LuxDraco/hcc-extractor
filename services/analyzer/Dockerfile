FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry && \
    poetry config virtualenvs.create false

# Copy Poetry configuration files
COPY pyproject.toml ./

# Copy application code
COPY . .

# Install dependencies
RUN poetry install --no-interaction --no-ansi

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port if needed
EXPOSE 8000

# Set entry point
CMD ["python", "-m", "main", "--mode", "consumer"]