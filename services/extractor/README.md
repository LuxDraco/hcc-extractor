# HCC Extractor Service

This service extracts medical conditions from clinical progress notes using LangGraph and Vertex AI Gemini 1.5 Flash.

## Overview

The HCC Extractor Service is a key component of the HCC Extractor system, responsible for:

1. Consuming clinical progress notes from the message queue or local directory
2. Extracting medical conditions and their ICD-10 codes using rule-based and LLM-based approaches
3. Sending the extracted information to the next stage in the processing pipeline

## Features

- **Dual Processing Modes**: Process files from a local directory or consume messages from RabbitMQ
- **LangGraph Integration**: Uses LangGraph to orchestrate the extraction workflow
- **Vertex AI Integration**: Leverages Gemini 1.5 Flash for accurate extraction
- **Hybrid Extraction**: Combines rule-based and LLM-based approaches for optimal results
- **Message Queue Integration**: Communicates with other services via RabbitMQ

## Architecture

The service follows a modular architecture:

- **Message Consumer**: Listens for document upload events and triggers processing
- **Document Processor**: Coordinates the extraction process
- **Extraction Pipeline**: LangGraph workflow for rule-based and LLM-based extraction
- **Storage Manager**: Handles file operations for input and output

## Installation

### Prerequisites

- Python 3.12+
- Poetry for dependency management
- RabbitMQ for message queue (optional for batch mode)
- Google Cloud service account with Vertex AI access

### Setup with Poetry

```bash
# Install dependencies
cd services/extractor
poetry install

# Set environment variables
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
export VERTEX_AI_PROJECT_ID=your-project-id
export VERTEX_AI_LOCATION=us-central1
export INPUT_DIR=./data
export OUTPUT_DIR=./output

# For message queue mode
export RABBITMQ_HOST=localhost
export RABBITMQ_PORT=5672
export RABBITMQ_USER=guest
export RABBITMQ_PASSWORD=guest
export RABBITMQ_QUEUE=document-events
```

## Usage

The service can run in three modes:

### 1. Batch Mode (Local Files)

Processes all files in the input directory:

```bash
python -m main --mode batch
```

### 2. Consumer Mode (Message Queue)

Listens for messages on RabbitMQ:

```bash
python -m main --mode consumer
```

### 3. Both Modes

First processes local files, then starts listening for messages:

```bash
python -m main --mode both
```

## Docker Deployment

Build and run using Docker:

```bash
# Build the image
docker build -t hcc-extractor-service .

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
  hcc-extractor-service
```

## Docker Compose

For a complete setup with all services:

```bash
# Run with standard docker-compose.yml
docker-compose up

# Run with messaging configuration
docker-compose -f docker-compose.yml -f docker-compose.messaging.yml up
```

## Understanding the Message Flow

1. **Document Upload**: API Gateway receives a document and publishes a message to RabbitMQ
2. **Message Consumption**: Extractor service consumes the message and retrieves the document
3. **Document Processing**: Document is processed through the LangGraph pipeline
4. **Result Publishing**: Extraction results are saved and a message is published for the next service
5. **Analyzer Processing**: Analyzer service processes the extraction results to determine HCC relevance

## Development

### Project Structure

```
services/extractor/
├── app/
│   ├── __init__.py
│   ├── extractor/           # Core extraction logic
│   │   ├── __init__.py
│   │   └── processor.py     # Document processing
│   ├── graph/               # LangGraph components
│   │   ├── __init__.py
│   │   ├── nodes.py         # Graph nodes
│   │   ├── pipeline.py      # Graph definition
│   │   └── state.py         # State schema
│   ├── llm/                 # LLM integration
│   │   ├── __init__.py
│   │   └── client.py        # Gemini client
│   ├── models/              # Data models
│   │   ├── __init__.py
│   │   └── document.py      # Document models
│   ├── storage/             # Storage operations
│   │   ├── __init__.py
│   │   ├── local.py         # Local storage
│   │   └── cloud.py         # Cloud storage
│   ├── utils/               # Utilities
│   │   ├── __init__.py
│   │   └── document_parser.py # Document parsing
│   └── message_consumer.py  # RabbitMQ consumer
├── main.py                  # Entry point
├── Dockerfile               # Docker build instructions
├── pyproject.toml           # Poetry configuration
└── README.md                # This file
```

## Troubleshooting

### Common Issues

1. **RabbitMQ Connection**:
   - Check that RabbitMQ is running and credentials are correct
   - Verify the virtual host "/" is properly URL-encoded as "%2F" if needed

2. **Document Not Found**:
   - Verify file paths in messages
   - Check mounted volumes in Docker

3. **Vertex AI**:
   - Ensure service account has Vertex AI permissions
   - Verify GOOGLE_APPLICATION_CREDENTIALS is correctly set

4. **Output Directory**:
   - Ensure the output directory exists and is writable

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

[MIT License](LICENSE)