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
export const getUpsellContacts = (search = "", page = 1) => request(`/learners/contacts?search=${encodeURIComponent(search)}&page=${page}`);
export const getUpsellContact = customerId => request(`/learners/contacts/${customerId}`);
export const getOpportunities = () => request("/opportunities");
export const getCounselors = () => request("/leads/counselors");
export const getTrackedLeads = (params = {}) => request(`/leads?${new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "")).toString()}`);
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

export function startUploadJob({ kind, file, importType, sourceCategory, uploadMode = "CREATE", uniqueNumber = "" }) {
  const formData = new FormData();
  formData.append("kind", kind);
  formData.append("file", file);
  if (importType) formData.append("import_type", importType);
  if (sourceCategory) formData.append("source_category", sourceCategory);
  formData.append("upload_mode", uploadMode);
  if (uniqueNumber) formData.append("unique_number", uniqueNumber);
  return request("/uploads/jobs", { method: "POST", body: formData });
}
export const getUploadJobProgress = jobId => request(`/uploads/jobs/${encodeURIComponent(jobId)}`);

export function getMainCrmLeads({ page = 1, pageSize = 50, sourceCategory = "ALL", search = "" } = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize), source_category: sourceCategory, search });
  return request(`/crm/leads?${params}`);
}
export const getMainCrmSummary = () => request("/crm/leads/summary");
export const getMainCrmLead = leadId => request(`/crm/leads/detail/${leadId}`);
export const getMainCrmCampaignActivities = () => request("/crm/leads/campaign-activities");
export const updateMainCrmLeadStatus = (leadId, status) => request(`/crm/leads/${leadId}/status`, {
  method: "PATCH", body: JSON.stringify({ status }),
});
export const assignMainCrmLead = (leadId, counselorUserId) => request(`/crm/leads/${leadId}/assignment`, {
  method: "PATCH", body: JSON.stringify({ counselor_user_id: counselorUserId || null }),
});
export const getMainCrmUploads = () => request("/crm/leads/uploads");
export function previewMainCrmMigration(file) {
  const formData = new FormData(); formData.append("file", file);
  return request("/crm/leads/migration-preview", { method: "POST", body: formData });
}
export function uploadMainCrmMigration(file, sourceCategories, uploadMode = "CREATE", uniqueNumber = "") {
  const formData = new FormData(); formData.append("file", file);
  formData.append("source_categories", JSON.stringify(sourceCategories));
  formData.append("upload_mode", uploadMode);
  if (uniqueNumber) formData.append("unique_number", uniqueNumber);
  return request("/crm/leads/migration-start", { method: "POST", body: formData });
}
export const getMainCrmMigrationProgress = uniqueNumber => request(`/crm/leads/migration-progress/${encodeURIComponent(uniqueNumber)}`);
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
export const searchLearnersCrm = (search, page = 1) => request(`/learners-crm/learners?search=${encodeURIComponent(search)}&page=${page}`);
export const getLearnersCrmProfile = learnerId => request(`/learners-crm/learners/${learnerId}`);
export const getLearnersCrmUploads = () => request("/learners-crm/uploads");
export const getLearnerCourseMapping = () => request("/learners-crm/course-mapping");
export const createLearnerCourseCategory = name => request("/learners-crm/course-mapping/categories", { method: "POST", body: JSON.stringify({ name }) });
export const updateLearnerCourseCategory = (id, name) => request(`/learners-crm/course-mapping/categories/${id}`, { method: "PATCH", body: JSON.stringify({ name }) });
export const deleteLearnerCourseCategory = id => request(`/learners-crm/course-mapping/categories/${id}`, { method: "DELETE" });
export const createLearnerCourseSubcategory = (name, categoryId) => request("/learners-crm/course-mapping/subcategories", { method: "POST", body: JSON.stringify({ name, category_id: categoryId }) });
export const updateLearnerCourseSubcategory = (id, name, categoryId) => request(`/learners-crm/course-mapping/subcategories/${id}`, { method: "PATCH", body: JSON.stringify({ name, category_id: categoryId }) });
export const deleteLearnerCourseSubcategory = id => request(`/learners-crm/course-mapping/subcategories/${id}`, { method: "DELETE" });
export const createLearnerCourse = (courseName, subcategoryId) => request("/learners-crm/course-mapping/courses", { method: "POST", body: JSON.stringify({ course_name: courseName, subcategory_id: subcategoryId }) });
export const updateLearnerCourse = (id, courseName, subcategoryId) => request(`/learners-crm/course-mapping/courses/${id}`, { method: "PATCH", body: JSON.stringify({ course_name: courseName, subcategory_id: subcategoryId }) });
export const deleteLearnerCourse = id => request(`/learners-crm/course-mapping/courses/${id}`, { method: "DELETE" });
export const getRecommendationRules = () => request("/settings/recommendation-rules");
export const updateRecommendationRules = coolingDays => request("/settings/recommendation-rules", { method: "PATCH", body: JSON.stringify({ cooling_days: coolingDays }) });
export function uploadLearnersCrm(file, uploadMode = "CREATE", uniqueNumber = "") {
  const formData = new FormData(); formData.append("file", file); formData.append("upload_mode", uploadMode);
  if (uniqueNumber) formData.append("unique_number", uniqueNumber);
  return request("/learners-crm/upload", { method: "POST", body: formData });
}
