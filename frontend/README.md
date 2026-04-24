# EvidenceChain Frontend

React + TypeScript SPA for the EvidenceChain dispute preparation system.

## Tech Stack

- **React 19** with TypeScript
- **Vite** for build tooling
- **Axios** for API calls with JWT interceptors
- **React Router DOM** for client-side routing

## Pages

| Page | Route | Description |
|------|-------|-------------|
| Login | `/login` | JWT authentication |
| Register | `/register` | Account creation |
| Dashboard | `/` | Case list with stats |
| New Case | `/cases/new` | Multi-step: narrative → classify → confirm |
| Case Detail | `/cases/:id` | 4 tabs: overview, evidence, timeline, packet |

## Components

| Component | Purpose |
|-----------|---------|
| `DisclaimerModal` | Advocates Act 1961 legal notice (shown once) |
| `Navbar` | Navigation with brand, dashboard, new case, logout |
| `EvidenceGuidedInterview` | Sequential evidence collection with file upload |

## Development

```bash
npm install
npm run dev       # Dev server at http://localhost:3000
npm run build     # Production build
npm run lint      # ESLint check
```

The dev server proxies `/api` requests to `http://localhost:8080` (Django backend).

## Design

- Dark glassmorphism aesthetic
- Inter font via Google Fonts
- CSS custom properties design system (no framework)
- Micro-animations for polish
