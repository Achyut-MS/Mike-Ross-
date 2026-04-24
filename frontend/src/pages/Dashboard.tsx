import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { listCases } from '../services/api';

interface CaseSummary {
  case_id: string;
  dispute_type: string;
  jurisdiction: string;
  status: string;
  created_at: string;
  evidence_count: number;
  timeline_event_count: number;
  case_packet_generated: boolean;
}

const DISPUTE_LABELS: Record<string, string> = {
  TENANT_LANDLORD: 'Tenant-Landlord',
  FREELANCE_PAYMENT: 'Freelance Payment',
};

export default function Dashboard() {
  const navigate = useNavigate();
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCases();
  }, []);

  const fetchCases = async () => {
    try {
      const res = await listCases();
      setCases(res.data.results);
    } catch (err) {
      console.error('Failed to fetch cases:', err);
    } finally {
      setLoading(false);
    }
  };

  const activeCount = cases.filter((c) => c.status === 'active').length;
  const completedCount = cases.filter((c) => c.status === 'completed').length;
  const totalEvidence = cases.reduce((sum, c) => sum + c.evidence_count, 0);

  if (loading) {
    return (
      <div className="page container text-center" style={{ paddingTop: 80 }}>
        <div className="spinner spinner-lg" style={{ margin: '0 auto' }} />
        <p className="text-muted mt-md">Loading your cases…</p>
      </div>
    );
  }

  return (
    <div className="page container">
      {/* Header */}
      <div className="flex justify-between items-center mb-md animate-in">
        <div>
          <h1>Dashboard</h1>
          <p className="text-muted text-sm" style={{ marginTop: 4 }}>
            Manage your dispute preparation cases
          </p>
        </div>
        <button
          className="btn btn-primary btn-lg"
          onClick={() => navigate('/cases/new')}
        >
          + New Case
        </button>
      </div>

      {/* Stats */}
      <div
        className="grid-3 mb-md"
        style={{ animationDelay: '80ms' }}
      >
        <div className="card stat-card animate-in" style={{ animationDelay: '100ms' }}>
          <div className="stat-value">{activeCount}</div>
          <div className="stat-label">Active Cases</div>
        </div>
        <div className="card stat-card animate-in" style={{ animationDelay: '180ms' }}>
          <div className="stat-value">{totalEvidence}</div>
          <div className="stat-label">Evidence Items</div>
        </div>
        <div className="card stat-card animate-in" style={{ animationDelay: '260ms' }}>
          <div className="stat-value">{completedCount}</div>
          <div className="stat-label">Completed</div>
        </div>
      </div>

      {/* Case List */}
      {cases.length === 0 ? (
        <div className="card empty-state animate-in" style={{ animationDelay: '300ms' }}>
          <div className="empty-state-icon">📋</div>
          <h3>No cases yet</h3>
          <p className="text-muted" style={{ margin: '8px 0 20px' }}>
            Create your first case to start organizing your dispute documentation.
          </p>
          <button
            className="btn btn-primary"
            onClick={() => navigate('/cases/new')}
          >
            + Create Your First Case
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-sm">
          {cases.map((c, i) => (
            <div
              key={c.case_id}
              className="card card-interactive animate-in"
              style={{
                cursor: 'pointer',
                animationDelay: `${300 + i * 60}ms`,
              }}
              onClick={() => navigate(`/cases/${c.case_id}`)}
            >
              <div className="flex justify-between items-center">
                <div>
                  <div className="flex items-center gap-sm mb-md" style={{ marginBottom: 4 }}>
                    <span className={`badge badge-${c.status}`}>
                      {c.status}
                    </span>
                    {c.dispute_type && (
                      <span className="badge badge-optional">
                        {DISPUTE_LABELS[c.dispute_type] || c.dispute_type}
                      </span>
                    )}
                  </div>
                  <h3 style={{ marginBottom: 4 }}>
                    {c.dispute_type
                      ? DISPUTE_LABELS[c.dispute_type] + ' Dispute'
                      : 'New Case — Pending Classification'}
                  </h3>
                  <p className="text-muted text-sm">
                    {c.jurisdiction && `${c.jurisdiction} · `}
                    Created {new Date(c.created_at).toLocaleDateString()}
                  </p>
                </div>

                <div className="flex gap-md" style={{ textAlign: 'center' }}>
                  <div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {c.evidence_count}
                    </div>
                    <div className="text-muted text-sm">Evidence</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {c.timeline_event_count}
                    </div>
                    <div className="text-muted text-sm">Events</div>
                  </div>
                  <div style={{ fontSize: '1.5rem' }}>
                    {c.case_packet_generated ? '📦' : '→'}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
