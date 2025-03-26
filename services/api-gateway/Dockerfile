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
COPY pyproject.toml ./

# Copy application code
COPY . ./

# Install dependencies (without dev dependencies)
RUN poetry install --no-interaction --no-ansi

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Crear un nuevo script de entrada - REEMPLAZAR EL EXISTENTE
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Run migrations\n\
echo "Running database migrations..."\n\
cd /app\n\
alembic upgrade head\n\
\n\
# Start the application\n\
echo "Starting API Gateway..."\n\
exec uvicorn main:app --host 0.0.0.0 --port 8000 --proxy-headers' > /app/start.sh

# Dar permisos de ejecución
RUN chmod +x /app/start.sh

# Comando para ejecutar
CMD ["/bin/bash", "/app/start.sh"]