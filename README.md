# HCC Extractor

A sophisticated AI pipeline that extracts medical conditions and HCC-relevant codes from clinical progress notes using LangGraph and Vertex AI Gemini 1.5 Flash.

## Overview

This system streamlines the process of reviewing clinical progress notes to extract HCC-relevant conditions, ensuring proper compliant documentation and reducing the risk of missed reimbursements or compliance issues.

## Features

- Automatic extraction of medical conditions and their associated codes from clinical progress notes
- Determination of HCC-relevance using reference data
- Modular architecture with separation of concerns
- Built with Vertex AI Gemini 1.5 Flash and LangGraph for optimal performance
- Containerized deployment for easy installation and scaling
- Event-driven architecture with RabbitMQ for reliable message passing
- Storage watching capabilities for local, S3, and GCS file systems

## Architecture

The system follows a microservices architecture with the following components:

- **API Gateway**: Entry point for HTTP requests, handles authentication and routing
- **Extractor Service**: Extracts medical conditions from clinical notes
- **Analyzer Service**: Determines HCC relevance of conditions using Vertex AI and LangGraph
- **Validator Service**: Validates conditions against business rules
- **Storage Watcher Service**: Monitors storage systems for new files and triggers processing
- **RabbitMQ**: Message broker for event-driven communication between services

## Prerequisites

- Python 3.10+
- Docker and Docker Compose
- Google Cloud Platform account with Vertex AI access
- Service account JSON key file with Vertex AI permissions

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/hcc-extractor.git
cd hcc-extractor
```

### 2. Set up environment variables

Copy the example environment file and update it with your GCP credentials:

```bash
cp .env.example .env
```

Edit the `.env` file to set your Google Cloud project ID and the path to your service account key file.

### 3. Start the services using Docker Compose

```bash
docker-compose up -d
```

This will start all the required services including:
- RabbitMQ message broker
- API Gateway
- Extractor Service
- Analyzer Service
- Validator Service
- Storage Watcher Service
- LangGraph development web app

### 4. Run the LangGraph development web app

The LangGraph development web app allows you to visualize and debug the extraction and analysis workflows. It's automatically started as part of the Docker Compose setup and can be accessed at:

```
http://localhost:8001
```

Alternatively, you can start it manually with:

```bash
langgraph dev
```

## Usage

### Processing files through API

You can submit clinical documents for processing through the API Gateway:

```bash
curl -X POST -F "file=@/path/to/progress_note.txt" http://localhost:8000/api/v1/documents
```

### Automated processing with Storage Watcher

The Storage Watcher service automatically monitors the configured storage location for new files and triggers processing without manual intervention.

1. Place clinical progress notes in the watched directory (default: `./data`)
2. The Storage Watcher will detect new files and publish events to RabbitMQ
3. The Extractor service will process the files and extract conditions
4. The Analyzer service will determine HCC relevance
5. The Validator service will validate the results
6. Results will be available in the output directory (default: `./output`)

### Configuring Storage Watcher

The Storage Watcher can be configured to monitor different storage systems:

#### Local Filesystem

```
STORAGE_TYPE=local
WATCH_PATH=/path/to/directory
```

#### Amazon S3

```
STORAGE_TYPE=s3
WATCH_PATH=s3://bucket-name/prefix
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
```

#### Google Cloud Storage

```
STORAGE_TYPE=gcs
WATCH_PATH=gs://bucket-name/prefix
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

## Project Structure

```
hcc-extractor/
├── docker-compose.yml              # Defines all services
├── .env.example                    # Template for environment variables
├── README.md                       # Documentation
├── services/
│   ├── api-gateway/                # API Gateway service
│   ├── extractor/                  # Extraction service
│   ├── analyzer/                   # Analysis service with LangGraph
│   ├── validator/                  # Validation service
│   └── storage-watcher/            # Storage watching service
├── traefik/                        # Traefik configuration
└── tests/                          # Tests
```
