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