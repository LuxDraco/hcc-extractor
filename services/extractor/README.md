# HCC Extractor

An AI-powered system to extract HCC-relevant medical conditions from clinical progress notes using LangGraph and Vertex AI Gemini.

## 📋 Overview

HCC Extractor is a Python-based solution that:

1. Processes clinical progress notes to extract medical conditions and their ICD-10 codes
2. Determines which conditions are HCC-relevant by cross-referencing with a provided CSV file
3. Returns structured results for further analysis or reporting

The system uses Vertex AI Gemini models through LangChain and orchestrates the extraction workflow using LangGraph, providing a reliable and maintainable solution for clinical document analysis.

## 🚀 Features

- **AI-Powered Extraction**: Uses Vertex AI Gemini models for accurate condition and code extraction
- **LangGraph Workflow**: Structured pipeline for processing clinical documents
- **ICD Code Handling**: Extracts and normalizes ICD-10 codes (with and without dots)
- **HCC Relevance Evaluation**: Identifies which conditions are HCC-relevant
- **Flexible Processing**: Works with single files, batches, or via a message queue
- **Error Handling**: Robust error handling and reporting
- **Containerized**: Docker support for easy deployment

## 📦 Installation

### Prerequisites

- Python 3.12+
- Poetry for dependency management
- Google Cloud service account with Vertex AI access
- Docker (optional)

### Using Poetry

```bash
# Clone the repository
git clone https://github.com/yourusername/hcc-extractor.git
cd hcc-extractor

# Install dependencies
poetry install

# Set environment variables
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
export VERTEX_AI_PROJECT_ID=your-project-id
export VERTEX_AI_LOCATION=us-central1
```

### Using Docker

```bash
# Build the Docker image
docker build -t hcc-extractor .

# Run the container
docker run -v /path/to/data:/app/data \
  -v /path/to/output:/app/output \
  -v /path/to/service-account.json:/app/credentials.json \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json \
  -e VERTEX_AI_PROJECT_ID=your-project-id \
  -e VERTEX_AI_LOCATION=us-central1 \
  hcc-extractor
```

## 🧑‍💻 Usage

### Processing Files

```bash
# Process all files in the data directory
python main.py --mode batch

# Process a single file
python main.py --mode file --file ./data/progress_note.txt

# Run the demo script
python run_extraction.py
```

### Using the LangGraph Development Web App

```bash
# Start the LangGraph development web app
langgraph dev
```

This will open a browser window with the LangGraph development interface, allowing you to visualize and debug the extraction workflow.

## 🏗️ Architecture

### Component Overview

- **DocumentProcessor**: Coordinates the extraction process
- **ExtractionPipeline**: LangGraph workflow for condition extraction
- **LangChainGeminiClient**: Interfaces with Vertex AI Gemini models
- **HCCCodeManager**: Manages HCC-relevant code lookup

### LangGraph Workflow

The extraction workflow consists of the following nodes:

1. **preprocess**: Extracts the Assessment/Plan section from the document
2. **extract_conditions**: Uses Gemini to extract conditions and codes
3. **load_hcc_codes**: Loads HCC-relevant codes from the CSV file
4. **determine_hcc_relevance**: Determines which conditions are HCC-relevant
5. **convert_to_model_objects**: Converts raw data to Condition objects
6. **create_result**: Creates the final extraction result

## 📄 Example

Input progress note:
```
Assessment / Plan

1. Gastroesophageal reflux disease -
   Stable
   Continue the antacids
   F/U in 3 months
   K21.9: Gastro-esophageal reflux disease without esophagitis

2. Hyperglycemia due to type 2 diabetes mellitus -
   Worsening
   Continue Metformin1000 mg BID and Glimepiride 8 mg
   E11.65: Type 2 diabetes mellitus with hyperglycemia
```

Output (simplified):
```json
{
  "document_id": "doc-sample_progress_note",
  "conditions": [
    {
      "id": "cond-1",
      "name": "Gastroesophageal reflux disease",
      "icd_code": "K21.9",
      "icd_description": "Gastro-esophageal reflux disease without esophagitis",
      "details": "Stable\nContinue the antacids\nF/U in 3 months",
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
      "details": "Worsening\nContinue Metformin1000 mg BID and Glimepiride 8 mg",
      "metadata": {
        "extraction_method": "langgraph_llm",
        "status": "Worsening",
        "icd_code_no_dot": "E1165",
        "is_hcc_relevant": true
      }
    }
  ],
  "metadata": {
    "source": "sample_progress_note.txt",
    "total_conditions": 2,
    "hcc_relevant_count": 1,
    "extraction_method": "langgraph_llm"
  }
}
```

## 📚 Project Structure

```
services/extractor/
├── app/
│   ├── __init__.py
│   ├── extractor/           # Core extraction logic
│   ├── graph/               # LangGraph components
│   ├── llm/                 # LLM integration
│   ├── models/              # Data models
│   ├── storage/             # Storage operations
│   ├── utils/               # Utilities
├── data/                    # Input data directory
├── output/                  # Output directory
├── main.py                  # Entry point
├── run_extraction.py        # Demo script
├── Dockerfile               # Docker build instructions
├── pyproject.toml           # Poetry configuration
└── README.md                # This file
```

## 🧪 Testing

```bash
# Run tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=extractor
```

## 🌱 Future Improvements

- Add support for more document types (PDF, scanned documents)
- Implement a web UI for document upload and results visualization
- Add batch processing optimizations for large datasets
