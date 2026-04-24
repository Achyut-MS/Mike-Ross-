# models.py - EvidenceChain Django Models
# Implements the exact PostgreSQL schema specified in the methodology

import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class Case(models.Model):
    """
    Primary case entity representing a user's dispute
    """
    DISPUTE_TYPE_CHOICES = [
        ('TENANT_LANDLORD', 'Tenant-Landlord Dispute'),
        ('FREELANCE_PAYMENT', 'Freelance/Contract Payment Dispute'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
    ]
    
    case_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cases')
    dispute_type = models.CharField(max_length=50, choices=DISPUTE_TYPE_CHOICES)
    dispute_stage = models.CharField(max_length=50, blank=True)
    jurisdiction = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    gap_report = models.JSONField(null=True, blank=True)
    
    # Additional metadata
    classification_confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        null=True,
        blank=True
    )
    user_narrative = models.TextField(blank=True)
    
    class Meta:
        db_table = 'cases'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['dispute_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Case {self.case_id} - {self.get_dispute_type_display()}"


class EvidenceItem(models.Model):
    """
    Individual evidence document/file uploaded by user
    """
    CLASSIFICATION_CHOICES = [
        ('CONTRACT', 'Contract'),
        ('RECEIPT', 'Receipt'),
        ('COMMUNICATION', 'Communication'),
        ('PHOTOGRAPH', 'Photograph'),
        ('LEGAL_NOTICE', 'Legal Notice'),
        ('OTHER', 'Other'),
    ]
    
    evidence_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='evidence_items')
    evidence_type = models.CharField(max_length=100)  # Template type (e.g., "Rental Agreement")
    file_path = models.CharField(max_length=500)  # S3 URI
    extracted_text = models.TextField(blank=True)
    classification_tag = models.CharField(
        max_length=100,
        choices=CLASSIFICATION_CHOICES,
        default='OTHER'
    )
    completeness_flag = models.BooleanField(default=False)
    upload_timestamp = models.DateTimeField(auto_now_add=True)
    
    # Additional processing metadata
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    processing_error = models.TextField(blank=True)
    
    # Extracted entities (from GPT-4o)
    extracted_entities = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = 'evidence_items'
        ordering = ['upload_timestamp']
        indexes = [
            models.Index(fields=['case', 'classification_tag']),
            models.Index(fields=['processing_status']),
        ]
    
    def __str__(self):
        return f"Evidence {self.evidence_id} - {self.evidence_type}"


class Event(models.Model):
    """
    Timeline event extracted from evidence or manually entered
    """
    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='events')
    event_date = models.DateField(null=True, blank=True)  # Null = undated event
    actors = models.JSONField(default=list)  # Array of party names
    action_description = models.TextField()
    evidence_refs = models.JSONField(default=list)  # Array of evidence_id UUIDs
    legal_relevance_tag = models.CharField(max_length=100, blank=True)
    
    # Source tracking
    source_type = models.CharField(
        max_length=20,
        choices=[
            ('auto_extracted', 'Auto-Extracted from Evidence'),
            ('manual_entry', 'Manual User Entry'),
        ],
        default='auto_extracted'
    )
    
    # Deduplication tracking
    is_merged = models.BooleanField(default=False)
    merged_from_event_ids = models.JSONField(default=list)
    
    class Meta:
        db_table = 'events'
        ordering = ['event_date', 'event_id']
        indexes = [
            models.Index(fields=['case', 'event_date']),
        ]
    
    def __str__(self):
        date_str = self.event_date.strftime('%Y-%m-%d') if self.event_date else 'UNDATED'
        return f"Event {date_str}: {self.action_description[:50]}"


class AILog(models.Model):
    """
    Comprehensive logging of all AI/LLM interactions
    Critical for hallucination rate calculation
    """
    MODULE_CHOICES = [
        ('classification', 'Dispute Classification'),
        ('evidence_guidance', 'Evidence Guidance'),
        ('document_processing', 'Document Processing'),
        ('timeline', 'Timeline Construction'),
        ('case_packet', 'Case Packet Generation'),
    ]
    
    log_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='ai_logs', null=True, blank=True)
    module = models.CharField(max_length=50, choices=MODULE_CHOICES)
    prompt_hash = models.CharField(max_length=64)  # SHA-256
    model_response = models.TextField()
    retrieved_chunks = models.JSONField(null=True, blank=True)  # RAG chunks
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Detailed tracking
    full_prompt = models.TextField(blank=True)  # Store for audit
    model_name = models.CharField(max_length=50, default='gpt-4o')
    tokens_used = models.IntegerField(null=True, blank=True)
    latency_ms = models.IntegerField(null=True, blank=True)
    
    # Similarity scores for RAG chunks
    chunk_similarity_scores = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = 'ai_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['case', 'module']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['prompt_hash']),
        ]
    
    def __str__(self):
        return f"AI Log {self.log_id} - {self.get_module_display()}"


class CasePacket(models.Model):
    """
    Final generated case packet with all 6 sections
    """
    packet_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.OneToOneField(Case, on_delete=models.CASCADE, related_name='case_packet')
    executive_summary = models.TextField()
    issues = models.JSONField()  # Template-populated (no LLM)
    evidence_table = models.JSONField()
    timeline = models.JSONField()
    gap_report = models.JSONField()
    generated_at = models.DateTimeField(auto_now_add=True)
    
    # Lawyer questions (LLM-generated)
    lawyer_questions = models.JSONField(default=list)
    
    # PDF file path
    pdf_file_path = models.CharField(max_length=500, blank=True)
    
    # Regeneration tracking
    regeneration_count = models.IntegerField(default=0)
    last_regenerated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'case_packets'
        ordering = ['-generated_at']
    
    def __str__(self):
        return f"Case Packet for {self.case.case_id}"


# Additional models for future extensibility

class EvidenceTemplate(models.Model):
    """
    Hardcoded evidence templates for each dispute type
    Separated from code for easier updates
    """
    PRIORITY_CHOICES = [
        ('critical', 'Critical'),
        ('supportive', 'Supportive'),
        ('optional', 'Optional'),
    ]
    
    template_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dispute_type = models.CharField(max_length=50)
    evidence_name = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES)
    display_order = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'evidence_templates'
        ordering = ['dispute_type', 'display_order']
        unique_together = ['dispute_type', 'evidence_name']
    
    def __str__(self):
        return f"{self.dispute_type} - {self.evidence_name}"


class JurisdictionMapping(models.Model):
    """
    Jurisdiction to applicable laws mapping
    """
    mapping_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dispute_type = models.CharField(max_length=50)
    jurisdiction = models.CharField(max_length=100)
    applicable_laws = models.JSONField()  # Array of law names
    
    class Meta:
        db_table = 'jurisdiction_mappings'
        unique_together = ['dispute_type', 'jurisdiction']
    
    def __str__(self):
        return f"{self.dispute_type} - {self.jurisdiction}"


class UserFeedback(models.Model):
    """
    User feedback on AI outputs for continuous improvement
    """
    feedback_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, null=True, blank=True)
    ai_log = models.ForeignKey(AILog, on_delete=models.CASCADE, null=True, blank=True)
    
    feedback_type = models.CharField(
        max_length=50,
        choices=[
            ('classification_error', 'Classification Error'),
            ('missing_evidence', 'Missing Evidence Item'),
            ('incorrect_timeline', 'Incorrect Timeline'),
            ('hallucination', 'Hallucinated Content'),
            ('other', 'Other'),
        ]
    )
    feedback_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'user_feedback'
        ordering = ['-created_at']
