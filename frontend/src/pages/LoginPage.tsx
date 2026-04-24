import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { login, setTokens } from '../services/api';

export default function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await login({ username, password });
      setTokens(res.data.access_token, res.data.refresh_token);
      window.location.href = '/';
    } catch {
      setError('Invalid credentials. Please try again.');
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
          <h2>Welcome Back</h2>
          <p className="text-muted text-sm" style={{ marginTop: 4 }}>
            Sign in to EvidenceChain
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          style={{ display: 'flex', flexDirection: 'column', gap: 16 }}
        >
          <div className="form-group">
            <label className="form-label">Username</label>
            <input
              className="input"
              type="text"
              placeholder="Enter your username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              className="input"
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
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
            {loading ? <span className="spinner" /> : 'Sign In'}
          </button>
        </form>

        <p
          className="text-muted text-sm"
          style={{ textAlign: 'center', marginTop: 20 }}
        >
          Don't have an account?{' '}
          <Link to="/register">Create one</Link>
        </p>
      </div>
    </div>
  );
}
