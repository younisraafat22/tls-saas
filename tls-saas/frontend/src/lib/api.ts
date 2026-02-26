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
    };

    if (body && method !== "GET") {
      config.body = JSON.stringify(body);
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, config);

    if (response.status === 401) {
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

    if (!response.ok) {
      let errorMessage = "Request failed";
      try {
        const errorData = await response.json();
        errorMessage = errorData.detail || errorData.message || errorMessage;
      } catch {
        errorMessage = await response.text();
      }
      throw new ApiError(response.status, errorMessage);
    }

    return response.json();
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

  savePushSubscription: (subscription: any) =>
    api.post("/api/auth/push-subscription", { subscription }),
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
  submit: (data: { plan_type: string; branch_id: number; method: string; reference: string; screenshot_data?: string; amount: number; tls_email: string; tls_password: string }) =>
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
  getResults: (branchId?: number, limit?: number) =>
    api.get(`/api/monitoring/results?${branchId ? `branch_id=${branchId}&` : ""}limit=${limit || 20}`),
  getNotifications: (limit?: number) =>
    api.get(`/api/monitoring/notifications?limit=${limit || 30}`),
};

// ── Contact API ───────────────────────────────────────

export const contactApi = {
  submit: (data: { name: string; email: string; subject: string; message: string }) =>
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
};
