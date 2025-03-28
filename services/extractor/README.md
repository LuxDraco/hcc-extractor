# HCC Extractor Service

![Python: 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)
![Testing: Pytest](https://img.shields.io/badge/Testing-Pytest-green.svg)
![Status: Production Ready](https://img.shields.io/badge/Status-Production_Ready-green.svg)

## Overview

The HCC Extractor Service is the cornerstone of the HCC Extractor system, responsible for parsing clinical progress notes and extracting medical conditions with their associated ICD-10 codes. This service employs advanced NLP techniques through Google's Vertex AI Gemini models and LangGraph to deliver precise, structured extraction results.

## Core Functionality

- **Clinical Note Parsing**: Advanced parsing of structured and unstructured clinical notes
- **Assessment/Plan Extraction**: Intelligent identification of the assessment/plan section
- **Condition & ICD Code Extraction**: Extraction of conditions and their associated ICD-10 codes
- **LangGraph Workflow**: Orchestrated extraction pipeline for consistent processing
- **Document Context Capture**: Extraction of patient demographics and document metadata
- **HCC Code Matching**: Initial HCC relevance determination through code matching

## Architecture

The service follows a multilayered architecture with the following components:

```
┌───────────────────┐       ┌───────────────────┐       ┌───────────────────┐
│                   │       │                   │       │                   │
│   Document Source │──────▶│  Extractor Core   │──────▶│   Storage Sink    │
│  (Files/Messages) │       │                   │       │ (Files/Messages)  │
│                   │       │                   │       │                   │
└───────────────────┘       └─────────┬─────────┘       └───────────────────┘
                                      │
                                      │
          ┌─────────────────┐         │         ┌───────────────────┐
          │                 │         │         │                   │
          │   LangGraph     │◀────────┴────────▶│   Vertex AI      │
          │   Pipeline      │                   │   Gemini Models  │
          │                 │                   │                   │
          └─────────────────┘                   └───────────────────┘
```

## Key Components

### 1. Document Parser

The Document Parser (`extractor/utils/document_parser.py`) extracts structured information:

- Patient demographics (name, age, gender, DOB)
- Document metadata (provider, date, chief complaint)
- Document structure and sectioning

### 2. Document Processor

The Document Processor (`extractor/extractor/processor.py`) orchestrates the extraction:

- Delegates to LangGraph or direct LLM extraction
- Manages condition extraction
- Converts raw extraction data to model objects
- Handles error conditions and fallbacks

### 3. LangGraph Pipeline

The LangGraph Pipeline (`extractor/graph/pipeline.py`) provides:

- Step-by-step extraction workflow
- State management between steps
- Error handling and recovery
- Extensibility for future enhancements

### 4. LLM Client

The LLM Client (`extractor/llm/client.py`) interfaces with Vertex AI:

- Crafts effective prompts for medical extraction
- Manages API communication with Vertex AI
- Processes and structures LLM responses
- Ensures consistent response format

### 5. HCC Code Manager

The HCC Code Manager (`extractor/utils/hcc_utils.py`) provides:

- Fast lookups of HCC-relevant codes
- Code normalization (with/without dots)
- Reference data for validation
- Performance optimization for large code sets

## Setup & Installation

### Prerequisites

- Python 3.12+
- Poetry for dependency management
- RabbitMQ for message queue
- Google Cloud Platform account with Vertex AI access
- Service account JSON key file with Vertex AI permissions
- HCC codes reference data in CSV format

### Using Poetry

```bash
# Install dependencies
cd services/extractor
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
RABBITMQ_QUEUE=extractor-events

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

Process all documents in the input directory:

```bash
python -m main --mode batch
```

### Consumer Mode

Listen for messages on RabbitMQ:

```bash
python -m main --mode consumer
```

### Both Modes

First process local files, then start listening for messages:

```bash
python -m main --mode both
```

### Single File Mode

Process a single file:

```bash
python -m main --mode file --file path/to/progress_note.txt
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
  -e RABBITMQ_HOST=rabbitmq \
  -e RABBITMQ_PORT=5672 \
  -e RABBITMQ_DEFAULT_USER=hccuser \
  -e RABBITMQ_DEFAULT_PASS=hccpass \
  -e RABBITMQ_USER=hccuser \
  -e RABBITMQ_PASSWORD=hccpass \
  -e RABBITMQ_VHOST=/ \
  -e RABBITMQ_QUEUE=extractor-events \
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
  -e USE_LANGGRAPH=1 \
  hcc-extractor-service
```

## Message Flow

1. **Document Uploaded**: The API Gateway or Storage Watcher publishes a `document.uploaded` message to RabbitMQ
2. **Message Consumption**: The Extractor service consumes the message and retrieves the document
3. **Extraction Process**: The document is processed by the extraction pipeline
4. **Result Publishing**: Extraction results are saved and a message is published for the Analyzer service

## Extraction Process

The extraction follows these steps:

1. **Document Parsing**: Initial metadata and structure extraction
2. **Assessment/Plan Identification**: Locating the section with conditions
3. **LLM Processing**: Using Vertex AI Gemini to extract conditions and codes
4. **HCC Code Lookup**: Cross-referencing extracted codes with HCC reference
5. **Result Formatting**: Creating structured extraction results

## Testing

The extractor service includes comprehensive unit tests:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=extractor

# Run specific test module
pytest tests/test_extractor.py
```

### Key Test Areas

The test suite covers:

- Document parsing functionality
- Extraction pipeline flow
- LLM client integration
- HCC code management
- Message handling

## Example Output

A typical extraction result looks like:

```json
{
  "document_id": "doc-progress_note_123",
  "conditions": [
    {
      "id": "cond-1",
      "name": "Type 2 diabetes mellitus",
      "icd_code": "E11.9",
      "icd_description": "Type 2 diabetes mellitus without complications",
      "details": "Stable\nContinue Metformin 1000mg twice daily",
      "confidence": 0.95,
      "metadata": {
        "status": "Stable",
        "extraction_method": "langgraph_llm",
        "icd_code_no_dot": "E119",
        "is_hcc_relevant": true
      }
    },
    {
      "id": "cond-2",
      "name": "Essential hypertension",
      "icd_code": "I10",
      "icd_description": "Essential (primary) hypertension",
      "details": "Improving with medication\nContinue lisinopril 20mg daily",
      "confidence": 0.92,
      "metadata": {
        "status": "Improving",
        "extraction_method": "langgraph_llm",
        "icd_code_no_dot": "I10",
        "is_hcc_relevant": true
      }
    }
  ],
  "metadata": {
    "source": "progress_note_123.txt",
    "total_conditions": 2,
    "hcc_relevant_count": 2,
    "extraction_method": "langgraph_llm"
  }
}
```

## Troubleshooting

### Common Issues

1. **LLM Extraction Issues**:
   - Verify Google Cloud credentials are correctly configured
   - Check if Vertex AI API is enabled in your project
   - Validate that the service account has proper permissions

2. **RabbitMQ Connection**:
   - Ensure RabbitMQ is running and credentials are correct
   - Verify the virtual host is properly URL-encoded if needed

3. **Document Parsing Issues**:
   - Check if the document format is supported
   - Ensure the Assessment/Plan section is present and follows standard format
   - Verify document encoding (UTF-8 recommended)

4. **Memory Usage**:
   - For large documents or batch processing, monitor memory usage
   - Consider adjusting Python's garbage collection settings for long-running processes

## Development

### Project Structure

```
extractor/
├── __init__.py
├── main.py                # Entry point
├── message_consumer.py    # RabbitMQ consumer
├── extractor/             # Core extraction components
│   ├── __init__.py
│   └── processor.py       # Document processor
├── graph/                 # LangGraph components
│   ├── __init__.py
│   ├── nodes.py           # Pipeline nodes
│   ├── pipeline.py        # Workflow definition
│   └── state.py           # State management
├── llm/                   # LLM integration
│   ├── __init__.py
│   ├── client.py          # Vertex AI client
│   └── prompts.py         # Prompt templates
├── models/                # Data models
│   ├── __init__.py
│   └── document.py        # Document models
├── storage/               # Storage operations
│   ├── __init__.py
│   ├── local.py           # Local storage
│   └── cloud.py           # Cloud storage
├── utils/                 # Utilities
│   ├── __init__.py
│   ├── document_parser.py # Document parsing
│   └── hcc_utils.py       # HCC code utilities
└── tests/                 # Test suite
    ├── __init__.py
    └── test_extractor.py  # Extractor tests
```