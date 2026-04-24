# EvidenceChain — Phase 1: Project Initialization

Setting up the Django 4.2 backend, React 18 frontend, and Docker development environment as specified in the project docs.

## Scope

Phase 1 covers **project scaffolding only** — no API views, no AI service integration, no frontend UI. The goal is a working dev environment with:
- Django project + `cases` app with all models migrated
- React + TypeScript project scaffolded
- Docker Compose environment for local dev
- All dependencies pinned to spec versions

---

## Proposed Changes

### Backend — Django Project

#### [NEW] `backend/` directory structure

```
backend/
├── evidencechain/          # Django project
│   ├── __init__.py
│   ├── settings.py         # Configured for PostgreSQL, Celery, JWT, CORS
│   ├── urls.py             # Root URL config with api/v1/ prefix
│   ├── wsgi.py
│   ├── asgi.py
│   └── celery.py           # Celery app setup
├── cases/                  # Main app
│   ├── __init__.py
│   ├── models.py           # Exact copy from django_models.py
│   ├── admin.py            # Model registration
│   ├── apps.py
│   ├── ai_service.py       # Copy from template (not wired yet)
│   ├── tasks.py            # Copy from template (not wired yet)
│   ├── services.py         # Placeholder
│   ├── serializers.py      # Placeholder
│   ├── views.py            # Placeholder
│   └── urls.py             # Placeholder
├── knowledge_base/         # RAG setup (empty for now)
│   └── legal_sources/
├── requirements.txt        # All deps pinned to spec versions
├── Dockerfile              # Python 3.11 container
└── manage.py
```

#### [NEW] `backend/requirements.txt`

Exact dependencies from the specification:
```
Django==4.2
djangorestframework==3.14.0
djangorestframework-simplejwt==5.3.0
django-cors-headers==4.3.1
psycopg2-binary==2.9.9
celery==5.3.4
redis==5.0.1
openai==1.3.0
sentence-transformers==2.2.2
chromadb==0.4.18
python-magic==0.4.27
pytesseract==0.3.10
Pillow==10.1.0
pdfplumber==0.10.3
boto3==1.34.0
reportlab==4.0.7
dj-database-url==2.1.0
python-dotenv==1.0.0
gunicorn==21.2.0
pdf2image==1.16.3
```

#### [NEW] `backend/evidencechain/settings.py`

Key configuration:
- `DATABASES` via `dj-database-url` (PostgreSQL)
- `REST_FRAMEWORK` with JWT default auth + pagination
- `SIMPLE_JWT` with 24-hour access token lifetime
- `CELERY_BROKER_URL` from env
- `CORS_ALLOWED_ORIGINS` restricted
- `OPENAI_API_KEY` from env
- `CHROMA_PERSIST_DIRECTORY` from env

#### [NEW] `backend/evidencechain/celery.py`

Standard Celery app configuration bound to Django settings.

#### [NEW] `backend/cases/models.py`

**Exact copy** of `django_models.py` — 8 models:
1. `Case` — primary dispute entity
2. `EvidenceItem` — uploaded evidence with processing status
3. `Event` — timeline events with deduplication tracking
4. `AILog` — all LLM interaction logs (critical for HR metric)
5. `CasePacket` — generated 6-section case packets
6. `EvidenceTemplate` — hardcoded evidence templates per dispute type
7. `JurisdictionMapping` — jurisdiction → applicable laws
8. `UserFeedback` — user feedback on AI outputs

#### [NEW] `backend/Dockerfile`

Python 3.11 on Debian slim, with system deps for Tesseract, libmagic, and poppler (pdf2image).

---

### Frontend — React Project

#### [NEW] `frontend/` via Vite

```
frontend/
├── src/
│   ├── components/
│   │   └── EvidenceGuidedInterview.tsx   # Copy from template
│   ├── services/
│   │   └── api.ts                       # Placeholder
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── package.json
├── tsconfig.json
├── vite.config.ts
└── Dockerfile
```

Dependencies: `axios`, `react-router-dom`

---

### Docker & Environment

#### [MODIFY] `docker-compose.yml`
Keep the provided file as-is — it already defines all 8 services (postgres, redis, chromadb, backend, celery_worker, celery_beat, frontend, localstack, nginx).

#### [NEW] `.env.example`
Template with all required env vars.

#### [NEW] `backend/init_db.sql`
PostgreSQL initialization script (create extensions if needed).

---

## Open Questions

> [!IMPORTANT]
> **Local vs Docker development?** The spec includes a full Docker Compose setup, but for faster iteration during initial development, I can set up the backend to run locally (with `python manage.py runserver`) against the Docker PostgreSQL and Redis containers. Which do you prefer?

> [!IMPORTANT]
> **OpenAI API key availability?** The AI service requires a valid `OPENAI_API_KEY`. Do you have one ready, or should I stub out the AI service calls for now so we can develop and test the API endpoints independently?

> [!NOTE]
> **React framework choice:** The spec says React 18 + TypeScript. I'll use **Vite** (fast, modern) instead of Create React App (deprecated). The spec doesn't mandate CRA. This gives us faster dev builds and HMR.

---

## Verification Plan

### Automated Tests
1. `python manage.py migrate` completes without errors
2. `python manage.py check` passes
3. `python manage.py test` passes (empty test suite for now)
4. Django admin loads at `/admin/` and shows all 8 models
5. Frontend dev server starts and renders

### Manual Verification
1. Confirm project structure matches spec's `README.md` tree
2. Confirm all models match `django_models.py` exactly
3. Confirm database tables are created in PostgreSQL
