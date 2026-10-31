const API_BASE_URL = '';

let accessToken = localStorage.getItem('sentinel_access_token') || null;
let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

export const setAccessToken = (token) => {
  accessToken = token;
  if (token) {
    localStorage.setItem('sentinel_access_token', token);
  } else {
    localStorage.removeItem('sentinel_access_token');
  }
};

export const getAccessToken = () => accessToken;

export async function apiClient(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (accessToken && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }

  const config = {
    ...options,
    headers,
    credentials: 'include', // Ensures HttpOnly cookies are attached
  };

  try {
    const response = await fetch(url, config);

    // If 401 Unauthorized and not already authenticating/refreshing
    if (
      response.status === 401 &&
      !endpoint.includes('/api/auth/login') &&
      !endpoint.includes('/api/auth/register') &&
      !endpoint.includes('/api/auth/refresh')
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((newTok) => {
            config.headers['Authorization'] = `Bearer ${newTok}`;
            return fetch(url, config).then(handleResponse);
          })
          .catch((err) => Promise.reject(err));
      }

      isRefreshing = true;

      try {
        const refreshRes = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
        });

        if (!refreshRes.ok) {
          throw new Error('Refresh token invalid or expired');
        }

        const data = await refreshRes.json();
        setAccessToken(data.access_token);
        processQueue(null, data.access_token);

        config.headers['Authorization'] = `Bearer ${data.access_token}`;
        return fetch(url, config).then(handleResponse);
      } catch (refreshErr) {
        processQueue(refreshErr, null);
        setAccessToken(null);
        window.dispatchEvent(new CustomEvent('auth:expired'));
        throw refreshErr;
      } finally {
        isRefreshing = false;
      }
    }

    return handleResponse(response);
  } catch (error) {
    return Promise.reject(error);
  }
}

async function handleResponse(response) {
  if (response.status === 204) {
    return null;
  }
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};

  if (!response.ok) {
    const errorMsg = data.detail || (Array.isArray(data.detail) ? data.detail.map(d => d.msg).join(', ') : 'An unexpected error occurred');
    const err = new Error(errorMsg);
    err.status = response.status;
    err.data = data;
    throw err;
  }

  return data;
}

// ----------------- Auth API -----------------
export const authApi = {
  register: (payload) =>
    apiClient('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  login: (payload) =>
    apiClient('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  logout: () =>
    apiClient('/api/auth/logout', {
      method: 'POST',
    }),
  getMe: () =>
    apiClient('/api/auth/me', {
      method: 'GET',
    }),
  refreshToken: () =>
    apiClient('/api/auth/refresh', {
      method: 'POST',
    }),
};

// ----------------- Organization API -----------------
export const orgApi = {
  list: () =>
    apiClient('/api/organizations', {
      method: 'GET',
    }),
  create: (data) =>
    apiClient('/api/organizations', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  get: (orgId) =>
    apiClient(`/api/organizations/${orgId}`, {
      method: 'GET',
    }),
  update: (orgId, data) =>
    apiClient(`/api/organizations/${orgId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  listMembers: (orgId) =>
    apiClient(`/api/organizations/${orgId}/members`, {
      method: 'GET',
    }),
  addMember: (orgId, data) =>
    apiClient(`/api/organizations/${orgId}/members`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateMemberRole: (orgId, userId, data) =>
    apiClient(`/api/organizations/${orgId}/members/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  removeMember: (orgId, userId) =>
    apiClient(`/api/organizations/${orgId}/members/${userId}`, {
      method: 'DELETE',
    }),
};

// ----------------- Audit API -----------------
export const auditApi = {
  list: (orgId, params = {}) => {
    const query = new URLSearchParams();
    if (params.search) query.append('search', params.search);
    if (params.status && params.status !== 'All') query.append('status', params.status);
    if (params.page) query.append('page', params.page);
    if (params.size) query.append('size', params.size);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return apiClient(`/api/organizations/${orgId}/audits${qs}`, {
      method: 'GET',
    });
  },
  create: (orgId, data) =>
    apiClient(`/api/organizations/${orgId}/audits`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  get: (orgId, auditId) =>
    apiClient(`/api/organizations/${orgId}/audits/${auditId}`, {
      method: 'GET',
    }),
  update: (orgId, auditId, data) =>
    apiClient(`/api/organizations/${orgId}/audits/${auditId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  archive: (orgId, auditId) =>
    apiClient(`/api/organizations/${orgId}/audits/${auditId}`, {
      method: 'DELETE',
    }),
  listRuns: (orgId, auditId) =>
    apiClient(`/api/organizations/${orgId}/audits/${auditId}/runs`, {
      method: 'GET',
    }),
  createRun: (orgId, auditId, data = {}) =>
    apiClient(`/api/organizations/${orgId}/audits/${auditId}/runs`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getRun: (orgId, auditId, runId) =>
    apiClient(`/api/organizations/${orgId}/audits/${auditId}/runs/${runId}`, {
      method: 'GET',
    }),
};
