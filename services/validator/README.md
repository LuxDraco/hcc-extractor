# HCC Validator Service

## Overview

The HCC Validator Service is a critical component of the HCC Extractor system, responsible for validating the HCC-relevant conditions identified by the Analyzer service. This service ensures that the identified conditions comply with business rules and documentation requirements for HCC submission.

## Features

- Consumes analysis results from the message queue (RabbitMQ)
- Validates HCC-relevant conditions against compliance rules
- Applies business rules to ensure proper documentation
- Verifies that ICD-10 codes are valid and match their descriptions
- Ensures sufficient confidence scores for HCC determinations
- Publishes validation results to the message queue for further processing
- Supports both batch processing and continuous message-based processing

## Architecture

The service follows a modular architecture with the following components:

- **Message Consumer**: Listens for analysis completed events and triggers validation
- **Rules Engine**: Applies configurable business rules to conditions
- **Code Repository**: Provides access to ICD-10 and HCC reference data
- **Storage Manager**: Handles file operations for input and output

## Prerequisites

- Python 3.12+
- Poetry for dependency management
- RabbitMQ for message queue
- HCC codes reference data in CSV format

## Installation

### Using Poetry

```bash
# Install dependencies
cd services/validator
poetry install

# Set environment variables
export RABBITMQ_HOST=localhost
export RABBITMQ_PORT=5672
export RABBITMQ_USER=guest
export RABBITMQ_PASSWORD=guest
export RABBITMQ_QUEUE=document-events
export RABBITMQ_EXCHANGE=hcc-extractor
export INPUT_DIR=./data
export OUTPUT_DIR=./output
export HCC_CODES_PATH=./data/HCC_relevant_codes.csv
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
  -e RABBITMQ_HOST=rabbitmq \
  -e RABBITMQ_USER=guest \
  -e RABBITMQ_PASSWORD=guest \
  -e HCC_CODES_PATH=/app/data/HCC_relevant_codes.csv \
  hcc-validator-service
```

## Message Flow

1. **Analysis Completed**: The Analyzer service publishes an `analysis.completed` message to RabbitMQ
2. **Message Consumption**: The Validator service consumes the message and retrieves the analysis results
3. **Rules Application**: The analysis results are validated using the Rules Engine
4. **Compliance Determination**: Conditions are validated for compliance with business rules
5. **Result Publishing**: Validation results are saved and a message is published for the next service

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