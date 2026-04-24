/**
 * Legal Disclaimer Modal — Advocates Act 1961 compliance.
 * Shown on first visit. Must be acknowledged before using the system.
 */
import { useState } from 'react';

interface Props {
  onAgree: () => void;
}

export default function DisclaimerModal({ onAgree }: Props) {
  const [checked, setChecked] = useState(false);

  return (
    <div className="modal-overlay" style={{ zIndex: 999 }}>
      <div className="modal-content" style={{ maxWidth: 560 }}>
        <div style={{ textAlign: 'center', marginBottom: 20 }}>
          <div style={{ fontSize: '2.5rem', marginBottom: 8 }}>⚖️</div>
          <h2>Important Legal Notice</h2>
        </div>

        <div className="alert alert-warning" style={{ marginBottom: 20 }}>
          <p style={{ marginBottom: 12 }}>
            This system provides <strong>informational tools only</strong> and does
            not constitute legal advice.
          </p>
          <p style={{ marginBottom: 12 }}>
            Under the <strong>Advocates Act, 1961</strong>, only licensed advocates
            can practice law in India.
          </p>
          <p>
            You <strong>must consult a licensed advocate</strong> before taking any
            legal action.
          </p>
        </div>

        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            cursor: 'pointer',
            marginBottom: 20,
            fontSize: '0.9rem',
            color: 'var(--text-secondary)',
          }}
        >
          <input
            type="checkbox"
            checked={checked}
            onChange={(e) => setChecked(e.target.checked)}
            style={{ width: 18, height: 18, accentColor: 'var(--accent)' }}
          />
          I understand and agree to these terms
        </label>

        <button
          className="btn btn-primary btn-lg btn-full"
          disabled={!checked}
          onClick={onAgree}
        >
          Continue to EvidenceChain
        </button>
      </div>
    </div>
  );
}
