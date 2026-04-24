import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createCase, extractEntities, categorizeDispute, confirmClassification } from '../services/api';

type Step = 'narrative' | 'extracting' | 'classifying' | 'confirm' | 'done';

export default function NewCase() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>('narrative');
  const [narrative, setNarrative] = useState('');
  const [caseId, setCaseId] = useState('');
  const [entities, setEntities] = useState<any>(null);
  const [classification, setClassification] = useState<any>(null);
  const [jurisdiction, setJurisdiction] = useState('Karnataka');
  const [error, setError] = useState('');

  const handleCreateCase = async () => {
    if (!narrative.trim()) return;
    setError('');
    setStep('extracting');

    try {
      // Step 1: Create case
      const caseRes = await createCase(narrative);
      const newCaseId = caseRes.data.case_id;
      setCaseId(newCaseId);

      // Step 2: Extract entities
      const entRes = await extractEntities(newCaseId, narrative);
      setEntities(entRes.data.entities);

      // Step 3: Classify dispute
      setStep('classifying');
      const classRes = await categorizeDispute(
        newCaseId,
        entRes.data.entities,
        narrative
      );
      setClassification(classRes.data);
      setStep('confirm');
    } catch (err: any) {
      // If AI service is unavailable, still create case and go to confirm with manual selection
      if (caseId || err?.response?.status === 503) {
        setStep('confirm');
        setClassification({
          dispute_type: 'TENANT_LANDLORD',
          confidence: 0,
          reasoning: 'AI service unavailable — please select manually',
          requires_manual_confirmation: true,
        });
      } else {
        setError('Failed to create case. Please try again.');
        setStep('narrative');
      }
    }
  };

  const handleConfirm = async (disputeType: string) => {
    try {
      await confirmClassification(caseId, disputeType, jurisdiction);
      setStep('done');
      setTimeout(() => navigate(`/cases/${caseId}`), 1200);
    } catch {
      setError('Failed to confirm classification.');
    }
  };

  return (
    <div className="page container" style={{ maxWidth: 680, margin: '0 auto' }}>
      <h1 className="animate-in">New Case</h1>
      <p className="text-muted text-sm mb-md animate-in" style={{ animationDelay: '50ms' }}>
        Describe your dispute and we'll help organize your evidence
      </p>

      {/* Step 1: Narrative */}
      {step === 'narrative' && (
        <div className="card animate-in" style={{ animationDelay: '100ms' }}>
          <h3 style={{ marginBottom: 16 }}>📝 Describe Your Dispute</h3>
          <p className="text-muted text-sm" style={{ marginBottom: 16 }}>
            Tell us what happened in your own words. Include names, dates, amounts,
            and locations if possible.
          </p>

          <textarea
            className="textarea"
            placeholder="Example: My landlord hasn't returned my security deposit of ₹1,50,000. I moved out 4 months ago from my apartment in Bengaluru, Karnataka..."
            value={narrative}
            onChange={(e) => setNarrative(e.target.value)}
            rows={8}
            autoFocus
          />

          {error && (
            <div className="alert alert-warning mt-md">{error}</div>
          )}

          <button
            className="btn btn-primary btn-lg btn-full mt-lg"
            onClick={handleCreateCase}
            disabled={!narrative.trim()}
          >
            Analyze My Dispute →
          </button>
        </div>
      )}

      {/* Step 2: Extracting */}
      {step === 'extracting' && (
        <div className="card animate-in text-center" style={{ padding: 48 }}>
          <div className="spinner spinner-lg" style={{ margin: '0 auto 20px' }} />
          <h3>Extracting Key Information</h3>
          <p className="text-muted text-sm mt-sm">
            Identifying parties, dates, amounts, and locations…
          </p>
        </div>
      )}

      {/* Step 3: Classifying */}
      {step === 'classifying' && (
        <div className="card animate-in text-center" style={{ padding: 48 }}>
          <div className="spinner spinner-lg" style={{ margin: '0 auto 20px' }} />
          <h3>Classifying Dispute</h3>
          <p className="text-muted text-sm mt-sm">
            Determining dispute type and applicable laws…
          </p>

          {entities && (
            <div className="mt-lg" style={{ textAlign: 'left' }}>
              <h4>Extracted Entities</h4>
              <div className="mt-sm flex gap-sm" style={{ flexWrap: 'wrap' }}>
                {entities.parties?.map((p: string, i: number) => (
                  <span key={i} className="badge badge-optional">{p}</span>
                ))}
                {entities.monetary_amounts?.map((a: string, i: number) => (
                  <span key={i} className="badge badge-critical">{a}</span>
                ))}
                {entities.locations?.map((l: string, i: number) => (
                  <span key={i} className="badge badge-supportive">{l}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Step 4: Confirm Classification */}
      {step === 'confirm' && (
        <div className="card animate-in">
          <h3 style={{ marginBottom: 16 }}>✅ Confirm Dispute Type</h3>

          {classification && (
            <div className="alert alert-info" style={{ marginBottom: 20 }}>
              <strong>
                {classification.dispute_type === 'TENANT_LANDLORD'
                  ? 'Tenant-Landlord Dispute'
                  : 'Freelance Payment Dispute'}
              </strong>
              {classification.confidence > 0 && (
                <span className="text-sm">
                  {' '}
                  (Confidence: {Math.round(classification.confidence * 100)}%)
                </span>
              )}
              <p className="text-sm mt-sm">{classification.reasoning}</p>
            </div>
          )}

          <div className="form-group" style={{ marginBottom: 16 }}>
            <label className="form-label">Dispute Type</label>
            <div className="flex gap-sm">
              <button
                className={`btn ${classification?.dispute_type === 'TENANT_LANDLORD' ? 'btn-primary' : ''}`}
                onClick={() =>
                  setClassification((prev: any) => ({
                    ...prev,
                    dispute_type: 'TENANT_LANDLORD',
                  }))
                }
              >
                🏠 Tenant-Landlord
              </button>
              <button
                className={`btn ${classification?.dispute_type === 'FREELANCE_PAYMENT' ? 'btn-primary' : ''}`}
                onClick={() =>
                  setClassification((prev: any) => ({
                    ...prev,
                    dispute_type: 'FREELANCE_PAYMENT',
                  }))
                }
              >
                💼 Freelance Payment
              </button>
            </div>
          </div>

          <div className="form-group" style={{ marginBottom: 24 }}>
            <label className="form-label">Jurisdiction</label>
            <select
              className="input"
              value={jurisdiction}
              onChange={(e) => setJurisdiction(e.target.value)}
            >
              <option value="Karnataka">Karnataka</option>
              <option value="Maharashtra">Maharashtra</option>
              <option value="Delhi">Delhi</option>
              <option value="Tamil Nadu">Tamil Nadu</option>
              <option value="All India">All India</option>
            </select>
          </div>

          {error && <div className="alert alert-warning mb-md">{error}</div>}

          <button
            className="btn btn-primary btn-lg btn-full"
            onClick={() => handleConfirm(classification?.dispute_type || 'TENANT_LANDLORD')}
          >
            Confirm & Continue →
          </button>
        </div>
      )}

      {/* Step 5: Done */}
      {step === 'done' && (
        <div className="card animate-in text-center" style={{ padding: 48 }}>
          <div style={{ fontSize: '3rem', marginBottom: 16 }}>🎉</div>
          <h2>Case Created!</h2>
          <p className="text-muted mt-sm">
            Redirecting to your case…
          </p>
        </div>
      )}
    </div>
  );
}
