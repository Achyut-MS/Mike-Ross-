import { useNavigate } from 'react-router-dom';
import { clearTokens } from '../services/api';

export default function Navbar() {
  const navigate = useNavigate();

  const handleLogout = () => {
    clearTokens();
    navigate('/login');
  };

  return (
    <nav className="navbar">
      <div
        className="navbar-brand"
        style={{ cursor: 'pointer' }}
        onClick={() => navigate('/')}
      >
        <div className="logo-icon">⚖</div>
        <span>EvidenceChain</span>
      </div>

      <div className="navbar-links">
        <button className="btn btn-sm" onClick={() => navigate('/')}>
          Dashboard
        </button>
        <button className="btn btn-sm" onClick={() => navigate('/cases/new')}>
          + New Case
        </button>
        <button className="btn btn-sm btn-danger" onClick={handleLogout}>
          Logout
        </button>
      </div>
    </nav>
  );
}
