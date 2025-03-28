# HCC Extractor

![Python: 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)
![Framework: LangGraph](https://img.shields.io/badge/Framework-LangGraph-orange.svg)
![AI: Vertex AI Gemini](https://img.shields.io/badge/AI-Vertex_AI_Gemini-green.svg)
![Status: Production Ready](https://img.shields.io/badge/Status-Production_Ready-green.svg)

## Overview

HCC Extractor is a sophisticated AI pipeline that revolutionizes the process of reviewing clinical progress notes for HCC (Hierarchical Condition Categories) documentation. By leveraging cutting-edge AI technologies including Vertex AI Gemini 1.5 Flash, LangGraph, and advanced NLP techniques, the system automates the extraction, analysis, and validation of HCC-relevant conditions, dramatically reducing the time healthcare professionals spend on compliance documentation.

## Key Features

- **Automated Condition Extraction**: Parse clinical progress notes to extract medical conditions and their associated ICD-10 codes
- **HCC Relevance Determination**: Intelligently identify which conditions are HCC-relevant using both rule-based and LLM approaches
- **Compliance Validation**: Ensure all identified conditions meet documentation requirements for HCC submission
- **Microservices Architecture**: Modular, scalable design with distinct services for extraction, analysis, and validation
- **Event-Driven Processing**: RabbitMQ-based message queue for reliable asynchronous processing
- **Multi-Storage Support**: Compatible with local, S3, and GCS storage backends
- **RESTful API**: Comprehensive API for document management and processing
- **Containerized Deployment**: Docker-based deployment for consistent environments and easy scaling

## Architecture

The system follows a microservices architecture with the following components:

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│                         External Clients                            │
│                        ┌────────────────────────┐                   │
│                        │   API HTTP Direct      │                   │
│                        └────────────┬───────────┘                   │
│                                     │                               │
└─────────────────────────────────────┼───────────────────────────────┘
                                      │
                                      │
                                      ▼
┌─────────┼───────────────────────────────────────────────────────────┐
│         │                                                           │
│         │                      TRAEFIK                              │
│         │                 (Proxy/Load Balancer)                     │
│         │                                                           │
└─────────┼───────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────────────────┐
│                                                                    │
│                          API GATEWAY                               │
│ ┌────────────────┐ ┌────────────┐ ┌────────────┐ ┌───────────────┐ │
│ │  Authentication│ │Rate Limiter│ │  Logging   │ │API Versioning │ │
│ └────────┬───────┘ └─────┬──────┘ └─────┬──────┘ └───────┬───────┘ │
│          │               │              │                │         │
└──────────┼───────────────┼──────────────┼────────────────┼─────────┘
           │               │              │                │
           │               │              │                │
           ▼               ▼              ▼                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│                         RabbitMQ                                    │
│                      (Message Broker)                               │
│                                                                     │
└───────┬─────────────────┬──────────────────┬────────────────────────┘
        │                 │                  │
        │                 │                  │
        ▼                 ▼                  ▼
┌────────────┐    ┌─────────────┐    ┌────────────────┐     ┌───────────────┐
│            │    │             │    │                │     │               │
│  Extractor │───▶│  Analyzer   │───▶│   Validator    │────▶│ Results Store │
│  Service   │    │  Service    │    │   Service      │     │               │
│            │    │ (LangGraph) │    │                │     │               │
└────────────┘    └─────────────┘    └────────────────┘     └───────────────┘
        │                 │                  │                      │
        │                 │                  │                      │
        │                 ▼                  │                      │
        │         ┌─────────────────┐        │                      │
        │         │                 │        │                      │
        │         │   Vertex AI    │        │                      │
        │         │  (Gemini 1.5)  │        │                      │
        │         │                 │        │                      │
        │         └─────────────────┘        │                      │
        │                                    │                      │
        │                                    │                      │
        ▼                                    ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│                           PostgreSQL                                │
│                         (Database)                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Core Services

### 1. API Gateway Service

The API Gateway serves as the unified entry point to the HCC Extractor system, providing:

- User authentication and authorization
- Document management API
- Webhook management for event notifications
- Rate limiting and metrics collection
- Comprehensive logging and monitoring

### 2. Extractor Service

The Extractor Service processes clinical progress notes to identify and extract medical conditions:

- Clinical document parsing and sectioning
- Assessment/Plan section identification
- Condition and ICD code extraction
- Patient demographics and metadata extraction
- LangGraph-orchestrated extraction workflow

### 3. Analyzer Service

The Analyzer Service evaluates each extracted condition for HCC relevance:

- Rule-based initial HCC matching
- LLM-based enrichment for complex determinations
- Confidence scoring and reasoning for each determination
- Multi-stage analysis pipeline with LangGraph
- Comprehensive metrics and confidence assessment

### 4. Validator Service

The Validator Service ensures that identified HCC conditions meet compliance requirements:

- Flexible rules engine for business rule application
- ICD-10 code validation
- Documentation compliance verification
- Confidence threshold enforcement
- Detailed validation reporting

## Setup & Installation

### Prerequisites

- Python 3.12+
- Docker and Docker Compose
- Google Cloud Platform account with Vertex AI access
- Service account JSON key file with Vertex AI permissions

### Environment Setup

1. Clone the repository:

```bash
git clone https://github.com/yourusername/hcc-extractor.git
cd hcc-extractor
```

### Using Docker Compose

The easiest way to run the entire system is using Docker Compose:

```bash
docker-compose up -d
```

This will start all the required services:
- RabbitMQ message broker
- PostgreSQL database
- Traefik reverse proxy
- API Gateway
- Extractor Service
- Analyzer Service
- Validator Service
- Storage Watcher Service

### LangGraph Development Web App

The LangGraph development web app allows you to visualize and debug the extraction and analysis workflows:

```bash
docker-compose up langgraph-dev
```

Access the web app at: http://localhost:8001

## Usage

### Processing Files Through API

Submit clinical documents for processing through the API Gateway:

```bash
curl -X POST -F "file=@/path/to/progress_note.txt" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/documents
```

### Batch Processing

For processing multiple files at once:

```bash
curl -X POST -F "files[]=@/path/to/note1.txt" \
  -F "files[]=@/path/to/note2.txt" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/batch/upload
```

### Automated Processing with Storage Watcher

The Storage Watcher service automatically monitors configured storage locations:

1. Place clinical progress notes in the watched directory (default: `./data`)
2. Files are automatically detected and processed through the pipeline
3. Results are available in the output directory (default: `./output`)

## Configuring Storage Options

The system supports multiple storage backends:

### Local Filesystem

```
STORAGE_TYPE=local
WATCH_PATH=/path/to/directory
```

### Amazon S3

```
STORAGE_TYPE=s3
WATCH_PATH=s3://bucket-name/prefix
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
```

### Google Cloud Storage

```
STORAGE_TYPE=gcs
WATCH_PATH=gs://bucket-name/prefix
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

## Processing Workflow

1. **Document Ingestion**: Clinical notes are uploaded via API or detected by Storage Watcher
2. **Extraction**: The Extractor Service parses the document and identifies conditions
3. **Analysis**: The Analyzer Service determines HCC relevance for each condition
4. **Validation**: The Validator Service ensures compliance with documentation requirements
5. **Result Storage**: Results are stored and made available via API or in the output directory

## Development

### Project Structure

```
hcc-extractor/
├── docker-compose.yml              # Defines all services
├── .env.example                    # Template for environment variables
├── README.md                       # This file
├── services/
│   ├── api-gateway/                # API Gateway service
│   ├── extractor/                  # Extraction service
│   ├── analyzer/                   # Analysis service with LangGraph
│   ├── validator/                  # Validation service
│   └── storage-watcher/            # Storage watching service
├── traefik/                        # Traefik configuration
├── data/                           # Input data directory
│   └── HCC_relevant_codes.csv      # HCC reference data
├── output/                         # Output results directory
└── tests/                          # System tests
```

### Running Tests

Each service includes its own test suite:

```bash
# Run tests for a specific service
cd services/extractor
pytest

# Run with coverage
pytest --cov=extractor
```

## API Documentation

API documentation is available at:

```
http://localhost:8000/api/docs
```

## Troubleshooting

### Common Issues

1. **LLM Integration**:
   - Verify Google Cloud credentials are correctly configured
   - Check if Vertex AI API is enabled in your project
   - Validate that the service account has proper permissions

2. **RabbitMQ Connection**:
   - Ensure RabbitMQ is running and credentials are correct
   - Check queue and exchange declarations

3. **HCC Codes CSV**:
   - Confirm the HCC codes CSV file is available at the specified path
   - Verify the CSV has the expected columns: "ICD-10-CM Codes", "Description", and "Tags"

4. **Database Connection**:
   - Check PostgreSQL credentials and connection settings
   - Ensure database migrations have been applied

### Logging

Each service includes comprehensive logging. View logs with:

```bash
docker-compose logs -f api-gateway
docker-compose logs -f extractor
docker-compose logs -f analyzer
docker-compose logs -f validator
```

## Acknowledgments

- This project uses Vertex AI Gemini 2.0 Flash for NLP processing
- LangGraph framework for workflow orchestration
- Healthcare experts for domain knowledge and validation