from django.contrib import admin
from .models import (
    Case, EvidenceItem, Event, AILog, CasePacket,
    EvidenceTemplate, JurisdictionMapping, UserFeedback
)


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ['case_id', 'user', 'dispute_type', 'status', 'jurisdiction', 'created_at']
    list_filter = ['dispute_type', 'status', 'jurisdiction']
    search_fields = ['case_id', 'user__username', 'user_narrative']
    readonly_fields = ['case_id', 'created_at']


@admin.register(EvidenceItem)
class EvidenceItemAdmin(admin.ModelAdmin):
    list_display = ['evidence_id', 'case', 'evidence_type', 'classification_tag', 'processing_status', 'completeness_flag']
    list_filter = ['classification_tag', 'processing_status', 'completeness_flag']
    search_fields = ['evidence_id', 'evidence_type']
    readonly_fields = ['evidence_id', 'upload_timestamp']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['event_id', 'case', 'event_date', 'action_description', 'source_type', 'is_merged']
    list_filter = ['source_type', 'is_merged']
    search_fields = ['action_description']
    readonly_fields = ['event_id']


@admin.register(AILog)
class AILogAdmin(admin.ModelAdmin):
    list_display = ['log_id', 'case', 'module', 'model_name', 'tokens_used', 'latency_ms', 'timestamp']
    list_filter = ['module', 'model_name']
    search_fields = ['prompt_hash']
    readonly_fields = ['log_id', 'timestamp']


@admin.register(CasePacket)
class CasePacketAdmin(admin.ModelAdmin):
    list_display = ['packet_id', 'case', 'generated_at', 'regeneration_count']
    readonly_fields = ['packet_id', 'generated_at']


@admin.register(EvidenceTemplate)
class EvidenceTemplateAdmin(admin.ModelAdmin):
    list_display = ['template_id', 'dispute_type', 'evidence_name', 'priority', 'display_order']
    list_filter = ['dispute_type', 'priority']
    ordering = ['dispute_type', 'display_order']


@admin.register(JurisdictionMapping)
class JurisdictionMappingAdmin(admin.ModelAdmin):
    list_display = ['mapping_id', 'dispute_type', 'jurisdiction']
    list_filter = ['dispute_type']


@admin.register(UserFeedback)
class UserFeedbackAdmin(admin.ModelAdmin):
    list_display = ['feedback_id', 'user', 'case', 'feedback_type', 'created_at']
    list_filter = ['feedback_type']
    readonly_fields = ['feedback_id', 'created_at']
