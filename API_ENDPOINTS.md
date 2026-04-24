# API Endpoints Specification - EvidenceChain REST API
# Django REST Framework implementation guide

"""
Base URL: https://api.evidencechain.com/api/v1/
Authentication: JWT Bearer Token
All requests require: Authorization: Bearer <token>
"""

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

POST /auth/register
"""
User registration
"""
Request:
{
    "username": "user@example.com",
    "password": "SecurePass123!",
    "first_name": "John",
    "last_name": "Doe"
}

Response (201 Created):
{
    "user_id": "uuid",
    "username": "user@example.com",
    "access_token": "jwt_token",
    "refresh_token": "refresh_token",
    "token_type": "Bearer",
    "expires_in": 86400
}

---

POST /auth/login
"""
User login
"""
Request:
{
    "username": "user@example.com",
    "password": "SecurePass123!"
}

Response (200 OK):
{
    "access_token": "jwt_token",
    "refresh_token": "refresh_token",
    "token_type": "Bearer",
    "expires_in": 86400,
    "user": {
        "user_id": "uuid",
        "username": "user@example.com",
        "first_name": "John",
        "last_name": "Doe"
    }
}

---

POST /auth/refresh
"""
Refresh access token
"""
Request:
{
    "refresh_token": "refresh_token"
}

Response (200 OK):
{
    "access_token": "new_jwt_token",
    "token_type": "Bearer",
    "expires_in": 86400
}

---

POST /auth/logout
"""
Invalidate tokens
"""
Request:
{
    "refresh_token": "refresh_token"
}

Response (204 No Content)


# ============================================================================
# CASE MANAGEMENT ENDPOINTS
# ============================================================================

POST /cases/create
"""
Create new case (initial step before classification)
"""
Request:
{
    "user_narrative": "My landlord hasn't returned my security deposit of ₹1,50,000..."
}

Response (201 Created):
{
    "case_id": "uuid",
    "status": "active",
    "created_at": "2024-01-15T10:30:00Z",
    "next_step": "classification"
}

---

GET /cases/
"""
List all cases for authenticated user
"""
Query Parameters:
- status: active|completed|archived (optional)
- dispute_type: TENANT_LANDLORD|FREELANCE_PAYMENT (optional)
- limit: int (default: 20)
- offset: int (default: 0)

Response (200 OK):
{
    "count": 5,
    "next": "https://api.evidencechain.com/api/v1/cases/?offset=20",
    "previous": null,
    "results": [
        {
            "case_id": "uuid",
            "dispute_type": "TENANT_LANDLORD",
            "jurisdiction": "Karnataka",
            "status": "active",
            "created_at": "2024-01-15T10:30:00Z",
            "evidence_count": 7,
            "timeline_event_count": 12,
            "case_packet_generated": false
        }
    ]
}

---

GET /cases/{case_id}
"""
Get detailed case information
"""
Response (200 OK):
{
    "case_id": "uuid",
    "dispute_type": "TENANT_LANDLORD",
    "dispute_stage": "evidence_collection",
    "jurisdiction": "Karnataka",
    "status": "active",
    "created_at": "2024-01-15T10:30:00Z",
    "user_narrative": "...",
    "classification_confidence": 0.92,
    "gap_report": {
        "critical_missing": ["Bank Transfer Records"],
        "supportive_missing": ["Move-out Photographs"],
        "completion_percentage": 60
    },
    "evidence_items": [...],
    "events": [...],
    "applicable_laws": [
        "Karnataka Rent Control Act 2001",
        "Transfer of Property Act 1882"
    ]
}

---

PATCH /cases/{case_id}
"""
Update case details
"""
Request:
{
    "dispute_stage": "timeline_construction",
    "status": "active"
}

Response (200 OK): <updated case object>

---

DELETE /cases/{case_id}
"""
Archive case (soft delete)
"""
Response (204 No Content)


# ============================================================================
# MODULE 1: DISPUTE CLASSIFICATION ENDPOINTS
# ============================================================================

POST /cases/{case_id}/classify/extract-entities
"""
Step 1: Extract named entities from narrative
Uses GPT-4o with RAG (if needed)
"""
Request:
{
    "narrative": "I paid ₹1,50,000 security deposit to landlord on Jan 5, 2024..."
}

Response (200 OK):
{
    "entities": {
        "parties": ["User (Tenant)", "Landlord"],
        "monetary_amounts": ["₹1,50,000"],
        "dates": ["2024-01-05"],
        "locations": ["Bengaluru", "Karnataka"],
        "legal_instruments": ["Security Deposit Receipt"]
    },
    "ai_log_id": "uuid",
    "processing_time_ms": 1250
}

---

POST /cases/{case_id}/classify/categorize
"""
Step 2: Classify dispute type
Uses extracted entities + narrative
"""
Request:
{
    "entities": {...},  # From previous step
    "narrative": "..."
}

Response (200 OK):
{
    "dispute_type": "TENANT_LANDLORD",
    "confidence": 0.92,
    "reasoning": "Security deposit non-return with landlord-tenant relationship indicated",
    "ai_log_id": "uuid",
    "requires_manual_confirmation": false
}

# If confidence < 0.7:
Response (200 OK):
{
    "requires_manual_confirmation": true,
    "suggestions": [
        {
            "dispute_type": "TENANT_LANDLORD",
            "confidence": 0.68,
            "reasoning": "..."
        },
        {
            "dispute_type": "FREELANCE_PAYMENT",
            "confidence": 0.32,
            "reasoning": "..."
        }
    ]
}

---

POST /cases/{case_id}/classify/confirm
"""
Step 3: User confirms classification
"""
Request:
{
    "dispute_type": "TENANT_LANDLORD",
    "jurisdiction": "Karnataka"
}

Response (200 OK):
{
    "case_id": "uuid",
    "dispute_type": "TENANT_LANDLORD",
    "jurisdiction": "Karnataka",
    "applicable_laws": [
        "Karnataka Rent Control Act 2001",
        "Transfer of Property Act 1882",
        "Specific Relief Act 1963"
    ],
    "next_step": "evidence_guidance"
}


# ============================================================================
# MODULE 2: EVIDENCE MANAGEMENT ENDPOINTS
# ============================================================================

GET /cases/{case_id}/evidence/template
"""
Get evidence template for dispute type
"""
Response (200 OK):
{
    "dispute_type": "TENANT_LANDLORD",
    "categories": {
        "critical": [
            {
                "template_id": "uuid",
                "name": "Rental/Lease Agreement",
                "description": "Signed rent agreement document",
                "display_order": 1,
                "collected": false
            },
            {
                "template_id": "uuid",
                "name": "Security Deposit Receipt",
                "description": "Proof of security deposit payment",
                "display_order": 2,
                "collected": true,
                "evidence_id": "uuid"  # If already uploaded
            }
        ],
        "supportive": [...],
        "optional": [...]
    },
    "completion_stats": {
        "critical_collected": 2,
        "critical_total": 3,
        "supportive_collected": 1,
        "supportive_total": 2,
        "overall_percentage": 60
    }
}

---

POST /evidence/presigned-url
"""
Request pre-signed S3 upload URL
Frontend uploads directly to S3
"""
Request:
{
    "case_id": "uuid",
    "evidence_type": "Rental Agreement",
    "filename": "lease_agreement.pdf",
    "content_type": "application/pdf",
    "file_size": 245760
}

Response (200 OK):
{
    "evidence_id": "uuid",
    "upload_url": "https://evidencechain-uploads.s3.amazonaws.com/...",
    "upload_fields": {
        "key": "case-uuid/evidence-uuid/lease_agreement.pdf",
        "AWSAccessKeyId": "...",
        "policy": "...",
        "signature": "..."
    },
    "expires_at": "2024-01-15T11:00:00Z"
}

---

POST /evidence/register
"""
Notify backend of successful S3 upload
Triggers Celery document processing pipeline
"""
Request:
{
    "evidence_id": "uuid",
    "s3_key": "case-uuid/evidence-uuid/lease_agreement.pdf",
    "file_size": 245760,
    "content_type": "application/pdf"
}

Response (202 Accepted):
{
    "evidence_id": "uuid",
    "processing_status": "queued",
    "estimated_completion": "2024-01-15T10:32:30Z",
    "check_status_url": "/evidence/{evidence_id}/status"
}

---

GET /evidence/{evidence_id}/status
"""
Check document processing status
"""
Response (200 OK):
{
    "evidence_id": "uuid",
    "processing_status": "completed",
    "extracted_text": "This lease agreement...",
    "classification": {
        "tag": "CONTRACT",
        "confidence": 0.95
    },
    "extracted_entities": {
        "dates": ["2024-01-01"],
        "parties": ["John Doe", "Landlord Name"],
        "amounts": ["₹20,000"]
    },
    "completeness_flag": true,
    "processing_completed_at": "2024-01-15T10:32:15Z"
}

# If processing failed:
Response (200 OK):
{
    "evidence_id": "uuid",
    "processing_status": "failed",
    "processing_error": "Unable to extract text from scanned PDF",
    "retry_available": true
}

---

GET /cases/{case_id}/evidence
"""
List all evidence items for case
"""
Response (200 OK):
{
    "count": 7,
    "items": [
        {
            "evidence_id": "uuid",
            "evidence_type": "Rental Agreement",
            "classification_tag": "CONTRACT",
            "file_path": "s3://...",
            "download_url": "https://presigned-download-url",
            "completeness_flag": true,
            "upload_timestamp": "2024-01-15T10:30:00Z",
            "file_size_bytes": 245760,
            "mime_type": "application/pdf"
        }
    ]
}

---

PATCH /evidence/{evidence_id}
"""
Update evidence metadata (user edits)
"""
Request:
{
    "evidence_type": "Updated Evidence Type",
    "user_notes": "This document shows..."
}

Response (200 OK): <updated evidence object>

---

DELETE /evidence/{evidence_id}
"""
Delete evidence item
"""
Response (204 No Content)

---

GET /cases/{case_id}/gap-report
"""
Get evidence gap analysis
"""
Response (200 OK):
{
    "case_id": "uuid",
    "generated_at": "2024-01-15T11:00:00Z",
    "gaps": [
        {
            "item": "Bank Transfer Records",
            "severity": "critical",
            "remediation": "Upload bank statements showing rent payments",
            "alternatives": ["UPI transaction screenshots", "Payment receipts"]
        }
    ],
    "completion_percentage": 60,
    "critical_gaps": 1,
    "supportive_gaps": 2
}


# ============================================================================
# MODULE 3: TIMELINE CONSTRUCTION ENDPOINTS
# ============================================================================

GET /cases/{case_id}/timeline
"""
Get chronological timeline of events
"""
Query Parameters:
- include_gaps: boolean (default: true)
- start_date: YYYY-MM-DD (optional)
- end_date: YYYY-MM-DD (optional)

Response (200 OK):
{
    "case_id": "uuid",
    "timeline_generated_at": "2024-01-15T12:00:00Z",
    "events": [
        {
            "event_id": "uuid",
            "event_date": "2024-01-01",
            "action_description": "Signed lease agreement for property",
            "actors": ["User", "Landlord"],
            "evidence_refs": ["evidence-uuid-1", "evidence-uuid-2"],
            "legal_relevance_tag": "contract_formation",
            "source_type": "auto_extracted"
        },
        {
            "type": "gap",
            "gap_after_event_id": "uuid",
            "description": "No record of deposit return request before legal notice",
            "suggested_question": "Did you contact the landlord about the deposit?"
        }
    ],
    "stats": {
        "total_events": 12,
        "auto_extracted": 10,
        "manual_entries": 2,
        "gaps_detected": 2,
        "date_range": {
            "earliest": "2024-01-01",
            "latest": "2024-10-15"
        }
    }
}

---

POST /cases/{case_id}/timeline/events
"""
Add manual timeline event
"""
Request:
{
    "event_date": "2024-06-15",
    "action_description": "Sent WhatsApp message requesting deposit return",
    "actors": ["User", "Landlord"],
    "evidence_refs": ["evidence-uuid-3"]
}

Response (201 Created):
{
    "event_id": "uuid",
    "event_date": "2024-06-15",
    "action_description": "Sent WhatsApp message requesting deposit return",
    "source_type": "manual_entry",
    "created_at": "2024-01-15T12:05:00Z"
}

---

PATCH /timeline/events/{event_id}
"""
Edit timeline event
"""
Request:
{
    "action_description": "Updated description",
    "event_date": "2024-06-16"
}

Response (200 OK): <updated event object>

---

DELETE /timeline/events/{event_id}
"""
Delete timeline event
"""
Response (204 No Content)

---

POST /cases/{case_id}/timeline/deduplicate
"""
Trigger AI deduplication analysis
"""
Response (200 OK):
{
    "duplicates_found": 3,
    "merged_events": [
        {
            "canonical_event_id": "uuid",
            "merged_from": ["event-uuid-1", "event-uuid-2"],
            "reasoning": "Same rent payment, 1-day date discrepancy"
        }
    ],
    "timeline_updated": true
}


# ============================================================================
# MODULE 4: CASE PACKET GENERATION ENDPOINTS
# ============================================================================

POST /cases/{case_id}/case-packet/generate
"""
Generate complete case packet (all 6 sections)
Asynchronous process
"""
Response (202 Accepted):
{
    "packet_id": "uuid",
    "status": "generating",
    "estimated_completion": "2024-01-15T12:08:00Z",
    "check_status_url": "/case-packets/{packet_id}/status"
}

---

GET /case-packets/{packet_id}/status
"""
Check case packet generation status
"""
Response (200 OK):
{
    "packet_id": "uuid",
    "status": "completed",
    "generated_at": "2024-01-15T12:07:45Z",
    "sections_completed": {
        "executive_summary": true,
        "issues": true,
        "evidence_table": true,
        "timeline": true,
        "gap_report": true,
        "lawyer_questions": true
    },
    "pdf_available": true,
    "download_url": "https://presigned-pdf-url"
}

---

GET /case-packets/{packet_id}
"""
Get case packet JSON data
"""
Response (200 OK):
{
    "packet_id": "uuid",
    "case_id": "uuid",
    "generated_at": "2024-01-15T12:07:45Z",
    
    "executive_summary": "This case involves a security deposit dispute...",
    
    "issues": [
        {
            "issue": "Security Deposit Recovery",
            "applicable_law": "Karnataka Rent Control Act 2001, Section 21",
            "description": "Recovery of ₹1,50,000 security deposit"
        }
    ],
    
    "evidence_table": [
        {
            "document_name": "Rental Agreement",
            "type": "CONTRACT",
            "date": "2024-01-01",
            "status": "Complete",
            "relevance": "Critical - Establishes tenancy"
        }
    ],
    
    "timeline": [...],
    
    "gap_report": {
        "critical_missing": [...],
        "supportive_missing": [...]
    },
    
    "lawyer_questions": [
        "What additional documentation would strengthen the security deposit claim?",
        "Are there statutory deadlines for filing this type of dispute in Karnataka?"
    ]
}

---

GET /case-packets/{packet_id}/download
"""
Download case packet as PDF
"""
Response (200 OK):
Content-Type: application/pdf
Content-Disposition: attachment; filename="case_packet_{case_id}.pdf"

<Binary PDF data>

---

POST /case-packets/{packet_id}/regenerate
"""
Regenerate case packet (if case data updated)
"""
Response (202 Accepted):
{
    "packet_id": "uuid",  # Same packet_id, incremented regeneration_count
    "status": "regenerating",
    "regeneration_count": 2
}


# ============================================================================
# AI INSIGHTS & ANALYTICS ENDPOINTS
# ============================================================================

GET /cases/{case_id}/ai-insights
"""
Get AI-powered insights and recommendations
"""
Response (200 OK):
{
    "case_id": "uuid",
    "insights_generated_at": "2024-01-15T12:10:00Z",
    
    "evidence_strength": {
        "critical_coverage": 67,  # Percentage
        "supportive_coverage": 50,
        "overall_score": 60,
        "missing_critical": ["Bank Transfer Records"]
    },
    
    "timeline_completeness": {
        "events_count": 12,
        "gaps_detected": 2,
        "date_coverage_days": 287
    },
    
    "next_recommended_actions": [
        "Upload bank transfer records (Critical)",
        "Add event: Deposit return request date",
        "Review timeline gaps"
    ]
}

---

GET /ai-logs
"""
Get AI interaction logs (for debugging/auditing)
Admin/development only
"""
Query Parameters:
- case_id: uuid (optional)
- module: classification|evidence_guidance|document_processing|timeline|case_packet
- start_date: YYYY-MM-DD
- end_date: YYYY-MM-DD

Response (200 OK):
{
    "count": 45,
    "logs": [
        {
            "log_id": "uuid",
            "case_id": "uuid",
            "module": "classification",
            "timestamp": "2024-01-15T10:31:00Z",
            "prompt_hash": "sha256-hash",
            "model_name": "gpt-4o",
            "tokens_used": 450,
            "latency_ms": 1250,
            "retrieved_chunks_count": 5
        }
    ]
}


# ============================================================================
# KNOWLEDGE BASE / RAG ENDPOINTS
# ============================================================================

POST /knowledge-base/search
"""
Search legal knowledge base (ChromaDB)
Direct RAG query for testing/exploration
"""
Request:
{
    "query": "security deposit return timeline in Karnataka",
    "top_k": 5,
    "dispute_type_filter": "TENANT_LANDLORD"
}

Response (200 OK):
{
    "query": "security deposit return timeline in Karnataka",
    "chunks": [
        {
            "chunk_id": "KRCA_2001_S21_C003",
            "text": "Under Section 21 of the Karnataka Rent Control Act...",
            "source_document": "Karnataka Rent Control Act 2001",
            "section": "Section 21 - Security Deposits",
            "similarity_score": 0.89
        }
    ],
    "processing_time_ms": 67
}

---

GET /knowledge-base/stats
"""
Knowledge base statistics
"""
Response (200 OK):
{
    "total_chunks": 1200,
    "source_documents": 8,
    "dispute_type_coverage": {
        "TENANT_LANDLORD": 650,
        "FREELANCE_PAYMENT": 550
    },
    "indexed_at": "2024-01-10T00:00:00Z",
    "embedding_model": "all-MiniLM-L6-v2",
    "embedding_dimensions": 384
}


# ============================================================================
# USER FEEDBACK ENDPOINTS
# ============================================================================

POST /feedback
"""
Submit user feedback on AI outputs
"""
Request:
{
    "case_id": "uuid",
    "ai_log_id": "uuid",  # Optional
    "feedback_type": "hallucination",
    "feedback_text": "The legal citation mentioned is incorrect..."
}

Response (201 Created):
{
    "feedback_id": "uuid",
    "created_at": "2024-01-15T12:15:00Z",
    "status": "submitted"
}


# ============================================================================
# SYSTEM HEALTH & MONITORING ENDPOINTS
# ============================================================================

GET /health
"""
Health check
"""
Response (200 OK):
{
    "status": "healthy",
    "timestamp": "2024-01-15T12:20:00Z",
    "services": {
        "database": "ok",
        "redis": "ok",
        "s3": "ok",
        "chromadb": "ok",
        "openai_api": "ok"
    }
}

---

GET /metrics
"""
System metrics (Prometheus format)
Admin only
"""
Response (200 OK):
# HELP api_requests_total Total API requests
# TYPE api_requests_total counter
api_requests_total{endpoint="/cases/create",method="POST"} 1234

# HELP ai_inference_latency_seconds AI inference latency
# TYPE ai_inference_latency_seconds histogram
ai_inference_latency_seconds_bucket{module="classification",le="1.0"} 450
...
