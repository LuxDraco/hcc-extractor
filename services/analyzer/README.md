# HCC Analyzer Service

## Overview

The HCC Analyzer Service is a vital component of the HCC Extractor system, responsible for analyzing medical conditions extracted from clinical progress notes to determine their HCC (Hierarchical Condition Category) relevance. This service uses Vertex AI Gemini 1.5 Flash model and LangGraph to perform advanced analysis and enrichment of extracted conditions.

## Features

- Consumes extraction results from the message queue (RabbitMQ)
- Determines which of the extracted conditions are HCC-relevant by comparing against the HCC codes reference list
- Employs a hybrid approach combining rule-based matching and LLM-based analysis
- Uses LangGraph for orchestrating the complex analysis workflow
- Enriches conditions with confidence scores, reasoning, and HCC categories
- Publishes analysis results to the message queue for further processing
- Supports both batch processing and continuous message-based processing

## Architecture

The service follows a modular architecture with the following components:

- **Message Consumer**: Listens for extraction completed events and triggers analysis
- **Analysis Pipeline**: LangGraph workflow for rule-based and LLM-based analysis
- **LLM Client**: Interface to the Vertex AI Gemini 1.5 Flash model
- **Storage Manager**: Handles file operations for input and output

## Prerequisites

- Python 3.12+
- Poetry for dependency management
- RabbitMQ for message queue
- Google Cloud service account with Vertex AI access
- HCC codes reference data in CSV format

## Installation

### Using Poetry

```bash
# Install dependencies
cd services/analyzer
poetry install

# Set environment variables
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
export VERTEX_AI_PROJECT_ID=your-project-id
export VERTEX_AI_LOCATION=us-central1
export INPUT_DIR=./data
export OUTPUT_DIR=./output
export HCC_CODES_PATH=./data/HCC_relevant_codes.csv

# RabbitMQ configuration
export RABBITMQ_HOST=localhost
export RABBITMQ_PORT=5672
export RABBITMQ_USER=guest
export RABBITMQ_PASSWORD=guest
export RABBITMQ_QUEUE=document-events
```

## Usage

The service can run in three modes:

### Batch Mode

Process all extraction result files in the input directory:

```bash
python -m app.main --mode batch
```

### Consumer Mode

Listen for messages on RabbitMQ:

```bash
python -m app.main --mode consumer
```

### Both Modes

First process local files, then start listening for messages:

```bash
python -m app.main --mode both
```

## Docker Deployment

Build and run using Docker:

```bash
# Build the image
docker build -t hcc-analyzer-service .

# Run the container
docker run -v /path/to/data:/app/data \
  -v /path/to/output:/app/output \
  -v /path/to/service-account.json:/app/credentials.json \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json \
  -e VERTEX_AI_PROJECT_ID=your-project-id \
  -e VERTEX_AI_LOCATION=us-central1 \
  -e RABBITMQ_HOST=rabbitmq \
  -e RABBITMQ_USER=guest \
  -e RABBITMQ_PASSWORD=guest \
  -e HCC_CODES_PATH=/app/data/HCC_relevant_codes.csv \
  hcc-analyzer-service
```

## Message Flow

1. **Extraction Completed**: The Extractor service publishes an `extraction.completed` message to RabbitMQ
2. **Message Consumption**: The Analyzer service consumes the message and retrieves the extraction results
3. **Analysis Pipeline**: The extraction results are processed through the LangGraph pipeline
4. **HCC Relevance Determination**: Conditions are analyzed for HCC relevance using both rule-based and LLM approaches
5. **Result Publishing**: Analysis results are saved and a message is published for the next service (Validator)

## LangGraph Visualization

You can visualize the analysis pipeline using the LangGraph development web app:

```bash
docker compose exec analyzer bash -c "cd /app && poetry run langgraph dev --host 0.0.0.0 --port 8001"
```

This will provide an interactive visualization of the workflow nodes and state transitions at:

```
http://127.0.0.1:8001
```

## Troubleshooting

### Common Issues

1. **RabbitMQ Connection**:
   - Ensure RabbitMQ is running and credentials are correct
   - Verify the virtual host is properly URL-encoded if needed

2. **HCC Codes CSV**:
   - Confirm the HCC codes CSV file is available at the specified path
   - Check that the CSV has the expected columns: "ICD-10-CM Codes", "Description", and "Tags"

3. **Vertex AI**:
   - Ensure service account has proper Vertex AI permissions
   - Verify GOOGLE_APPLICATION_CREDENTIALS is correctly set

4. **Memory Usage**:
   - For large datasets, monitor memory usage as loading many HCC codes can be memory-intensive
