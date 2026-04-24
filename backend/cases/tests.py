"""
Unit tests for EvidenceChain backend API.

Covers:
  - Auth (register, login, refresh, logout)
  - Case CRUD (create, list, detail, update, archive)
  - Classification (confirm)
  - Evidence (template, gap report)
  - Timeline (create event, list)
  - Knowledge base (search)
  - Health check
"""

import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Case, EvidenceItem, Event


class AuthTests(TestCase):
    """Test JWT authentication endpoints."""

    def setUp(self):
        self.client = Client()

    def test_register_success(self):
        """POST /api/v1/auth/register creates user and returns tokens."""
        res = self.client.post(
            '/api/v1/auth/register',
            data=json.dumps({
                'username': 'testuser',
                'password': 'TestPass123!',
                'first_name': 'Test',
                'last_name': 'User',
            }),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertIn('access_token', data)
        self.assertIn('refresh_token', data)
        self.assertEqual(data['username'], 'testuser')
        self.assertEqual(data['token_type'], 'Bearer')

    def test_register_duplicate(self):
        """Duplicate username returns 409."""
        User.objects.create_user('dupe', password='pass1234')
        res = self.client.post(
            '/api/v1/auth/register',
            data=json.dumps({'username': 'dupe', 'password': 'pass1234'}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 409)

    def test_login_success(self):
        """POST /api/v1/auth/login returns tokens for valid credentials."""
        User.objects.create_user('loginuser', password='TestPass123!')
        res = self.client.post(
            '/api/v1/auth/login',
            data=json.dumps({'username': 'loginuser', 'password': 'TestPass123!'}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('access_token', data)
        self.assertIn('user', data)
        self.assertEqual(data['user']['username'], 'loginuser')

    def test_login_invalid(self):
        """Invalid credentials return 401."""
        res = self.client.post(
            '/api/v1/auth/login',
            data=json.dumps({'username': 'nobody', 'password': 'wrong'}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 401)

    def test_refresh_token(self):
        """POST /api/v1/auth/refresh returns new access token."""
        user = User.objects.create_user('refreshuser', password='pass1234')
        refresh = RefreshToken.for_user(user)

        res = self.client.post(
            '/api/v1/auth/refresh',
            data=json.dumps({'refresh_token': str(refresh)}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn('access_token', res.json())

    def test_protected_endpoint_without_token(self):
        """Accessing protected endpoint without token returns 401."""
        res = self.client.get('/api/v1/cases/')
        self.assertEqual(res.status_code, 401)


class HealthCheckTests(TestCase):
    """Test health endpoint."""

    def test_health(self):
        res = self.client.get('/api/v1/health')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['status'], 'healthy')


class CaseTests(TestCase):
    """Test case management endpoints."""

    def setUp(self):
        self.user = User.objects.create_user('caseuser', password='pass1234')
        refresh = RefreshToken.for_user(self.user)
        self.token = str(refresh.access_token)
        self.auth = {'HTTP_AUTHORIZATION': f'Bearer {self.token}'}
        self.client = Client()

    def test_create_case(self):
        """POST /api/v1/cases/create creates a case."""
        res = self.client.post(
            '/api/v1/cases/create',
            data=json.dumps({'user_narrative': 'My landlord took my deposit.'}),
            content_type='application/json',
            **self.auth,
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertIn('case_id', data)
        self.assertEqual(data['status'], 'active')
        self.assertEqual(data['next_step'], 'classification')

    def test_list_cases(self):
        """GET /api/v1/cases/ returns user's cases."""
        Case.objects.create(user=self.user, user_narrative='Test', status='active')
        Case.objects.create(user=self.user, user_narrative='Test2', status='active')

        res = self.client.get('/api/v1/cases/', **self.auth)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['count'], 2)
        self.assertEqual(len(data['results']), 2)

    def test_list_cases_isolation(self):
        """Users can only see their own cases."""
        other = User.objects.create_user('other', password='pass1234')
        Case.objects.create(user=other, user_narrative='Other user case', status='active')
        Case.objects.create(user=self.user, user_narrative='My case', status='active')

        res = self.client.get('/api/v1/cases/', **self.auth)
        self.assertEqual(res.json()['count'], 1)

    def test_case_detail(self):
        """GET /api/v1/cases/{id} returns case detail."""
        case = Case.objects.create(
            user=self.user,
            user_narrative='Detail test',
            status='active',
            dispute_type='TENANT_LANDLORD',
            jurisdiction='Karnataka',
        )
        res = self.client.get(f'/api/v1/cases/{case.case_id}', **self.auth)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['dispute_type'], 'TENANT_LANDLORD')
        self.assertIn('applicable_laws', data)

    def test_archive_case(self):
        """DELETE /api/v1/cases/{id} archives the case."""
        case = Case.objects.create(user=self.user, user_narrative='Archive', status='active')
        res = self.client.delete(f'/api/v1/cases/{case.case_id}', **self.auth)
        self.assertEqual(res.status_code, 204)

        case.refresh_from_db()
        self.assertEqual(case.status, 'archived')

    def test_update_case(self):
        """PATCH /api/v1/cases/{id} updates the case."""
        case = Case.objects.create(user=self.user, user_narrative='Update', status='active')
        res = self.client.patch(
            f'/api/v1/cases/{case.case_id}',
            data=json.dumps({'dispute_stage': 'timeline_construction'}),
            content_type='application/json',
            **self.auth,
        )
        self.assertEqual(res.status_code, 200)
        case.refresh_from_db()
        self.assertEqual(case.dispute_stage, 'timeline_construction')


class ClassificationTests(TestCase):
    """Test dispute classification endpoints."""

    def setUp(self):
        self.user = User.objects.create_user('classuser', password='pass1234')
        refresh = RefreshToken.for_user(self.user)
        self.token = str(refresh.access_token)
        self.auth = {'HTTP_AUTHORIZATION': f'Bearer {self.token}'}
        self.client = Client()
        self.case = Case.objects.create(
            user=self.user, user_narrative='Test', status='active'
        )

    def test_confirm_classification(self):
        """POST .../classify/confirm sets dispute type and returns laws."""
        res = self.client.post(
            f'/api/v1/cases/{self.case.case_id}/classify/confirm',
            data=json.dumps({
                'dispute_type': 'TENANT_LANDLORD',
                'jurisdiction': 'Karnataka',
            }),
            content_type='application/json',
            **self.auth,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['dispute_type'], 'TENANT_LANDLORD')
        self.assertEqual(data['jurisdiction'], 'Karnataka')
        self.assertIn('Karnataka Rent Control Act 2001', data['applicable_laws'])
        self.assertEqual(data['next_step'], 'evidence_guidance')

        self.case.refresh_from_db()
        self.assertEqual(self.case.dispute_type, 'TENANT_LANDLORD')


class EvidenceTests(TestCase):
    """Test evidence management endpoints."""

    def setUp(self):
        self.user = User.objects.create_user('eviduser', password='pass1234')
        refresh = RefreshToken.for_user(self.user)
        self.auth = {'HTTP_AUTHORIZATION': f'Bearer {str(refresh.access_token)}'}
        self.client = Client()
        self.case = Case.objects.create(
            user=self.user,
            user_narrative='Test',
            status='active',
            dispute_type='TENANT_LANDLORD',
            jurisdiction='Karnataka',
        )

    def test_evidence_template(self):
        """GET .../evidence/template returns checklist for dispute type."""
        res = self.client.get(
            f'/api/v1/cases/{self.case.case_id}/evidence/template',
            **self.auth,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['dispute_type'], 'TENANT_LANDLORD')
        self.assertIn('critical', data['categories'])
        self.assertIn('completion_stats', data)

        # Critical items should include rental agreement
        critical_names = [i['name'] for i in data['categories']['critical']]
        self.assertIn('Rental/Lease Agreement', critical_names)

    def test_gap_report(self):
        """GET .../gap-report returns evidence gaps."""
        res = self.client.get(
            f'/api/v1/cases/{self.case.case_id}/gap-report',
            **self.auth,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('gaps', data)
        self.assertIn('completion_percentage', data)

    def test_evidence_list(self):
        """GET .../evidence returns evidence items."""
        EvidenceItem.objects.create(
            case=self.case,
            evidence_type='Rental Agreement',
            file_path='s3://test/file.pdf',
        )
        res = self.client.get(
            f'/api/v1/cases/{self.case.case_id}/evidence',
            **self.auth,
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['count'], 1)


class TimelineTests(TestCase):
    """Test timeline endpoints."""

    def setUp(self):
        self.user = User.objects.create_user('timeuser', password='pass1234')
        refresh = RefreshToken.for_user(self.user)
        self.auth = {'HTTP_AUTHORIZATION': f'Bearer {str(refresh.access_token)}'}
        self.client = Client()
        self.case = Case.objects.create(
            user=self.user, user_narrative='Test', status='active'
        )

    def test_create_event(self):
        """POST .../timeline/events creates a manual event."""
        res = self.client.post(
            f'/api/v1/cases/{self.case.case_id}/timeline/events',
            data=json.dumps({
                'event_date': '2024-06-15',
                'action_description': 'Sent deposit return request via WhatsApp',
                'actors': ['Tenant', 'Landlord'],
            }),
            content_type='application/json',
            **self.auth,
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data['source_type'], 'manual_entry')
        self.assertEqual(data['action_description'], 'Sent deposit return request via WhatsApp')

    def test_timeline_list(self):
        """GET .../timeline returns ordered events."""
        Event.objects.create(
            case=self.case,
            event_date='2024-01-01',
            action_description='Signed lease',
            source_type='manual_entry',
        )
        Event.objects.create(
            case=self.case,
            event_date='2024-06-15',
            action_description='Moved out',
            source_type='manual_entry',
        )

        res = self.client.get(
            f'/api/v1/cases/{self.case.case_id}/timeline',
            **self.auth,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['stats']['total_events'], 2)
        self.assertEqual(data['stats']['manual_entries'], 2)

    def test_delete_event(self):
        """DELETE /timeline/events/{id} removes the event."""
        event = Event.objects.create(
            case=self.case,
            event_date='2024-01-01',
            action_description='Test event',
            source_type='manual_entry',
        )
        res = self.client.delete(
            f'/api/v1/timeline/events/{event.event_id}',
            **self.auth,
        )
        self.assertEqual(res.status_code, 204)
        self.assertFalse(Event.objects.filter(event_id=event.event_id).exists())


class KnowledgeBaseTests(TestCase):
    """Test knowledge base functionality."""

    def test_chunk_text(self):
        """Chunking produces overlapping segments."""
        from .knowledge_base import KnowledgeBaseManager
        kb = KnowledgeBaseManager()

        long_text = "A " * 500  # ~500 words, well over chunk size
        chunks = kb.chunk_text(long_text, chunk_size=64, overlap=16)
        self.assertGreater(len(chunks), 1)

    def test_ingest_and_search(self):
        """Ingestion + search returns relevant results."""
        from .knowledge_base import KnowledgeBaseManager
        kb = KnowledgeBaseManager()

        result = kb.ingest_all()
        self.assertGreater(result['documents_ingested'], 0)
        self.assertGreater(result['collection_count'], 0)

        texts, scores, metas = kb.search('freelance payment contract breach')
        self.assertGreater(len(texts), 0)

        # Should find Indian Contract Act entries
        sources = [m['source'] for m in metas]
        self.assertTrue(
            any('Contract' in s for s in sources),
            f'Expected Contract Act in results, got: {sources}'
        )

    def test_search_with_dispute_filter(self):
        """Filtered search returns matching dispute type."""
        from .knowledge_base import KnowledgeBaseManager
        kb = KnowledgeBaseManager()
        kb.ingest_all()

        texts, scores, metas = kb.search(
            'rent payment',
            dispute_type_filter='TENANT_LANDLORD',
        )
        self.assertGreater(len(texts), 0)

        for m in metas:
            self.assertIn(
                m['dispute_type'],
                ['TENANT_LANDLORD', 'ALL'],
                f"Unexpected dispute type: {m['dispute_type']}"
            )
