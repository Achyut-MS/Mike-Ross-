import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { getAccessToken } from './services/api';

import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import Dashboard from './pages/Dashboard';
import NewCase from './pages/NewCase';
import CaseDetail from './pages/CaseDetail';
import DisclaimerModal from './components/DisclaimerModal';
import Navbar from './components/Navbar';

import './index.css';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = getAccessToken();
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function App() {
  const [agreedToDisclaimer, setAgreedToDisclaimer] = useState(false);

  useEffect(() => {
    const agreed = localStorage.getItem('ec_disclaimer_agreed');
    if (agreed === 'true') setAgreedToDisclaimer(true);
  }, []);

  const handleAgree = () => {
    localStorage.setItem('ec_disclaimer_agreed', 'true');
    setAgreedToDisclaimer(true);
  };

  const isLoggedIn = !!getAccessToken();

  return (
    <BrowserRouter>
      {!agreedToDisclaimer && <DisclaimerModal onAgree={handleAgree} />}

      {isLoggedIn && <Navbar />}

      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/cases/new"
          element={
            <ProtectedRoute>
              <NewCase />
            </ProtectedRoute>
          }
        />
        <Route
          path="/cases/:caseId"
          element={
            <ProtectedRoute>
              <CaseDetail />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
