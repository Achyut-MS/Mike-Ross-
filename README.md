# EvidenceChain (MIKE ROSS) - Implementation Guide

## 📋 Project Overview

AI-Powered Dispute Preparation and Evidence-Chain Builder for Self-Represented Litigants in India.

**Proof-of-Concept Scope**: Tenant-Landlord & Freelance Payment disputes

---

## 📁 Project Structure

```
evidencechain/
├── backend/                    # Django REST API
│   ├── evidencechain/         # Main Django project
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── cases/                 # Core app
│   │   ├── models.py          # Database models (provided)
│   │   ├── views.py           # API views
│   │   ├── serializers.py     # DRF serializers
│   │   ├── ai_service.py      # AI orchestration (provided)
│   │   ├── tasks.py           # Celery tasks (provided)
│   │   └── services.py        # Business logic
│   ├── knowledge_base/        # RAG setup
│   │   ├── chunk_legal_docs.py
│   │   ├── build_chromadb.py
│   │   └── legal_sources/     # Downloaded PDFs
│   ├── requirements.txt
│   ├── Dockerfile
│   └── manage.py
│
├── frontend/                  # React TypeScript SPA
│   ├── src/
│   │   ├── components/
│   │   │   ├── EvidenceGuidedInterview.tsx (provided)
│   │   │   ├── Timeline.tsx
│   │   │   ├── CasePacketViewer.tsx
│   │   │   └── Dashboard.tsx
│   │   ├── services/
│   │   │   └── api.ts
│   │   ├── App.tsx
│   │   └── index.tsx
│   ├── package.json
│   ├── tsconfig.json
│   └── Dockerfile
│
├── docker-compose.yml         # Local dev environment (provided)
├── .env.example               # Environment variables template
└── README.md                  # This file
```

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose (recommended)
- OR: Python 3.11+, Node 18+, PostgreSQL 15, Redis 7
- OpenAI API key (GPT-4o access)
- AWS account (S3, RDS) for production

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd evidencechain
```

### 2. Environment Configuration

```bash
cp .env.example .env
```

Edit `.env` and add:
```env
# Required
OPENAI_API_KEY=sk-...

# AWS (for production)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
```

### 3. Start with Docker Compose

```bash
docker-compose up -d
```

This starts:
- PostgreSQL (port 5432)
- Redis (port 6379)
- ChromaDB (port 8000)
- Django Backend (port 8080)
- React Frontend (port 3000)
- Celery Worker
- LocalStack (S3 emulation)

### 4. Initialize Database

```bash
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py createsuperuser
```

### 5. Build Knowledge Base

```bash
# Download legal documents (see instructions below)
docker-compose exec backend python manage.py build_knowledge_base
```

### 6. Access Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8080/api/v1
- **Admin Panel**: http://localhost:8080/admin
- **ChromaDB**: http://localhost:8000

---

## 📚 Knowledge Base Setup

### Download Legal Sources

Create `backend/knowledge_base/legal_sources/` directory and download:

1. **Karnataka Rent Control Act 2001**
   - URL: http://dpal.kar.nic.in/pdf2001/ACT.40.2001.pdf
   - Save as: `KRCA_2001.pdf`

2. **Transfer of Property Act 1882**
   - URL: https://legislative.gov.in/sites/default/files/A1882-04.pdf
   - Save as: `TPA_1882.pdf`

3. **Indian Contract Act 1872**
   - URL: https://legislative.gov.in/sites/default/files/A1872-09.pdf
   - Save as: `ICA_1872.pdf`

4. **Consumer Protection Act 2019**
   - URL: https://legislative.gov.in/sites/default/files/A2019-35.pdf
   - Save as: `CPA_2019.pdf`

5. **Limitation Act 1963**
   - URL: https://legislative.gov.in/sites/default/files/A1963-36.pdf
   - Save as: `Limitation_Act_1963.pdf`

6. **MSMED Act 2006**
   - URL: https://legislative.gov.in/sites/default/files/A2006-27.pdf
   - Save as: `MSMED_Act_2006.pdf`

7-8. Karnataka Stamp Act & NALSA guides (obtain from respective portals)

### Build ChromaDB Index

```bash
cd backend/knowledge_base
python chunk_legal_docs.py    # Chunks PDFs into 512-token segments
python build_chromadb.py       # Embeds and indexes into ChromaDB
```

Expected output: ~1,200 chunks indexed

---

## 🔧 Development Workflow

### Backend Development

```bash
# Install dependencies
cd backend
pip install -r requirements.txt

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Start development server
python manage.py runserver 0.0.0.0:8080

# Start Celery worker
celery -A evidencechain worker -l info

# Run tests
python manage.py test
```

### Frontend Development

```bash
# Install dependencies
cd frontend
npm install

# Start development server
npm start

# Build for production
npm run build

# Run tests
npm test
```

---

## 📖 API Documentation

See `API_ENDPOINTS.md` for complete API reference.

**Key Endpoints**:

- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `POST /cases/create` - Create new case
- `POST /cases/{id}/classify/extract-entities` - Entity extraction
- `POST /cases/{id}/classify/categorize` - Dispute classification
- `GET /cases/{id}/evidence/template` - Get evidence checklist
- `POST /evidence/presigned-url` - Request S3 upload URL
- `GET /cases/{id}/timeline` - Get chronological timeline
- `POST /cases/{id}/case-packet/generate` - Generate case packet

---

## 🧪 Testing

### Unit Tests

```bash
# Backend
python manage.py test cases.tests

# Frontend
npm test
```

### Integration Tests

```bash
# Run full API integration tests
python manage.py test cases.tests.integration
```

### AI Quality Tests

```bash
# Test hallucination rate
python manage.py test_hallucination_rate

# Test classification accuracy
python manage.py test_classification_accuracy

# Test evidence completeness
python manage.py test_evidence_completeness
```

---

## 📊 Evaluation Metrics

### 1. Evidence Completeness Score (ECS)

```bash
python manage.py calculate_ecs --scenario=tenant_deposit
```

Target: ECS ≥ 0.85

### 2. Hallucination Rate (HR)

```bash
python manage.py calculate_hallucination_rate --case-id=<uuid>
```

Target: HR ≤ 5%

### 3. Classification Accuracy

```bash
python manage.py test_classification --num-samples=100
```

Target: ≥ 90%

---

## 🚢 Production Deployment

### AWS Elastic Beanstalk

1. **Install EB CLI**:
   ```bash
   pip install awsebcli
   ```

2. **Initialize EB Application**:
   ```bash
   eb init -p python-3.11 evidencechain --region ap-south-1
   ```

3. **Create Environment**:
   ```bash
   eb create evidencechain-prod \
     --instance-type t3.medium \
     --database.engine postgres \
     --database.size 50 \
     --database.instance db.t3.small \
     --envvars OPENAI_API_KEY=$OPENAI_API_KEY
   ```

4. **Deploy**:
   ```bash
   eb deploy
   ```

### Environment Variables (Production)

Set in EB Console or via CLI:

```bash
eb setenv \
  DEBUG=False \
  SECRET_KEY=<generate-strong-key> \
  ALLOWED_HOSTS=api.evidencechain.com \
  DATABASE_URL=<rds-url> \
  OPENAI_API_KEY=<your-key> \
  AWS_S3_BUCKET_UPLOADS=evidencechain-uploads-prod \
  CELERY_BROKER_URL=<elasticache-redis-url>
```

---

## 📈 Monitoring

### Prometheus Metrics

Access at: `http://localhost:8080/metrics`

Key metrics:
- `api_requests_total` - Total API requests
- `ai_inference_latency_seconds` - AI latency histogram
- `case_packet_generation_duration_seconds` - Case packet generation time

### Logging

Logs are written to:
- Development: Console
- Production: CloudWatch Logs

View logs:
```bash
# Local
docker-compose logs -f backend

# Production
eb logs
```

---

## 🔒 Security

### Environment-Specific Configurations

**Development**:
- DEBUG=True
- SQLite or local PostgreSQL
- LocalStack for S3

**Production**:
- DEBUG=False
- AWS RDS PostgreSQL
- AWS S3 with encryption
- HTTPS only
- Rate limiting enabled

### API Authentication

All endpoints (except `/auth/register` and `/auth/login`) require JWT token:

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8080/api/v1/cases/
```

---

## 🛠️ Troubleshooting

### ChromaDB Connection Issues

```bash
# Check ChromaDB is running
curl http://localhost:8000/api/v1/heartbeat

# Rebuild index
docker-compose exec backend python manage.py rebuild_chromadb
```

### Celery Tasks Not Processing

```bash
# Check Redis connection
docker-compose exec redis redis-cli ping

# Restart Celery worker
docker-compose restart celery_worker
```

### S3 Upload Failures (LocalStack)

```bash
# Create bucket in LocalStack
aws --endpoint-url=http://localhost:4566 s3 mb s3://evidencechain-uploads-dev

# List buckets
aws --endpoint-url=http://localhost:4566 s3 ls
```

---

## 📝 Research Paper Checklist

- [ ] Abstract (200 words)
- [ ] Introduction (access-to-justice problem)
- [ ] Literature Review (existing legal AI tools)
- [ ] Research Gap (evidence-chain builders)
- [ ] Proposed System (EvidenceChain architecture)
- [ ] Methodology (copy from EVIDENCECHAIN_PROJECT_SPECIFICATION.md)
- [ ] Implementation (technologies, database schema)
- [ ] Evaluation (ECS, HR metrics, scenario testing)
- [ ] Results and Discussion
- [ ] Conclusion and Future Work
- [ ] References (IEEE format)

---

## 🎯 Implementation Checklist

### Phase 1: Foundation (Weeks 1-2)
- [ ] Set up Git repository
- [ ] Configure Docker development environment
- [ ] Initialize Django project
- [ ] Initialize React project
- [ ] Set up PostgreSQL database
- [ ] Implement user authentication (JWT)

### Phase 2: Core Backend (Weeks 3-4)
- [ ] Implement database models (provided in `django_models.py`)
- [ ] Create API endpoints (reference `API_ENDPOINTS.md`)
- [ ] Integrate AI service (provided in `ai_service.py`)
- [ ] Set up Celery for async processing (provided in `celery_tasks.py`)

### Phase 3: AI Components (Weeks 5-6)
- [ ] Download legal knowledge base sources
- [ ] Chunk legal documents (512 tokens, 64 overlap)
- [ ] Build ChromaDB index
- [ ] Validate knowledge base (KBAS ≥ 0.88)
- [ ] Test all 7 prompt templates

### Phase 4: Frontend (Weeks 7-8)
- [ ] Implement Evidence Guided Interview (provided in `EvidenceGuidedInterview.tsx`)
- [ ] Build Timeline visualization component
- [ ] Create Case Packet viewer
- [ ] Implement Dashboard
- [ ] Add session disclaimer modal

### Phase 5: Integration (Week 9)
- [ ] S3 direct upload integration
- [ ] Real-time processing status updates
- [ ] PDF generation with reportlab
- [ ] End-to-end testing

### Phase 6: Deployment (Weeks 10-11)
- [ ] Deploy to AWS Elastic Beanstalk
- [ ] Configure AWS RDS PostgreSQL
- [ ] Set up AWS S3 buckets
- [ ] Configure ElastiCache Redis
- [ ] Performance testing

### Phase 7: Evaluation (Weeks 12-13)
- [ ] Create 2 test scenarios (fact sheets)
- [ ] Recruit reviewer panel (advocate + LLB student)
- [ ] Calculate ECS metric
- [ ] Calculate HR metric
- [ ] Measure inter-rater reliability (Cohen's κ)
- [ ] Write research paper

---

## 📚 Additional Resources

- **Django Documentation**: https://docs.djangoproject.com/
- **Django REST Framework**: https://www.django-rest-framework.org/
- **React Documentation**: https://react.dev/
- **OpenAI API**: https://platform.openai.com/docs
- **ChromaDB**: https://docs.trychroma.com/
- **Celery**: https://docs.celeryq.dev/

---

## 👥 Team Roles

- **Backend Engineer**: Django API, PostgreSQL, Celery
- **Frontend Engineer**: React, TypeScript, UI/UX
- **AI/ML Engineer**: RAG pipeline, prompt engineering, ChromaDB
- **Research/QA Lead**: Literature review, evaluation, paper writing

---

## 📄 License

[Add your license here]

---

## 🤝 Contributing

[Add contribution guidelines]

---

## 📧 Contact

[Add contact information]

---

**Built with ❤️ for improving access to justice in India**
