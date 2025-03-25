FROM python:3.12-slim

WORKDIR /app

# Install system dependencies including C headers
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libpq-dev \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry && \
    poetry config virtualenvs.create false

# Copy Poetry configuration files
COPY pyproject.toml poetry.lock* ./

# Create empty app directory to satisfy poetry
RUN mkdir -p app

# Install dependencies (without dev dependencies)
RUN poetry install --no-interaction --no-ansi --without dev --no-root

# Copy application code
# First remove the placeholder directory
RUN rm -rf app
COPY app ./app/

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Set entry point
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]