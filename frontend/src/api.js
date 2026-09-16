const API_URL = "http://127.0.0.1:8000";
const TOKEN_KEY = "learning_crm_token";

export function getStoredToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function storeToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function request(url, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getStoredToken();
  if (token && options.auth !== false) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_URL}${url}`, { ...options, headers });
  if (!response.ok) {
    let message = "Something went wrong.";
    try {
      const error = await response.json();
      message = error.detail || message;
    } catch {}
    const err = new Error(message);
    err.status = response.status;
    throw err;
  }
  return response.json();
}

export const login = (username, password) => request("/auth/login", {
  method: "POST",
  auth: false,
  body: JSON.stringify({ username, password }),
});
export const getMe = () => request("/auth/me");
export const logout = () => request("/auth/logout", { method: "POST" });

export const getDashboardSummary = () => request("/dashboard/summary");
export const getLearners = (search = "") => request(`/learners${search ? `?search=${encodeURIComponent(search)}` : ""}`);
export const getLearner = learnerNumber => request(`/learners/${learnerNumber}`);
export const getOpportunities = () => request("/opportunities");
export const getCounselors = () => request("/leads/counselors");
export const getTrackedLeads = () => request("/leads");
export const getLead = leadId => request(`/leads/${leadId}`);
export const updateLeadStatus = (leadId, status) => request(`/leads/${leadId}/status`, {
  method: "PATCH",
  body: JSON.stringify({ status }),
});
export const assignLead = (leadId, counselorUserId) => request(`/leads/${leadId}/assignment`, {
  method: "PATCH",
  body: JSON.stringify({ counselor_user_id: counselorUserId || null }),
});
export const addLeadActivity = (leadId, activity) => request(`/leads/${leadId}/activities`, {
  method: "POST",
  body: JSON.stringify(activity),
});
export const getLeadAnalytics = () => request("/analytics/leads");

export async function downloadLeadAnalytics(opportunityKey = "") {
  const headers = new Headers();
  const token = getStoredToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const query = opportunityKey ? `?opportunity_key=${encodeURIComponent(opportunityKey)}` : "";
  const response = await fetch(`${API_URL}/analytics/leads/export${query}`, { headers });
  if (!response.ok) {
    let message = "Could not download analytics.";
    try {
      const error = await response.json();
      message = error.detail || message;
    } catch {}
    throw new Error(message);
  }
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^\"]+)"?/i);
  const filename = match?.[1] || "lead-analytics.xlsx";
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export const getImportTypes = () => request("/uploads/import-types");
export const getUploads = () => request("/uploads");
export const getUploadResetOptions = () => request("/uploads/reset-options");
export const resetSelectedUploads = uploadIds => request("/uploads/reset", {
  method: "POST",
  body: JSON.stringify({ upload_ids: uploadIds, confirmation: "DELETE SELECTED UPLOADS" }),
});
export const getCampaignHistory = () => request("/campaigns");

export function uploadExcel(importType, file) {
  const formData = new FormData();
  formData.append("import_type", importType);
  formData.append("file", file);
  return request("/uploads", { method: "POST", body: formData });
}

export function uploadCampaignExcel(file) {
  const formData = new FormData();
  formData.append("file", file);
  return request("/campaigns/upload", { method: "POST", body: formData });
}

export const getMainCrmLeads = () => request("/crm/leads");
export const getMainCrmLead = leadId => request(`/crm/leads/detail/${leadId}`);
export const getMainCrmCampaignActivities = () => request("/crm/leads/campaign-activities");
export const updateMainCrmLeadStatus = (leadId, status) => request(`/crm/leads/${leadId}/status`, {
  method: "PATCH", body: JSON.stringify({ status }),
});
export const assignMainCrmLead = (leadId, counselorUserId) => request(`/crm/leads/${leadId}/assignment`, {
  method: "PATCH", body: JSON.stringify({ counselor_user_id: counselorUserId || null }),
});
export const getMainCrmUploads = () => request("/crm/leads/uploads");
export function uploadMainCrmLeads(sourceCategory, file, uploadMode = "CREATE", uniqueNumber = "") {
  const formData = new FormData();
  formData.append("source_category", sourceCategory); formData.append("file", file);
  formData.append("upload_mode", uploadMode);
  if (uniqueNumber) formData.append("unique_number", uniqueNumber);
  return request("/crm/leads/upload", { method: "POST", body: formData });
}
export const getCounselorMapping = () => request("/crm/leads/counselor-mapping");
export const createCounselor = payload => request("/crm/leads/counselor-mapping", { method: "POST", body: JSON.stringify(payload) });
export const updateCounselor = (userId, payload) => request(`/crm/leads/counselor-mapping/${userId}`, { method: "PATCH", body: JSON.stringify(payload) });
export const getLearnersCrmOverview = () => request("/learners-crm/overview");
export const getLearnersCrmUploads = () => request("/learners-crm/uploads");
export function uploadLearnersCrm(file, uploadMode = "CREATE", uniqueNumber = "") {
  const formData = new FormData(); formData.append("file", file); formData.append("upload_mode", uploadMode);
  if (uniqueNumber) formData.append("unique_number", uniqueNumber);
  return request("/learners-crm/upload", { method: "POST", body: formData });
}
