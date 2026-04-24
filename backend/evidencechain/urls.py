"""
EvidenceChain URL Configuration

All API endpoints are mounted under /api/v1/
Admin panel is at /admin/
Auth endpoints at /api/v1/auth/
"""

from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

from cases.auth_views import (
    RegisterView, LoginView, RefreshTokenView, LogoutView,
)


def health_check(request):
    """System health check endpoint."""
    return JsonResponse({
        'status': 'healthy',
        'service': 'evidencechain-backend',
    })


urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth endpoints
    path('api/v1/auth/register', RegisterView.as_view(), name='auth-register'),
    path('api/v1/auth/login', LoginView.as_view(), name='auth-login'),
    path('api/v1/auth/refresh', RefreshTokenView.as_view(), name='auth-refresh'),
    path('api/v1/auth/logout', LogoutView.as_view(), name='auth-logout'),

    # Cases app (all other endpoints)
    path('api/v1/', include('cases.urls')),

    # Health check
    path('api/v1/health', health_check, name='health-check'),
]
