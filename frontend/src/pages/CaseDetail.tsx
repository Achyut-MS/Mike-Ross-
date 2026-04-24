import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  getCase, getTimeline, getGapReport, getEvidenceTemplate,
  generateCasePacket, getCasePacket,
} from '../services/api';
import EvidenceGuidedInterview from '../components/EvidenceGuidedInterview';

type Tab = 'overview' | 'evidence' | 'timeline' | 'packet';

const DISPUTE_LABELS: Record<string, string> = {
  TENANT_LANDLORD: 'Tenant-Landlord Dispute',
  FREELANCE_PAYMENT: 'Freelance Payment Dispute',
};

export default function CaseDetail() {
  const { caseId } = useParams<{ caseId: string }>();
  const [tab, setTab] = useState<Tab>('overview');
  const [caseData, setCaseData] = useState<any>(null);
  const [timeline, setTimeline] = useState<any>(null);
  const [gapReport, setGapReport] = useState<any>(null);
  const [packet, setPacket] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    if (caseId) fetchAll();
  }, [caseId]);

  const fetchAll = async () => {
    try {
      const [caseRes, timelineRes, gapRes] = await Promise.allSettled([
        getCase(caseId!),
        getTimeline(caseId!),
        getGapReport(caseId!),
      ]);

      if (caseRes.status === 'fulfilled') setCaseData(caseRes.value.data);
      if (timelineRes.status === 'fulfilled') setTimeline(timelineRes.value.data);
      if (gapRes.status === 'fulfilled') setGapReport(gapRes.value.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleGeneratePacket = async () => {
    setGenerating(true);
    try {
      await generateCasePacket(caseId!);
      // Poll for completion (simplified — just wait)
      setTimeout(async () => {
        await fetchAll();
        setGenerating(false);
      }, 3000);
    } catch {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="page container text-center" style={{ paddingTop: 80 }}>
        <div className="spinner spinner-lg" style={{ margin: '0 auto' }} />
      </div>
    );
  }

  if (!caseData) {
    return (
      <div className="page container">
        <div className="card empty-state">
          <h3>Case not found</h3>
        </div>
      </div>
    );
  }

  const tabs: { key: Tab; label: string; icon: string }[] = [
    { key: 'overview', label: 'Overview', icon: '📊' },
    { key: 'evidence', label: 'Evidence', icon: '📎' },
    { key: 'timeline', label: 'Timeline', icon: '📅' },
    { key: 'packet', label: 'Case Packet', icon: '📦' },
  ];

  return (
    <div className="page container">
      {/* Header */}
      <div className="animate-in mb-md">
        <div className="flex items-center gap-sm" style={{ marginBottom: 8 }}>
          <span className={`badge badge-${caseData.status}`}>{caseData.status}</span>
          {caseData.dispute_type && (
            <span className="badge badge-optional">
              {DISPUTE_LABELS[caseData.dispute_type] || caseData.dispute_type}
            </span>
          )}
        </div>
        <h1>{DISPUTE_LABELS[caseData.dispute_type] || 'Case Details'}</h1>
        <p className="text-muted text-sm">
          {caseData.jurisdiction && `${caseData.jurisdiction} · `}
          Case ID: {caseData.case_id?.slice(0, 8)}…
        </p>
      </div>

      {/* Tabs */}
      <div
        className="flex gap-sm mb-md animate-in"
        style={{ borderBottom: '1px solid var(--border)', paddingBottom: 0, animationDelay: '80ms' }}
      >
        {tabs.map((t) => (
          <button
            key={t.key}
            className="btn btn-sm"
            style={{
              borderRadius: '8px 8px 0 0',
              borderBottom: tab === t.key ? '2px solid var(--accent)' : '2px solid transparent',
              background: tab === t.key ? 'var(--bg-glass-hover)' : 'transparent',
              color: tab === t.key ? 'var(--text-primary)' : 'var(--text-muted)',
            }}
            onClick={() => setTab(t.key)}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="animate-in" style={{ animationDelay: '160ms' }}>
        {tab === 'overview' && (
          <OverviewTab caseData={caseData} gapReport={gapReport} timeline={timeline} />
        )}
        {tab === 'evidence' && <EvidenceGuidedInterview caseId={caseId!} />}
        {tab === 'timeline' && <TimelineTab timeline={timeline} />}
        {tab === 'packet' && (
          <PacketTab
            caseData={caseData}
            onGenerate={handleGeneratePacket}
            generating={generating}
          />
        )}
      </div>
    </div>
  );
}

/* ---- Overview Tab ---- */
function OverviewTab({
  caseData,
  gapReport,
  timeline,
}: {
  caseData: any;
  gapReport: any;
  timeline: any;
}) {
  return (
    <div className="flex flex-col gap-md">
      {/* Stats Row */}
      <div className="grid-4">
        <div className="card stat-card">
          <div className="stat-value">{caseData.evidence_items?.length || 0}</div>
          <div className="stat-label">Evidence Items</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value">{timeline?.stats?.total_events || 0}</div>
          <div className="stat-label">Timeline Events</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value">{gapReport?.completion_percentage || 0}%</div>
          <div className="stat-label">Completion</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value">{gapReport?.critical_gaps || 0}</div>
          <div className="stat-label">Critical Gaps</div>
        </div>
      </div>

      {/* Narrative */}
      {caseData.user_narrative && (
        <div className="card">
          <h3 style={{ marginBottom: 12 }}>📝 Your Narrative</h3>
          <p className="text-muted" style={{ lineHeight: 1.7 }}>
            {caseData.user_narrative}
          </p>
        </div>
      )}

      {/* Applicable Laws */}
      {caseData.applicable_laws?.length > 0 && (
        <div className="card">
          <h3 style={{ marginBottom: 12 }}>⚖️ Applicable Laws</h3>
          <div className="flex flex-col gap-sm">
            {caseData.applicable_laws.map((law: string, i: number) => (
              <div
                key={i}
                style={{
                  padding: '10px 14px',
                  background: 'var(--bg-glass)',
                  borderRadius: 'var(--radius-md)',
                  borderLeft: '3px solid var(--accent)',
                  fontSize: '0.9rem',
                }}
              >
                {law}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Gap Report */}
      {gapReport?.gaps?.length > 0 && (
        <div className="card">
          <h3 style={{ marginBottom: 12 }}>🔍 Evidence Gaps</h3>
          <div className="flex flex-col gap-sm">
            {gapReport.gaps.map((gap: any, i: number) => (
              <div
                key={i}
                className="flex items-center gap-sm"
                style={{
                  padding: '10px 14px',
                  background: gap.severity === 'critical' ? 'var(--danger-bg)' : 'var(--warning-bg)',
                  borderRadius: 'var(--radius-md)',
                }}
              >
                <span className={`badge badge-${gap.severity}`}>{gap.severity}</span>
                <span style={{ fontSize: '0.9rem' }}>{gap.item}</span>
                <span className="text-muted text-sm" style={{ marginLeft: 'auto' }}>
                  {gap.remediation}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ---- Timeline Tab ---- */
function TimelineTab({ timeline }: { timeline: any }) {
  if (!timeline?.events?.length) {
    return (
      <div className="card empty-state">
        <div className="empty-state-icon">📅</div>
        <h3>No timeline events yet</h3>
        <p className="text-muted mt-sm">
          Upload evidence to auto-populate your timeline, or add events manually.
        </p>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="flex justify-between items-center" style={{ marginBottom: 20 }}>
        <h3>📅 Case Timeline</h3>
        <span className="text-muted text-sm">
          {timeline.stats?.total_events} events
        </span>
      </div>

      <div className="timeline">
        {timeline.events.map((event: any) => (
          <div key={event.event_id} className="timeline-item">
            <div className={`timeline-dot ${event.type === 'gap' ? 'gap' : ''}`} />
            <div className="timeline-date">
              {event.event_date || event.date || 'UNDATED'}
            </div>
            <div className="timeline-desc">
              {event.action_description || event.description}
            </div>
            {event.actors?.length > 0 && (
              <div className="flex gap-sm mt-sm">
                {event.actors.map((a: string, i: number) => (
                  <span key={i} className="badge badge-optional">{a}</span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ---- Case Packet Tab ---- */
function PacketTab({
  caseData,
  onGenerate,
  generating,
}: {
  caseData: any;
  onGenerate: () => void;
  generating: boolean;
}) {
  return (
    <div className="flex flex-col gap-md">
      <div className="card">
        <h3 style={{ marginBottom: 16 }}>📦 Case Packet Generator</h3>
        <p className="text-muted text-sm" style={{ marginBottom: 20 }}>
          Generate a comprehensive 6-section case preparation document including
          executive summary, applicable issues, evidence table, chronological timeline,
          gap report, and preliminary questions for your lawyer.
        </p>

        <div className="alert alert-info" style={{ marginBottom: 20 }}>
          <strong>Sections included:</strong>
          <ol style={{ marginTop: 8, paddingLeft: 20, lineHeight: 1.8 }}>
            <li>Executive Summary (AI-generated)</li>
            <li>Issues and Likely Claims (Template-based)</li>
            <li>Evidence Table</li>
            <li>Chronological Timeline</li>
            <li>Evidence Gap Report</li>
            <li>Questions for Your Lawyer (AI-generated)</li>
          </ol>
        </div>

        <button
          className="btn btn-primary btn-lg btn-full"
          onClick={onGenerate}
          disabled={generating}
        >
          {generating ? (
            <>
              <span className="spinner" /> Generating…
            </>
          ) : (
            '⚡ Generate Case Packet'
          )}
        </button>
      </div>

      <div className="alert alert-warning">
        This document is for informational purposes only and does not constitute
        legal advice. Consult a licensed advocate before taking any legal action.
      </div>
    </div>
  );
}
