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
    ...options.headers,
  };

  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  }

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

// ----------------- Document Management API -----------------
export const documentApi = {
  list: (orgId, auditId, params = {}) => {
    const query = new URLSearchParams();
    if (params.search) query.append('search', params.search);
    if (params.status && params.status !== 'All') query.append('status', params.status);
    if (params.page) query.append('page', params.page);
    if (params.size) query.append('size', params.size);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return apiClient(`/api/organizations/${orgId}/audits/${auditId}/documents${qs}`, {
      method: 'GET',
    });
  },
  upload: (orgId, auditId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient(`/api/organizations/${orgId}/audits/${auditId}/documents`, {
      method: 'POST',
      body: formData,
    });
  },
  get: (orgId, auditId, docId) =>
    apiClient(`/api/organizations/${orgId}/audits/${auditId}/documents/${docId}`, {
      method: 'GET',
    }),
  getStatus: (orgId, auditId, docId) =>
    apiClient(`/api/organizations/${orgId}/audits/${auditId}/documents/${docId}/status`, {
      method: 'GET',
    }),
  getText: (orgId, auditId, docId) =>
    apiClient(`/api/organizations/${orgId}/audits/${auditId}/documents/${docId}/text`, {
      method: 'GET',
    }),
  getChunks: (orgId, auditId, docId, params = {}) => {
    const query = new URLSearchParams();
    if (params.page) query.append('page', params.page);
    if (params.size) query.append('size', params.size);
    if (params.page_number) query.append('page_number', params.page_number);
    if (params.section) query.append('section', params.section);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return apiClient(`/api/organizations/${orgId}/audits/${auditId}/documents/${docId}/chunks${qs}`, {
      method: 'GET',
    });
  },
  retry: (orgId, auditId, docId) =>
    apiClient(`/api/organizations/${orgId}/audits/${auditId}/documents/${docId}/retry`, {
      method: 'POST',
    }),
  delete: (orgId, auditId, docId) =>
    apiClient(`/api/organizations/${orgId}/audits/${auditId}/documents/${docId}`, {
      method: 'DELETE',
    }),
  download: async (orgId, auditId, docId, filename) => {
    const url = `${API_BASE_URL}/api/organizations/${orgId}/audits/${auditId}/documents/${docId}/download`;
    const headers = {};
    if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;
    const response = await fetch(url, { headers, credentials: 'include' });
    if (!response.ok) {
      throw new Error(`Failed to download document: HTTP ${response.status}`);
    }
    const blob = await response.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = filename || 'document';
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(blobUrl);
  },
};

// ----------------- Regulatory Knowledge Base & Legal Analyst API -----------------
export const regulatoryApi = {
  // Frameworks
  listFrameworks: (params = {}) => {
    const query = new URLSearchParams();
    if (params.search) query.append('search', params.search);
    if (params.status) query.append('status', params.status);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return apiClient(`/api/regulatory/frameworks${qs}`, { method: 'GET' });
  },
  createFramework: (data) =>
    apiClient('/api/regulatory/frameworks', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getFramework: (frameworkId) =>
    apiClient(`/api/regulatory/frameworks/${frameworkId}`, { method: 'GET' }),
  updateFramework: (frameworkId, data) =>
    apiClient(`/api/regulatory/frameworks/${frameworkId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  deleteFramework: (frameworkId) =>
    apiClient(`/api/regulatory/frameworks/${frameworkId}`, { method: 'DELETE' }),

  // Regulatory Documents
  uploadDocument: (frameworkId, file, meta = {}) => {
    const formData = new FormData();
    formData.append('file', file);
    if (meta.title) formData.append('title', meta.title);
    if (meta.document_number) formData.append('document_number', meta.document_number);
    if (meta.version) formData.append('version', meta.version);
    if (meta.source_url) formData.append('source_url', meta.source_url);
    if (meta.issuing_authority) formData.append('issuing_authority', meta.issuing_authority);
    return apiClient(`/api/regulatory/frameworks/${frameworkId}/documents`, {
      method: 'POST',
      body: formData,
    });
  },
  listDocuments: (frameworkId) =>
    apiClient(`/api/regulatory/frameworks/${frameworkId}/documents`, { method: 'GET' }),
  getDocument: (docId) =>
    apiClient(`/api/regulatory/documents/${docId}`, { method: 'GET' }),
  getDocumentChunks: (docId, params = {}) => {
    const query = new URLSearchParams();
    if (params.limit) query.append('limit', params.limit);
    if (params.offset) query.append('offset', params.offset);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return apiClient(`/api/regulatory/documents/${docId}/chunks${qs}`, { method: 'GET' });
  },

  // Legal Analyst Extraction
  triggerExtraction: (docId, runSynchronous = false) => {
    const qs = runSynchronous ? '?run_synchronous=true' : '';
    return apiClient(`/api/regulatory/documents/${docId}/extract${qs}`, { method: 'POST' });
  },
  listExtractionJobs: (docId) =>
    apiClient(`/api/regulatory/documents/${docId}/jobs`, { method: 'GET' }),

  // Requirements Review
  listRequirements: (params = {}) => {
    const query = new URLSearchParams();
    if (params.framework_id) query.append('framework_id', params.framework_id);
    if (params.document_id) query.append('document_id', params.document_id);
    if (params.review_status && params.review_status !== 'all') query.append('review_status', params.review_status);
    if (params.category && params.category !== 'all') query.append('category', params.category);
    if (params.search) query.append('search', params.search);
    if (params.limit) query.append('limit', params.limit);
    if (params.offset) query.append('offset', params.offset);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return apiClient(`/api/regulatory/requirements${qs}`, { method: 'GET' });
  },
  getRequirement: (requirementId) =>
    apiClient(`/api/regulatory/requirements/${requirementId}`, { method: 'GET' }),
  approveRequirement: (requirementId, reason = '') =>
    apiClient(`/api/regulatory/requirements/${requirementId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  rejectRequirement: (requirementId, reason) =>
    apiClient(`/api/regulatory/requirements/${requirementId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  editRequirement: (requirementId, data) =>
    apiClient(`/api/regulatory/requirements/${requirementId}/edit`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  requestRevision: (requirementId, reason) =>
    apiClient(`/api/regulatory/requirements/${requirementId}/revision`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  getRequirementHistory: (requirementId) =>
    apiClient(`/api/regulatory/requirements/${requirementId}/history`, { method: 'GET' }),

  // Audit Requirement Mapping
  mapRequirementsToAudit: (orgId, auditId, requirementIds) =>
    apiClient(`/api/organizations/${orgId}/audits/${auditId}/requirements`, {
      method: 'POST',
      body: JSON.stringify({ requirement_ids: requirementIds }),
    }),
  listAuditRequirements: (orgId, auditId, applicabilityStatus = null) => {
    const qs = applicabilityStatus ? `?applicability_status=${applicabilityStatus}` : '';
    return apiClient(`/api/organizations/${orgId}/audits/${auditId}/requirements${qs}`, {
      method: 'GET',
    });
  },
  updateAuditRequirement: (orgId, auditId, requirementId, status, reason = null) =>
    apiClient(`/api/organizations/${orgId}/audits/${auditId}/requirements/${requirementId}`, {
      method: 'PATCH',
      body: JSON.stringify({ applicability_status: status, applicability_reason: reason }),
    }),
  removeAuditRequirement: (orgId, auditId, requirementId) =>
    apiClient(`/api/organizations/${orgId}/audits/${auditId}/requirements/${requirementId}`, {
      method: 'DELETE',
    }),
  suggestAuditEvidence: (orgId, auditId, requirementId) =>
    apiClient(
      `/api/organizations/${orgId}/audits/${auditId}/requirements/${requirementId}/evidence-suggestions`,
      { method: 'GET' }
    ),
};



