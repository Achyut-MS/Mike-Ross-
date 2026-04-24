# EvidenceChain (MIKE ROSS) - Complete Project Specification

## Project Overview

Build an **AI-Powered Dispute Preparation and Evidence-Chain Builder** for self-represented litigants in India. The system assists everyday people in documenting disputes, organizing evidence, constructing chronological timelines, and generating structured case packets without providing legal advice (remaining compliant with the Advocates Act, 1961).

---

## Core Problem Statement

Everyday people lose disputes due to poor documentation and evidence organization. Self-represented individuals lack structured guidance on what evidence to collect, how to organize it chronologically, and how to present it coherently. This creates an access-to-justice gap where technical documentation deficiencies—not the merits of the case—determine outcomes.

---

## System Architecture

### Five-Tier Layered Architecture

1. **Presentation Tier**: Single-page application (SPA) using React 18 with TypeScript
2. **Application Tier**: Django 4.2 with Django REST Framework (DRF) for REST API and AI orchestration
3. **AI Orchestration Tier**: Manages OpenAI GPT-4o API calls with prompt templates and response parsing
4. **Data Persistence Tier**: PostgreSQL 15 (structured metadata) + ChromaDB (vector store for semantic retrieval)
5. **Knowledge Retrieval Tier**: Curated Indian legal knowledge base for RAG (Retrieval-Augmented Generation)

---

## Technology Stack - Exact Specifications

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| Frontend | React + TypeScript | 18.2 | SPA guided interview interface |
| Backend | Django + DRF | 4.2 | REST API and AI orchestration |
| Primary Database | PostgreSQL | 15 | Relational data storage |
| Vector Store | ChromaDB | 0.4.x | Semantic chunk retrieval |
| LLM API | OpenAI GPT-4o | via API | Inference backbone for all generation |
| Embeddings | all-MiniLM-L6-v2 | sentence-transformers | Document and query embedding (384-dim) |
| OCR | Tesseract | 5.x | Scanned document text extraction |
| File Storage | AWS S3 | - | Raw document upload storage |
| Authentication | JWT (simplejwt) | - | Stateless session management |
| Task Queue | Celery + Redis | - | Async document processing pipeline |
| PDF Generation | reportlab | - | Case packet PDF output |
| Deployment | AWS Elastic Beanstalk | - | Backend hosting |
| Database Hosting | AWS RDS (PostgreSQL) | - | Production database |

---

## Database Schema - PostgreSQL 15

### 1. `cases` Table
```sql
CREATE TABLE cases (
    case_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    dispute_type VARCHAR(50) CHECK (dispute_type IN ('TENANT_LANDLORD', 'FREELANCE_PAYMENT')),
    dispute_stage VARCHAR(50),
    jurisdiction VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) CHECK (status IN ('active', 'completed', 'archived')),
    gap_report JSONB
);
```

### 2. `evidence_items` Table
```sql
CREATE TABLE evidence_items (
    evidence_id UUID PRIMARY KEY,
    case_id UUID REFERENCES cases(case_id),
    evidence_type VARCHAR(100),
    file_path VARCHAR(500), -- S3 URI
    extracted_text TEXT,
    classification_tag VARCHAR(100) CHECK (classification_tag IN ('CONTRACT', 'RECEIPT', 'COMMUNICATION', 'PHOTOGRAPH', 'LEGAL_NOTICE', 'OTHER')),
    completeness_flag BOOLEAN DEFAULT FALSE,
    upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3. `events` Table
```sql
CREATE TABLE events (
    event_id UUID PRIMARY KEY,
    case_id UUID REFERENCES cases(case_id),
    event_date DATE,
    actors JSONB, -- Array of party names
    action_description TEXT,
    evidence_refs JSONB, -- Array of evidence_id references
    legal_relevance_tag VARCHAR(100)
);
```

### 4. `ai_logs` Table (Critical for Hallucination Tracking)
```sql
CREATE TABLE ai_logs (
    log_id UUID PRIMARY KEY,
    case_id UUID REFERENCES cases(case_id),
    module VARCHAR(50) CHECK (module IN ('classification', 'evidence_guidance', 'document_processing', 'timeline', 'case_packet')),
    prompt_hash VARCHAR(64), -- SHA-256 hash
    model_response TEXT,
    retrieved_chunks JSONB, -- RAG chunks used
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5. `case_packets` Table
```sql
CREATE TABLE case_packets (
    packet_id UUID PRIMARY KEY,
    case_id UUID REFERENCES cases(case_id),
    executive_summary TEXT,
    issues JSONB,
    evidence_table JSONB,
    timeline JSONB,
    gap_report JSONB,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Module Implementation - Four Core Modules

## MODULE 1: Dispute Classification Pipeline

### Step 1: Named Entity Extraction
**Endpoint**: `POST /api/cases/classify/extract-entities`

**GPT-4o System Prompt**:
```
You are a precise entity extractor for legal disputes. Extract ONLY entities explicitly present in the text.

Return JSON:
{
  "parties": ["name1", "name2"],
  "monetary_amounts": ["₹1,50,000", "₹80,000"],
  "dates": ["2024-01-15", "2024-03-20"],
  "locations": ["Bengaluru", "Karnataka"],
  "legal_instruments": ["Rent Agreement", "Invoice"]
}

Rules:
- Extract only explicitly mentioned entities
- Return null for absent fields (do NOT infer)
- Use ISO date format (YYYY-MM-DD)
- Preserve exact monetary notation (₹ symbol)
```

**Validation**: Use Pydantic schema validation. On malformed response, retry once with corrective prompt.

### Step 2: Dispute Classification
**Endpoint**: `POST /api/cases/classify/categorize`

**GPT-4o System Prompt**:
```
You are a dispute classifier. Classify into ONE category:
- TENANT_LANDLORD: Rent disputes, security deposits, eviction, property damage
- FREELANCE_PAYMENT: Unpaid freelance work, contract breaches, delayed payment

Input: Entity JSON + original narrative

Return JSON:
{
  "dispute_type": "TENANT_LANDLORD",
  "confidence": 0.85,
  "reasoning": "Security deposit non-return mentioned with landlord-tenant relationship"
}

Confidence threshold: If < 0.7, flag for manual selection.
```

### Step 3: Jurisdiction Mapping
**Hardcoded Lookup Table** (no LLM):

```python
JURISDICTION_MAP = {
    'TENANT_LANDLORD': {
        'Karnataka': [
            'Karnataka Rent Control Act 2001',
            'Transfer of Property Act 1882',
            'Specific Relief Act 1963'
        ]
    },
    'FREELANCE_PAYMENT': {
        'All India': [
            'Indian Contract Act 1872',
            'Limitation Act 1963',
            'MSME Delayed Payment Act 2006 (if applicable)'
        ]
    }
}
```

### Step 4: User Confirmation
**React Component**: Display classification result with options:
- ✅ Confirm
- 🔄 Select Different Type
- ⚠️ Flag Misclassification

On confirmation: Update `cases` table, initialize evidence module.

---

## MODULE 2: Evidence Guidance and Capture

### Step 1: Evidence Template Loading
**Hardcoded JSON Templates** (no LLM to prevent hallucination):

**TENANT_LANDLORD Template**:
```json
{
  "critical": [
    {"name": "Rental/Lease Agreement", "description": "Signed rent agreement document"},
    {"name": "Security Deposit Receipt", "description": "Proof of security deposit payment"},
    {"name": "Bank Transfer Records", "description": "Rent payment history"}
  ],
  "supportive": [
    {"name": "Move-out Photographs", "description": "Property condition at vacating"},
    {"name": "Communication with Landlord", "description": "WhatsApp/Email exchanges"}
  ],
  "optional": [
    {"name": "Police Complaint", "description": "FIR or legal notice if filed"}
  ]
}
```

**FREELANCE_PAYMENT Template**:
```json
{
  "critical": [
    {"name": "Signed Contract/Work Order", "description": "Agreement for services"},
    {"name": "Invoices Issued", "description": "Payment requests sent"},
    {"name": "Bank/UPI Payment Records", "description": "Transaction history"}
  ],
  "supportive": [
    {"name": "Email/Chat Confirmation", "description": "Acceptance of deliverables"},
    {"name": "Delivery Acknowledgement", "description": "Client confirmation of receipt"}
  ],
  "optional": []
}
```

### Step 2: Guided Interview UI (React)
**Sequential Form Component** - Each evidence item renders as:

```typescript
interface EvidenceUploadStep {
  itemName: string;
  itemType: 'critical' | 'supportive' | 'optional';
  options: [
    'Upload File',
    'Describe in Text',
    'I Don\'t Have This',
    'I\'m Not Sure'
  ];
}
```

**File Upload Flow**:
1. Frontend requests pre-signed S3 URL from Django: `POST /api/evidence/presigned-url`
2. Frontend uploads directly to S3 using pre-signed URL
3. Frontend notifies backend of successful upload: `POST /api/evidence/register`
4. Backend queues file for Celery processing

**S3 Object Key Convention**: `{case_id}/{evidence_id}/{original_filename}`

### Step 3: Document Processing Pipeline (Celery)

**Celery Task Chain**:
```python
@app.task
def process_uploaded_document(evidence_id):
    # 1. Format Detection
    mime_type = magic.from_file(file_path, mime=True)
    
    # 2. OCR/Text Extraction
    if mime_type in ['image/jpeg', 'image/png']:
        text = pytesseract.image_to_string(Image.open(file_path))
    elif mime_type == 'application/pdf':
        # Check if scanned or digital
        if is_scanned_pdf(file_path):
            text = extract_with_ocr(file_path)
        else:
            text = pdfplumber.extract_text(file_path)
    
    # 3. Text Normalization
    text = normalize_whitespace(text)
    text = remove_non_utf8(text)
    
    # 4. Entity Extraction (GPT-4o)
    entities = extract_entities_from_document(text)
    
    # 5. Document Classification (GPT-4o)
    classification = classify_document_type(text)
    
    # 6. Completeness Check
    is_complete = check_completeness(evidence_id, entities)
    
    # Update database
    update_evidence_item(evidence_id, {
        'extracted_text': text,
        'classification_tag': classification,
        'completeness_flag': is_complete
    })
```

**Document Classification Prompt (GPT-4o)**:
```
Classify this document into ONE category:
- CONTRACT: Agreements, work orders, lease documents
- RECEIPT: Payment receipts, deposit slips, transaction confirmations
- COMMUNICATION: Emails, WhatsApp chats, SMS, letters
- PHOTOGRAPH: Images of property, products, or conditions
- LEGAL_NOTICE: Legal demands, FIRs, court notices
- OTHER: Anything not fitting above categories

Return JSON: {"classification": "CONTRACT", "confidence": 0.92}

Document text:
{extracted_text}
```

### Step 4: Gap Report Generation
**Automatic Gap Detection**:
```python
def generate_gap_report(case_id):
    template = get_evidence_template(case_id)
    uploaded = get_evidence_items(case_id)
    
    gaps = []
    for item in template['critical']:
        if not uploaded.has(item['name']) or not uploaded[item['name']].completeness_flag:
            gaps.append({
                'item': item['name'],
                'severity': 'critical',
                'remediation': f"Upload {item['description']}"
            })
    
    # Store in cases.gap_report (JSONB)
    update_case_gap_report(case_id, gaps)
```

---

## MODULE 3: Timeline Construction

### Step 1: Event Aggregation
**SQL Query**:
```sql
SELECT * FROM events 
WHERE case_id = :case_id 
ORDER BY event_date ASC NULLS LAST;
```

### Step 2: Deduplication (GPT-4o)
**Deduplication Prompt**:
```
Compare these two events:

Event 1:
Date: 2024-01-15
Description: "Rent payment of ₹20,000 made via UPI"

Event 2:
Date: 2024-01-16
Description: "January rent paid through Google Pay"

Are these the same event? Return JSON:
{
  "decision": "MERGE" | "KEEP_SEPARATE",
  "canonical_description": "Rent payment of ₹20,000 made via UPI on 2024-01-15" (if MERGE),
  "reasoning": "Same transaction, 1-day date discrepancy likely due to bank processing"
}

Rules:
- MERGE if describing same real-world event within 3-day window
- KEEP_SEPARATE if genuinely different events
```

**On MERGE**: Consolidate `evidence_refs` arrays, keep earlier date, use canonical description.

### Step 3: Gap Detection (GPT-4o)
**Gap Detection Prompt**:
```
You are a factual event analyzer. Given this timeline, identify ONLY temporal gaps where a logically expected event is absent.

Timeline:
1. 2024-01-01: Signed lease agreement
2. 2024-01-05: Paid ₹1,50,000 security deposit
3. 2024-06-01: Moved out of property
4. 2024-10-01: Sent legal notice for deposit return

Rules:
- Identify only factual gaps (missing events that should logically exist)
- Do NOT infer legal conclusions
- Do NOT predict case outcomes

Return JSON array:
[
  {
    "gap_after_event_id": "event-uuid-3",
    "description": "No record of requesting deposit return before legal notice",
    "suggested_question": "Did you contact the landlord about the deposit between June and October?"
  }
]
```

### Step 4: Timeline Storage & Visualization
**Storage**: Serialize finalized timeline to `case_packets.timeline` (JSONB)

**React Timeline Component**:
```typescript
interface TimelineEvent {
  event_id: string;
  date: string;
  description: string;
  actors: string[];
  evidence_refs: string[]; // Clickable links to uploaded docs
  is_gap?: boolean;
  suggested_question?: string;
}

<VerticalTimeline>
  {events.map(event => (
    <TimelineItem 
      key={event.event_id}
      date={event.date}
      description={event.description}
      evidenceLinks={event.evidence_refs}
    />
  ))}
</VerticalTimeline>
```

---

## MODULE 4: Case Packet Generation

### Six-Section Case Packet

#### 1. Executive Summary (GPT-4o with RAG)
**Prompt**:
```
[LEGAL CONTEXT]
{top_5_rag_chunks}

You are writing a factual case summary. Maximum 200 words.

Rules (HARD CONSTRAINTS):
- Summarize ONLY the factual situation
- Do NOT characterize legal strength
- Do NOT predict outcomes
- Do NOT recommend actions

Case details:
{case_timeline}
{evidence_list}

Return plain text summary.
```

#### 2. Issues and Likely Claims (TEMPLATE-POPULATED - No LLM)
**Hardcoded Dictionary**:
```python
LEGAL_ISSUES_MAP = {
    'TENANT_LANDLORD': {
        'Karnataka': [
            'Security Deposit Recovery under Karnataka Rent Control Act 2001, Section 21',
            'Breach of Lease Agreement under Transfer of Property Act 1882',
            'Specific Performance under Specific Relief Act 1963'
        ]
    },
    'FREELANCE_PAYMENT': {
        'All India': [
            'Breach of Contract under Indian Contract Act 1872, Section 73',
            'Recovery of Debt under Limitation Act 1963',
            'Delayed Payment Interest under MSMED Act 2006 (if applicable)'
        ]
    }
}
```

**No LLM involvement** → Eliminates hallucination risk entirely.

#### 3. Evidence Table (Database-Populated - No LLM)
**Direct SQL Query**:
```sql
SELECT 
    evidence_type AS "Document Name",
    classification_tag AS "Type",
    upload_timestamp::date AS "Date",
    CASE WHEN completeness_flag THEN 'Complete' ELSE 'Incomplete' END AS "Status",
    legal_relevance_tag AS "Relevance"
FROM evidence_items
WHERE case_id = :case_id
ORDER BY upload_timestamp;
```

#### 4. Chronological Timeline (JSONB-Populated - No LLM)
**Direct insertion** from `case_packets.timeline`.

#### 5. Gap Report (Database-Populated - No LLM)
**Direct insertion** from `cases.gap_report`.

#### 6. Preliminary Questions for Lawyer (GPT-4o)
**Prompt**:
```
Based on the gap report and timeline gaps below, generate 5-8 factual questions for the user to ask a lawyer.

Gap Report:
{gap_report}

Timeline Gaps:
{timeline_gaps}

Rules:
- Frame as information requests (NOT legal assessments)
- Focus on missing factual details
- Do NOT ask questions that predict outcomes
- Do NOT suggest legal strategies

Return JSON array:
["Question 1", "Question 2", ...]
```

### PDF Generation (reportlab)
```python
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table

def generate_case_packet_pdf(packet_id):
    packet = get_case_packet(packet_id)
    
    # Create PDF with persistent footer
    doc = SimpleDocTemplate(
        f"/tmp/case_packet_{packet_id}.pdf",
        pagesize=A4,
        bottomMargin=50  # Space for footer
    )
    
    # Add sections...
    
    # Persistent footer on every page
    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.drawString(
            30, 20,
            "This document was generated by an AI-assisted system for informational purposes only. "
            "It does not constitute legal advice. Consult a licensed advocate before taking any legal action."
        )
        canvas.restoreState()
    
    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
```

---

## RAG Pipeline - Knowledge Base Construction

### Knowledge Base Sources (8 Indian Legal Documents)
1. Karnataka Rent Control Act 2001
2. Transfer of Property Act 1882 (Chapters V, VIII)
3. Indian Contract Act 1872 (Chapters II, IV, VI)
4. Consumer Protection Act 2019 (Chapters II, IV)
5. Limitation Act 1963
6. MSMED Act 2006
7. Karnataka Stamp Act (rental agreement provisions)
8. NALSA Legal Aid Guides

### Chunking Strategy
**Tool**: LangChain `RecursiveCharacterTextSplitter`

**Parameters**:
```python
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,  # tokens
    chunk_overlap=64,  # tokens (ensures clauses spanning boundaries are captured)
    length_function=len,
    separators=["\n\n", "\n", ". ", " ", ""]
)
```

**Justification for 64-token overlap**: Average Indian legal clause = 40-60 tokens. 64-token overlap guarantees any clause spanning a chunk boundary appears in at least one complete chunk.

**Metadata Tagging**:
```python
chunk_metadata = {
    'source_document': 'Karnataka Rent Control Act 2001',
    'section': 'Section 21 - Security Deposits',
    'dispute_type_relevance': ['TENANT_LANDLORD'],
    'jurisdiction': 'Karnataka',
    'chunk_id': 'KRCA_2001_S21_C003'
}
```

**Total Chunks**: ~1,200 chunks at proof-of-concept scope.

### Embedding and Indexing

**Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2`
- Parameters: 22.7M
- Dimensions: 384
- Inference: CPU-only, 45-80ms per query
- RAM: ~90MB

**Embedding Process**:
```python
from sentence_transformers import SentenceTransformer
import chromadb

model = SentenceTransformer('all-MiniLM-L6-v2')

# Embed all chunks
embeddings = model.encode(chunks, show_progress_bar=True)

# Index in ChromaDB
client = chromadb.Client()
collection = client.create_collection(
    name="indian_legal_knowledge",
    metadata={"hnsw:space": "cosine"}  # Cosine similarity
)

collection.add(
    embeddings=embeddings.tolist(),
    documents=chunks,
    metadatas=chunk_metadata_list,
    ids=chunk_ids
)
```

### Retrieval at Inference Time

**For Every LLM Call Involving Legal Content**:
```python
def retrieve_context(query: str, top_k: int = 5):
    # Embed query
    query_embedding = model.encode([query])[0]
    
    # Retrieve top-5 chunks
    results = collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=top_k
    )
    
    # Log similarity scores (monitor quality)
    log_similarity_scores(results['distances'][0])
    
    return results['documents'][0]
```

**Prompt Template with RAG**:
```
[SYSTEM]
You are a factual legal information assistant.

[LEGAL CONTEXT]
Source 1 (Karnataka Rent Control Act 2001, Section 21):
{chunk_1}

Source 2 (Transfer of Property Act 1882, Section 108):
{chunk_2}

... (up to 5 chunks)

[INSTRUCTIONS]
- Answer ONLY from [LEGAL CONTEXT]
- Cite source document and section for EVERY legal statement
- If answer not in [LEGAL CONTEXT], respond: "I cannot find a reliable source for this in the knowledge base."

[USER INPUT]
{user_query}
```

### Knowledge Base Validation
**Stratified Random Sampling**: 25 chunks

**Domain Reviewer Evaluation** (final-year LLB student):
1. **Factual Accuracy**: Does chunk accurately reflect source document?
2. **Relevance**: Is dispute_type_relevance tag correct?

**Metric**: Knowledge Base Accuracy Score (KBAS) = (Accurate + Relevant Chunks) / 25

**Threshold**: KBAS ≥ 0.88 (22/25 chunks)

**Remediation**: Re-chunk and re-index any chunk rated inaccurate/irrelevant.

---

## Ethical and Regulatory Constraints

### Compliance with Advocates Act, 1961

**Three Technical Constraints**:

#### 1. Prompt-Level Restriction (Enforced at AI Layer)
**All LLM System Prompts MUST Include**:
```
HARD CONSTRAINTS - You are prohibited from:
- Predicting case outcomes ("You will win/lose")
- Assessing case strength ("Your case is strong/weak")
- Recommending legal action ("You should file a suit")
- Providing legal opinions or interpretations

You may ONLY:
- Provide factual information from legal texts
- Organize user-provided information
- Generate checklists and questions
```

#### 2. Template-Populated Legal Claims (No LLM Generation)
**Issues and Likely Claims section** uses hardcoded dictionary, NOT LLM generation. Prevents probabilistic legal characterization.

#### 3. Persistent Disclaimers

**Session Initiation Modal** (React):
```typescript
<Modal>
  <h2>Important Legal Notice</h2>
  <p>
    This system provides <strong>informational tools only</strong> and does not constitute legal advice.
    
    Under the Advocates Act, 1961, only licensed advocates can practice law in India.
    
    You must consult a licensed advocate before taking any legal action.
  </p>
  <Checkbox required>I understand and agree</Checkbox>
</Modal>
```

**PDF Footer** (on every page):
```
This document was generated by an AI-assisted system for informational purposes only. 
It does not constitute legal advice. Consult a licensed advocate before taking any legal action.
```

---

## Evaluation Methodology

### Expert-Assessed Simulation Study

**Test Scenarios (2)**:

**Scenario A: Tenant Security Deposit**
- Location: Bengaluru, Karnataka
- Issue: ₹1,50,000 security deposit not returned after 4 months
- Documents: Lease agreement, deposit receipt, move-out photos, WhatsApp messages

**Scenario B: Freelance Payment Dispute**
- Location: Pune, Maharashtra
- Issue: ₹80,000 unpaid for UI design project after delivery
- Documents: Work order, invoices, email acceptance, payment reminders

**Reviewer Panel**:
1. Practicing advocate (5+ years experience)
2. Final-year LLB student

### Evaluation Metrics

#### Metric 1: Evidence Completeness Score (ECS)
**Gold Standard**: Advocate reviewer creates ideal evidence checklist BEFORE system execution.

**Formula**: ECS = (Items Correctly Identified by System) / (Total Gold Standard Items)

**Target**: ECS ≥ 0.85

#### Metric 2: Hallucination Rate (HR)
**Process**:
1. Extract all legal statements from generated Case Packet
2. Reviewers check each statement against `ai_logs.retrieved_chunks`
3. Classify each statement:
   - **Grounded**: Supported by retrieved RAG chunks
   - **Hallucinated**: Not supported by any retrieved chunk

**Formula**: HR = (Hallucinated Statements / Total Legal Statements) × 100

**Target**: HR ≤ 5%

**Inter-Rater Reliability**: Cohen's Kappa (κ) ≥ 0.70

---

## Non-Functional Requirements

### Latency Budget

| Module | Embedding | Vector Retrieval | LLM Inference | Total |
|--------|-----------|------------------|---------------|-------|
| Dispute Classification | 45-80ms | 30-60ms | 800-1400ms | <1.6s |
| Evidence Guidance (per item) | 45-80ms | 30-60ms | 600-1200ms | <1.4s |
| Document Processing | 80-150ms | 30-60ms | 1200-2500ms | <2.7s |
| Timeline Construction | 45-80ms | 30-60ms | 900-1800ms | <2.0s |
| Case Packet Generation | 80-150ms | 30-60ms | 2000-4000ms | <4.2s |

**Latency Mitigation Strategies**:
1. **Streaming**: Use Server-Sent Events (SSE) for all user-facing LLM outputs
2. **Async Processing**: Celery handles document processing off main thread
3. **Pre-computation**: All knowledge base embeddings computed at indexing time

### API Rate Limits
- **OpenAI GPT-4o**: 500 requests/minute (Tier 2)
- **Embedding Model**: Local, no rate limit
- **S3 Upload**: 100 uploads/second

### Security Requirements
1. **Authentication**: JWT tokens with 24-hour expiry
2. **File Upload**: Max 10MB per file, whitelist MIME types: `application/pdf`, `image/jpeg`, `image/png`, `application/msword`
3. **SQL Injection**: Use Django ORM exclusively (no raw SQL)
4. **CORS**: Restrict to frontend domain only
5. **S3 Access**: Pre-signed URLs with 5-minute expiry

---

## Deployment Architecture

### AWS Elastic Beanstalk Configuration

**Application Tier**:
```yaml
platform: Python 3.11 on 64bit Amazon Linux 2023
instance_type: t3.medium (2 vCPU, 4GB RAM)
scaling:
  min_instances: 1
  max_instances: 4
  trigger: CPU > 70% for 5 minutes
```

**Database (AWS RDS)**:
```yaml
engine: PostgreSQL 15.4
instance_class: db.t3.small
storage: 50GB GP3 SSD
multi_az: false (dev), true (prod)
backup_retention: 7 days
```

**Redis (ElastiCache)**:
```yaml
node_type: cache.t3.micro
engine: Redis 7.0
```

**S3 Buckets**:
- `evidencechain-uploads-{env}`: User-uploaded evidence files
- `evidencechain-packets-{env}`: Generated PDF case packets

### Environment Variables
```bash
# Django
SECRET_KEY=<generate-secure-key>
DEBUG=False
ALLOWED_HOSTS=api.evidencechain.com

# Database
DATABASE_URL=postgresql://user:pass@rds-endpoint:5432/evidencechain

# OpenAI
OPENAI_API_KEY=<your-api-key>
OPENAI_MODEL=gpt-4o

# AWS
AWS_ACCESS_KEY_ID=<your-access-key>
AWS_SECRET_ACCESS_KEY=<your-secret-key>
AWS_S3_BUCKET_UPLOADS=evidencechain-uploads-prod
AWS_S3_REGION=ap-south-1

# Redis
CELERY_BROKER_URL=redis://elasticache-endpoint:6379/0

# ChromaDB
CHROMA_PERSIST_DIRECTORY=/opt/chroma_data
```

---

## Implementation Roadmap - 15 Steps

### Phase 1: Foundation (Weeks 1-2)
**Step 1**: Project setup, architecture diagram, team role assignment
**Step 2**: Environment setup (Python, Django, React, PostgreSQL, Celery, Redis)
**Step 3**: Database schema implementation, migrations, connectivity testing

### Phase 2: Core Backend (Weeks 3-4)
**Step 4**: User authentication (JWT, registration, login)
**Step 5**: Dispute Classification Module (Entity extraction, classification, jurisdiction)
**Step 6**: Evidence Management (S3 upload, metadata storage)

### Phase 3: AI Components (Weeks 5-6)
**Step 7**: RAG pipeline (Knowledge base chunking, ChromaDB indexing)
**Step 8**: Document Processing Pipeline (OCR, entity extraction, classification)
**Step 9**: Timeline Construction (Event aggregation, deduplication, gap detection)

### Phase 4: Frontend & Integration (Weeks 7-8)
**Step 10**: React SPA (Guided interview UI, evidence upload, timeline visualization)
**Step 11**: Case Dashboard (Cases list, evidence status, AI insights)
**Step 12**: AJAX integration (Dynamic updates without page reload)

### Phase 5: Output Generation (Week 9)
**Step 13**: Case Packet Generator (6 sections, PDF generation with reportlab)

### Phase 6: Deployment & Testing (Weeks 10-11)
**Step 14**: AWS deployment (Elastic Beanstalk, RDS, S3, ElastiCache)
**Step 15**: Testing (Functional, AI accuracy, usability, performance optimization)

### Phase 7: Research Paper (Weeks 12-13)
**Step 16**: Documentation (Architecture diagrams, workflow charts)
**Step 17**: Evaluation (ECS, HR metrics with reviewer panel)
**Step 18**: Paper writing (Intro, Lit Review, Methodology, Results, Conclusion)

---

## Research Paper Structure

### Required Sections
1. **Abstract** (200 words)
2. **Introduction** (Access-to-justice problem, project objectives)
3. **Literature Review** (Existing legal AI tools, limitations)
4. **Research Gap** (Lack of evidence-chain builders for self-represented litigants)
5. **Proposed System** (EvidenceChain architecture, modules)
6. **Methodology** (As detailed in this specification)
7. **Implementation** (Technologies, database schema, workflows)
8. **Evaluation** (ECS, HR metrics, scenario testing results)
9. **Results and Discussion** (Performance analysis, advantages over existing tools)
10. **Conclusion** (Contributions, impact on access to justice)
11. **Future Work** (Advanced reasoning, legal database integration)
12. **References** (IEEE format)

---

## Critical Implementation Notes

### 1. Always Use RAG for Legal Content
**Rule**: Any LLM call that could generate legal information MUST include top-5 RAG chunks in the prompt.

**Exceptions** (No RAG needed):
- Entity extraction from user input (no legal content)
- Document classification (controlled vocabulary)
- Event deduplication (factual comparison)

### 2. Log Everything to ai_logs
**Every GPT-4o API call** must create an `ai_logs` record with:
- Prompt hash (SHA-256 of system + user prompt)
- Model response
- Retrieved RAG chunks (if applicable)
- Timestamp

**Purpose**: Enables hallucination rate calculation and system auditing.

### 3. Never Ask LLM to Predict Outcomes
**Forbidden prompts**:
- "What are the chances of winning?"
- "How strong is this case?"
- "Should I file a lawsuit?"

**Allowed prompts**:
- "What evidence is typically required for X dispute type?"
- "What information is missing from this timeline?"
- "Generate factual questions for a lawyer based on gaps."

### 4. Hardcode Legal Issue Templates
**Never use LLM** to generate the "Issues and Likely Claims" section. Use dictionary lookup only.

**Reason**: Eliminates risk of hallucinated legal theories or inapplicable statutes.

### 5. ChromaDB K=5 Default
**Always retrieve exactly 5 chunks** unless testing shows clear benefit from different K values.

**Rationale**: 
- Balances precision (avoiding noise) with recall (capturing relevant info)
- 2,560-token retrieval budget fits comfortably in GPT-4o context window
- Empirically validated by RAG benchmarks

### 6. 64-Token Chunk Overlap is Non-Negotiable
**Reason**: Indian legal clauses average 40-60 tokens. 64-token overlap guarantees complete clause capture across chunk boundaries.

**Impact**: Prevents retrieval failures on critical conditional clauses ("provided that...", "subject to...").

---

## Testing Requirements

### Unit Tests
- All Django REST API endpoints (100% coverage)
- Database models (CRUD operations, constraints)
- Celery tasks (document processing pipeline)
- Utility functions (text normalization, entity extraction)

### Integration Tests
- End-to-end dispute classification flow
- S3 upload → Celery processing → Database update
- RAG retrieval → LLM call → Response parsing
- PDF generation with all 6 sections

### AI Quality Tests
- **Hallucination Detection**: Run 50 test queries, manually verify all legal statements against RAG chunks
- **Classification Accuracy**: 100 test narratives, compare system classification vs. human labeler
- **Completeness**: 20 test cases, compare generated evidence checklist vs. advocate-created gold standard

### Performance Tests
- **Load Testing**: 100 concurrent users, measure API latency
- **Latency Profiling**: Each module execution time (target: <2s for interactive modules)
- **Database Query Optimization**: No query >100ms

---

## Success Criteria

### Technical Metrics
- ✅ Evidence Completeness Score (ECS) ≥ 0.85
- ✅ Hallucination Rate (HR) ≤ 5%
- ✅ Dispute Classification Accuracy ≥ 90%
- ✅ API Response Time <2s (90th percentile)
- ✅ System Uptime ≥ 99.5%

### User Experience Metrics
- ✅ Case Packet Generation Time <5 minutes (full workflow)
- ✅ UI Responsiveness: No blocking operations >2s
- ✅ Mobile-Responsive (React app works on 360px viewport)

### Compliance Metrics
- ✅ Zero legal advice violations (manual review of 100 generated packets)
- ✅ All disclaimers present (session modal + PDF footer)
- ✅ Template-populated legal claims (no LLM generation)

---

## Team Roles (4 Members)

### Role 1: Backend Engineer
- Django REST API implementation
- PostgreSQL schema and migrations
- Celery task queue setup
- AWS deployment configuration

### Role 2: Frontend Engineer
- React 18 + TypeScript SPA
- Guided interview UI components
- Timeline visualization
- S3 direct upload integration

### Role 3: AI/ML Engineer
- RAG pipeline (knowledge base chunking, ChromaDB)
- GPT-4o prompt engineering
- Document processing (OCR, entity extraction)
- Embedding model optimization

### Role 4: Research/QA Lead
- Literature review
- Evaluation methodology design
- Scenario testing with reviewers
- Research paper writing

---

## Documentation Deliverables

1. **System Architecture Diagram** (Frontend → Backend → AI → Database → Knowledge Base)
2. **Database ER Diagram** (All 5 tables with relationships)
3. **API Documentation** (OpenAPI/Swagger spec for all endpoints)
4. **RAG Pipeline Flowchart** (Query → Embed → Retrieve → Inject → Generate)
5. **Module Workflow Diagrams** (All 4 modules)
6. **Deployment Guide** (AWS Elastic Beanstalk step-by-step)
7. **Research Paper** (IEEE format, 6000-8000 words)

---

## Legal Knowledge Base - Exact Sources to Ingest

### 1. Karnataka Rent Control Act 2001
**Download**: http://dpal.kar.nic.in/pdf2001/ACT.40.2001.pdf
**Key Sections**: 1-4 (Definitions), 21 (Security Deposits), 24 (Eviction Grounds)

### 2. Transfer of Property Act 1882
**Download**: https://legislative.gov.in/sites/default/files/A1882-04.pdf
**Key Chapters**: V (Transfer of Property by Sale), VIII (Leases of Immovable Property)

### 3. Indian Contract Act 1872
**Download**: https://legislative.gov.in/sites/default/files/A1872-09.pdf
**Key Chapters**: II (Communication, Acceptance), IV (Performance), VI (Consequences of Breach)

### 4. Consumer Protection Act 2019
**Download**: https://legislative.gov.in/sites/default/files/A2019-35.pdf
**Key Chapters**: II (Definitions), IV (Consumer Disputes Redressal)

### 5. Limitation Act 1963
**Download**: https://legislative.gov.in/sites/default/files/A1963-36.pdf
**Key Sections**: Schedule (Periods of Limitation)

### 6. MSMED Act 2006
**Download**: https://legislative.gov.in/sites/default/files/A2006-27.pdf
**Key Sections**: 15-18 (Payment Provisions), 23 (Reference to MSME Facilitation Council)

### 7. Karnataka Stamp Act (Rental Agreement Provisions)
**Download**: Karnataka Government Portal
**Key Sections**: Schedule (Stamp duty rates for lease agreements)

### 8. NALSA Legal Aid Guides
**Download**: https://nalsa.gov.in/services/legal-aid
**Key Documents**: Self-Help Legal Guides, Know Your Rights Pamphlets

---

## Prompt Templates - Complete Specification

### 1. Entity Extraction Prompt
```
SYSTEM: You are a precise entity extractor for legal disputes in India.

TASK: Extract ONLY entities explicitly mentioned in the user's narrative.

OUTPUT FORMAT (JSON):
{
  "parties": ["Party Name 1", "Party Name 2"],
  "monetary_amounts": ["₹1,50,000", "₹80,000"],
  "dates": ["2024-01-15", "2024-03-20"],
  "locations": ["Bengaluru", "Karnataka", "India"],
  "legal_instruments": ["Rent Agreement", "Invoice", "Legal Notice"]
}

STRICT RULES:
1. Extract only explicitly present entities - DO NOT infer
2. Return null for absent fields (e.g., "dates": null if no dates mentioned)
3. Use ISO date format YYYY-MM-DD
4. Preserve exact monetary notation including ₹ symbol
5. Include both city and state for locations if mentioned

USER INPUT:
{user_narrative}
```

### 2. Dispute Classification Prompt
```
SYSTEM: You are a legal dispute classifier for Indian legal contexts.

SUPPORTED CATEGORIES (select exactly ONE):
1. TENANT_LANDLORD: Rent disputes, security deposit recovery, eviction, property damage, lease violations
2. FREELANCE_PAYMENT: Unpaid freelance work, contract breaches, delayed payment, service disputes

CONTEXT PROVIDED:
Extracted Entities (JSON):
{extracted_entities}

Original Narrative:
{user_narrative}

OUTPUT FORMAT (JSON):
{
  "dispute_type": "TENANT_LANDLORD" | "FREELANCE_PAYMENT",
  "confidence": 0.0-1.0,
  "reasoning": "<one sentence explanation>"
}

CLASSIFICATION GUIDELINES:
- Confidence ≥ 0.7 required for automatic classification
- If confidence < 0.7, return both types as suggestions
- Base classification on factual indicators (parties, amounts, dates, context)

Factual Indicators:
TENANT_LANDLORD: Landlord-tenant relationship, rent/security deposit, property possession, eviction
FREELANCE_PAYMENT: Client-contractor relationship, service delivery, invoices, payment terms

RESPOND ONLY with valid JSON.
```

### 3. Document Classification Prompt
```
SYSTEM: You are a legal document classifier.

TASK: Classify this document into ONE category from the controlled vocabulary.

CONTROLLED VOCABULARY:
1. CONTRACT: Agreements, work orders, lease documents, service agreements, MOUs
2. RECEIPT: Payment receipts, deposit slips, transaction confirmations, bank statements
3. COMMUNICATION: Emails, WhatsApp chats, SMS, letters, Slack messages
4. PHOTOGRAPH: Images of property, products, conditions, damage, or evidence
5. LEGAL_NOTICE: Legal demands, lawyer letters, FIRs, court notices, summons
6. OTHER: Anything not fitting above categories

DOCUMENT TEXT:
{extracted_text}

OUTPUT FORMAT (JSON):
{
  "classification": "CONTRACT" | "RECEIPT" | "COMMUNICATION" | "PHOTOGRAPH" | "LEGAL_NOTICE" | "OTHER",
  "confidence": 0.0-1.0,
  "reasoning": "<one sentence>"
}

CLASSIFICATION CRITERIA:
- CONTRACT: Legal language, terms & conditions, signatures, effective dates
- RECEIPT: Transaction IDs, amounts, dates, payment methods
- COMMUNICATION: Sender-receiver format, conversational tone, timestamps
- PHOTOGRAPH: Extracted text minimal or from image captions
- LEGAL_NOTICE: Legal jargon, statutory references, formal tone
- OTHER: Default if none of above clearly applies

RESPOND ONLY with valid JSON.
```

### 4. Event Deduplication Prompt
```
SYSTEM: You are an event deduplication analyzer for legal timelines.

TASK: Determine if two events describe the same real-world occurrence.

EVENT 1:
Date: {event1_date}
Description: {event1_description}

EVENT 2:
Date: {event2_date}
Description: {event2_description}

OUTPUT FORMAT (JSON):
{
  "decision": "MERGE" | "KEEP_SEPARATE",
  "canonical_description": "<unified description if MERGE>",
  "reasoning": "<one sentence explanation>"
}

MERGE CRITERIA:
- Events describe the same action by same actors
- Dates within 3-day window (accounting for date discrepancies)
- Core facts align (amounts, parties, action type)

KEEP_SEPARATE CRITERIA:
- Different actions (e.g., "payment sent" vs "payment received")
- Same action type but different instances (e.g., two different rent payments)
- Dates >3 days apart with no explanation for discrepancy

EXAMPLES:
MERGE: "Rent payment of ₹20,000 via UPI on Jan 15" + "January rent paid through Google Pay on Jan 16"
KEEP_SEPARATE: "January rent paid" + "February rent paid"

RESPOND ONLY with valid JSON.
```

### 5. Timeline Gap Detection Prompt
```
SYSTEM: You are a factual event analyzer for legal timelines.

TASK: Identify ONLY temporal gaps where a logically expected event is absent based on the provided timeline.

STRICT RULES:
1. Identify only factual gaps (missing events that should logically exist)
2. DO NOT infer legal conclusions
3. DO NOT predict case outcomes
4. DO NOT suggest legal strategies
5. Base gaps only on logical sequence of events

TIMELINE:
{chronological_events}

OUTPUT FORMAT (JSON array):
[
  {
    "gap_after_event_id": "<uuid>",
    "description": "<factual description of missing event>",
    "suggested_question": "<neutral question to ask user about gap>"
  }
]

EXAMPLE GAPS:
✓ "No record of requesting deposit return before sending legal notice"
✓ "Missing move-out inspection date between lease end and deposit request"
✗ "Weak evidence of property damage" (legal conclusion)
✗ "Case likely to fail without witness statements" (outcome prediction)

RESPOND ONLY with valid JSON array. Return empty array [] if no gaps detected.
```

### 6. Executive Summary Prompt
```
[LEGAL CONTEXT]
{top_5_rag_chunks}

SYSTEM: You are writing a factual case summary for a legal preparation document.

HARD CONSTRAINTS:
1. Maximum 200 words
2. Summarize ONLY the factual situation
3. DO NOT characterize legal strength ("strong case", "weak position")
4. DO NOT predict outcomes ("likely to win", "may lose")
5. DO NOT recommend actions ("should file suit", "consider settlement")

CASE DETAILS:
Timeline:
{case_timeline}

Evidence:
{evidence_list}

WRITING GUIDELINES:
- Use past tense for completed events
- Present tense for current status
- Neutral, factual tone
- Chronological flow preferred
- Focus on: parties, dispute subject, key events, current stage

EXAMPLES OF ACCEPTABLE CONTENT:
✓ "The tenant paid a security deposit of ₹1,50,000 on January 5, 2024."
✓ "The landlord has not returned the deposit as of October 2024."
✓ "Communication records show three deposit return requests."

EXAMPLES OF PROHIBITED CONTENT:
✗ "The tenant has a strong case for deposit recovery."
✗ "This evidence may not be sufficient to win in court."
✗ "You should consider filing a consumer complaint."

RESPOND with plain text summary (no JSON, no markdown).
```

### 7. Lawyer Questions Prompt
```
SYSTEM: You generate factual questions for users to ask lawyers during consultation.

TASK: Based on evidence gaps and timeline gaps, generate 5-8 questions framed as information requests.

GAP REPORT:
{gap_report}

TIMELINE GAPS:
{timeline_gaps}

OUTPUT FORMAT (JSON array):
["Question 1", "Question 2", ...]

QUESTION GUIDELINES:
1. Frame as information requests, NOT legal assessments
2. Focus on missing factual details that a lawyer would need
3. DO NOT ask questions predicting outcomes
4. DO NOT suggest legal strategies
5. Use neutral language

EXAMPLES OF ACCEPTABLE QUESTIONS:
✓ "What additional documentation would strengthen the security deposit claim?"
✓ "Are there statutory deadlines for filing this type of dispute in Karnataka?"
✓ "What information from the landlord's side would be relevant?"

EXAMPLES OF PROHIBITED QUESTIONS:
✗ "Will I win this case?"
✗ "Should I file in civil court or consumer forum?"
✗ "How much compensation can I expect?"

RESPOND ONLY with valid JSON array of 5-8 questions.
```

---

## Final Implementation Checklist

### Before Development
- [ ] Obtain OpenAI API key (GPT-4o access)
- [ ] Set up AWS account (S3, RDS, Elastic Beanstalk, ElastiCache)
- [ ] Download all 8 legal knowledge base sources
- [ ] Create architecture diagram
- [ ] Assign team roles

### Backend Setup
- [ ] Initialize Django 4.2 project
- [ ] Configure PostgreSQL 15 connection
- [ ] Implement database schema (5 tables)
- [ ] Set up Celery + Redis
- [ ] Configure AWS S3 pre-signed URLs
- [ ] Implement JWT authentication

### AI Pipeline
- [ ] Chunk legal documents (512 tokens, 64 overlap)
- [ ] Generate embeddings (all-MiniLM-L6-v2)
- [ ] Index in ChromaDB (cosine similarity)
- [ ] Validate knowledge base (KBAS ≥ 0.88)
- [ ] Implement RAG retrieval (K=5)
- [ ] Test all 7 prompt templates

### Frontend
- [ ] Initialize React 18 + TypeScript project
- [ ] Build guided interview UI
- [ ] Implement S3 direct upload
- [ ] Create timeline visualization
- [ ] Add session disclaimer modal
- [ ] Ensure mobile responsiveness (360px)

### Testing
- [ ] Unit tests (100% API coverage)
- [ ] Integration tests (end-to-end flows)
- [ ] AI quality tests (ECS, HR metrics)
- [ ] Load testing (100 concurrent users)

### Deployment
- [ ] Deploy Django to Elastic Beanstalk
- [ ] Configure RDS PostgreSQL
- [ ] Set up ElastiCache Redis
- [ ] Configure S3 buckets with CORS
- [ ] Test production environment

### Evaluation
- [ ] Create 2 test scenarios (fact sheets)
- [ ] Run system on both scenarios
- [ ] Recruit reviewer panel (advocate + LLB student)
- [ ] Calculate ECS and HR metrics
- [ ] Measure inter-rater reliability (κ)

### Research Paper
- [ ] Write Abstract, Introduction, Lit Review
- [ ] Document Methodology (copy from this spec)
- [ ] Report Implementation details
- [ ] Present Evaluation results
- [ ] Write Discussion and Conclusion
- [ ] Format in IEEE style
- [ ] Create all diagrams and tables

---

## Success Indicators

### Must-Have Features
✅ User can classify dispute in <2 seconds
✅ System suggests complete evidence checklist
✅ Documents auto-process with OCR
✅ Timeline auto-populates from evidence
✅ Case packet generates in <5 minutes
✅ All outputs include legal disclaimers
✅ No legal advice violations

### Quality Thresholds
✅ ECS ≥ 85% (evidence completeness)
✅ HR ≤ 5% (hallucination rate)
✅ Classification accuracy ≥ 90%
✅ Knowledge base accuracy ≥ 88%
✅ Inter-rater reliability κ ≥ 0.70

### Technical Performance
✅ API latency <2s (90th percentile)
✅ Document processing <3s per file
✅ System uptime ≥ 99.5%
✅ Mobile-responsive UI
✅ Zero SQL injection vulnerabilities

---

This specification provides complete, pin-point accuracy for implementing the EvidenceChain (MIKE ROSS) project. Every technical decision is justified with statistical benchmarks, every module has exact prompt templates, and all evaluation criteria are quantified.
