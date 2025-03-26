# HCC Extractor - API Gateway Service

The API Gateway service provides a unified interface for accessing the various components of the HCC Extractor system. It handles authentication, routing, rate limiting, and serves as the entry point for all client interactions.

## Features

- User authentication and authorization with JWT tokens
- RESTful API for document management
- Integration with multiple storage backends (Local, S3, GCS)
- Document processing status tracking
- Webhook management for event notifications
- HCC code information and statistics
- Batch processing capabilities
- Comprehensive metrics and logging

## Architecture

This service follows a layered architecture:

- **API Layer**: FastAPI routes and endpoints
- **Service Layer**: Business logic implementation
- **Data Access Layer**: Database models and interactions
- **Infrastructure Layer**: External services integration

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy (async)
- **Authentication**: JWT with OAuth2
- **Message Broker**: RabbitMQ
- **Validation**: Pydantic
- **Documentation**: OpenAPI/Swagger
- **Logging**: Structlog
- **Metrics**: Prometheus
- **Dependency Management**: Poetry

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL
- RabbitMQ
- Poetry

### Installation

1. Install dependencies with Poetry:

```bash
cd services/api-gateway
poetry install
```

2. Set up environment variables (or create a `.env` file):

```bash
# Database settings
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=hcc_extractor

# RabbitMQ settings
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest

# Security settings
SECRET_KEY=your-secret-key  # Generate a secure key for production

# Storage settings
STORAGE_TYPE=local  # local, s3, or gcs
LOCAL_STORAGE_PATH=./data

# For AWS S3
# S3_BUCKET=your-bucket
# S3_REGION=us-east-1

# For Google Cloud Storage
# GCS_BUCKET=your-bucket
# GCS_PROJECT_ID=your-project-id

# API settings
PORT=8000
LOG_LEVEL=INFO
```

3. Initialize the database:

```bash
# Apply migrations
alembic upgrade head

# Create an admin user (optional)
python -m scripts.create_admin_user
```

### Running the Service

Start the service in development mode:

```bash
uvicorn gateway.main:gateway --reload --port 8000
```

Or using Poetry:

```bash
poetry run uvicorn gateway.main:gateway --reload --port 8000
```

### Using Docker

Build and run using Docker:

```bash
docker build -t hcc-extractor-api-gateway .
docker run -p 8000:8000 --env-file .env hcc-extractor-api-gateway
```

## API Endpoints

The API Gateway exposes the following endpoints:

### Authentication

- `POST /api/v1/auth/login` - Login and get an access token
- `POST /api/v1/auth/register` - Register a new user

### Documents

- `POST /api/v1/documents` - Upload a document
- `GET /api/v1/documents` - List documents
- `GET /api/v1/documents/{document_id}` - Get document details
- `DELETE /api/v1/documents/{document_id}` - Delete a document
- `GET /api/v1/documents/{document_id}/download` - Download a document
- `POST /api/v1/documents/{document_id}/reprocess` - Reprocess a document

### Batch Operations

- `POST /api/v1/batch/upload` - Batch upload documents
- `POST /api/v1/batch/process` - Batch process documents
- `GET /api/v1/batch/status` - Get batch processing status
- `DELETE /api/v1/batch` - Delete multiple documents

### HCC Codes

- `GET /api/v1/hcc/codes` - List HCC codes
- `GET /api/v1/hcc/codes/{code}` - Get HCC code details
- `GET /api/v1/hcc/categories` - List HCC categories
- `GET /api/v1/hcc/statistics` - Get HCC statistics

### Webhooks

- `POST /api/v1/webhooks` - Create a webhook
- `GET /api/v1/webhooks` - List webhooks
- `GET /api/v1/webhooks/{webhook_id}` - Get webhook details
- `PUT /api/v1/webhooks/{webhook_id}` - Update a webhook
- `DELETE /api/v1/webhooks/{webhook_id}` - Delete a webhook
- `POST /api/v1/webhooks/{webhook_id}/test` - Test a webhook

## Database Migrations

This service uses Alembic for database migrations:

```bash
# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Revert migrations
alembic downgrade -1
```

## Development

### Project Structure

```
services/api-gateway/
├── alembic.ini                # Alembic configuration
├── Dockerfile                 # Docker build instructions
├── pyproject.toml            # Poetry project definition
├── README.md                 # This file
├── migrations/               # Database migrations
│   ├── env.py
│   ├── README
│   ├── script.py.mako
│   └── versions/             # Migration scripts
│       └── 001_initial.py
└── app/                      # Application code
    ├── __init__.py
    ├── main.py               # Entry point
    ├── api/                  # API definition
    │   ├── __init__.py
    │   └── v1/               # API version 1
    │       ├── __init__.py
    │       ├── router.py     # Main router
    │       └── endpoints/    # Endpoint modules
    ├── core/                 # Core components
    │   ├── __init__.py
    │   ├── config.py         # Configuration
    │   ├── security.py       # Authentication
    │   └── dependencies.py   # Dependency injection
    ├── db/                   # Database layer
    │   ├── __init__.py
    │   ├── session.py        # SQLAlchemy session
    │   ├── base.py           # Base model
    │   └── models/           # SQLAlchemy models
    ├── schemas/              # Pydantic models
    │   ├── __init__.py
    │   ├── document.py
    │   └── ...
    ├── services/             # Business logic
    │   ├── __init__.py
    │   ├── document.py
    │   └── ...
    ├── utils/                # Utilities
    │   ├── __init__.py
    │   ├── logging.py
    │   └── ...
    └── middleware/           # Middleware components
        ├── __init__.py
        ├── logging.py
        └── ...
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=gateway
```

### Code Formatting

```bash
# Format code with Black
black gateway tests

# Check imports with isort
isort gateway tests
```

## Troubleshooting

### Common Issues

1. **Database Connection Errors**

   Check your database connection settings and ensure PostgreSQL is running.

2. **RabbitMQ Connection Errors**

   Verify RabbitMQ is running and the credentials are correct.

3. **Authentication Issues**

   Ensure your JWT secret key is set correctly.

4. **Storage Access Issues**

   Verify your storage credentials and permissions.

### Logs

Check the application logs for detailed error information:

```bash
# Set log level to DEBUG for more detailed logs
export LOG_LEVEL=DEBUG
```

## Security Considerations

- The API Gateway uses JWT for authentication
- Passwords are hashed using bcrypt
- Rate limiting is applied to prevent abuse
- CORS is configured to restrict cross-origin requests
- All sensitive data is stored securely

## Performance Optimization

- Connection pooling for database access
- Request metrics collection for monitoring
- Rate limiting to prevent resource exhaustion
- Asynchronous request handling for improved throughput