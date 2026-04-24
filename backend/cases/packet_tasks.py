"""
Case packet generation Celery task.

Orchestrates the full 6-section case packet:
  1. Executive Summary (GPT-4o + RAG)
  2. Issues and Likely Claims (hardcoded template — no LLM)
  3. Evidence Table (database query — no LLM)
  4. Chronological Timeline (database query — no LLM)
  5. Gap Report (database query — no LLM)
  6. Preliminary Questions for Lawyer (GPT-4o)

Then generates a PDF with reportlab.
"""

import logging
import os
from datetime import datetime, timezone

from celery import shared_task
from django.conf import settings

logger = logging.getLogger('cases')


@shared_task(bind=True, max_retries=2)
def generate_case_packet_task(self, case_id: str):
    """
    Generate or regenerate a complete case packet.
    """
    from .models import Case, EvidenceItem, Event, CasePacket
    from .services import get_legal_issues, generate_gap_report
    from .ai_service import ai_service

    try:
        case = Case.objects.get(case_id=case_id)
    except Case.DoesNotExist:
        logger.error(f'Case {case_id} not found')
        return {'error': 'Case not found'}

    # ---- Section 2: Issues (hardcoded — no LLM) ----
    issues = get_legal_issues(case.dispute_type, case.jurisdiction)
    issues_data = [
        {'issue': issue, 'applicable_law': issue.split(' under ')[-1] if ' under ' in issue else ''}
        for issue in issues
    ]

    # ---- Section 3: Evidence Table (DB query — no LLM) ----
    evidence_items = EvidenceItem.objects.filter(case=case)
    evidence_table = [
        {
            'document_name': e.evidence_type,
            'type': e.classification_tag,
            'date': e.upload_timestamp.strftime('%Y-%m-%d'),
            'status': 'Complete' if e.completeness_flag else 'Incomplete',
        }
        for e in evidence_items
    ]

    # ---- Section 4: Timeline (DB query — no LLM) ----
    events = Event.objects.filter(case=case).order_by('event_date')
    timeline_data = [
        {
            'event_id': str(e.event_id),
            'date': str(e.event_date) if e.event_date else 'UNDATED',
            'description': e.action_description,
            'actors': e.actors,
            'evidence_refs': e.evidence_refs,
        }
        for e in events
    ]

    # ---- Section 5: Gap Report (DB query — no LLM) ----
    gap_report = generate_gap_report(case_id)

    # ---- Section 1: Executive Summary (GPT-4o + RAG) ----
    executive_summary = ''
    try:
        summary_result = ai_service.generate_executive_summary(
            case_id=case_id,
            case_timeline=timeline_data,
            evidence_list=evidence_table,
        )
        executive_summary = summary_result.get('executive_summary', '')
    except Exception as e:
        logger.warning(f'Executive summary generation failed: {e}')
        executive_summary = 'Executive summary could not be generated at this time.'

    # ---- Section 6: Lawyer Questions (GPT-4o) ----
    lawyer_questions = []
    try:
        # Gather timeline gaps for the prompt
        timeline_gaps = []  # Would come from gap detection, empty for now
        questions_result = ai_service.generate_lawyer_questions(
            case_id=case_id,
            gap_report=gap_report,
            timeline_gaps=timeline_gaps,
        )
        lawyer_questions = questions_result.get('lawyer_questions', [])
    except Exception as e:
        logger.warning(f'Lawyer questions generation failed: {e}')
        lawyer_questions = ['Please consult your lawyer about the missing evidence items.']

    # ---- Save to DB ----
    packet, created = CasePacket.objects.update_or_create(
        case=case,
        defaults={
            'executive_summary': executive_summary,
            'issues': issues_data,
            'evidence_table': evidence_table,
            'timeline': timeline_data,
            'gap_report': gap_report,
            'lawyer_questions': lawyer_questions,
        },
    )

    if not created:
        packet.regeneration_count += 1
        packet.last_regenerated_at = datetime.now(timezone.utc)
        packet.save()

    # ---- Generate PDF ----
    try:
        pdf_path = _generate_pdf(packet)
        packet.pdf_file_path = pdf_path
        packet.save()
    except Exception as e:
        logger.warning(f'PDF generation failed: {e}')

    # Update case stage
    case.dispute_stage = 'case_packet_generated'
    case.save()

    return {
        'packet_id': str(packet.packet_id),
        'status': 'completed',
    }


def _generate_pdf(packet) -> str:
    """
    Generate PDF case packet using reportlab.
    Returns the file path of the generated PDF.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )

    # Output path
    output_dir = os.path.join(settings.BASE_DIR, 'generated_packets')
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, f'case_packet_{packet.case.case_id}.pdf')

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'PacketTitle',
        parent=styles['Title'],
        fontSize=18,
        spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=16,
        spaceAfter=8,
        textColor=HexColor('#1a365d'),
    )
    body_style = styles['BodyText']

    # Footer with legal disclaimer
    disclaimer_text = (
        "This document was generated by an AI-assisted system for informational purposes only. "
        "It does not constitute legal advice. Consult a licensed advocate before taking any legal action."
    )

    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(HexColor('#666666'))
        canvas.drawString(30, 20, disclaimer_text)
        canvas.restoreState()

    # Build document
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )

    story = []

    # Title
    story.append(Paragraph('EvidenceChain — Case Preparation Packet', title_style))
    story.append(Paragraph(
        f'Case ID: {packet.case.case_id} | '
        f'Type: {packet.case.get_dispute_type_display()} | '
        f'Generated: {packet.generated_at.strftime("%Y-%m-%d %H:%M")}',
        body_style,
    ))
    story.append(Spacer(1, 12))

    # Section 1: Executive Summary
    story.append(Paragraph('1. Executive Summary', heading_style))
    story.append(Paragraph(packet.executive_summary or 'Not available.', body_style))
    story.append(Spacer(1, 8))

    # Section 2: Issues and Likely Claims
    story.append(Paragraph('2. Issues and Likely Claims', heading_style))
    if packet.issues:
        for i, issue in enumerate(packet.issues, 1):
            issue_text = issue.get('issue', '') if isinstance(issue, dict) else str(issue)
            story.append(Paragraph(f'{i}. {issue_text}', body_style))
    else:
        story.append(Paragraph('No issues identified.', body_style))
    story.append(Spacer(1, 8))

    # Section 3: Evidence Table
    story.append(Paragraph('3. Evidence Table', heading_style))
    if packet.evidence_table:
        table_data = [['Document', 'Type', 'Date', 'Status']]
        for item in packet.evidence_table:
            if isinstance(item, dict):
                table_data.append([
                    item.get('document_name', ''),
                    item.get('type', ''),
                    item.get('date', ''),
                    item.get('status', ''),
                ])

        if len(table_data) > 1:
            t = Table(table_data, colWidths=[150, 80, 80, 80])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1a365d')),
                ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#f7fafc'), HexColor('#ffffff')]),
            ]))
            story.append(t)
    else:
        story.append(Paragraph('No evidence uploaded.', body_style))
    story.append(Spacer(1, 8))

    # Section 4: Chronological Timeline
    story.append(Paragraph('4. Chronological Timeline', heading_style))
    if packet.timeline:
        for event in packet.timeline:
            if isinstance(event, dict):
                date_str = event.get('date', 'UNDATED')
                desc = event.get('description', '')
                story.append(Paragraph(f'<b>{date_str}</b> — {desc}', body_style))
    else:
        story.append(Paragraph('No timeline events.', body_style))
    story.append(Spacer(1, 8))

    # Section 5: Gap Report
    story.append(Paragraph('5. Evidence Gap Report', heading_style))
    if packet.gap_report and isinstance(packet.gap_report, dict):
        gaps = packet.gap_report.get('gaps', [])
        if gaps:
            for gap in gaps:
                if isinstance(gap, dict):
                    severity = gap.get('severity', '').upper()
                    item_name = gap.get('item', '')
                    remediation = gap.get('remediation', '')
                    story.append(Paragraph(
                        f'<b>[{severity}]</b> {item_name} — {remediation}',
                        body_style,
                    ))
        else:
            story.append(Paragraph('No gaps detected. Evidence appears complete.', body_style))

        pct = packet.gap_report.get('completion_percentage', 0)
        story.append(Paragraph(f'<b>Overall completion: {pct}%</b>', body_style))
    story.append(Spacer(1, 8))

    # Section 6: Questions for Lawyer
    story.append(Paragraph('6. Preliminary Questions for Your Lawyer', heading_style))
    if packet.lawyer_questions:
        for i, q in enumerate(packet.lawyer_questions, 1):
            story.append(Paragraph(f'{i}. {q}', body_style))
    else:
        story.append(Paragraph('No questions generated.', body_style))

    # Build
    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)

    return pdf_path
