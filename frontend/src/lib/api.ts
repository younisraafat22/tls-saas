/**
 * API Client — Handles all HTTP requests to the FastAPI backend.
 * Includes automatic token refresh and error handling.
 */

import Cookies from "js-cookie";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ApiOptions {
  method?: string;
  body?: any;
  headers?: Record<string, string>;
  noAuth?: boolean;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private getToken(): string | undefined {
    return Cookies.get("access_token");
  }

  async request<T = any>(endpoint: string, options: ApiOptions = {}): Promise<T> {
    const { method = "GET", body, headers = {}, noAuth = false } = options;

    const requestHeaders: Record<string, string> = {
      "Content-Type": "application/json",
      ...headers,
    };

    if (!noAuth) {
      const token = this.getToken();
      if (token) {
        requestHeaders["Authorization"] = `Bearer ${token}`;
      }
    }

    const config: RequestInit = {
      method,
      headers: requestHeaders,
      cache: method === "GET" ? "no-store" : "default",
    };

    if (body && method !== "GET") {
      config.body = JSON.stringify(body);
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, config);

    if (response.status === 401) {
      if (!noAuth) {
        // Try to refresh token
        const refreshed = await this.refreshToken();
        if (refreshed) {
          // Retry original request
          requestHeaders["Authorization"] = `Bearer ${this.getToken()}`;
          const retryResponse = await fetch(`${this.baseUrl}${endpoint}`, {
            ...config,
            headers: requestHeaders,
          });
          if (!retryResponse.ok) {
            throw new ApiError(retryResponse.status, await retryResponse.text());
          }
          return retryResponse.json();
        }
        // Refresh failed — redirect to login
        if (typeof window !== "undefined") {
          Cookies.remove("access_token");
          Cookies.remove("refresh_token");
          window.location.href = "/login";
        }
        throw new ApiError(401, "Session expired");
      }
      // noAuth request got 401 — parse and surface the real error detail
      let errorDetail = "Invalid email or password";
      try {
        const errorData = await response.json();
        errorDetail = errorData.detail || errorData.message || errorDetail;
      } catch { }
      throw new ApiError(401, errorDetail);
    }

    if (!response.ok) {
      let errorMessage = "Request failed";
      try {
        const errorData = await response.json();
        errorMessage = errorData.detail || errorData.message || errorMessage;
      } catch {
        errorMessage = await response.text().catch(() => errorMessage);
      }
      throw new ApiError(response.status, errorMessage);
    }

    // Handle empty responses (204 No Content or empty body)
    const contentType = response.headers.get("content-type") || "";
    if (response.status === 204 || !contentType.includes("application/json")) {
      return {} as T;
    }
    const text = await response.text();
    if (!text.trim()) return {} as T;
    return JSON.parse(text) as T;
  }

  private async refreshToken(): Promise<boolean> {
    const refreshToken = Cookies.get("refresh_token");
    if (!refreshToken) return false;

    try {
      const response = await fetch(`${this.baseUrl}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (response.ok) {
        const data = await response.json();
        Cookies.set("access_token", data.access_token, { expires: 1 });
        Cookies.set("refresh_token", data.refresh_token, { expires: 30 });
        return true;
      }
    } catch {
      // Refresh failed
    }
    return false;
  }

  // ── Convenience methods ─────────────────────────────

  get<T = any>(endpoint: string, noAuth?: boolean) {
    return this.request<T>(endpoint, { noAuth });
  }

  post<T = any>(endpoint: string, body?: any, noAuth?: boolean) {
    return this.request<T>(endpoint, { method: "POST", body, noAuth });
  }

  patch<T = any>(endpoint: string, body?: any) {
    return this.request<T>(endpoint, { method: "PATCH", body });
  }

  delete<T = any>(endpoint: string) {
    return this.request<T>(endpoint, { method: "DELETE" });
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

export const api = new ApiClient(API_URL);

// ── Auth API ──────────────────────────────────────────

export const authApi = {
  register: (data: { email: string; password: string; full_name: string; phone?: string }) =>
    api.post("/api/auth/register", data, true),

  login: (data: { email: string; password: string }) =>
    api.post("/api/auth/login", data, true),

  getMe: () => api.get("/api/auth/me"),

  updateProfile: (data: { full_name?: string; phone?: string }) =>
    api.patch("/api/auth/me", data),

  changePassword: (data: { current_password: string; new_password: string }) =>
    api.post("/api/auth/change-password", data),

  forgotPassword: (email: string) =>
    api.post("/api/auth/forgot-password", { email }, true),

  resetPassword: (token: string, new_password: string) =>
    api.post("/api/auth/reset-password", { token, new_password }, true),

  savePushSubscription: (subscription: any) =>
    api.post("/api/auth/push-subscription", { subscription }),

  deleteAccount: (password: string) =>
    api.request("/api/auth/me", { method: "DELETE", body: { password } }),
};

// ── Subscription API ──────────────────────────────────

export const subscriptionApi = {
  getPlans: () => api.get("/api/subscriptions/plans", true),
  getMySubscriptions: () => api.get("/api/subscriptions/my"),
  getActiveSubscription: () => api.get("/api/subscriptions/active"),
  getBranches: () => api.get("/api/subscriptions/branches"),
  getMyBranches: () => api.get("/api/subscriptions/my-branches"),
  setMonitoredBranches: (branchIds: number[]) =>
    api.post("/api/subscriptions/monitor-branches", { branch_ids: branchIds }),
};

// ── Payment API ───────────────────────────────────────

export const paymentApi = {
  submit: (data: { plan_type: string; branch_id?: number; method: string; reference: string; screenshot_data?: string; amount: number; tls_email?: string; tls_password?: string; hardware_id?: string }) =>
    api.post("/api/payments/submit", data),
  getMyPayments: () => api.get("/api/payments/my"),
  getStatus: (id: number) => api.get(`/api/payments/status/${id}`),
};

// ── Credential API ────────────────────────────────────

export const credentialApi = {
  getAll: () => api.get("/api/credentials/"),
  save: (data: { service_type: string; tls_email: string; tls_password: string }) =>
    api.post("/api/credentials/", data),
  remove: (service_type: string) => api.delete(`/api/credentials/${service_type}`),
};

// ── Monitoring API ────────────────────────────────────

export const monitoringApi = {
  getStatus: () => api.get("/api/monitoring/status"),
  getResults: (branchId?: number, limit?: number, offset?: number) =>
    api.get(`/api/monitoring/results?${branchId ? `branch_id=${branchId}&` : ""}limit=${limit || 10}&offset=${offset || 0}`),
  getNotifications: (limit?: number) =>
    api.get(`/api/monitoring/notifications?limit=${limit || 30}`),
};

// ── Contact API ───────────────────────────────────────

export const contactApi = {
  submit: (data: { name: string; email: string; subject: string; message: string; source?: string; locale?: string }) =>
    api.post("/api/contact", data, true),
};

// ── Admin API ─────────────────────────────────────────

export const adminApi = {
  getDashboard: () => api.get("/api/admin/dashboard"),
  getUsers: (page?: number, search?: string) =>
    api.get(`/api/admin/users?page=${page || 1}${search ? `&search=${search}` : ""}`),
  updateUser: (id: number, data: any) => api.patch(`/api/admin/users/${id}`, data),
  deleteUser: (id: number) => api.delete(`/api/admin/users/${id}`),
  assignBranch: (userId: number, branchId: number) =>
    api.post(`/api/admin/users/${userId}/assign-branch/${branchId}`),
  getPayments: (page?: number, status?: string) =>
    api.get(`/api/admin/payments?page=${page || 1}${status ? `&status=${status}` : ""}`),
  approvePayment: (id: number, data?: { admin_notes?: string; months?: number }) =>
    api.post(`/api/admin/payments/${id}/approve`, data || {}),
  rejectPayment: (id: number, reason?: string) =>
    api.post(`/api/admin/payments/${id}/reject`, { admin_notes: reason }),
  deletePayment: (id: number) => api.delete(`/api/admin/payments/${id}`),
  getPlans: () => api.get("/api/admin/plans"),
  updatePlan: (id: number, data: any) => api.patch(`/api/admin/plans/${id}`, data),
  getBranches: () => api.get("/api/admin/branches"),
  toggleBranch: (id: number, is_active?: boolean) =>
    api.patch(`/api/admin/branches/${id}`, is_active !== undefined ? { is_active } : {}),
  getServiceAccounts: () => api.get("/api/admin/service-accounts"),
  addServiceAccount: (data: any) => api.post("/api/admin/service-accounts", data),
  createServiceAccount: (data: any) => api.post("/api/admin/service-accounts", data),
  deleteServiceAccount: (id: number) => api.delete(`/api/admin/service-accounts/${id}`),
  getCheckResults: (limit?: number, branchId?: number) => {
    const params = new URLSearchParams();
    if (limit) params.set("limit", String(limit));
    if (branchId) params.set("branch_id", String(branchId));
    return api.get(`/api/admin/check-results?${params.toString()}`);
  },
  getCheckErrors: (limit?: number) => {
    const params = new URLSearchParams();
    if (limit) params.set("limit", String(limit));
    return api.get(`/api/admin/check-errors?${params.toString()}`);
  },
  resolveCheckError: (id: number) => api.patch(`/api/admin/check-errors/${id}/resolve`, {}),
  deleteCheckError: (id: number) => api.delete(`/api/admin/check-errors/${id}`),
  messageUserForError: (id: number, data: { subject: string; message: string }) =>
    api.post(`/api/admin/check-errors/${id}/message-user`, data),
  deleteCheckResults: (branchId?: number) => {
    const params = new URLSearchParams();
    if (branchId) params.set("branch_id", String(branchId));
    return api.delete(`/api/admin/check-results?${params.toString()}`);
  },
  deleteCheckResult: (id: number) => api.delete(`/api/admin/check-results/${id}`),
  getSettings: () => api.get("/api/admin/settings"),
  updateSetting: (key: string, value: string) =>
    api.post("/api/admin/settings", { key, value }),
  updateSettings: (settings: Record<string, string>) =>
    api.post("/api/admin/settings/bulk", settings),
  getActivityLog: () => api.get("/api/admin/activity-log"),
  // Scheduler / checker control
  startScheduler: () => api.post("/api/admin/checker/start"),
  stopScheduler: () => api.post("/api/admin/checker/stop"),
  getSchedulerStatus: () => api.get("/api/admin/checker/status"),
  triggerCheck: (branchId: number) => api.post(`/api/admin/checker/run-now/${branchId}`),
  runAllNow: () => api.post("/api/admin/checker/run-all-now"),
  restartWorkerLaptop: () => api.post("/api/admin/checker/restart-worker-laptop"),
  // Legacy aliases
  startChecker: () => api.post("/api/admin/checker/start"),
  stopChecker: () => api.post("/api/admin/checker/stop"),
  getCheckerStatus: () => api.get("/api/admin/checker/status"),
  getCheckerLogs: (limit?: number) => api.get(`/api/admin/checker/logs?limit=${limit || 100}`),
  getSystemLogs: (lines?: number) => api.get(`/api/admin/system-logs?lines=${lines || 200}`),
  runCheckNow: (branchId: number) => api.post(`/api/admin/checker/run-now/${branchId}`),
  // Headless mode toggle
  getHeadlessMode: () => api.get("/api/admin/checker/headless"),
  setHeadlessMode: (headless: boolean) => api.post("/api/admin/checker/headless", { headless }),
  // Test notifications
  testNotification: () => api.post("/api/admin/test-notification"),
  testAppointmentEmail: () => api.post("/api/admin/test-appointment-email"),
  // Desktop license management
  getDesktopPayments: (page?: number, status?: string) =>
    api.get(`/api/admin/desktop-payments?page=${page || 1}${status ? `&status=${status}` : ""}`),
  generateLicense: (paymentId: number) =>
    api.post(`/api/admin/desktop-payments/${paymentId}/generate-license`),
  // Full license management
  getLicenses: (page?: number, status?: string, search?: string) => {
    const params = new URLSearchParams();
    if (page) params.set("page", String(page));
    if (status) params.set("status", status);
    if (search) params.set("search", search);
    return api.get(`/api/admin/licenses?${params.toString()}`);
  },
  createLicense: (data: { hardware_id: string; plan_key: string; customer_name?: string; customer_email?: string; notes?: string; branch_id?: number | null; user_id?: number | null }) =>
    api.post("/api/admin/licenses/create", data),
  importLicense: (data: { license_key: string; customer_name?: string; customer_email?: string; notes?: string }) =>
    api.post("/api/admin/licenses/import", data),
  revokeLicense: (paymentId: number) =>
    api.post(`/api/admin/licenses/${paymentId}/revoke`),
  regenerateLicense: (paymentId: number) =>
    api.post(`/api/admin/licenses/${paymentId}/regenerate`),
  generateTestLicense: (hardware_id: string) =>
    api.post("/api/admin/generate-test-license", { hardware_id }),
  // Admin-only lookup for support/recovery workflows
  recoverLicensesByEmail: (email: string) =>
    api.post("/api/app/license/recover", { email }),
  resendLicenseEmail: (paymentId: number) =>
    api.post(`/api/admin/payments/${paymentId}/resend-email`),
  getUserPayments: (userId: number) =>
    api.get(`/api/admin/users/${userId}/payments`),
  getUserSubscriptions: (userId: number) =>
    api.get(`/api/admin/users/${userId}/subscriptions`),
  revokeUserSubscription: (userId: number, subscriptionId: number) =>
    api.post(`/api/admin/users/${userId}/subscriptions/${subscriptionId}/revoke`),
  deleteUserSubscription: (userId: number, subscriptionId: number) =>
    api.delete(`/api/admin/users/${userId}/subscriptions/${subscriptionId}`),
  sendPasswordReset: (userId: number) =>
    api.post(`/api/admin/users/${userId}/send-password-reset`),
  getNotificationCounts: () =>
    api.get("/api/admin/notifications/counts"),
  getNotifications: (page?: number, unreadOnly?: boolean, category?: string) =>
    api.get(`/api/admin/notifications?page=${page || 1}${unreadOnly ? "&unread_only=true" : ""}${category ? `&category=${category}` : ""}`),
  markNotificationRead: (id: number) =>
    api.post(`/api/admin/notifications/${id}/read`),
  markAllNotificationsRead: (category?: string) =>
    api.post(`/api/admin/notifications/read-all${category ? `?category=${category}` : ""}`),
  deleteNotification: (id: number) =>
    api.delete(`/api/admin/notifications/${id}`),
  deleteNotifications: (category?: string, onlyRead?: boolean) =>
    api.delete(`/api/admin/notifications${category || onlyRead ? `?${[
      category ? `category=${encodeURIComponent(category)}` : "",
      onlyRead ? "only_read=true" : "",
    ].filter(Boolean).join("&")}` : ""}`),
  getInquiries: (page?: number, status?: string, search?: string) =>
    api.get(`/api/admin/inquiries?page=${page || 1}${status ? `&status=${status}` : ""}${search ? `&search=${encodeURIComponent(search)}` : ""}`),
  replyInquiry: (id: number, data: { subject: string; message: string; close_after_reply?: boolean }) =>
    api.post(`/api/admin/inquiries/${id}/reply`, data),
  closeInquiry: (id: number) =>
    api.post(`/api/admin/inquiries/${id}/mark-closed`),
  updateInquiryStatus: (id: number, status: "new" | "replied" | "closed") =>
    api.patch(`/api/admin/inquiries/${id}/status`, { status }),
  deleteInquiry: (id: number) =>
    api.delete(`/api/admin/inquiries/${id}`),
};
