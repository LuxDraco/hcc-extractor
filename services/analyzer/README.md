# HCC Analyzer Service

![Python: 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)
![Testing: Pytest](https://img.shields.io/badge/Testing-Pytest-green.svg)
![Status: Production Ready](https://img.shields.io/badge/Status-Production_Ready-green.svg)

## Overview

The HCC Analyzer Service is a critical component of the HCC Extractor system, responsible for determining the Hierarchical Condition Category (HCC) relevance of medical conditions extracted from clinical progress notes. This service leverages Google's Vertex AI Gemini 1.5 Flash model and LangGraph to deliver accurate, consistent HCC relevance determinations.

## Core Functionality

- **Rule-Based HCC Matching**: Initial determination of HCC relevance based on ICD-10 code lookups
- **LLM-Based Enrichment**: Advanced analysis using Vertex AI Gemini models for edge cases and complex determinations
- **Multi-Stage Pipeline**: LangGraph-orchestrated workflow for consistent, reliable analysis
- **Comprehensive Confidence Scoring**: Confidence metrics based on multiple determination methods
- **Detailed Reasoning**: Explicit reasoning for each HCC determination
- **Event-Driven Processing**: Integration with message queues for efficient processing

## Architecture

The service follows a multi-layered architecture with the following components:

```
┌───────────────────┐       ┌───────────────────┐       ┌───────────────────┐
│                   │       │                   │       │                   │
│   Message Queue   │──────▶│   Analyzer Core   │──────▶│  Results Store    │
│    (RabbitMQ)     │       │                   │       │ (Files/Messages)  │
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
                   │                                     │
                   │                                     │
                   ▼                                     ▼
          ┌─────────────────┐                   ┌───────────────────┐
          │                 │                   │                   │
          │   HCC Code      │                   │    Database       │
          │   Repository    │                   │    Integration    │
          │                 │                   │                   │
          └─────────────────┘                   └───────────────────┘
```

## Key Components

### 1. LangGraph Pipeline

The LangGraph Pipeline (`analyzer/graph/pipeline.py`) orchestrates the analysis workflow:

- Multi-step processing with state management
- Hybrid rule-based and LLM analysis
- Explicit error handling and recovery
- Detailed metrics and diagnostics

### 2. LLM Client

The LLM Client (`analyzer/llm/client.py`) manages interactions with Vertex AI:

- Expert-crafted medical prompts for Gemini models
- Output parsing and validation
- JSON normalization and error handling
- Structured response processing

### 3. Graph Nodes

The Graph Nodes (`analyzer/graph/nodes.py`) implement each processing step:

- `load_hcc_codes`: Prepares HCC reference data
- `prepare_conditions`: Validates and processes input conditions
- `determine_hcc_relevance`: Rule-based HCC matching
- `enrichment_with_llm`: LLM-based analysis
- `finalize_analysis`: Result compilation and metrics

### 4. Database Integration

Database Integration (`analyzer/db/database_integration.py`) provides:

- Status tracking for analyzed documents
- Metrics and results persistence
- Error handling and retry logic
- Transaction management

### 5. Message Consumer

Message Consumer (`analyzer/message_consumer.py`) handles event-driven processing:

- RabbitMQ message consumption and production
- JSON serialization and parsing
- Error handling and message acknowledgment
- Service discovery and connection management

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
cd services/analyzer
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
RABBITMQ_QUEUE=analyzer-events

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

Process all extraction result files in the input directory:

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
  -e VERTEX_AI_PROJECT_ID=guacamayo-tech \
  -e VERTEX_AI_LOCATION=us-central1 \
  -e RABBITMQ_HOST=rabbitmq \
  -e RABBITMQ_PORT=5672 \
  -e RABBITMQ_DEFAULT_USER=hccuser \
  -e RABBITMQ_DEFAULT_PASS=hccpass \
  -e RABBITMQ_USER=hccuser \
  -e RABBITMQ_PASSWORD=hccpass \
  -e RABBITMQ_VHOST=/ \
  -e RABBITMQ_QUEUE=analyzer-events \
  -e POSTGRES_HOST=postgres \
  -e POSTGRES_PORT=5432 \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=hcc_extractor \
  -e INPUT_DIR=/app/data/pn \
  -e OUTPUT_DIR=/app/output \
  -e HCC_CODES_PATH=/app/data/HCC_relevant_codes.csv \
  hcc-analyzer-service
```

## LangGraph Visualization

You can visualize the analysis pipeline using the LangGraph development web app:

```bash
langgraph dev --host 0.0.0.0 --port 8001
```

This will provide an interactive visualization of the workflow nodes and state transitions at:

```
http://localhost:8001
```

## Message Flow

1. **Extraction Completed**: The Extractor service publishes an `extraction.completed` message to RabbitMQ
2. **Message Consumption**: The Analyzer service consumes the message and retrieves the extraction results
3. **Analysis Pipeline**: The extraction results are processed through the LangGraph pipeline
4. **HCC Relevance Determination**: Conditions are analyzed for HCC relevance using both rule-based and LLM approaches
5. **Result Publishing**: Analysis results are saved and a message is published for the next service (Validator)

## Analysis Process

The HCC relevance analysis follows these steps:

1. **Load HCC Codes**: Load and prepare reference HCC codes from CSV
2. **Prepare Conditions**: Validate input conditions and structure for analysis
3. **Rule-Based Analysis**: Initial determination of HCC relevance by direct code lookup
4. **LLM Enrichment**: Enhance determinations with Vertex AI Gemini analysis
5. **Result Finalization**: Calculate metrics, standardize output, and prepare final results

## Testing

The analyzer service includes comprehensive unit tests:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=analyzer

# Run specific test module
pytest tests/test_analyzer.py
```

### Key Test Areas

The test suite covers:

- LangGraph pipeline functionality
- LLM client integration
- Graph node functionality
- Database integration
- Message handling
- Error recovery and edge cases

## Example Output

A typical analysis result looks like:

```json
{
  "document_id": "788e5e9c-8d9d-4fc7-98eb-2553460a9e35",
  "conditions": [
    {
      "id": "cond-1",
      "name": "Gastroesophageal reflux disease",
      "icd_code": "K21.9",
      "icd_description": "Gastro-esophageal reflux disease without esophagitis",
      "details": "Continue the antacids, F/U in 3 months",
      "hcc_relevant": false,
      "hcc_code": null,
      "hcc_category": null,
      "confidence": 0.8,
      "reasoning": "No exact match with HCC-relevant codes in reference data",
      "metadata": {
        "extraction_method": "langgraph_llm",
        "status": "Stable",
        "icd_code_no_dot": "K219",
        "is_hcc_relevant": false
      }
    },
    {
      "id": "cond-2",
      "name": "Hyperglycemia due to type 2 diabetes mellitus",
      "icd_code": "E11.65",
      "icd_description": "Type 2 diabetes mellitus with hyperglycemia",
      "details": "Continue Metformin1000 mg BID and Glimepiride 8 mg. Recommend a low sugar and low carbohydrate diet. Fruits and vegetables are acceptable. Discussed 1/2 plate with non-starchy vegetables, 1/4 of plate with carbohydrates such as whole grain, 1/4 of plate with lean protein. Include healthy fats in your meal like: Olive oil, canola oil, avocado, and nuts",
      "hcc_relevant": true,
      "hcc_code": "E1165",
      "hcc_category": null,
      "confidence": 1.0,
      "reasoning": "Direct match with HCC-relevant code: E11.65",
      "metadata": {
        "extraction_method": "langgraph_llm",
        "status": "Worsening",
        "icd_code_no_dot": "E1165",
        "is_hcc_relevant": true
      }
    },
    {
      "id": "cond-3",
      "name": "Chronic obstructive lung disease",
      "icd_code": "J44.9",
      "icd_description": "Chronic obstructive pulmonary disease, unspecified",
      "details": "SPO2-98% today. Maintain current inhaler regimen: Tiotropium and Fluticasone/Salmeterol. Counseled for smoking cessation today",
      "hcc_relevant": true,
      "hcc_code": "J449",
      "hcc_category": null,
      "confidence": 1.0,
      "reasoning": "Direct match with HCC-relevant code: J44.9",
      "metadata": {
        "extraction_method": "langgraph_llm",
        "status": "Unchanged",
        "icd_code_no_dot": "J449",
        "is_hcc_relevant": true
      }
    }
  ],
  "metadata": {
    "document_id": "788e5e9c-8d9d-4fc7-98eb-2553460a9e35",
    "total_conditions": 7,
    "hcc_relevant_count": 5,
    "high_confidence_count": 5,
    "confidence_avg": 0.9428571428571428,
    "error_count": 0
  },
  "errors": []
}
```

## Troubleshooting

### Common Issues

1. **LLM Integration**:
   - Verify Google Cloud credentials are correctly configured
   - Check if Vertex AI API is enabled in your project
   - Validate that the service account has proper permissions

2. **RabbitMQ Connection**:
   - Ensure RabbitMQ is running and credentials are correct
   - Verify the virtual host is properly URL-encoded if needed
   - Check queue and exchange declarations

3. **HCC Codes CSV**:
   - Confirm the HCC codes CSV file is available at the specified path
   - Check that the CSV has the expected columns: "ICD-10-CM Codes", "Description", and "Tags"

4. **Memory Usage**:
   - For large datasets, monitor memory usage as loading many HCC codes can be memory-intensive
   - Consider batching or pagination for large document processing

## Development

### Adding New Analysis Capabilities

The analyzer architecture is designed for extensibility:

1. **Add New Graph Nodes**:
   - Create new analysis functions in `analyzer/graph/nodes.py`
   - Register them in the pipeline with appropriate edges

2. **Enhance LLM Prompts**:
   - Modify prompts in the LLM client for specialized analysis
   - Add domain-specific context and examples

3. **Add Custom Metrics**:
   - Extend the metadata in `finalize_analysis` node
   - Add specialized confidence or quality metrics

### Project Structure

```
analyzer/
├── __init__.py
├── main.py                # Entry point
├── message_consumer.py    # RabbitMQ consumer
├── graph/                 # LangGraph components
│   ├── __init__.py
│   ├── nodes.py           # Pipeline nodes
│   ├── pipeline.py        # Workflow definition
│   └── state.py           # State definition
├── llm/                   # LLM integration
│   ├── __init__.py
│   ├── client.py          # Vertex AI client
│   ├── decorators.py      # Function decorators
│   └── prompts.py         # Prompt templates
├── models/                # Data models
│   ├── __init__.py
│   ├── condition.py       # Condition models
│   └── message.py         # Message models
├── storage/               # Storage operations
│   ├── __init__.py
│   └── local.py           # Local storage manager
├── db/                    # Database integration
│   ├── __init__.py
│   ├── base.py            # Base model
│   ├── models/            # Database models
│   └── database_integration.py # DB update utilities
└── tests/                 # Test suite
    ├── __init__.py
    └── test_analyzer.py   # Analyzer tests
```