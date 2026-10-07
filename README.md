# Bulk Certificate Generator API

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/tests-28%20passed-brightgreen.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-96%25-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A high-performance, resilient backend API built with **Python 3**, **FastAPI**, **SQLAlchemy**, and **ReportLab** that accepts bulk certificate generation requests for event participants, generates professional vector PDF certificates based on a predefined template, tracks real-time generation progress, isolates individual recipient failures, and provides individual and bulk ZIP retrieval.

---

## Table of Contents
- [System Architecture](#system-architecture)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [Project Layout](#project-layout)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation (uv or pip)](#installation-uv-or-pip)
  - [Running the API](#running-the-api)
  - [Running with Docker & Docker Compose](#running-with-docker--docker-compose)
- [Running Tests & Coverage](#running-tests--coverage)
- [Running the Interactive Demo](#running-the-interactive-demo)
- [API Reference & Usage](#api-reference--usage)
  - [1. Submit Certificate Generation Job](#1-submit-certificate-generation-job)
  - [2. Poll Job Status & Progress](#2-poll-job-status--progress)
  - [3. List Job Certificates with Filtering](#3-list-job-certificates-with-filtering)
  - [4. Download Bulk Certificates ZIP](#4-download-bulk-certificates-zip)
  - [5. Download Individual Certificate PDF](#5-download-individual-certificate-pdf)
  - [6. Public Certificate Verification](#6-public-certificate-verification)
  - [7. Health Check](#7-health-check)
- [Design Decisions & Trade-offs](#design-decisions--trade-offs)
  - [1. Asynchronous Background Processing](#1-asynchronous-background-processing)
  - [2. Granular Failure Isolation](#2-granular-failure-isolation)
  - [3. Certificate Rendering Engine](#3-certificate-rendering-engine)
  - [4. Storage & Retrieval Strategy](#4-storage--retrieval-strategy)
  - [5. Database Schema & State Machine](#5-database-schema--state-machine)
- [Production Scaling Considerations](#production-scaling-considerations)

---

## System Architecture

```mermaid
flowchart TD
    Client["Client / Web Application"] -->|1. POST /api/v1/jobs (Bulk Recipients)| API["FastAPI Endpoint"]
    API -->|Validate Payload| Pydantic["Pydantic v2 Validation"]
    API -->|2. Create Job & Certs (PENDING)| DB[("Relational Database\nSQLite / PostgreSQL")]
    API -->|3. Return 202 Accepted + job_id| Client
    API -->|4. Dispatch Background Task| Worker["Background Worker / Task Pool"]

    Worker -->|Update Status: PROCESSING| DB
    Worker -->|Iterate Each Recipient| Loop{"Process Recipient"}
    
    Loop -->|Success| GenPDF["ReportLab Generator\nRender Vector PDF"]
    GenPDF -->|Save PDF| Storage["Local Storage / S3\nstorage/certificates/{job_id}/"]
    Storage -->|Update Cert: COMPLETED| DB
    
    Loop -->|Failure / Invalid| ErrorHandler["Isolate Error\nRecord Diagnostic"]
    ErrorHandler -->|Update Cert: FAILED| DB
    
    Worker -->|Finalize Job: COMPLETED / PARTIAL| Archiver["StorageService\nBundle Success ZIP"]
    Archiver --> DB

    Client -->|5. GET /api/v1/jobs/{id}| API
    Client -->|6. GET /api/v1/jobs/{id}/download| API
    Client -->|7. GET /api/v1/verify/{code}| API
```

---

## Key Features

1. **Bulk Request Handling**: Submit hundreds or thousands of recipients in a single API call without HTTP connection timeouts.
2. **Immediate 202 Accepted Response**: Generation runs asynchronously in the background while clients receive a tracking URL immediately.
3. **Strict Input Validation**: Validates recipient email structures, names, custom IDs, and payload metadata using Pydantic v2 before processing begins.
4. **Resilient Failure Isolation**: A failure in generating one recipient's certificate (e.g. malformed data, storage constraint) **never stops** the rest of the batch.
5. **Real-time Status & Metrics**: Tracks `total_count`, `processed_count`, `success_count`, `failed_count`, and calculated `progress_percentage`.
6. **Predefined Professional Certificate Template**: High-resolution vector PDF certificate with ornate borders, gold seal, dynamic font scaling for long names, wrapped text, and signature line.
7. **Multiple Retrieval Modes**:
   - Download individual certificates as standalone PDFs.
   - Bulk-download all successfully generated certificates as a single compressed `.zip` archive.
8. **Public Verification System**: Verification endpoint (`/api/v1/verify/{code}`) enabling anyone to verify authenticity using the certificate's unique verification code.
9. **Interactive Swagger/OpenAPI Documentation**: Automatically generated interactive documentation at `/docs` and `/redoc`.

---

## Technology Stack

- **Language**: Python 3.11+ (tested on Python 3.12 & 3.14)
- **Web Framework**: FastAPI (modern, high-performance async framework)
- **Server**: Uvicorn (ASGI server with uvloop support)
- **Data Validation**: Pydantic v2 (with `email-validator`)
- **Database & ORM**: SQLAlchemy 2.0 (SQLite default, PostgreSQL ready via `DATABASE_URL`)
- **PDF Generation**: ReportLab 5.0 (pure Python, vector graphics, standalone)
- **Testing**: Pytest, Pytest-Cov, HTTPX
- **Containerization**: Docker & Docker Compose

---

## Project Layout

```
random_assignment/
├── app/
│   ├── __init__.py
│   ├── config.py             # Environment configuration & settings
│   ├── database.py           # Database engine, sessionmaker & init_db
│   ├── models.py             # SQLAlchemy models (Job, Certificate)
│   ├── schemas.py            # Pydantic v2 schemas for requests & responses
│   ├── main.py               # FastAPI application setup & lifecycle
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py         # REST API endpoints (Jobs, Certs, Verification, Health)
│   └── services/
│       ├── __init__.py
│       ├── generator.py      # Predefined ReportLab PDF template generator
│       ├── storage.py        # Path management, sanitization, and ZIP bundling
│       └── job_service.py    # Job coordination, worker execution & failure isolation
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Isolated test database and temporary storage fixtures
│   ├── test_api.py           # Full API integration and endpoint test suite
│   ├── test_generator.py     # PDF generation and layout verification tests
│   ├── test_job_service.py   # Job execution and failure isolation tests
│   └── test_storage.py       # Filename sanitization and ZIP archive tests
├── storage/                  # Default storage directory for generated files (gitignored)
│   ├── certificates/         # Organized by {job_id}/{cert_id}_{name}.pdf
│   └── zips/                 # Bundled job archives
├── demo.py                   # Automated end-to-end demonstration script
├── Dockerfile                # Production container specification
├── docker-compose.yml        # Docker Compose configuration
├── pyproject.toml            # Project dependencies & build config
├── requirements.txt          # Standard pip requirements
└── README.md                 # Full documentation
```

---

## Getting Started

### Prerequisites
- Python 3.11 or newer
- `pip` or `uv` (recommended for ultra-fast package management)

### Installation (uv or pip)

#### Using `uv` (Fastest):
```bash
# 1. Create virtual environment
uv venv

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Install dependencies
uv pip install -r requirements.txt
```

#### Using standard `pip`:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

### Running the API

Start the development server with hot-reload enabled:

```bash
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Once running:
- **API Base URL**: `http://127.0.0.1:8000`
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`
- **ReDoc Documentation**: `http://127.0.0.1:8000/redoc`

---

### Running with Docker & Docker Compose

#### With Docker Compose:
```bash
docker compose up --build
```

#### With standalone Docker:
```bash
docker build -t bulk-certificate-generator .
docker run -p 8000:8000 bulk-certificate-generator
```

---

## Running Tests & Coverage

The test suite covers:
- Job submission & asynchronous processing
- Input validation (empty lists, invalid email formats, blank strings)
- ReportLab PDF generation (font scaling, paragraph wrapping, header verification)
- Job progress tracking and status polling
- Individual certificate failure isolation
- Single certificate PDF download & Bulk ZIP archive download
- Public certificate verification
- Edge cases (non-existent jobs, downloading uncompleted certificates)

Execute the test suite with coverage report:

```bash
source .venv/bin/activate
pytest -v --cov=app --cov-report=term-missing
```

### Test Results
```
======================== 28 passed in 0.55s ========================
TOTAL: 96% coverage
```

---

## Running the Interactive Demo

We have provided an automated script `demo.py` that demonstrates the complete end-to-end lifecycle:

1. Starts against the running server.
2. Submits a job with 5 recipients (including a simulated failure to illustrate failure isolation).
3. Polls progress in real-time.
4. Downloads an individual recipient certificate PDF.
5. Downloads the bulk ZIP bundle.
6. Queries the public verification endpoint.

To run:
```bash
# Make sure the server is running in one terminal
uvicorn app.main:app --port 8000

# In another terminal:
python3 demo.py
```

---

## API Reference & Usage

### 1. Submit Certificate Generation Job

Creates a new generation job and immediately returns `202 Accepted`.

- **Endpoint**: `POST /api/v1/jobs`
- **Status Code**: `202 Accepted`

#### Example Request:
```bash
curl -X POST "http://localhost:8000/api/v1/jobs" \
     -H "Content-Type: application/json" \
     -d '{
       "title": "Full-Stack Distributed Systems Engineering",
       "description": "For demonstrating exceptional proficiency in backend systems, asynchronous pipelines, and high-throughput APIs.",
       "issuer_name": "Dr. Grace Hopper",
       "issuer_title": "Dean of Computer Science",
       "issue_date": "2026-10-08",
       "recipients": [
         {
           "name": "Alice Johnson",
           "email": "alice.johnson@example.com",
           "custom_id": "STUDENT-101"
         },
         {
           "name": "Bob Smith",
           "email": "bob.smith@example.com",
           "custom_id": "STUDENT-102"
         }
       ]
     }'
```

#### Example Response:
```json
{
  "job_id": "a0ce9308-cc05-40f1-98cc-3756b77022d0",
  "status": "PENDING",
  "message": "Certificate generation job accepted. Generation is processing in the background.",
  "total_recipients": 2,
  "status_url": "http://localhost:8000/api/v1/jobs/a0ce9308-cc05-40f1-98cc-3756b77022d0",
  "created_at": "2026-10-08T05:22:00.123456Z"
}
```

---

### 2. Poll Job Status & Progress

Check the current status and metrics of a job.

- **Endpoint**: `GET /api/v1/jobs/{job_id}`
- **Query Parameters**:
  - `include_certificates` (boolean, optional, default: `false`): Include the array of individual certificate items.

#### Example Request:
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/a0ce9308-cc05-40f1-98cc-3756b77022d0?include_certificates=true"
```

#### Example Response:
```json
{
  "id": "a0ce9308-cc05-40f1-98cc-3756b77022d0",
  "title": "Full-Stack Distributed Systems Engineering",
  "description": "For demonstrating exceptional proficiency in backend systems, asynchronous pipelines, and high-throughput APIs.",
  "issuer_name": "Dr. Grace Hopper",
  "issuer_title": "Dean of Computer Science",
  "issue_date": "October 08, 2026",
  "status": "COMPLETED",
  "total_count": 2,
  "processed_count": 2,
  "success_count": 2,
  "failed_count": 0,
  "progress_percentage": 100.0,
  "created_at": "2026-10-08T05:22:00.123456Z",
  "updated_at": "2026-10-08T05:22:01.456789Z",
  "completed_at": "2026-10-08T05:22:01.456789Z",
  "certificates_download_url": "http://localhost:8000/api/v1/jobs/a0ce9308-cc05-40f1-98cc-3756b77022d0/download",
  "certificates": [
    {
      "id": "096fbf9e-c21e-4fa1-af15-fd94b1ebdd20",
      "job_id": "a0ce9308-cc05-40f1-98cc-3756b77022d0",
      "recipient_name": "Alice Johnson",
      "recipient_email": "alice.johnson@example.com",
      "custom_id": "STUDENT-101",
      "certificate_code": "CERT-50DFB700",
      "status": "COMPLETED",
      "file_size_bytes": 3066,
      "error_message": null,
      "download_url": "http://localhost:8000/api/v1/certificates/096fbf9e-c21e-4fa1-af15-fd94b1ebdd20/download",
      "created_at": "2026-10-08T05:22:00.123456Z",
      "updated_at": "2026-10-08T05:22:00.789123Z"
    }
  ]
}
```

---

### 3. List Job Certificates with Filtering

Retrieve paginated certificate records for a specific job, with optional status filter.

- **Endpoint**: `GET /api/v1/jobs/{job_id}/certificates`
- **Query Parameters**:
  - `status`: Filter by `COMPLETED`, `FAILED`, or `PROCESSING`.
  - `offset`: Pagination offset (default: 0).
  - `limit`: Pagination limit (default: 100).

#### Example Request:
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/a0ce9308-cc05-40f1-98cc-3756b77022d0/certificates?status=FAILED"
```

---

### 4. Download Bulk Certificates ZIP

Download all successfully generated certificates bundled as a ZIP archive.

- **Endpoint**: `GET /api/v1/jobs/{job_id}/download`

```bash
curl -O -J "http://localhost:8000/api/v1/jobs/a0ce9308-cc05-40f1-98cc-3756b77022d0/download"
```

---

### 5. Download Individual Certificate PDF

Download a single certificate PDF.

- **Endpoint**: `GET /api/v1/certificates/{certificate_id}/download`

```bash
curl -O -J "http://localhost:8000/api/v1/certificates/096fbf9e-c21e-4fa1-af15-fd94b1ebdd20/download"
```

---

### 6. Public Certificate Verification

Verify authenticity using the unique code printed on the certificate.

- **Endpoint**: `GET /api/v1/verify/{certificate_code}`

#### Example Request:
```bash
curl -X GET "http://localhost:8000/api/v1/verify/CERT-50DFB700"
```

#### Example Response:
```json
{
  "certificate_code": "CERT-50DFB700",
  "recipient_name": "Alice Johnson",
  "title": "Full-Stack Distributed Systems Engineering",
  "description": "For demonstrating exceptional proficiency in backend systems, asynchronous pipelines, and high-throughput APIs.",
  "issuer_name": "Dr. Grace Hopper",
  "issuer_title": "Dean of Computer Science",
  "issue_date": "October 08, 2026",
  "status": "COMPLETED",
  "is_valid": true,
  "download_url": "http://localhost:8000/api/v1/certificates/096fbf9e-c21e-4fa1-af15-fd94b1ebdd20/download"
}
```

---

### 7. Health Check

- **Endpoint**: `GET /api/v1/health`

```bash
curl -X GET "http://localhost:8000/api/v1/health"
```

---

## Design Decisions & Trade-offs

### 1. Asynchronous Background Processing
- **Decision**: Bulk generation requests return `202 Accepted` immediately, and generation executes in background tasks.
- **Rationale**: Bulk requests can contain hundreds or thousands of recipients. Synchronous execution would lead to HTTP gateway timeouts (typically 30–60s on proxies like Nginx, Cloudflare, or AWS ALB) and tie up HTTP server worker threads.
- **Implementation**: We leverage FastAPI's native background task orchestration. Each background job acquires an isolated database session and commits incremental progress per certificate, allowing polling clients to observe live progress bars.

### 2. Granular Failure Isolation
- **Decision**: Isolated `try/except` block wrapping each certificate generation within a job loop.
- **Rationale**: Real-world bulk jobs often encounter corrupted inputs, unicode rendering edge cases, or disk glitches on specific entries. A single recipient failure must never abort generation for other legitimate recipients.
- **State Representation**:
  - If all succeed: Job status is `COMPLETED`.
  - If some fail and some succeed: Job status is `PARTIALLY_COMPLETED`. Failed items record the specific `error_message`, and successful items are bundled into the ZIP.
  - If all fail: Job status is `FAILED`.

### 3. Certificate Rendering Engine
- **Decision**: Predefined vector PDF template implemented using **ReportLab**.
- **Rationale**:
  - ReportLab is pure Python, produces lightweight vector PDFs (typically 3KB per certificate vs. 500KB+ for image-based generators), and requires no external binary headless browsers (like Chrome/Puppeteer/Weasyprint), keeping Docker containers tiny and deployment trivial.
  - Vector PDFs print with crisp resolution at any scale (300+ DPI).
  - Includes dynamic font scaling (reducing font size for names > 25 characters to prevent overlap), paragraph wrapping for descriptions, and vector seal/border drawings.

### 4. Storage & Retrieval Strategy
- **Decision**: Storage organized in partitioned directories: `storage/certificates/{job_id}/{cert_id}_{sanitized_name}.pdf`.
- **Rationale**:
  - Partitioning by `job_id` prevents directory entry limits when processing millions of certificates.
  - Filenames are sanitized against directory traversal and special character exploits.
  - ZIP archives are generated upon job completion and can be downloaded in one click or streamed on demand.

### 5. Database Schema & State Machine
- **Relational Tables**:
  - `jobs`: Stores batch-level metadata, status, issuer info, timestamps, and aggregated counters (`total_count`, `processed_count`, `success_count`, `failed_count`).
  - `certificates`: Stores recipient metadata, unique `certificate_code` (indexed for instant public verification), execution status, file path, and error diagnostics.
- Cascading foreign key deletes ensure removing a job automatically cleans up associated certificate records.

---

## Production Scaling Considerations

For enterprise scale (100,000+ recipients per job):

1. **Distributed Task Queue**:
   - Swap FastAPI in-process background tasks for **Celery**, **ARQ**, or **Temporal** backed by Redis/RabbitMQ.
   - Partition batches into chunks of 100 certificates across a pool of horizontally auto-scaled worker nodes.
2. **Cloud Object Storage**:
   - Swap `StorageService` local paths with **AWS S3**, **Google Cloud Storage**, or **Azure Blob Storage**.
   - Serve certificate downloads via signed pre-signed URLs or CloudFront/Cloudflare CDN.
3. **Database Concurrency**:
   - For multi-worker deployments, point `DATABASE_URL` to PostgreSQL. Counter increments can use atomic SQL expressions (`UPDATE jobs SET processed_count = processed_count + 1 WHERE id = :id`).
4. **Webhooks / Event Notifications**:
   - Add a `webhook_url` parameter to `CertificateJobCreateRequest` to ping the client system when the job reaches `COMPLETED` or `PARTIALLY_COMPLETED`.

---

## License

This project is licensed under the MIT License.
