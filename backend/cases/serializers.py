"""
Cases app serializers.

DRF serializers for all models and API request/response shapes.
"""

from rest_framework import serializers
from django.contrib.auth.models import User

from .models import (
    Case, EvidenceItem, Event, AILog, CasePacket,
    EvidenceTemplate, JurisdictionMapping, UserFeedback,
)
from .services import get_jurisdiction_laws, get_evidence_template


# ============================================================================
# USER
# ============================================================================

class UserBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']


# ============================================================================
# CASE
# ============================================================================

class CaseCreateSerializer(serializers.Serializer):
    """Input for POST /cases/create"""
    user_narrative = serializers.CharField()


class CaseListSerializer(serializers.ModelSerializer):
    """Compact representation for GET /cases/"""
    evidence_count = serializers.SerializerMethodField()
    timeline_event_count = serializers.SerializerMethodField()
    case_packet_generated = serializers.SerializerMethodField()

    class Meta:
        model = Case
        fields = [
            'case_id', 'dispute_type', 'jurisdiction', 'status',
            'created_at', 'evidence_count', 'timeline_event_count',
            'case_packet_generated',
        ]

    def get_evidence_count(self, obj):
        return obj.evidence_items.count()

    def get_timeline_event_count(self, obj):
        return obj.events.count()

    def get_case_packet_generated(self, obj):
        return hasattr(obj, 'case_packet') and obj.case_packet is not None


class CaseDetailSerializer(serializers.ModelSerializer):
    """Full representation for GET /cases/{id}"""
    evidence_items = serializers.SerializerMethodField()
    events = serializers.SerializerMethodField()
    applicable_laws = serializers.SerializerMethodField()

    class Meta:
        model = Case
        fields = [
            'case_id', 'dispute_type', 'dispute_stage', 'jurisdiction',
            'status', 'created_at', 'user_narrative',
            'classification_confidence', 'gap_report',
            'evidence_items', 'events', 'applicable_laws',
        ]

    def get_evidence_items(self, obj):
        items = obj.evidence_items.all()
        return EvidenceItemSerializer(items, many=True).data

    def get_events(self, obj):
        events = obj.events.all()
        return EventSerializer(events, many=True).data

    def get_applicable_laws(self, obj):
        if obj.dispute_type and obj.jurisdiction:
            return get_jurisdiction_laws(obj.dispute_type, obj.jurisdiction)
        return []


class CaseUpdateSerializer(serializers.ModelSerializer):
    """Input for PATCH /cases/{id}"""
    class Meta:
        model = Case
        fields = ['dispute_stage', 'status']
        extra_kwargs = {
            'dispute_stage': {'required': False},
            'status': {'required': False},
        }


# ============================================================================
# EVIDENCE
# ============================================================================

class EvidenceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvidenceItem
        fields = [
            'evidence_id', 'case', 'evidence_type', 'file_path',
            'extracted_text', 'classification_tag', 'completeness_flag',
            'upload_timestamp', 'file_size_bytes', 'mime_type',
            'processing_status', 'processing_error', 'extracted_entities',
        ]
        read_only_fields = [
            'evidence_id', 'upload_timestamp', 'extracted_text',
            'classification_tag', 'completeness_flag', 'processing_status',
            'processing_error', 'extracted_entities',
        ]


class EvidenceUpdateSerializer(serializers.ModelSerializer):
    """Input for PATCH /evidence/{id}"""
    class Meta:
        model = EvidenceItem
        fields = ['evidence_type']
        extra_kwargs = {
            'evidence_type': {'required': False},
        }


class PresignedUrlRequestSerializer(serializers.Serializer):
    """Input for POST /evidence/presigned-url"""
    case_id = serializers.UUIDField()
    evidence_type = serializers.CharField(max_length=100)
    filename = serializers.CharField(max_length=255)
    content_type = serializers.CharField(max_length=100)
    file_size = serializers.IntegerField()


class RegisterEvidenceSerializer(serializers.Serializer):
    """Input for POST /evidence/register"""
    evidence_id = serializers.UUIDField()
    s3_key = serializers.CharField(max_length=500)
    file_size = serializers.IntegerField()
    content_type = serializers.CharField(max_length=100)


# ============================================================================
# EVENTS / TIMELINE
# ============================================================================

class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            'event_id', 'case', 'event_date', 'actors',
            'action_description', 'evidence_refs',
            'legal_relevance_tag', 'source_type',
            'is_merged', 'merged_from_event_ids',
        ]
        read_only_fields = ['event_id', 'is_merged', 'merged_from_event_ids']


class EventCreateSerializer(serializers.Serializer):
    """Input for POST /cases/{id}/timeline/events"""
    event_date = serializers.DateField()
    action_description = serializers.CharField()
    actors = serializers.ListField(child=serializers.CharField(), default=list)
    evidence_refs = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class EventUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ['action_description', 'event_date', 'actors', 'evidence_refs']
        extra_kwargs = {field: {'required': False} for field in fields}


# ============================================================================
# CLASSIFICATION PIPELINE
# ============================================================================

class EntityExtractionSerializer(serializers.Serializer):
    """Input for POST /cases/{id}/classify/extract-entities"""
    narrative = serializers.CharField()


class CategorizeDisputeSerializer(serializers.Serializer):
    """Input for POST /cases/{id}/classify/categorize"""
    entities = serializers.DictField()
    narrative = serializers.CharField()


class ConfirmClassificationSerializer(serializers.Serializer):
    """Input for POST /cases/{id}/classify/confirm"""
    dispute_type = serializers.ChoiceField(choices=['TENANT_LANDLORD', 'FREELANCE_PAYMENT'])
    jurisdiction = serializers.CharField(max_length=100)


# ============================================================================
# CASE PACKET
# ============================================================================

class CasePacketSerializer(serializers.ModelSerializer):
    class Meta:
        model = CasePacket
        fields = [
            'packet_id', 'case', 'executive_summary', 'issues',
            'evidence_table', 'timeline', 'gap_report',
            'lawyer_questions', 'pdf_file_path',
            'generated_at', 'regeneration_count', 'last_regenerated_at',
        ]
        read_only_fields = fields


# ============================================================================
# AI LOGS
# ============================================================================

class AILogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AILog
        fields = [
            'log_id', 'case', 'module', 'timestamp',
            'prompt_hash', 'model_name', 'tokens_used',
            'latency_ms',
        ]
        # Full prompt and response excluded from list view for brevity


class AILogDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = AILog
        fields = '__all__'


# ============================================================================
# USER FEEDBACK
# ============================================================================

class UserFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserFeedback
        fields = [
            'feedback_id', 'user', 'case', 'ai_log',
            'feedback_type', 'feedback_text', 'created_at',
        ]
        read_only_fields = ['feedback_id', 'user', 'created_at']


# ============================================================================
# EVIDENCE TEMPLATE / JURISDICTION (reference data)
# ============================================================================

class EvidenceTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvidenceTemplate
        fields = '__all__'


class JurisdictionMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = JurisdictionMapping
        fields = '__all__'


# ============================================================================
# KNOWLEDGE BASE
# ============================================================================

class KnowledgeBaseSearchSerializer(serializers.Serializer):
    """Input for POST /knowledge-base/search"""
    query = serializers.CharField()
    top_k = serializers.IntegerField(default=5, required=False)
    dispute_type_filter = serializers.CharField(required=False, allow_blank=True)
