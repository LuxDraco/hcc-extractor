#!/bin/bash
set -e

# Run migrations
echo "Running database migrations..."
cd /app
alembic upgrade head

# Start the application
echo "Starting API Gateway..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers