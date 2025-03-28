# HCC Validator Service

![Python: 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)
![Testing: Pytest](https://img.shields.io/badge/Testing-Pytest-green.svg)
![Status: Production Ready](https://img.shields.io/badge/Status-Production_Ready-green.svg)

## Overview

The HCC Validator Service is a critical component of the HCC Extractor system, responsible for validating the HCC-relevant conditions identified by the Analyzer service. This service ensures that the identified conditions comply with business rules and documentation requirements for HCC submission.

## Core Functionality

- **Rule-based Validation**: Applies configurable business rules to conditions
- **Compliance Verification**: Ensures proper documentation for HCC submission
- **ICD-10 Code Validation**: Verifies that ICD-10 codes are valid and match their descriptions
- **Confidence Threshold Enforcement**: Validates sufficient confidence scores for HCC determinations
- **Event-Driven Processing**: Consumes analysis results from RabbitMQ and publishes validation results

## Architecture

The service follows a modular architecture with the following components:

```
┌───────────────────┐       ┌───────────────────┐       ┌─────────────────┐
│                   │       │                   │       │                 │
│   Message Queue   │──────▶│  Validator Core   │──────▶│  Results Store  │
│    (RabbitMQ)     │       │                   │       │                 │
│                   │       │                   │       │                 │
└───────────────────┘       └─────────┬─────────┘       └─────────────────┘
                                      │
                                      │
                                      ▼
                            ┌───────────────────┐
                            │                   │
                            │  Code Repository  │
                            │    (HCC Codes)    │
                            │                   │
                            └───────────────────┘
```

## Key Components

### 1. Rules Engine

The Rules Engine (`validator/validator/rules_engine.py`) is a flexible framework for applying business rules to conditions. It supports:

- Dynamic rule registration
- Rule prioritization
- Exception handling
- Detailed rule evaluation results

### 2. HCC Validator

The HCC Validator (`validator/validator/hcc_validator.py`) combines the Rules Engine with domain-specific logic to:

- Validate HCC relevance determinations
- Apply compliance rules
- Generate validation reports
- Track metrics for validation

### 3. Code Repository

The Code Repository (`validator/data/code_repository.py`) provides:

- Fast lookup of ICD-10 and HCC codes
- Code-description matching
- HCC category information
- Validation utilities for code formatting

### 4. Message Consumer

The Message Consumer (`validator/message_consumer.py`) handles:

- RabbitMQ message consumption
- Processing of analysis results
- Database status updates
- Publishing of validation results

## Setup & Installation

### Prerequisites

- Python 3.12+
- Poetry for dependency management
- RabbitMQ for message queue
- HCC codes reference data in CSV format

### Using Poetry

```bash
# Install dependencies
cd services/validator
poetry install

# Create and configure the .env file
cat > .env << EOF
# RabbitMQ Configuration
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_DEFAULT_USER=hccuser
RABBITMQ_DEFAULT_PASS=hccpass
RABBITMQ_USER=hccuser
RABBITMQ_PASSWORD=hccpass
RABBITMQ_VHOST=/
RABBITMQ_QUEUE=validator-events

# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=hcc_extractor

# Google Cloud Configuration
GOOGLE_APPLICATION_CREDENTIALS=../../service-account.json
VERTEX_AI_PROJECT_ID=guacamayo-tech
VERTEX_AI_LOCATION=us-central1

# Path Configuration
INPUT_DIR=../../data/pn
OUTPUT_DIR=../../output
HCC_CODES_PATH=../../data/HCC_relevant_codes.csv
EOF
```

## Usage

The service can run in three modes:

### Batch Mode

Process all analysis result files in the input directory:

```bash
python -m validator.main --mode batch
```

### Consumer Mode

Listen for messages on RabbitMQ:

```bash
python -m validator.main --mode consumer
```

### Both Modes

First process local files, then start listening for messages:

```bash
python -m validator.main --mode both
```

## Docker Deployment

Build and run using Docker:

```bash
# Build the image
docker build -t hcc-validator-service .

# Run the container
docker run -v /path/to/data:/app/data \
  -v /path/to/output:/app/output \
  -v /path/to/service-account.json:/app/credentials.json \
  -e RABBITMQ_HOST=rabbitmq \
  -e RABBITMQ_PORT=5672 \
  -e RABBITMQ_DEFAULT_USER=hccuser \
  -e RABBITMQ_DEFAULT_PASS=hccpass \
  -e RABBITMQ_USER=hccuser \
  -e RABBITMQ_PASSWORD=hccpass \
  -e RABBITMQ_VHOST=/ \
  -e RABBITMQ_QUEUE=validator-events \
  -e POSTGRES_HOST=postgres \
  -e POSTGRES_PORT=5432 \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=hcc_extractor \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json \
  -e VERTEX_AI_PROJECT_ID=guacamayo-tech \
  -e VERTEX_AI_LOCATION=us-central1 \
  -e INPUT_DIR=/app/data/pn \
  -e OUTPUT_DIR=/app/output \
  -e HCC_CODES_PATH=/app/data/HCC_relevant_codes.csv \
  hcc-validator-service
```

## Message Flow

1. **Analysis Completed**: The Analyzer service publishes an `analysis.completed` message to RabbitMQ
2. **Message Consumption**: The Validator service consumes the message and retrieves the analysis results
3. **Rules Application**: The analysis results are validated using the Rules Engine
4. **Compliance Determination**: Conditions are validated for compliance with business rules
5. **Result Publishing**: Validation results are saved and a message is published for the next service

## Testing

The validator service includes comprehensive unit tests:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=validator

# Run specific test module
pytest tests/test_validator.py
```

### Key Test Areas

The test suite covers:

- Rules Engine functionality
- HCC Validator logic
- Code Repository operations
- Message processing
- Compliance determination

## Validation Rules

The validator applies several business rules to each condition:

1. **Valid ICD-10 Code**: Each condition must have a valid ICD-10 code
2. **HCC Relevance Verification**: If marked as HCC-relevant, the code must exist in the HCC reference list
3. **Sufficient Confidence**: Confidence score must be above a threshold (0.7 by default)
4. **Code-Description Match**: ICD code and description must match reference data

## Troubleshooting

### Common Issues

1. **RabbitMQ Connection**:
   - Ensure RabbitMQ is running and credentials are correct
   - Verify the virtual host is properly URL-encoded if needed

2. **HCC Codes CSV**:
   - Confirm the HCC codes CSV file is available at the specified path
   - Check that the CSV has the expected columns: "ICD-10-CM Codes", "Description", and "Tags"

3. **File Paths**:
   - Ensure input and output directories exist and are accessible
   - Verify file permissions allow the service to read and write files

4. **Memory Usage**:
   - For large datasets, monitor memory usage as loading many HCC codes can be memory-intensive

## Development

### Adding New Validation Rules

New validation rules can be added to the `_register_rules` method in `HCCValidator`:

```python
# Example: Adding a new rule for minimum condition description length
self.rules_engine.register_rule(
    "description_length",
    lambda condition: condition.name and len(condition.name) >= 10,
    "Condition description must be at least 10 characters"
)
```

### Project Structure

```
validator/
├── __init__.py
├── main.py                 # Entry point
├── message_consumer.py     # RabbitMQ consumer
├── data/                   # Data access components
│   ├── __init__.py
│   └── code_repository.py  # HCC code repository
├── models/                 # Data models
│   ├── __init__.py
│   └── condition.py        # Condition and result models
├── storage/                # Storage operations
│   ├── __init__.py
│   └── local.py            # Local file operations
├── validator/              # Validation logic
│   ├── __init__.py
│   ├── rules_engine.py     # Generic rules engine
│   └── hcc_validator.py    # HCC-specific validation
├── db/                     # Database integration
│   ├── __init__.py
│   ├── base.py             # Base model
│   ├── models/             # Database models
│   └── database_integration.py # DB update utilities
└── tests/                  # Test suite
    ├── __init__.py
    └── test_validator.py   # Validator tests
```