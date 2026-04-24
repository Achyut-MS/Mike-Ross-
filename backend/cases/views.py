"""
Cases app views.

All REST API views implementing endpoints from API_ENDPOINTS.md.
"""

import logging
import os
import uuid
from datetime import datetime, timezone

import boto3
from django.conf import settings
from django.http import FileResponse, Http404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Case, EvidenceItem, Event, AILog, CasePacket, UserFeedback,
)
from .serializers import (
    CaseCreateSerializer, CaseListSerializer, CaseDetailSerializer,
    CaseUpdateSerializer, EvidenceItemSerializer, EvidenceUpdateSerializer,
    PresignedUrlRequestSerializer, RegisterEvidenceSerializer,
    EventSerializer, EventCreateSerializer, EventUpdateSerializer,
    EntityExtractionSerializer, CategorizeDisputeSerializer,
    ConfirmClassificationSerializer, CasePacketSerializer,
    AILogSerializer, AILogDetailSerializer, UserFeedbackSerializer,
    KnowledgeBaseSearchSerializer,
)
from .services import (
    get_jurisdiction_laws, get_legal_issues, get_evidence_template,
    generate_gap_report,
)

logger = logging.getLogger('cases')


# ============================================================================
# CASE MANAGEMENT
# ============================================================================

class CaseListCreateView(APIView):
    """
    GET  /cases/         — list authenticated user's cases
    POST /cases/create   — create a new case
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Case.objects.filter(user=request.user)

        # Optional filters
        filter_status = request.query_params.get('status')
        if filter_status:
            qs = qs.filter(status=filter_status)

        dispute_type = request.query_params.get('dispute_type')
        if dispute_type:
            qs = qs.filter(dispute_type=dispute_type)

        # Pagination
        limit = int(request.query_params.get('limit', 20))
        offset = int(request.query_params.get('offset', 0))
        total = qs.count()
        qs = qs[offset:offset + limit]

        serializer = CaseListSerializer(qs, many=True)
        return Response({
            'count': total,
            'next': None,
            'previous': None,
            'results': serializer.data,
        })

    def post(self, request):
        serializer = CaseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        case = Case.objects.create(
            user=request.user,
            user_narrative=serializer.validated_data['user_narrative'],
            status='active',
        )

        return Response(
            {
                'case_id': str(case.case_id),
                'status': case.status,
                'created_at': case.created_at.isoformat(),
                'next_step': 'classification',
            },
            status=status.HTTP_201_CREATED,
        )


class CaseDetailView(APIView):
    """
    GET    /cases/{case_id}  — detailed case info
    PATCH  /cases/{case_id}  — update fields
    DELETE /cases/{case_id}  — soft-delete (archive)
    """
    permission_classes = [IsAuthenticated]

    def _get_case(self, request, case_id):
        try:
            return Case.objects.get(case_id=case_id, user=request.user)
        except Case.DoesNotExist:
            return None

    def get(self, request, case_id):
        case = self._get_case(request, case_id)
        if not case:
            return Response({'error': 'Case not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CaseDetailSerializer(case)
        return Response(serializer.data)

    def patch(self, request, case_id):
        case = self._get_case(request, case_id)
        if not case:
            return Response({'error': 'Case not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CaseUpdateSerializer(case, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(CaseDetailSerializer(case).data)

    def delete(self, request, case_id):
        case = self._get_case(request, case_id)
        if not case:
            return Response({'error': 'Case not found'}, status=status.HTTP_404_NOT_FOUND)

        case.status = 'archived'
        case.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================================
# MODULE 1: DISPUTE CLASSIFICATION
# ============================================================================

class ExtractEntitiesView(APIView):
    """POST /cases/{case_id}/classify/extract-entities"""
    permission_classes = [IsAuthenticated]

    def post(self, request, case_id):
        try:
            case = Case.objects.get(case_id=case_id, user=request.user)
        except Case.DoesNotExist:
            return Response({'error': 'Case not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = EntityExtractionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        narrative = serializer.validated_data['narrative']

        try:
            from .ai_service import ai_service
            result = ai_service.extract_entities(str(case_id), narrative)
        except Exception as e:
            logger.exception('Entity extraction failed')
            return Response(
                {'error': f'AI service error: {str(e)}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(result)


class CategorizeDisputeView(APIView):
    """POST /cases/{case_id}/classify/categorize"""
    permission_classes = [IsAuthenticated]

    def post(self, request, case_id):
        try:
            case = Case.objects.get(case_id=case_id, user=request.user)
        except Case.DoesNotExist:
            return Response({'error': 'Case not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CategorizeDisputeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        entities = serializer.validated_data['entities']
        narrative = serializer.validated_data['narrative']

        try:
            from .ai_service import ai_service
            result = ai_service.classify_dispute(str(case_id), entities, narrative)
        except Exception as e:
            logger.exception('Dispute categorization failed')
            return Response(
                {'error': f'AI service error: {str(e)}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(result)


class ConfirmClassificationView(APIView):
    """POST /cases/{case_id}/classify/confirm"""
    permission_classes = [IsAuthenticated]

    def post(self, request, case_id):
        try:
            case = Case.objects.get(case_id=case_id, user=request.user)
        except Case.DoesNotExist:
            return Response({'error': 'Case not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ConfirmClassificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        case.dispute_type = serializer.validated_data['dispute_type']
        case.jurisdiction = serializer.validated_data['jurisdiction']
        case.dispute_stage = 'evidence_guidance'
        case.save()

        applicable_laws = get_jurisdiction_laws(case.dispute_type, case.jurisdiction)

        return Response({
            'case_id': str(case.case_id),
            'dispute_type': case.dispute_type,
            'jurisdiction': case.jurisdiction,
            'applicable_laws': applicable_laws,
            'next_step': 'evidence_guidance',
        })


# ============================================================================
# MODULE 2: EVIDENCE MANAGEMENT
# ============================================================================

class EvidenceTemplateView(APIView):
    """GET /cases/{case_id}/evidence/template"""
    permission_classes = [IsAuthenticated]

    def get(self, request, case_id):
        try:
            case = Case.objects.get(case_id=case_id, user=request.user)
        except Case.DoesNotExist:
            return Response({'error': 'Case not found'}, status=status.HTTP_404_NOT_FOUND)

        template = get_evidence_template(case.dispute_type)
        uploaded = EvidenceItem.objects.filter(case=case)
        uploaded_types = set(uploaded.values_list('evidence_type', flat=True))

        categories = {}
        total_items = 0
        total_collected = 0

        for category in ['critical', 'supportive', 'optional']:
            items = []
            for i, item in enumerate(template.get(category, []), 1):
                collected = item['name'] in uploaded_types
                entry = {
                    'name': item['name'],
                    'description': item['description'],
                    'display_order': i,
                    'collected': collected,
                }
                if collected:
                    evidence = uploaded.filter(evidence_type=item['name']).first()
                    if evidence:
                        entry['evidence_id'] = str(evidence.evidence_id)
                    total_collected += 1
                items.append(entry)
                total_items += 1
            categories[category] = items

        critical_total = len(categories.get('critical', []))
        critical_collected = sum(1 for i in categories.get('critical', []) if i['collected'])
        supportive_total = len(categories.get('supportive', []))
        supportive_collected = sum(1 for i in categories.get('supportive', []) if i['collected'])
        overall_pct = round((total_collected / total_items) * 100) if total_items > 0 else 0

        return Response({
            'dispute_type': case.dispute_type,
            'categories': categories,
            'completion_stats': {
                'critical_collected': critical_collected,
                'critical_total': critical_total,
                'supportive_collected': supportive_collected,
                'supportive_total': supportive_total,
                'overall_percentage': overall_pct,
            },
        })


class PresignedUrlView(APIView):
    """POST /evidence/presigned-url"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PresignedUrlRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Validate case ownership
        try:
            case = Case.objects.get(case_id=data['case_id'], user=request.user)
        except Case.DoesNotExist:
            return Response({'error': 'Case not found'}, status=status.HTTP_404_NOT_FOUND)

        # File size check (10 MB max, per spec)
        if data['file_size'] > settings.MAX_UPLOAD_SIZE_BYTES:
            return Response(
                {'error': f'File too large. Maximum size is {settings.MAX_UPLOAD_SIZE_BYTES // (1024*1024)}MB'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # MIME type check
        if data['content_type'] not in settings.ALLOWED_UPLOAD_MIME_TYPES:
            return Response(
                {'error': f'Unsupported file type: {data["content_type"]}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create evidence record
        evidence = EvidenceItem.objects.create(
            case=case,
            evidence_type=data['evidence_type'],
            file_path='',  # Will be set after upload
            file_size_bytes=data['file_size'],
            mime_type=data['content_type'],
            processing_status='pending',
        )

        # Generate S3 pre-signed URL
        s3_key = f"{case.case_id}/{evidence.evidence_id}/{data['filename']}"
        bucket = settings.AWS_S3_BUCKET_UPLOADS

        try:
            s3_kwargs = {
                'aws_access_key_id': settings.AWS_ACCESS_KEY_ID,
                'aws_secret_access_key': settings.AWS_SECRET_ACCESS_KEY,
                'region_name': settings.AWS_S3_REGION,
            }
            if settings.AWS_S3_ENDPOINT_URL:
                s3_kwargs['endpoint_url'] = settings.AWS_S3_ENDPOINT_URL

            s3 = boto3.client('s3', **s3_kwargs)

            presigned = s3.generate_presigned_post(
                Bucket=bucket,
                Key=s3_key,
                ExpiresIn=settings.AWS_PRESIGNED_URL_EXPIRY,
                Conditions=[
                    ['content-length-range', 1, settings.MAX_UPLOAD_SIZE_BYTES],
                ],
            )
        except Exception as e:
            logger.exception('S3 presigned URL generation failed')
            evidence.delete()
            return Response(
                {'error': f'Could not generate upload URL: {str(e)}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.AWS_PRESIGNED_URL_EXPIRY)

        return Response({
            'evidence_id': str(evidence.evidence_id),
            'upload_url': presigned['url'],
            'upload_fields': presigned['fields'],
            'expires_at': expires_at.isoformat(),
        })


class RegisterEvidenceView(APIView):
    """POST /evidence/register — notify backend after successful S3 upload"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RegisterEvidenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            evidence = EvidenceItem.objects.get(evidence_id=data['evidence_id'])
        except EvidenceItem.DoesNotExist:
            return Response({'error': 'Evidence not found'}, status=status.HTTP_404_NOT_FOUND)

        # Verify ownership
        if evidence.case.user != request.user:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        # Update file path
        bucket = settings.AWS_S3_BUCKET_UPLOADS
        evidence.file_path = f's3://{bucket}/{data["s3_key"]}'
        evidence.file_size_bytes = data['file_size']
        evidence.mime_type = data['content_type']
        evidence.processing_status = 'pending'
        evidence.save()

        # Queue Celery processing
        try:
            from .tasks import process_uploaded_document
            process_uploaded_document.delay(str(evidence.evidence_id))
        except Exception as e:
            logger.warning(f'Could not queue processing task: {e}')

        return Response(
            {
                'evidence_id': str(evidence.evidence_id),
                'processing_status': 'queued',
                'check_status_url': f'/evidence/{evidence.evidence_id}/status',
            },
            status=status.HTTP_202_ACCEPTED,
        )


class EvidenceStatusView(APIView):
    """GET /evidence/{evidence_id}/status"""
    permission_classes = [IsAuthenticated]

    def get(self, request, evidence_id):
        try:
            evidence = EvidenceItem.objects.get(evidence_id=evidence_id)
        except EvidenceItem.DoesNotExist:
            return Response({'error': 'Evidence not found'}, status=status.HTTP_404_NOT_FOUND)

        if evidence.case.user != request.user:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        data = {
            'evidence_id': str(evidence.evidence_id),
            'processing_status': evidence.processing_status,
        }

        if evidence.processing_status == 'completed':
            data.update({
                'extracted_text': evidence.extracted_text[:500] if evidence.extracted_text else '',
                'classification': {
                    'tag': evidence.classification_tag,
                },
                'extracted_entities': evidence.extracted_entities,
                'completeness_flag': evidence.completeness_flag,
            })
        elif evidence.processing_status == 'failed':
            data.update({
                'processing_error': evidence.processing_error,
                'retry_available': True,
            })

        return Response(data)


class CaseEvidenceListView(APIView):
    """GET /cases/{case_id}/evidence"""
    permission_classes = [IsAuthenticated]

    def get(self, request, case_id):
        try:
            case = Case.objects.get(case_id=case_id, user=request.user)
        except Case.DoesNotExist:
            return Response({'error': 'Case not found'}, status=status.HTTP_404_NOT_FOUND)

        items = EvidenceItem.objects.filter(case=case)
        serializer = EvidenceItemSerializer(items, many=True)

        return Response({
            'count': items.count(),
            'items': serializer.data,
        })


class EvidenceUpdateDeleteView(APIView):
    """
    PATCH  /evidence/{evidence_id}  — update metadata
    DELETE /evidence/{evidence_id}  — delete evidence
    """
    permission_classes = [IsAuthenticated]

    def _get_evidence(self, request, evidence_id):
        try:
            evidence = EvidenceItem.objects.get(evidence_id=evidence_id)
            if evidence.case.user != request.user:
                return None
            return evidence
        except EvidenceItem.DoesNotExist:
            return None

    def patch(self, request, evidence_id):
        evidence = self._get_evidence(request, evidence_id)
        if not evidence:
            return Response({'error': 'Evidence not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = EvidenceUpdateSerializer(evidence, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(EvidenceItemSerializer(evidence).data)

    def delete(self, request, evidence_id):
        evidence = self._get_evidence(request, evidence_id)
        if not evidence:
            return Response({'error': 'Evidence not found'}, status=status.HTTP_404_NOT_FOUND)

        evidence.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GapReportView(APIView):
    """GET /cases/{case_id}/gap-report"""
    permission_classes = [IsAuthenticated]

    def get(self, request, case_id):
        try:
            case = Case.objects.get(case_id=case_id, user=request.user)
        except Case.DoesNotExist:
            return Response({'error': 'Case not found'}, status=status.HTTP_404_NOT_FOUND)

        report = generate_gap_report(str(case_id))
        report['case_id'] = str(case_id)
        report['generated_at'] = datetime.now(timezone.utc).isoformat()

        return Response(report)


# ============================================================================
# MODULE 3: TIMELINE CONSTRUCTION
# ============================================================================

class TimelineView(APIView):
    """GET /cases/{case_id}/timeline"""
    permission_classes = [IsAuthenticated]

    def get(self, request, case_id):
        try:
            case = Case.objects.get(case_id=case_id, user=request.user)
        except Case.DoesNotExist:
            return Response({'error': 'Case not found'}, status=status.HTTP_404_NOT_FOUND)

        events = Event.objects.filter(case=case).order_by('event_date', 'event_id')

        # Optional date filtering
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if start_date:
            events = events.filter(event_date__gte=start_date)
        if end_date:
            events = events.filter(event_date__lte=end_date)

        serializer = EventSerializer(events, many=True)

        auto_count = events.filter(source_type='auto_extracted').count()
        manual_count = events.filter(source_type='manual_entry').count()

        dates = events.exclude(event_date__isnull=True).values_list('event_date', flat=True)
        date_range = {}
        if dates:
            date_range = {
                'earliest': str(min(dates)),
                'latest': str(max(dates)),
            }

        return Response({
            'case_id': str(case_id),
            'timeline_generated_at': datetime.now(timezone.utc).isoformat(),
            'events': serializer.data,
            'stats': {
                'total_events': events.count(),
                'auto_extracted': auto_count,
                'manual_entries': manual_count,
                'date_range': date_range,
            },
        })


class TimelineEventCreateView(APIView):
    """POST /cases/{case_id}/timeline/events"""
    permission_classes = [IsAuthenticated]

    def post(self, request, case_id):
        try:
            case = Case.objects.get(case_id=case_id, user=request.user)
        except Case.DoesNotExist:
            return Response({'error': 'Case not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = EventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        event = Event.objects.create(
            case=case,
            event_date=serializer.validated_data['event_date'],
            action_description=serializer.validated_data['action_description'],
            actors=serializer.validated_data.get('actors', []),
            evidence_refs=serializer.validated_data.get('evidence_refs', []),
            source_type='manual_entry',
        )

        return Response(
            EventSerializer(event).data,
            status=status.HTTP_201_CREATED,
        )


class TimelineEventUpdateDeleteView(APIView):
    """
    PATCH  /timeline/events/{event_id}
    DELETE /timeline/events/{event_id}
    """
    permission_classes = [IsAuthenticated]

    def _get_event(self, request, event_id):
        try:
            event = Event.objects.get(event_id=event_id)
            if event.case.user != request.user:
                return None
            return event
        except Event.DoesNotExist:
            return None

    def patch(self, request, event_id):
        event = self._get_event(request, event_id)
        if not event:
            return Response({'error': 'Event not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = EventUpdateSerializer(event, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(EventSerializer(event).data)

    def delete(self, request, event_id):
        event = self._get_event(request, event_id)
        if not event:
            return Response({'error': 'Event not found'}, status=status.HTTP_404_NOT_FOUND)

        event.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DeduplicateTimelineView(APIView):
    """POST /cases/{case_id}/timeline/deduplicate"""
    permission_classes = [IsAuthenticated]

    def post(self, request, case_id):
        try:
            case = Case.objects.get(case_id=case_id, user=request.user)
        except Case.DoesNotExist:
            return Response({'error': 'Case not found'}, status=status.HTTP_404_NOT_FOUND)

        events = list(Event.objects.filter(case=case).order_by('event_date'))

        if len(events) < 2:
            return Response({
                'duplicates_found': 0,
                'merged_events': [],
                'timeline_updated': False,
            })

        merged_events = []

        try:
            from .ai_service import ai_service

            # Compare consecutive pairs
            i = 0
            while i < len(events) - 1:
                e1 = events[i]
                e2 = events[i + 1]

                result = ai_service.deduplicate_events(
                    str(case_id),
                    {
                        'event_date': str(e1.event_date) if e1.event_date else 'UNDATED',
                        'action_description': e1.action_description,
                    },
                    {
                        'event_date': str(e2.event_date) if e2.event_date else 'UNDATED',
                        'action_description': e2.action_description,
                    },
                )

                if result.get('decision') == 'MERGE':
                    # Keep first event as canonical
                    e1.action_description = result.get('canonical_description', e1.action_description)
                    e1.evidence_refs = list(set(e1.evidence_refs + e2.evidence_refs))
                    e1.is_merged = True
                    e1.merged_from_event_ids = list(set(
                        e1.merged_from_event_ids + [str(e2.event_id)]
                    ))
                    e1.save()

                    merged_events.append({
                        'canonical_event_id': str(e1.event_id),
                        'merged_from': [str(e2.event_id)],
                        'reasoning': result.get('reasoning', ''),
                    })

                    e2.delete()
                    events.pop(i + 1)
                else:
                    i += 1

        except Exception as e:
            logger.exception('Timeline deduplication failed')
            return Response(
                {'error': f'AI service error: {str(e)}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({
            'duplicates_found': len(merged_events),
            'merged_events': merged_events,
            'timeline_updated': len(merged_events) > 0,
        })


# ============================================================================
# MODULE 4: CASE PACKET GENERATION
# ============================================================================

class GenerateCasePacketView(APIView):
    """POST /cases/{case_id}/case-packet/generate"""
    permission_classes = [IsAuthenticated]

    def post(self, request, case_id):
        try:
            case = Case.objects.get(case_id=case_id, user=request.user)
        except Case.DoesNotExist:
            return Response({'error': 'Case not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check if packet already exists
        try:
            existing = case.case_packet
            return Response({
                'packet_id': str(existing.packet_id),
                'status': 'already_exists',
                'message': 'Use regenerate endpoint to update',
            })
        except CasePacket.DoesNotExist:
            pass

        # Queue async generation
        try:
            from .packet_tasks import generate_case_packet_task
            task = generate_case_packet_task.delay(str(case_id))
        except Exception as e:
            logger.warning(f'Could not queue packet generation: {e}')

        return Response(
            {
                'case_id': str(case_id),
                'status': 'generating',
            },
            status=status.HTTP_202_ACCEPTED,
        )


class CasePacketStatusView(APIView):
    """GET /case-packets/{packet_id}/status"""
    permission_classes = [IsAuthenticated]

    def get(self, request, packet_id):
        try:
            packet = CasePacket.objects.get(packet_id=packet_id)
        except CasePacket.DoesNotExist:
            return Response({'error': 'Case packet not found'}, status=status.HTTP_404_NOT_FOUND)

        if packet.case.user != request.user:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        return Response({
            'packet_id': str(packet.packet_id),
            'status': 'completed',
            'generated_at': packet.generated_at.isoformat(),
            'sections_completed': {
                'executive_summary': bool(packet.executive_summary),
                'issues': bool(packet.issues),
                'evidence_table': bool(packet.evidence_table),
                'timeline': bool(packet.timeline),
                'gap_report': bool(packet.gap_report),
                'lawyer_questions': bool(packet.lawyer_questions),
            },
            'pdf_available': bool(packet.pdf_file_path),
        })


class CasePacketDetailView(APIView):
    """GET /case-packets/{packet_id}"""
    permission_classes = [IsAuthenticated]

    def get(self, request, packet_id):
        try:
            packet = CasePacket.objects.get(packet_id=packet_id)
        except CasePacket.DoesNotExist:
            return Response({'error': 'Case packet not found'}, status=status.HTTP_404_NOT_FOUND)

        if packet.case.user != request.user:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        serializer = CasePacketSerializer(packet)
        return Response(serializer.data)


class CasePacketDownloadView(APIView):
    """GET /case-packets/{packet_id}/download"""
    permission_classes = [IsAuthenticated]

    def get(self, request, packet_id):
        try:
            packet = CasePacket.objects.get(packet_id=packet_id)
        except CasePacket.DoesNotExist:
            return Response({'error': 'Case packet not found'}, status=status.HTTP_404_NOT_FOUND)

        if packet.case.user != request.user:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        if not packet.pdf_file_path or not os.path.exists(packet.pdf_file_path):
            return Response(
                {'error': 'PDF not available'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return FileResponse(
            open(packet.pdf_file_path, 'rb'),
            content_type='application/pdf',
            as_attachment=True,
            filename=f'case_packet_{packet.case.case_id}.pdf',
        )


class RegenerateCasePacketView(APIView):
    """POST /case-packets/{packet_id}/regenerate"""
    permission_classes = [IsAuthenticated]

    def post(self, request, packet_id):
        try:
            packet = CasePacket.objects.get(packet_id=packet_id)
        except CasePacket.DoesNotExist:
            return Response({'error': 'Case packet not found'}, status=status.HTTP_404_NOT_FOUND)

        if packet.case.user != request.user:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        # Queue regeneration
        try:
            from .packet_tasks import generate_case_packet_task
            generate_case_packet_task.delay(str(packet.case.case_id))
        except Exception as e:
            logger.warning(f'Could not queue packet regeneration: {e}')

        packet.regeneration_count += 1
        packet.save()

        return Response(
            {
                'packet_id': str(packet.packet_id),
                'status': 'regenerating',
                'regeneration_count': packet.regeneration_count,
            },
            status=status.HTTP_202_ACCEPTED,
        )


# ============================================================================
# AI INSIGHTS & ANALYTICS
# ============================================================================

class AIInsightsView(APIView):
    """GET /cases/{case_id}/ai-insights"""
    permission_classes = [IsAuthenticated]

    def get(self, request, case_id):
        try:
            case = Case.objects.get(case_id=case_id, user=request.user)
        except Case.DoesNotExist:
            return Response({'error': 'Case not found'}, status=status.HTTP_404_NOT_FOUND)

        # Evidence strength
        gap_report = generate_gap_report(str(case_id))
        template = get_evidence_template(case.dispute_type)

        critical_total = len(template.get('critical', []))
        critical_collected = critical_total - gap_report.get('critical_gaps', 0)
        supportive_total = len(template.get('supportive', []))
        supportive_collected = supportive_total - gap_report.get('supportive_gaps', 0)

        critical_pct = round((critical_collected / critical_total) * 100) if critical_total > 0 else 0
        supportive_pct = round((supportive_collected / supportive_total) * 100) if supportive_total > 0 else 0

        # Timeline stats
        events = Event.objects.filter(case=case)
        event_count = events.count()

        # Next actions
        actions = []
        for gap in gap_report.get('gaps', []):
            if gap['severity'] == 'critical':
                actions.append(f"Upload {gap['item']} (Critical)")

        return Response({
            'case_id': str(case_id),
            'insights_generated_at': datetime.now(timezone.utc).isoformat(),
            'evidence_strength': {
                'critical_coverage': critical_pct,
                'supportive_coverage': supportive_pct,
                'overall_score': gap_report.get('completion_percentage', 0),
                'missing_critical': [
                    g['item'] for g in gap_report.get('gaps', [])
                    if g['severity'] == 'critical'
                ],
            },
            'timeline_completeness': {
                'events_count': event_count,
            },
            'next_recommended_actions': actions[:5],
        })


class AILogListView(APIView):
    """GET /ai-logs"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = AILog.objects.all()

        case_id = request.query_params.get('case_id')
        if case_id:
            qs = qs.filter(case_id=case_id)

        module = request.query_params.get('module')
        if module:
            qs = qs.filter(module=module)

        start_date = request.query_params.get('start_date')
        if start_date:
            qs = qs.filter(timestamp__date__gte=start_date)

        end_date = request.query_params.get('end_date')
        if end_date:
            qs = qs.filter(timestamp__date__lte=end_date)

        serializer = AILogSerializer(qs[:100], many=True)
        return Response({
            'count': qs.count(),
            'logs': serializer.data,
        })


# ============================================================================
# KNOWLEDGE BASE
# ============================================================================

class KnowledgeBaseSearchView(APIView):
    """POST /knowledge-base/search"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = KnowledgeBaseSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        query = serializer.validated_data['query']
        top_k = serializer.validated_data.get('top_k', 5)
        dispute_filter = serializer.validated_data.get('dispute_type_filter')

        try:
            from .ai_service import ai_service
            chunks, scores = ai_service._retrieve_context(
                query, top_k=top_k, dispute_type_filter=dispute_filter
            )

            results = []
            for i, (chunk, score) in enumerate(zip(chunks, scores)):
                results.append({
                    'text': chunk,
                    'similarity_score': round(score, 4),
                })

            return Response({
                'query': query,
                'chunks': results,
                'retrieval_count': len(results),
            })

        except Exception as e:
            logger.exception('Knowledge base search failed')
            return Response(
                {'error': f'Search failed: {str(e)}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


# ============================================================================
# USER FEEDBACK
# ============================================================================

class UserFeedbackView(APIView):
    """POST /feedback"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UserFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
