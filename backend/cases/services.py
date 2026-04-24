"""
Cases app business logic services.

Placeholder — business logic will be implemented alongside API views.
Contains non-AI business logic like gap report generation,
evidence template loading, jurisdiction mapping, etc.
"""


# Hardcoded jurisdiction mapping (no LLM — per specification)
JURISDICTION_MAP = {
    'TENANT_LANDLORD': {
        'Karnataka': [
            'Karnataka Rent Control Act 2001',
            'Transfer of Property Act 1882',
            'Specific Relief Act 1963',
        ],
    },
    'FREELANCE_PAYMENT': {
        'All India': [
            'Indian Contract Act 1872, Section 73',
            'Limitation Act 1963',
            'MSME Delayed Payment Act 2006 (if applicable)',
        ],
    },
}


# Hardcoded legal issues map (TEMPLATE-POPULATED — no LLM per specification)
LEGAL_ISSUES_MAP = {
    'TENANT_LANDLORD': {
        'Karnataka': [
            'Security Deposit Recovery under Karnataka Rent Control Act 2001, Section 21',
            'Breach of Lease Agreement under Transfer of Property Act 1882',
            'Specific Performance under Specific Relief Act 1963',
        ],
    },
    'FREELANCE_PAYMENT': {
        'All India': [
            'Breach of Contract under Indian Contract Act 1872, Section 73',
            'Recovery of Debt under Limitation Act 1963',
            'Delayed Payment Interest under MSMED Act 2006 (if applicable)',
        ],
    },
}


# Hardcoded evidence templates (no LLM to prevent hallucination)
EVIDENCE_TEMPLATES = {
    'TENANT_LANDLORD': {
        'critical': [
            {'name': 'Rental/Lease Agreement', 'description': 'Signed rent agreement document'},
            {'name': 'Security Deposit Receipt', 'description': 'Proof of security deposit payment'},
            {'name': 'Bank Transfer Records', 'description': 'Rent payment history'},
        ],
        'supportive': [
            {'name': 'Move-out Photographs', 'description': 'Property condition at vacating'},
            {'name': 'Communication with Landlord', 'description': 'WhatsApp/Email exchanges'},
        ],
        'optional': [
            {'name': 'Police Complaint', 'description': 'FIR or legal notice if filed'},
        ],
    },
    'FREELANCE_PAYMENT': {
        'critical': [
            {'name': 'Signed Contract/Work Order', 'description': 'Agreement for services'},
            {'name': 'Invoices Issued', 'description': 'Payment requests sent'},
            {'name': 'Bank/UPI Payment Records', 'description': 'Transaction history'},
        ],
        'supportive': [
            {'name': 'Email/Chat Confirmation', 'description': 'Acceptance of deliverables'},
            {'name': 'Delivery Acknowledgement', 'description': 'Client confirmation of receipt'},
        ],
        'optional': [],
    },
}


def get_jurisdiction_laws(dispute_type: str, jurisdiction: str) -> list:
    """
    Get applicable laws for a dispute type and jurisdiction.
    Uses hardcoded lookup table — no LLM involved.
    """
    type_map = JURISDICTION_MAP.get(dispute_type, {})
    # Try exact jurisdiction first, then fallback to 'All India'
    laws = type_map.get(jurisdiction, type_map.get('All India', []))
    return laws


def get_legal_issues(dispute_type: str, jurisdiction: str) -> list:
    """
    Get likely legal issues for a dispute type and jurisdiction.
    TEMPLATE-POPULATED — no LLM generation per specification.
    """
    type_map = LEGAL_ISSUES_MAP.get(dispute_type, {})
    issues = type_map.get(jurisdiction, type_map.get('All India', []))
    return issues


def get_evidence_template(dispute_type: str) -> dict:
    """
    Get evidence checklist template for a dispute type.
    Hardcoded JSON templates — no LLM to prevent hallucination.
    """
    return EVIDENCE_TEMPLATES.get(dispute_type, {'critical': [], 'supportive': [], 'optional': []})


def generate_gap_report(case_id: str) -> dict:
    """
    Generate evidence gap report by comparing uploaded evidence
    against the template for the case's dispute type.

    Will be fully implemented in Phase 3.
    """
    from .models import Case, EvidenceItem

    try:
        case = Case.objects.get(case_id=case_id)
    except Case.DoesNotExist:
        return {'gaps': [], 'completion_percentage': 0}

    template = get_evidence_template(case.dispute_type)
    uploaded = EvidenceItem.objects.filter(case=case)
    uploaded_types = set(uploaded.values_list('evidence_type', flat=True))

    gaps = []
    for category in ['critical', 'supportive', 'optional']:
        for item in template.get(category, []):
            if item['name'] not in uploaded_types:
                gaps.append({
                    'item': item['name'],
                    'severity': category,
                    'remediation': f"Upload {item['description']}",
                })

    total_items = sum(len(template.get(cat, [])) for cat in ['critical', 'supportive', 'optional'])
    collected = total_items - len(gaps)
    completion_pct = round((collected / total_items) * 100) if total_items > 0 else 0

    return {
        'gaps': gaps,
        'completion_percentage': completion_pct,
        'critical_gaps': len([g for g in gaps if g['severity'] == 'critical']),
        'supportive_gaps': len([g for g in gaps if g['severity'] == 'supportive']),
    }
