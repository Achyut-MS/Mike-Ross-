# tasks.py - Celery Asynchronous Tasks
# Document processing pipeline for evidence uploads

import os
import magic
import pytesseract
from PIL import Image
import pdfplumber
from celery import shared_task, chain
import boto3

from .models import EvidenceItem, Event, Case
from .ai_service import ai_service


# AWS S3 Client
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_S3_REGION', 'ap-south-1')
)


@shared_task(bind=True, max_retries=3)
def process_uploaded_document(self, evidence_id: str):
    """
    Master orchestration task for document processing pipeline
    Chains multiple subtasks together
    """
    try:
        # Chain: download → detect format → extract text → classify → extract entities → check completeness
        pipeline = chain(
            download_from_s3.s(evidence_id),
            detect_file_format.s(evidence_id),
            extract_text.s(evidence_id),
            classify_document_task.s(evidence_id),
            extract_document_entities_task.s(evidence_id),
            check_completeness.s(evidence_id),
            cleanup_temp_files.s(evidence_id)
        )
        
        result = pipeline.apply_async()
        return result.get()
        
    except Exception as exc:
        # Update evidence item with error
        evidence = EvidenceItem.objects.get(evidence_id=evidence_id)
        evidence.processing_status = 'failed'
        evidence.processing_error = str(exc)
        evidence.save()
        
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task
def download_from_s3(evidence_id: str) -> str:
    """
    Step 1: Download file from S3 to temp directory
    """
    evidence = EvidenceItem.objects.get(evidence_id=evidence_id)
    evidence.processing_status = 'processing'
    evidence.save()
    
    # Parse S3 URI
    # Format: s3://bucket-name/case-uuid/evidence-uuid/filename.pdf
    s3_uri = evidence.file_path
    bucket_name = os.getenv('AWS_S3_BUCKET_UPLOADS')
    s3_key = s3_uri.replace(f's3://{bucket_name}/', '')
    
    # Download to temp
    temp_path = f'/tmp/{evidence_id}'
    os.makedirs(temp_path, exist_ok=True)
    
    local_file = os.path.join(temp_path, os.path.basename(s3_key))
    
    s3_client.download_file(bucket_name, s3_key, local_file)
    
    return local_file


@shared_task
def detect_file_format(local_file: str, evidence_id: str) -> dict:
    """
    Step 2: Detect file format using python-magic
    """
    evidence = EvidenceItem.objects.get(evidence_id=evidence_id)
    
    # Detect MIME type
    mime = magic.Magic(mime=True)
    mime_type = mime.from_file(local_file)
    
    # Update evidence
    evidence.mime_type = mime_type
    evidence.file_size_bytes = os.path.getsize(local_file)
    evidence.save()
    
    return {
        'local_file': local_file,
        'mime_type': mime_type
    }


@shared_task
def extract_text(file_info: dict, evidence_id: str) -> dict:
    """
    Step 3: Extract text using appropriate method
    - Images: Tesseract OCR
    - PDFs: Check if scanned or digital
        - Scanned: Tesseract OCR
        - Digital: pdfplumber
    """
    local_file = file_info['local_file']
    mime_type = file_info['mime_type']
    
    evidence = EvidenceItem.objects.get(evidence_id=evidence_id)
    
    extracted_text = ""
    
    try:
        # Image files
        if mime_type in ['image/jpeg', 'image/png', 'image/jpg', 'image/webp']:
            image = Image.open(local_file)
            extracted_text = pytesseract.image_to_string(image)
        
        # PDF files
        elif mime_type == 'application/pdf':
            # Check if scanned
            if is_scanned_pdf(local_file):
                # Convert PDF to images and OCR
                extracted_text = extract_text_from_scanned_pdf(local_file)
            else:
                # Digital PDF - direct text extraction
                with pdfplumber.open(local_file) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            extracted_text += page_text + "\n"
        
        # Text files
        elif mime_type.startswith('text/'):
            with open(local_file, 'r', encoding='utf-8', errors='ignore') as f:
                extracted_text = f.read()
        
        # Normalize text
        extracted_text = normalize_text(extracted_text)
        
        # Update evidence
        evidence.extracted_text = extracted_text
        evidence.save()
        
    except Exception as e:
        evidence.processing_error = f"Text extraction failed: {str(e)}"
        evidence.save()
        raise
    
    return {
        'local_file': local_file,
        'extracted_text': extracted_text
    }


def is_scanned_pdf(pdf_path: str) -> bool:
    """
    Heuristic to detect if PDF is scanned
    If first page has no extractable text, likely scanned
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if len(pdf.pages) == 0:
                return False
            
            first_page_text = pdf.pages[0].extract_text()
            
            # If less than 50 characters, likely scanned
            if not first_page_text or len(first_page_text.strip()) < 50:
                return True
            
            return False
    except Exception:
        return True  # Default to scanned if uncertain


def extract_text_from_scanned_pdf(pdf_path: str) -> str:
    """
    Convert PDF pages to images and OCR
    """
    from pdf2image import convert_from_path
    
    images = convert_from_path(pdf_path, dpi=300)
    
    extracted_text = ""
    for i, image in enumerate(images):
        page_text = pytesseract.image_to_string(image)
        extracted_text += f"\n--- Page {i+1} ---\n{page_text}"
    
    return extracted_text


def normalize_text(text: str) -> str:
    """
    Normalize whitespace and remove non-UTF-8 characters
    """
    import re
    
    # Remove non-UTF-8 characters
    text = text.encode('utf-8', errors='ignore').decode('utf-8')
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text


@shared_task
def classify_document_task(text_info: dict, evidence_id: str) -> dict:
    """
    Step 4: Classify document using AI
    """
    evidence = EvidenceItem.objects.get(evidence_id=evidence_id)
    extracted_text = text_info['extracted_text']
    
    # Call AI service
    classification_result = ai_service.classify_document(
        case_id=str(evidence.case.case_id),
        extracted_text=extracted_text
    )
    
    # Update evidence
    evidence.classification_tag = classification_result['classification']
    evidence.save()
    
    text_info['classification'] = classification_result
    return text_info


@shared_task
def extract_document_entities_task(text_info: dict, evidence_id: str) -> dict:
    """
    Step 5: Extract entities from document (dates, parties, amounts, clauses)
    """
    evidence = EvidenceItem.objects.get(evidence_id=evidence_id)
    extracted_text = text_info['extracted_text']
    
    # Call AI service
    entities_result = ai_service.extract_document_entities(
        case_id=str(evidence.case.case_id),
        extracted_text=extracted_text
    )
    
    # Update evidence
    evidence.extracted_entities = entities_result['entities']
    evidence.save()
    
    # Auto-create timeline events from extracted dates
    create_timeline_events_from_entities(evidence_id, entities_result['entities'])
    
    text_info['entities'] = entities_result
    return text_info


def create_timeline_events_from_entities(evidence_id: str, entities: dict):
    """
    Auto-create timeline events from extracted entities
    """
    evidence = EvidenceItem.objects.get(evidence_id=evidence_id)
    case = evidence.case
    
    dates = entities.get('dates', [])
    parties = entities.get('parties', [])
    key_clauses = entities.get('key_clauses', [])
    
    # Create events for key dates
    for date_str in dates:
        if date_str and date_str != 'null':
            try:
                from datetime import datetime
                event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                # Create event
                Event.objects.create(
                    case=case,
                    event_date=event_date,
                    actors=parties[:2] if parties else [],  # First 2 parties
                    action_description=f"Event from {evidence.evidence_type}",
                    evidence_refs=[str(evidence_id)],
                    source_type='auto_extracted'
                )
            except ValueError:
                pass  # Invalid date format


@shared_task
def check_completeness(text_info: dict, evidence_id: str) -> dict:
    """
    Step 6: Check if evidence item is complete
    Cross-reference extracted entities with template requirements
    """
    evidence = EvidenceItem.objects.get(evidence_id=evidence_id)
    entities = evidence.extracted_entities or {}
    
    # Completeness logic based on evidence type
    is_complete = False
    
    if evidence.classification_tag == 'CONTRACT':
        # Contract should have: dates, parties, amounts
        if entities.get('dates') and entities.get('parties'):
            is_complete = True
    
    elif evidence.classification_tag == 'RECEIPT':
        # Receipt should have: amounts, dates
        if entities.get('monetary_amounts') and entities.get('dates'):
            is_complete = True
    
    elif evidence.classification_tag == 'COMMUNICATION':
        # Communication should have: dates, parties
        if entities.get('dates') and entities.get('parties'):
            is_complete = True
    
    elif evidence.classification_tag == 'PHOTOGRAPH':
        # Photographs always considered complete if uploaded
        is_complete = True
    
    elif evidence.classification_tag == 'LEGAL_NOTICE':
        # Legal notice should have: dates, parties
        if entities.get('dates') and entities.get('parties'):
            is_complete = True
    
    # Update evidence
    evidence.completeness_flag = is_complete
    evidence.processing_status = 'completed'
    evidence.save()
    
    # Update case gap report
    update_case_gap_report(evidence.case.case_id)
    
    return text_info


def update_case_gap_report(case_id: str):
    """
    Regenerate gap report after evidence processing
    """
    from .services import generate_gap_report
    
    gap_report = generate_gap_report(case_id)
    
    case = Case.objects.get(case_id=case_id)
    case.gap_report = gap_report
    case.save()


@shared_task
def cleanup_temp_files(text_info: dict, evidence_id: str):
    """
    Step 7: Clean up temporary files
    """
    local_file = text_info.get('local_file')
    
    if local_file and os.path.exists(local_file):
        os.remove(local_file)
        
        # Remove temp directory if empty
        temp_dir = os.path.dirname(local_file)
        if os.path.exists(temp_dir) and not os.listdir(temp_dir):
            os.rmdir(temp_dir)
    
    return {'status': 'completed', 'evidence_id': evidence_id}


# ============================================================================
# SCHEDULED TASKS
# ============================================================================

@shared_task
def cleanup_old_temp_files():
    """
    Periodic task to clean up old temp files
    Run daily
    """
    import time
    temp_dir = '/tmp'
    
    current_time = time.time()
    max_age = 24 * 3600  # 24 hours
    
    for root, dirs, files in os.walk(temp_dir):
        for filename in files:
            filepath = os.path.join(root, filename)
            
            # Check file age
            if os.path.getmtime(filepath) < (current_time - max_age):
                try:
                    os.remove(filepath)
                except Exception:
                    pass


@shared_task
def generate_daily_metrics():
    """
    Generate daily system metrics
    """
    from .models import AILog, Case, EvidenceItem
    from datetime import datetime, timedelta
    
    yesterday = datetime.now() - timedelta(days=1)
    
    metrics = {
        'date': yesterday.date().isoformat(),
        'cases_created': Case.objects.filter(created_at__date=yesterday.date()).count(),
        'evidence_uploaded': EvidenceItem.objects.filter(upload_timestamp__date=yesterday.date()).count(),
        'ai_calls': AILog.objects.filter(timestamp__date=yesterday.date()).count(),
        'avg_latency_ms': AILog.objects.filter(
            timestamp__date=yesterday.date()
        ).aggregate(models.Avg('latency_ms'))['latency_ms__avg'],
        'total_tokens_used': AILog.objects.filter(
            timestamp__date=yesterday.date()
        ).aggregate(models.Sum('tokens_used'))['tokens_used__sum']
    }
    
    # Log to metrics system (Prometheus/CloudWatch/etc.)
    print(f"Daily metrics: {metrics}")
    
    return metrics
