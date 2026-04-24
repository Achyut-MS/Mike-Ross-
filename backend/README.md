# EvidenceChain Backend

Django REST Framework API for the EvidenceChain system.

## Tech Stack

- **Django 6** with DRF
- **SimpleJWT** for authentication
- **Celery + Redis** for async document processing
- **ChromaDB** for RAG vector storage
- **ReportLab** for PDF generation
- **Boto3** for AWS S3 integration

## Quick Start

```bash
pip install -r requirements.txt
pip install chromadb

python manage.py migrate
python manage.py ingest_knowledge
python manage.py runserver 0.0.0.0:8080
```

## Models

| Model | Purpose |
|-------|---------|
| `Case` | Core case with narrative, dispute type, jurisdiction |
| `EvidenceItem` | Uploaded document with OCR/classification results |
| `Event` | Timeline event (auto-extracted or manual) |
| `AILog` | Audit log for every LLM interaction |
| `CasePacket` | Generated 6-section case preparation document |
| `EvidenceTemplate` | Reference templates per dispute type |
| `JurisdictionMapping` | State → applicable laws mapping |
| `UserFeedback` | User feedback on AI outputs |

## API Endpoints

30+ endpoints across 7 categories. See [API_ENDPOINTS.md](../API_ENDPOINTS.md).

## Tests

```bash
python manage.py test cases -v 2
# 23 tests, all passing
```

## Management Commands

```bash
python manage.py ingest_knowledge          # Ingest legal KB into ChromaDB
python manage.py ingest_knowledge --stats   # Show KB statistics
python manage.py ingest_knowledge --clear   # Clear and re-ingest
```
