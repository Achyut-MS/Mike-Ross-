"""
Cases app URL configuration.

Maps all API endpoints from API_ENDPOINTS.md to their views.
"""

from django.urls import path

from . import views

app_name = 'cases'

urlpatterns = [
    # ---- Case Management ----
    path('cases/', views.CaseListCreateView.as_view(), name='case-list'),
    path('cases/create', views.CaseListCreateView.as_view(), name='case-create'),
    path('cases/<uuid:case_id>', views.CaseDetailView.as_view(), name='case-detail'),

    # ---- Module 1: Dispute Classification ----
    path('cases/<uuid:case_id>/classify/extract-entities', views.ExtractEntitiesView.as_view(), name='classify-extract'),
    path('cases/<uuid:case_id>/classify/categorize', views.CategorizeDisputeView.as_view(), name='classify-categorize'),
    path('cases/<uuid:case_id>/classify/confirm', views.ConfirmClassificationView.as_view(), name='classify-confirm'),

    # ---- Module 2: Evidence Management ----
    path('cases/<uuid:case_id>/evidence/template', views.EvidenceTemplateView.as_view(), name='evidence-template'),
    path('cases/<uuid:case_id>/evidence', views.CaseEvidenceListView.as_view(), name='case-evidence-list'),
    path('cases/<uuid:case_id>/gap-report', views.GapReportView.as_view(), name='gap-report'),
    path('evidence/presigned-url', views.PresignedUrlView.as_view(), name='presigned-url'),
    path('evidence/register', views.RegisterEvidenceView.as_view(), name='evidence-register'),
    path('evidence/<uuid:evidence_id>/status', views.EvidenceStatusView.as_view(), name='evidence-status'),
    path('evidence/<uuid:evidence_id>', views.EvidenceUpdateDeleteView.as_view(), name='evidence-detail'),

    # ---- Module 3: Timeline Construction ----
    path('cases/<uuid:case_id>/timeline', views.TimelineView.as_view(), name='timeline'),
    path('cases/<uuid:case_id>/timeline/events', views.TimelineEventCreateView.as_view(), name='timeline-event-create'),
    path('cases/<uuid:case_id>/timeline/deduplicate', views.DeduplicateTimelineView.as_view(), name='timeline-deduplicate'),
    path('timeline/events/<uuid:event_id>', views.TimelineEventUpdateDeleteView.as_view(), name='timeline-event-detail'),

    # ---- Module 4: Case Packet Generation ----
    path('cases/<uuid:case_id>/case-packet/generate', views.GenerateCasePacketView.as_view(), name='case-packet-generate'),
    path('case-packets/<uuid:packet_id>/status', views.CasePacketStatusView.as_view(), name='case-packet-status'),
    path('case-packets/<uuid:packet_id>', views.CasePacketDetailView.as_view(), name='case-packet-detail'),
    path('case-packets/<uuid:packet_id>/download', views.CasePacketDownloadView.as_view(), name='case-packet-download'),
    path('case-packets/<uuid:packet_id>/regenerate', views.RegenerateCasePacketView.as_view(), name='case-packet-regenerate'),

    # ---- AI Insights & Analytics ----
    path('cases/<uuid:case_id>/ai-insights', views.AIInsightsView.as_view(), name='ai-insights'),
    path('ai-logs', views.AILogListView.as_view(), name='ai-logs'),

    # ---- Knowledge Base ----
    path('knowledge-base/search', views.KnowledgeBaseSearchView.as_view(), name='kb-search'),

    # ---- User Feedback ----
    path('feedback', views.UserFeedbackView.as_view(), name='feedback'),
]
