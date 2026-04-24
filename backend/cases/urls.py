"""
Cases app URL configuration.

Placeholder — endpoints will be added in Phase 3 (Core API Implementation).
"""

from django.urls import path

app_name = 'cases'

urlpatterns = [
    # Phase 3: Dispute Classification endpoints
    # path('cases/create', views.CreateCaseView.as_view(), name='case-create'),
    # path('cases/<uuid:case_id>/classify/extract-entities', ...),
    # path('cases/<uuid:case_id>/classify/categorize', ...),
    # path('cases/<uuid:case_id>/classify/confirm', ...),

    # Phase 3: Evidence Management endpoints
    # path('evidence/presigned-url', ...),
    # path('evidence/register', ...),

    # Phase 3: Timeline endpoints
    # path('cases/<uuid:case_id>/timeline', ...),

    # Phase 3: Case Packet endpoints
    # path('cases/<uuid:case_id>/case-packet/generate', ...),
]
