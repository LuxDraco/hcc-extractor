FROM python:3.10-slim

WORKDIR /app

# Install Poetry
RUN pip install poetry && \
    poetry config virtualenvs.create false

# Copy Poetry configuration files
COPY pyproject.toml poetry.lock* ./

# Install dependencies
RUN poetry install --no-interaction --no-ansi

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000
EXPOSE 8001

# Set entry point
CMD ["python", "-m", "hcc_extractor.main"]