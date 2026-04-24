# ⚖️ EvidenceChain (MIKE ROSS)

**AI-Powered Dispute Preparation & Evidence-Chain Builder for Self-Represented Litigants in India**

> Proof-of-Concept — Tenant-Landlord & Freelance Payment disputes

---

## What It Does

EvidenceChain helps self-represented litigants organize their dispute documentation using AI. Users describe their dispute in plain language, and the system:

1. **Classifies** the dispute type and identifies applicable Indian laws
2. **Guides** evidence collection with a prioritized checklist (critical → supportive → optional)
3. **Processes** uploaded documents via OCR + AI classification
4. **Constructs** a chronological timeline from extracted events
5. **Generates** a 6-section case preparation packet (PDF) ready for a lawyer consultation

All legal issue mappings and jurisdiction data are **hardcoded templates** — no LLM hallucination on critical legal references.

---

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────┐
│  React SPA   │────▶│  Django REST API  │────▶│  PostgreSQL  │
│  (Vite + TS) │     │  (DRF + JWT)     │     │  (SQLite dev)│
└──────────────┘     └──────┬───────────┘     └─────────────┘
                            │
                     ┌──────┴───────┐
                     │              │
              ┌──────▼──────┐ ┌────▼─────┐
              │   GPT-4o    │ │ ChromaDB │
              │  + RAG      │ │  (RAG)   │
              └─────────────┘ └──────────┘
```

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite, Axios |
| Backend API | Django 6, DRF, SimpleJWT |
| AI Engine | GPT-4o via OpenAI API |
| Vector Store | ChromaDB (all-MiniLM-L6-v2 embeddings) |
| Async Tasks | Celery + Redis |
| File Storage | AWS S3 (pre-signed URLs) |
| PDF Output | ReportLab |

---

## Project Structure

```
Mike-Ross-/
├── backend/
│   ├── cases/
│   │   ├── models.py              # 8 Django models
│   │   ├── views.py               # 20+ API views
│   │   ├── serializers.py         # 20 DRF serializers
│   │   ├── urls.py                # 30+ URL patterns
│   │   ├── auth_views.py          # JWT auth endpoints
│   │   ├── ai_service.py          # GPT-4o orchestration + RAG
│   │   ├── tasks.py               # Celery document pipeline
│   │   ├── packet_tasks.py        # Case packet generation + PDF
│   │   ├── services.py            # Hardcoded legal templates
│   │   ├── knowledge_base.py      # ChromaDB RAG manager
│   │   ├── tests.py               # 23 unit tests
│   │   └── management/commands/
│   │       └── ingest_knowledge.py # KB ingestion command
│   ├── evidencechain/
│   │   ├── settings.py            # Django config
│   │   ├── urls.py                # Root URL routing
│   │   └── celery.py              # Celery config
│   ├── requirements.txt
│   ├── Dockerfile
│   └── manage.py
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── EvidenceGuidedInterview.tsx
│   │   │   ├── DisclaimerModal.tsx
│   │   │   └── Navbar.tsx
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── RegisterPage.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   ├── NewCase.tsx
│   │   │   └── CaseDetail.tsx
│   │   ├── services/
│   │   │   └── api.ts             # Axios client + JWT handling
│   │   ├── App.tsx                # Routing + auth
│   │   └── index.css              # Design system
│   ├── package.json
│   └── vite.config.ts
│
├── docker-compose.yml
├── .env.example
├── API_ENDPOINTS.md               # Full API reference
├── EVIDENCECHAIN_PROJECT_SPECIFICATION.md
└── README.md
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- (Optional) Docker & Docker Compose

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
pip install chromadb

# Migrate database (SQLite for local dev)
python manage.py migrate

# Ingest legal knowledge base
python manage.py ingest_knowledge

# Run server
python manage.py runserver 0.0.0.0:8080
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

App runs at **http://localhost:3000** (proxies API to `:8080`).

### 3. Run Tests

```bash
cd backend
python manage.py test cases -v 2
# Output: Ran 23 tests in 15s — OK
```

---

## API Overview

All endpoints are under `/api/v1/`. See [API_ENDPOINTS.md](API_ENDPOINTS.md) for full reference.

| Category | Endpoints | Auth |
|----------|-----------|------|
| **Auth** | register, login, refresh, logout | Public |
| **Cases** | create, list, detail, update, archive | JWT |
| **Classification** | extract-entities, categorize, confirm | JWT |
| **Evidence** | template, presigned-url, register, status, list, update, delete, gap-report | JWT |
| **Timeline** | list, create event, update, delete, deduplicate | JWT |
| **Case Packet** | generate, status, detail, download PDF, regenerate | JWT |
| **AI** | insights, logs, knowledge-base search | JWT |

---

## Knowledge Base

15 Indian legal provisions are embedded in ChromaDB:

- **Karnataka Rent Control Act 2001** — Sections 4, 21, 27
- **Maharashtra Rent Control Act 1999** — Section 7
- **Delhi Rent Control Act 1958** — Section 14
- **Transfer of Property Act 1882** — Sections 108, 111
- **Specific Relief Act 1963** — Section 14
- **Indian Contract Act 1872** — Sections 10, 62, 73
- **Consumer Protection Act 2019** — Section 2(7)
- **Information Technology Act 2000** — Section 65B
- **Limitation Act 1963** — Article 113

```bash
python manage.py ingest_knowledge          # Ingest all
python manage.py ingest_knowledge --stats   # Show stats
python manage.py ingest_knowledge --clear   # Clear & re-ingest
```

---

## Test Results

**23/23 tests passing** ✅

| Suite | Tests |
|-------|-------|
| Auth | register, login, refresh, duplicate, 401 protection (6) |
| Health | endpoint check (1) |
| Cases | create, list, detail, update, archive, user isolation (6) |
| Classification | confirm → dispute type + applicable laws (1) |
| Evidence | template, gap report, listing (3) |
| Timeline | create event, list, delete (3) |
| Knowledge Base | chunking, ingest + search, filtered search (3) |

---

## Ethical Safeguards

- **Advocates Act 1961 compliance** — mandatory disclaimer modal on first use
- **No legal advice** — system explicitly states it provides informational tools only
- **No outcome prediction** — AI prompts prohibit predicting case outcomes
- **Hardcoded legal references** — jurisdiction maps and legal issues never use LLM generation
- **Audit trail** — every AI interaction logged to `AILog` with prompt hashes
- **PDF footer disclaimer** — persistent on every page of generated case packets

---

## Future Roadmap

### Near-Term
- [ ] **OpenAI integration testing** — validate GPT-4o entity extraction and classification with live API key
- [ ] **S3 upload flow** — end-to-end file upload via pre-signed URLs with LocalStack
- [ ] **Celery worker** — spin up Redis + Celery for async document processing
- [ ] **Frontend polish** — loading states, error boundaries, responsive mobile layout
- [ ] **More dispute types** — Employment, Consumer, Property disputes

### Mid-Term
- [ ] **PDF external document ingestion** — chunk and embed user-uploaded legal PDFs into ChromaDB
- [ ] **Real-time status updates** — WebSocket notifications for document processing progress
- [ ] **Multi-language support** — Hindi, Kannada, Tamil UI translations
- [ ] **Case sharing** — share case packet with advocate via secure link
- [ ] **Docker production compose** — single `docker-compose up` for full stack

### Long-Term
- [ ] **Evaluation study** — ECS (Evidence Completeness Score) and HR (Hallucination Rate) metrics with reviewer panel
- [ ] **AWS deployment** — Elastic Beanstalk + RDS + S3 + ElastiCache
- [ ] **Legal aid integration** — connect with NALSA legal aid clinics
- [ ] **Court filing assistant** — generate court-ready formats for specific forums
- [ ] **Research paper** — IEEE format publication on AI-assisted dispute preparation

---

## Environment Variables

```bash
cp .env.example .env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Django secret key |
| `OPENAI_API_KEY` | For AI features | GPT-4o API key |
| `DATABASE_URL` | No (SQLite default) | PostgreSQL connection string |
| `AWS_ACCESS_KEY_ID` | For S3 uploads | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | For S3 uploads | AWS credentials |
| `CELERY_BROKER_URL` | For async tasks | Redis URL |

---

## License

MIT

---

**Built for improving access to justice in India** ⚖️
