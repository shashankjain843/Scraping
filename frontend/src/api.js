const API_BASE = "http://localhost:8000/api";

export function getAuthToken() {
  return localStorage.getItem("token");
}

export function setAuthToken(token) {
  localStorage.setItem("token", token);
}

export function removeAuthToken() {
  localStorage.removeItem("token");
}

async function request(endpoint, options = {}) {
  const token = getAuthToken();
  const headers = { ...options.headers };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const config = {
    ...options,
    headers,
  };

  const response = await fetch(`${API_BASE}${endpoint}`, config);

  if (response.status === 401) {
    // Token expired or invalid
    removeAuthToken();
    window.dispatchEvent(new Event("auth-expired"));
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || data.message || "API Request Failed");
  }

  return data;
}

export const api = {
  // Auth
  login: (email, password) =>
    request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  register: (email, password, full_name) =>
    request("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, full_name }),
    }),
  getMe: () => request("/auth/me"),

  // Jobs
  getJobs: (params = {}) => {
    const query = new URLSearchParams();
    if (params.roles && params.roles.length) {
      params.roles.forEach((r) => query.append("roles", r));
    }
    if (params.cities && params.cities.length) {
      params.cities.forEach((c) => query.append("cities", c));
    }
    if (params.exp_buckets && params.exp_buckets.length) {
      params.exp_buckets.forEach((b) => query.append("exp_buckets", b));
    }
    if (params.q) query.append("q", params.q);

    return request(`/jobs?${query.toString()}`);
  },
  triggerFetchJobs: () => request("/jobs/fetch", { method: "POST" }),

  // Templates
  getTemplates: () => request("/templates"),
  updateTemplate: (roleCategory, subject, body) =>
    request(`/templates/${roleCategory}`, {
      method: "PUT",
      body: JSON.stringify({ subject_template: subject, body_template: body }),
    }),
  uploadResume: (roleCategory, file) => {
    const formData = new FormData();
    formData.append("file", file);
    return request(`/templates/${roleCategory}/resume`, {
      method: "POST",
      body: formData,
    });
  },
  removeResume: (roleCategory) =>
    request(`/templates/${roleCategory}/resume`, { method: "DELETE" }),

  // Applications & Drafts
  getCoverNote: (jobId) =>
    request("/applications/cover-note", {
      method: "POST",
      body: JSON.stringify({ job_id: jobId }),
    }),
  createDraft: (jobId, recipientEmail) =>
    request("/applications/draft", {
      method: "POST",
      body: JSON.stringify({ job_id: jobId, recipient_email: recipientEmail }),
    }),
  getDrafts: () => request("/applications/drafts"),
  updateDraft: (draftId, subject, body) =>
    request(`/applications/drafts/${draftId}`, {
      method: "PUT",
      body: JSON.stringify({ subject, body }),
    }),
  sendDraftNow: (draftId) =>
    request(`/applications/drafts/${draftId}/send`, { method: "POST" }),
  approveBatchDrafts: (draftIds, spaceSeconds = 120) =>
    request("/applications/drafts/approve-batch", {
      method: "POST",
      body: JSON.stringify({ draft_ids: draftIds, space_seconds: spaceSeconds }),
    }),
  deleteDraft: (draftId) =>
    request(`/applications/drafts/${draftId}`, { method: "DELETE" }),

  searchAssistant: (role, location) =>
    request("/assistant/search", {
      method: "POST",
      body: JSON.stringify({ role, location }),
    }),
  uploadDraftResume: (draftId, file) => {

    const formData = new FormData();
    formData.append("file", file);
    return request(`/applications/drafts/${draftId}/resume`, {
      method: "POST",
      body: formData,
    });
  },
  removeDraftResume: (draftId) =>
    request(`/applications/drafts/${draftId}/resume`, { method: "DELETE" }),
  getSentLogs: () => request("/applications/logs"),


  // Settings
  getSettings: () => request("/settings"),
  updateSettings: (settingsData) =>
    request("/settings", {
      method: "PUT",
      body: JSON.stringify(settingsData),
    }),
};
