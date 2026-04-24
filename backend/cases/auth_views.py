"""
Authentication views for EvidenceChain.

Implements JWT-based auth endpoints per API_ENDPOINTS.md:
  POST /auth/register
  POST /auth/login
  POST /auth/refresh
  POST /auth/logout
"""

from django.contrib.auth.models import User
from django.contrib.auth import authenticate

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError


class RegisterView(APIView):
    """Create a new user account and return JWT tokens."""

    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')

        if not username or not password:
            return Response(
                {'error': 'username and password are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(username=username).exists():
            return Response(
                {'error': 'A user with this username already exists'},
                status=status.HTTP_409_CONFLICT,
            )

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                'user_id': str(user.pk),
                'username': user.username,
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
                'token_type': 'Bearer',
                'expires_in': 86400,  # 24 hours
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """Authenticate user and return JWT tokens."""

    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response(
                {'error': 'username and password are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(username=username, password=password)

        if user is None:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)

        return Response({
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'token_type': 'Bearer',
            'expires_in': 86400,
            'user': {
                'user_id': str(user.pk),
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
        })


class RefreshTokenView(APIView):
    """Refresh an access token using a valid refresh token."""

    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get('refresh_token')

        if not refresh_token:
            return Response(
                {'error': 'refresh_token is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            refresh = RefreshToken(refresh_token)
            return Response({
                'access_token': str(refresh.access_token),
                'token_type': 'Bearer',
                'expires_in': 86400,
            })
        except TokenError:
            return Response(
                {'error': 'Invalid or expired refresh token'},
                status=status.HTTP_401_UNAUTHORIZED,
            )


class LogoutView(APIView):
    """Blacklist the refresh token to invalidate the session."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh_token')

        if not refresh_token:
            return Response(
                {'error': 'refresh_token is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            pass  # Token already expired/blacklisted — still a successful logout

        return Response(status=status.HTTP_204_NO_CONTENT)
