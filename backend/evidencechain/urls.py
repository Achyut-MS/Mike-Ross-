"""
EvidenceChain URL Configuration

All API endpoints are mounted under /api/v1/
Admin panel is at /admin/
"""

from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def health_check(request):
    """System health check endpoint."""
    return JsonResponse({
        'status': 'healthy',
        'service': 'evidencechain-backend',
    })


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('cases.urls')),
    path('api/v1/health', health_check, name='health-check'),
]
