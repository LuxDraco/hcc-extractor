FROM python:3.12-slim

WORKDIR /app

# Install Poetry
RUN pip install poetry && \
    poetry config virtualenvs.create false

# Copy Poetry configuration files
COPY pyproject.toml ./

# Copy application code
COPY . .

# Install dependencies
RUN poetry install --no-interaction --no-ansi --no-root

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000
EXPOSE 8001

# Set entry point
CMD ["python", "-m", "hcc_extractor.main"]