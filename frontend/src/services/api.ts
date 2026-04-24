/**
 * API service for EvidenceChain frontend.
 *
 * Handles JWT token management and all API calls to the Django backend.
 * Base URL is configured via VITE_API_URL environment variable.
 */

import axios from 'axios';
import type { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080/api/v1';

// Create axios instance
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ---- Token Management ----

const TOKEN_KEY = 'ec_access_token';
const REFRESH_KEY = 'ec_refresh_token';

export const getAccessToken = (): string | null => localStorage.getItem(TOKEN_KEY);
export const getRefreshToken = (): string | null => localStorage.getItem(REFRESH_KEY);

export const setTokens = (access: string, refresh: string): void => {
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
};

export const clearTokens = (): void => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
};

// ---- Request Interceptor: Attach JWT ----

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getAccessToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ---- Response Interceptor: Handle 401 / Refresh ----

api.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const refresh = getRefreshToken();
      if (refresh) {
        try {
          const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: refresh,
          });
          const { access_token } = response.data;
          setTokens(access_token, refresh);

          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return api(originalRequest);
        } catch {
          clearTokens();
          window.location.href = '/login';
        }
      } else {
        clearTokens();
        window.location.href = '/login';
      }
    }

    return Promise.reject(error);
  }
);

// ---- API Methods ----

// Auth
export const register = (data: { username: string; password: string; first_name: string; last_name: string }) =>
  api.post('/auth/register', data);

export const login = (data: { username: string; password: string }) =>
  api.post('/auth/login', data);

export const logout = () => {
  const refresh = getRefreshToken();
  return api.post('/auth/logout', { refresh_token: refresh });
};

// Cases
export const createCase = (narrative: string) =>
  api.post('/cases/create', { user_narrative: narrative });

export const listCases = (params?: { status?: string; limit?: number; offset?: number }) =>
  api.get('/cases/', { params });

export const getCase = (caseId: string) =>
  api.get(`/cases/${caseId}`);

// Classification
export const extractEntities = (caseId: string, narrative: string) =>
  api.post(`/cases/${caseId}/classify/extract-entities`, { narrative });

export const categorizeDispute = (caseId: string, entities: object, narrative: string) =>
  api.post(`/cases/${caseId}/classify/categorize`, { entities, narrative });

export const confirmClassification = (caseId: string, disputeType: string, jurisdiction: string) =>
  api.post(`/cases/${caseId}/classify/confirm`, { dispute_type: disputeType, jurisdiction });

// Evidence
export const getEvidenceTemplate = (caseId: string) =>
  api.get(`/cases/${caseId}/evidence/template`);

export const requestPresignedUrl = (data: {
  case_id: string;
  evidence_type: string;
  filename: string;
  content_type: string;
  file_size: number;
}) => api.post('/evidence/presigned-url', data);

export const registerEvidence = (data: {
  evidence_id: string;
  s3_key: string;
  file_size: number;
  content_type: string;
}) => api.post('/evidence/register', data);

export const getEvidenceStatus = (evidenceId: string) =>
  api.get(`/evidence/${evidenceId}/status`);

export const getGapReport = (caseId: string) =>
  api.get(`/cases/${caseId}/gap-report`);

// Timeline
export const getTimeline = (caseId: string) =>
  api.get(`/cases/${caseId}/timeline`);

export const addTimelineEvent = (caseId: string, event: {
  event_date: string;
  action_description: string;
  actors: string[];
  evidence_refs?: string[];
}) => api.post(`/cases/${caseId}/timeline/events`, event);

export const deduplicateTimeline = (caseId: string) =>
  api.post(`/cases/${caseId}/timeline/deduplicate`);

// Case Packet
export const generateCasePacket = (caseId: string) =>
  api.post(`/cases/${caseId}/case-packet/generate`);

export const getCasePacketStatus = (packetId: string) =>
  api.get(`/case-packets/${packetId}/status`);

export const getCasePacket = (packetId: string) =>
  api.get(`/case-packets/${packetId}`);

export const downloadCasePacketPdf = (packetId: string) =>
  api.get(`/case-packets/${packetId}/download`, { responseType: 'blob' });

// Health
export const healthCheck = () =>
  api.get('/health');

export default api;
