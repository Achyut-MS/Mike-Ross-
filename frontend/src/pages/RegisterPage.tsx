import { useState } from 'react';
import { Link } from 'react-router-dom';
import { register, setTokens } from '../services/api';

export default function RegisterPage() {
  const [form, setForm] = useState({
    username: '',
    password: '',
    first_name: '',
    last_name: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const update = (field: string, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await register(form);
      setTokens(res.data.access_token, res.data.refresh_token);
      window.location.href = '/';
    } catch (err: any) {
      setError(err?.response?.data?.error || 'Registration failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
    >
      <div className="card animate-in" style={{ maxWidth: 420, width: '100%' }}>
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ fontSize: '2.5rem', marginBottom: 8 }}>⚖️</div>
          <h2>Create Account</h2>
          <p className="text-muted text-sm" style={{ marginTop: 4 }}>
            Get started with EvidenceChain
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          style={{ display: 'flex', flexDirection: 'column', gap: 16 }}
        >
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div className="form-group">
              <label className="form-label">First Name</label>
              <input
                className="input"
                placeholder="First"
                value={form.first_name}
                onChange={(e) => update('first_name', e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Last Name</label>
              <input
                className="input"
                placeholder="Last"
                value={form.last_name}
                onChange={(e) => update('last_name', e.target.value)}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Username</label>
            <input
              className="input"
              placeholder="Choose a username"
              value={form.username}
              onChange={(e) => update('username', e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              className="input"
              type="password"
              placeholder="Min 8 characters"
              value={form.password}
              onChange={(e) => update('password', e.target.value)}
              required
              minLength={8}
            />
          </div>

          {error && (
            <div className="alert alert-warning" style={{ fontSize: '0.85rem' }}>
              {error}
            </div>
          )}

          <button
            className="btn btn-primary btn-lg btn-full"
            type="submit"
            disabled={loading}
          >
            {loading ? <span className="spinner" /> : 'Create Account'}
          </button>
        </form>

        <p
          className="text-muted text-sm"
          style={{ textAlign: 'center', marginTop: 20 }}
        >
          Already have an account?{' '}
          <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
