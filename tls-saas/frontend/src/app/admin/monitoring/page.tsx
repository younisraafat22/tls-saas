"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { adminApi } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";
import {
  Activity, Play, Pause, RefreshCw,
  Key, Plus, Trash2, Loader2,
  CheckCircle2, XCircle, AlertCircle, Zap, Clock,
  Bell, Monitor, Save, Terminal, Download,
  ChevronDown, ChevronUp, Wifi, WifiOff, Circle,
} from "lucide-react";

interface LogEntry {
  ts: string;
  level: string;
  branch: string;
  message: string;
}

type LogTab = "monitor" | "system";
type LineCount = 50 | 100 | 200 | 500;

function logLevelColor(level: string): string {
  switch (level?.toUpperCase()) {
    case "ERROR":   return "text-red-400";
    case "WARNING":
    case "WARN":    return "text-yellow-400";
    case "INFO":    return "text-green-400";
    case "DEBUG":   return "text-blue-400";
    default:        return "text-gray-300";
  }
}

function logLevelBg(level: string): string {
  switch (level?.toUpperCase()) {
    case "ERROR":   return "bg-red-500/10 border-red-500/20";
    case "WARNING":
    case "WARN":    return "bg-yellow-500/10 border-yellow-500/20";
    case "INFO":    return "bg-green-500/10 border-green-500/20";
    case "DEBUG":   return "bg-blue-500/10 border-blue-500/20";
    default:        return "bg-white/3 border-white/5";
  }
}

function sysLogLevel(line: string): string {
  const l = line.toLowerCase();
  if (l.includes(" error") || l.includes("[error]"))    return "ERROR";
  if (l.includes(" warning") || l.includes("[warn"))   return "WARNING";
  if (l.includes(" info") || l.includes("[info]"))     return "INFO";
  if (l.includes(" debug") || l.includes("[debug]"))   return "DEBUG";
  return "DEFAULT";
}

function formatTs(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString("en-GB", { hour12: false });
  } catch {
    return ts?.slice(11, 19) ?? "";
  }
}

export default function AdminMonitoringPage() {
  const [schedulerStatus, setSchedulerStatus] = useState<any>(null);
  const [branches, setBranches] = useState<any[]>([]);
  const [serviceAccounts, setServiceAccounts] = useState<any[]>([]);
  const [recentResults, setRecentResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ type: "success" | "error"; msg: string } | null>(null);
  const [settingsInterval, setSettingsInterval] = useState(5);
  const [savingInterval, setSavingInterval] = useState(false);

  // Logs state
  const [logTab, setLogTab] = useState<LogTab>("monitor");
  const [lineCount, setLineCount] = useState<LineCount>(200);
  const [autoScroll, setAutoScroll] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [monitorLogs, setMonitorLogs] = useState<LogEntry[]>([]);
  const [monitorLoading, setMonitorLoading] = useState(false);
  const [systemLines, setSystemLines] = useState<string[]>([]);
  const [systemLoading, setSystemLoading] = useState(false);
  const [lastLogRefresh, setLastLogRefresh] = useState<Date | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);
  const logIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // WebSocket for live results + logs
  const { connected, lastMessage } = useWebSocket(true);

  // Add service account form
  const [showAddAccount, setShowAddAccount] = useState(false);
  const [newAccount, setNewAccount] = useState({ branch_id: 0, email: "", password: "", is_primary: true });
  const [addingAccount, setAddingAccount] = useState(false);
  const [showPassword, setShowPassword] = useState<Record<number, boolean>>({});

  // Processing states
  const [schedulerLoading, setSchedulerLoading] = useState(false);
  const [headless, setHeadless] = useState(true);
  const [headlessLoading, setHeadlessLoading] = useState(false);
  const [testNotifLoading, setTestNotifLoading] = useState(false);
  const [testApptEmailLoading, setTestApptEmailLoading] = useState(false);
  const [deletingAllResults, setDeletingAllResults] = useState(false);
  const [deletingResultId, setDeletingResultId] = useState<number | null>(null);

  useEffect(() => {
    loadAll();
  }, []);

  // Live WS: results + monitor logs
  useEffect(() => {
    if (!lastMessage) return;
    if (lastMessage.type === "admin_check_result") {
      adminApi.getCheckResults(20).then(setRecentResults).catch(() => {});
    }
    if (lastMessage.type === "monitor_log") {
      const entry: LogEntry = {
        ts: lastMessage.ts,
        level: lastMessage.level,
        branch: lastMessage.branch || "",
        message: lastMessage.message,
      };
      setMonitorLogs((prev) => [...prev.slice(-299), entry]);
    }
  }, [lastMessage]);

  const fetchMonitorLogs = useCallback(async () => {
    setMonitorLoading(true);
    try {
      const data = await adminApi.getCheckerLogs(lineCount);
      if (Array.isArray(data)) setMonitorLogs(data);
    } catch {}
    setMonitorLoading(false);
  }, [lineCount]);

  const fetchSystemLogs = useCallback(async () => {
    setSystemLoading(true);
    try {
      const data: any = await adminApi.getSystemLogs(lineCount);
      setSystemLines(data?.lines ?? []);
      setLastLogRefresh(new Date());
    } catch {}
    setSystemLoading(false);
  }, [lineCount]);

  // Auto-refresh system logs every 10s
  useEffect(() => {
    if (logIntervalRef.current) clearInterval(logIntervalRef.current);
    if (autoRefresh && logTab === "system") {
      logIntervalRef.current = setInterval(fetchSystemLogs, 10000);
    }
    return () => { if (logIntervalRef.current) clearInterval(logIntervalRef.current); };
  }, [autoRefresh, logTab, fetchSystemLogs]);

  // Auto-scroll logs
  useEffect(() => {
    if (autoScroll && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [monitorLogs, systemLines, autoScroll]);

  const copyLogs = () => {
    const text = logTab === "system"
      ? systemLines.join("\n")
      : monitorLogs.map(e => `[${e.ts}] [${e.level}] ${e.branch ? `[${e.branch}] ` : ""}${e.message}`).join("\n");
    navigator.clipboard.writeText(text).catch(() => {});
  };

  const downloadLogs = () => {
    const text = logTab === "system"
      ? systemLines.join("\n")
      : monitorLogs.map(e => `[${e.ts}] [${e.level}] ${e.branch ? `[${e.branch}] ` : ""}${e.message}`).join("\n");
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `tls-${logTab}-logs-${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const loadAll = async () => {
    try {
      const [brData, saData, schedulerData, resultsData, headlessData] = await Promise.all([
        adminApi.getBranches(),
        adminApi.getServiceAccounts(),
        adminApi.getSchedulerStatus(),
        adminApi.getCheckResults(20),
        adminApi.getHeadlessMode(),
      ]);
      setBranches(brData);
      setServiceAccounts(saData);
      setSchedulerStatus(schedulerData);
      setRecentResults(resultsData);
      setSettingsInterval(schedulerData?.interval_minutes || 5);
      if (headlessData) setHeadless(headlessData.headless);
      // Load logs in parallel (non-blocking)
      fetchMonitorLogs();
      fetchSystemLogs();
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const showToastMsg = (type: "success" | "error", msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 4000);
  };

  const toggleHeadless = async () => {
    setHeadlessLoading(true);
    try {
      const newVal = !headless;
      await adminApi.setHeadlessMode(newVal);
      setHeadless(newVal);
      showToastMsg("success", newVal ? "Browser set to headless (invisible)" : "Browser set to visible (debug mode)");
    } catch (err: any) {
      showToastMsg("error", err?.detail || "Failed to toggle headless mode");
    } finally {
      setHeadlessLoading(false);
    }
  };

  const testNotifications = async () => {
    setTestNotifLoading(true);
    try {
      const res = await adminApi.testNotification();
      showToastMsg("success", res.message || "Test sent!");
    } catch (err: any) {
      showToastMsg("error", err?.detail || "Failed to send test notification");
    } finally {
      setTestNotifLoading(false);
    }
  };

  const testAppointmentEmail = async () => {
    setTestApptEmailLoading(true);
    try {
      const res = await adminApi.testAppointmentEmail();
      showToastMsg("success", res.message || "Appointment test email sent!");
    } catch (err: any) {
      showToastMsg("error", err?.detail || "Failed — check SMTP settings");
    } finally {
      setTestApptEmailLoading(false);
    }
  };

  const saveInterval = async () => {
    setSavingInterval(true);
    try {
      await adminApi.updateSettings({ check_interval_minutes: String(settingsInterval) });
      setSchedulerStatus((prev: any) => prev ? { ...prev, interval_minutes: settingsInterval } : prev);
      showToastMsg("success", `Interval set to ${settingsInterval}min`);
    } catch (err: any) {
      showToastMsg("error", err?.detail || "Failed to save interval");
    } finally {
      setSavingInterval(false);
    }
  };

  const toggleScheduler = async () => {
    setSchedulerLoading(true);
    try {
      if (schedulerStatus?.running) {
        await adminApi.stopScheduler();
        setSchedulerStatus({ ...schedulerStatus, running: false });
        showToastMsg("success", "Scheduler stopped");
      } else {
        await adminApi.startScheduler();
        setSchedulerStatus({ ...schedulerStatus, running: true });
        showToastMsg("success", "Scheduler started");
      }
    } catch (err: any) {
      showToastMsg("error", err?.detail || "Failed to toggle scheduler");
    } finally {
      setSchedulerLoading(false);
    }
  };

  const addServiceAccount = async () => {
    if (!newAccount.branch_id || !newAccount.email || !newAccount.password) {
      showToastMsg("error", "Fill in all fields");
      return;
    }
    setAddingAccount(true);
    try {
      await adminApi.addServiceAccount(newAccount);
      showToastMsg("success", "Service account added!");
      setShowAddAccount(false);
      setNewAccount({ branch_id: 0, email: "", password: "", is_primary: true });
      loadAll();
    } catch (err: any) {
      showToastMsg("error", err?.detail || "Failed to add account");
    } finally {
      setAddingAccount(false);
    }
  };

  const deleteServiceAccount = async (id: number) => {
    if (!confirm("Delete this service account?")) return;
    try {
      await adminApi.deleteServiceAccount(id);
      setServiceAccounts((prev) => prev.filter((a) => a.id !== id));
      showToastMsg("success", "Account deleted");
    } catch (err: any) {
      showToastMsg("error", err?.detail || "Failed to delete");
    }
  };

  const deleteAllCheckResults = async () => {
    if (!confirm("Delete ALL check results? This cannot be undone.")) return;
    setDeletingAllResults(true);
    try {
      const res = await adminApi.deleteCheckResults();
      setRecentResults([]);
      showToastMsg("success", `Deleted ${res.deleted} check results`);
    } catch (err: any) {
      showToastMsg("error", err?.detail || "Failed to delete results");
    } finally {
      setDeletingAllResults(false);
    }
  };

  const deleteCheckResult = async (id: number) => {
    setDeletingResultId(id);
    try {
      await adminApi.deleteCheckResult(id);
      setRecentResults((prev) => prev.filter((r) => r.id !== id));
      showToastMsg("success", "Result deleted");
    } catch (err: any) {
      showToastMsg("error", err?.detail || "Failed to delete result");
    } finally {
      setDeletingResultId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="spinner w-10 h-10" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ x: 100, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 100, opacity: 0 }}
            className={`fixed top-4 right-4 z-50 px-6 py-3 rounded-xl font-medium shadow-lg ${
              toast.type === "success" ? "bg-accent-green text-black" : "bg-red-500 text-white"
            }`}
          >
            {toast.msg}
          </motion.div>
        )}
      </AnimatePresence>

      <h1 className="text-2xl font-display font-bold">Monitoring Control</h1>

      {/* Scheduler control */}
      <div className="glass-card p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
              schedulerStatus?.running ? "bg-accent-green/10" : "bg-red-500/10"
            }`}>
              <Activity className={`w-5 h-5 ${schedulerStatus?.running ? "text-accent-green" : "text-red-400"}`} />
            </div>
            <div>
              <div className="font-semibold">Checker Scheduler</div>
              <div className="text-sm text-gray-400">
                {schedulerStatus?.running ? "Running" : "Stopped"}
                {schedulerStatus?.interval_minutes && ` · Every ${schedulerStatus.interval_minutes}min`}
              </div>
            </div>
          </div>
          <button
            onClick={toggleScheduler}
            disabled={schedulerLoading}
            className={`px-4 py-2.5 rounded-xl text-sm font-medium flex items-center gap-2 transition-all ${
              schedulerStatus?.running
                ? "bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20"
                : "bg-accent-green/10 text-accent-green hover:bg-accent-green/20 border border-accent-green/20"
            }`}
          >
            {schedulerLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : schedulerStatus?.running ? (
              <Pause className="w-4 h-4" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            {schedulerStatus?.running ? "Stop" : "Start"}
          </button>
        </div>

        {/* Headless toggle + Test notifications */}
        <div className="mt-4 pt-4 border-t border-white/5 flex flex-wrap items-center gap-3">
          <button
            onClick={toggleHeadless}
            disabled={headlessLoading}
            className={`px-3 py-2 rounded-xl text-sm font-medium flex items-center gap-2 transition-all border ${
              headless
                ? "border-white/10 text-gray-400 hover:border-white/20"
                : "bg-amber-500/10 border-amber-500/30 text-amber-400"
            }`}
          >
            {headlessLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Monitor className="w-3 h-3" />}
            {headless ? "Headless (Hidden)" : "Visible (Debug)"}
          </button>

          <button
            onClick={testNotifications}
            disabled={testNotifLoading}
            className="px-3 py-2 rounded-xl text-sm font-medium flex items-center gap-2 transition-all border border-white/10 text-gray-400 hover:border-primary-500/30 hover:text-primary-400"
          >
            {testNotifLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Bell className="w-3 h-3" />}
            Test Notifications
          </button>

          <button
            onClick={testAppointmentEmail}
            disabled={testApptEmailLoading}
            className="px-3 py-2 rounded-xl text-sm font-medium flex items-center gap-2 transition-all border border-accent-green/20 text-accent-green hover:border-accent-green/40 hover:bg-accent-green/5"
          >
            {testApptEmailLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
            Test Appointment Email
          </button>
        </div>

        {/* Check interval */}
        <div className="mt-4 pt-4 border-t border-white/5 flex flex-wrap items-center gap-3">
          <Clock className="w-3.5 h-3.5 text-gray-400" />
          <span className="text-xs text-gray-400">Check Interval</span>
          <input
            type="number"
            min={1}
            value={settingsInterval}
            onChange={(e) => setSettingsInterval(Number(e.target.value))}
            className="w-20 bg-dark-700 border border-white/10 rounded-lg px-2 py-1 text-center text-sm text-white focus:outline-none focus:border-primary-500/50"
          />
          <span className="text-xs text-gray-500">minutes</span>
          <button
            onClick={saveInterval}
            disabled={savingInterval}
            className="px-3 py-1.5 text-xs font-medium rounded-xl bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 border border-primary-500/20 flex items-center gap-1.5 disabled:opacity-50"
          >
            {savingInterval ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
            Save
          </button>
        </div>
      </div>

      {/* Service Accounts */}
      <div className="glass-card overflow-hidden">
        <div className="p-4 border-b border-white/5 flex items-center justify-between">
          <h2 className="font-semibold flex items-center gap-2">
            <Key className="w-4 h-4 text-primary-400" /> Service Accounts
          </h2>
          <button
            onClick={() => setShowAddAccount(!showAddAccount)}
            className="text-sm text-primary-400 hover:text-primary-300 flex items-center gap-1"
          >
            <Plus className="w-4 h-4" /> Add Account
          </button>
        </div>

        {/* Add form */}
        <AnimatePresence>
          {showAddAccount && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="p-4 bg-dark-800 space-y-3 border-b border-white/5">
                <div className="grid sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-gray-400 mb-1 block">Branch</label>
                    <select
                      value={newAccount.branch_id}
                      onChange={(e) => setNewAccount({ ...newAccount, branch_id: Number(e.target.value) })}
                      className="input-field"
                    >
                      <option value={0}>Select branch...</option>
                      {branches.map((b) => (
                        <option key={b.id} value={b.id}>{b.name} ({b.service_type})</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 mb-1 block">Type</label>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setNewAccount({ ...newAccount, is_primary: true })}
                        className={`flex-1 py-2 rounded-lg text-sm border transition-all ${
                          newAccount.is_primary
                            ? "bg-primary-500/10 border-primary-500/50 text-primary-400"
                            : "border-white/10 text-gray-400"
                        }`}
                      >
                        Admin&apos;s Account
                      </button>
                      <button
                        onClick={() => setNewAccount({ ...newAccount, is_primary: false })}
                        className={`flex-1 py-2 rounded-lg text-sm border transition-all ${
                          !newAccount.is_primary
                            ? "bg-primary-500/10 border-primary-500/50 text-primary-400"
                            : "border-white/10 text-gray-400"
                        }`}
                      >
                        User Account
                      </button>
                    </div>
                  </div>
                </div>
                <div className="grid sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-gray-400 mb-1 block">TLS Email</label>
                    <input
                      type="email"
                      value={newAccount.email}
                      onChange={(e) => setNewAccount({ ...newAccount, email: e.target.value })}
                      className="input-field"
                      placeholder="account@example.com"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 mb-1 block">TLS Password</label>
                    <input
                      type="password"
                      value={newAccount.password}
                      onChange={(e) => setNewAccount({ ...newAccount, password: e.target.value })}
                      className="input-field"
                      placeholder="Account password"
                    />
                  </div>
                </div>
                <div className="flex justify-end gap-2">
                  <button
                    onClick={() => setShowAddAccount(false)}
                    className="px-4 py-2 text-sm text-gray-400 hover:text-white"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={addServiceAccount}
                    disabled={addingAccount}
                    className="btn-gradient !py-2 text-sm flex items-center gap-1 disabled:opacity-50"
                  >
                    {addingAccount ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
                    Add Account
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {serviceAccounts.length === 0 ? (
          <div className="p-8 text-center text-gray-500 text-sm">
            No service accounts configured. Add accounts to start monitoring.
          </div>
        ) : (
          <div className="divide-y divide-white/5">
            {serviceAccounts.map((acc) => (
              <div key={acc.id} className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Key className="w-4 h-4 text-gray-500" />
                  <div>
                    <div className="text-sm font-medium flex items-center gap-2">
                      {acc.email}
                      {acc.is_primary && (
                        <span className="text-xs bg-primary-500/10 text-primary-400 px-1.5 py-0.5 rounded">Primary</span>
                      )}
                    </div>
                    <div className="text-xs text-gray-500">
                      {acc.branch_name} &middot; Last used: {acc.last_used_at ? new Date(acc.last_used_at.includes('Z') || acc.last_used_at.includes('+') ? acc.last_used_at : acc.last_used_at + 'Z').toLocaleString() : "Never"}
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => deleteServiceAccount(acc.id)}
                  className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent check results */}
      <div className="glass-card overflow-hidden">
        <div className="p-4 border-b border-white/5 flex items-center justify-between">
          <h2 className="font-semibold">Recent Check Results</h2>
          <div className="flex items-center gap-2">
            <button
              onClick={deleteAllCheckResults}
              disabled={deletingAllResults || recentResults.length === 0}
              className="flex items-center gap-1.5 text-xs text-red-400 hover:text-red-300 border border-red-500/20 hover:border-red-500/40 px-2.5 py-1 rounded-lg transition-colors disabled:opacity-40"
            >
              {deletingAllResults ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
              Clear All
            </button>
            <button onClick={loadAll} className="text-gray-400 hover:text-white p-1">
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>
        {recentResults.length === 0 ? (
          <div className="p-8 text-center text-gray-500 text-sm">No check results yet</div>
        ) : (
          <div className="divide-y divide-white/5">
            {recentResults.map((r) => (
              <div key={r.id} className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {r.slots_available ? (
                    <CheckCircle2 className="w-5 h-5 text-accent-green" />
                  ) : r.error ? (
                    <AlertCircle className="w-5 h-5 text-amber-400" />
                  ) : (
                    <XCircle className="w-5 h-5 text-gray-500" />
                  )}
                  <div>
                    <div className="text-sm font-medium">{r.branch_name}</div>
                    <div className="text-xs text-gray-500">
                      {new Date(r.checked_at.includes('Z') || r.checked_at.includes('+') ? r.checked_at : r.checked_at + 'Z').toLocaleString()}
                      {r.duration_seconds && ` · ${r.duration_seconds}s`}
                    </div>
                    {r.error && <div className="text-xs text-amber-400 mt-0.5 truncate max-w-md">{r.error}</div>}
                    {r.slot_details && (
                      <div className="text-xs mt-1 space-y-1">
                        {(() => {
                          const details = typeof r.slot_details === "string" ? (() => { try { return JSON.parse(r.slot_details); } catch { return null; } })() : r.slot_details;
                          if (!details || !details.slots) return <span className="text-accent-green">{typeof r.slot_details === "string" ? r.slot_details : JSON.stringify(r.slot_details)}</span>;
                          return (
                            <div>
                              <div className="text-accent-green font-semibold mb-1">
                                {details.slots.length} day{details.slots.length !== 1 ? 's' : ''} with appointments found
                                {details.months_checked && <span className="text-gray-500 font-normal"> (checked {details.months_checked} months)</span>}
                              </div>
                              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-1">
                                {details.slots.slice(0, 12).map((s: { day: string; times: string[] }, i: number) => (
                                  <div key={i} className="bg-accent-green/10 border border-accent-green/20 rounded px-2 py-1">
                                    <div className="text-accent-green font-medium">{s.day}</div>
                                    <div className="text-gray-400 text-[10px]">{s.times?.map((t: string) => t.replace(/\n/g, ' ')).join(', ')}</div>
                                  </div>
                                ))}
                                {details.slots.length > 12 && <div className="text-gray-500 text-[10px] flex items-center">+{details.slots.length - 12} more days</div>}
                              </div>
                            </div>
                          );
                        })()}
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${
                    r.slots_available
                      ? "bg-accent-green/10 text-accent-green"
                      : r.error
                      ? "bg-amber-500/10 text-amber-400"
                      : "bg-gray-500/10 text-gray-400"
                  }`}>
                    {r.slots_available ? "Available!" : r.error ? "Error" : "No Slots"}
                  </span>
                  <button
                    onClick={() => deleteCheckResult(r.id)}
                    disabled={deletingResultId === r.id}
                    className="p-1.5 text-gray-600 hover:text-red-400 rounded-lg hover:bg-red-500/10 transition-colors"
                  >
                    {deletingResultId === r.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Backend Logs */}
      <div className="bg-dark-900 border border-white/5 rounded-2xl overflow-hidden">
        {/* Log header */}
        <div className="flex items-center justify-between flex-wrap gap-3 px-4 py-3 border-b border-white/5 bg-dark-800">
          <div className="flex items-center gap-3">
            <Terminal className="w-4 h-4 text-primary-400" />
            <span className="font-semibold text-sm">Logs</span>
            {/* Tabs */}
            <div className="flex gap-1 bg-dark-700 border border-white/5 rounded-lg p-0.5">
              {(["monitor", "system"] as LogTab[]).map((key) => (
                <button
                  key={key}
                  onClick={() => setLogTab(key)}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                    logTab === key ? "bg-primary-500/20 text-primary-400" : "text-gray-400 hover:text-white"
                  }`}
                >
                  {key === "monitor" ? "Monitoring" : "System (journalctl)"}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {/* WS indicator */}
            <div className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-lg border ${
              connected ? "bg-green-500/10 border-green-500/20 text-green-400" : "bg-red-500/10 border-red-500/20 text-red-400"
            }`}>
              {connected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
              {connected ? "Live" : "Offline"}
            </div>

            {/* Line count */}
            <select
              value={lineCount}
              onChange={(e) => setLineCount(Number(e.target.value) as LineCount)}
              className="bg-dark-700 border border-white/10 text-gray-300 text-xs rounded-lg px-2 py-1"
            >
              <option value={50}>50 lines</option>
              <option value={100}>100 lines</option>
              <option value={200}>200 lines</option>
              <option value={500}>500 lines</option>
            </select>

            {/* Auto-scroll */}
            <button
              onClick={() => setAutoScroll(!autoScroll)}
              className={`flex items-center gap-1 text-xs px-2 py-1 rounded-lg border transition-all ${
                autoScroll ? "bg-primary-500/10 border-primary-500/20 text-primary-400" : "bg-dark-700 border-white/10 text-gray-400"
              }`}
            >
              {autoScroll ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />}
              Auto-scroll
            </button>

            {/* Auto-refresh (system tab) */}
            {logTab === "system" && (
              <button
                onClick={() => setAutoRefresh(!autoRefresh)}
                className={`flex items-center gap-1 text-xs px-2 py-1 rounded-lg border transition-all ${
                  autoRefresh ? "bg-primary-500/10 border-primary-500/20 text-primary-400" : "bg-dark-700 border-white/10 text-gray-400"
                }`}
              >
                <Circle className={`w-2 h-2 ${autoRefresh ? "fill-primary-400" : "fill-gray-500"}`} />
                Auto-refresh
              </button>
            )}

            {/* Refresh */}
            <button
              onClick={logTab === "system" ? fetchSystemLogs : fetchMonitorLogs}
              disabled={logTab === "system" ? systemLoading : monitorLoading}
              className="btn-secondary flex items-center gap-1 text-xs px-2.5 py-1"
            >
              <RefreshCw className={`w-3 h-3 ${(logTab === "system" ? systemLoading : monitorLoading) ? "animate-spin" : ""}`} />
              Refresh
            </button>

            {/* Download */}
            <button onClick={downloadLogs} className="btn-secondary flex items-center gap-1 text-xs px-2.5 py-1">
              <Download className="w-3 h-3" />
              Download
            </button>

            {/* Clear monitor logs */}
            {logTab === "monitor" && (
              <button
                onClick={() => setMonitorLogs([])}
                className="btn-secondary flex items-center gap-1 text-xs px-2.5 py-1 text-red-400 border-red-500/20 hover:bg-red-500/10"
              >
                <Trash2 className="w-3 h-3" />
                Clear
              </button>
            )}

            <button onClick={copyLogs} className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
              Copy all
            </button>
          </div>
        </div>

        {/* Pane sub-header */}
        <div className="px-4 py-1.5 border-b border-white/5 bg-dark-800/60">
          <span className="text-xs text-gray-500 font-mono">
            {logTab === "system"
              ? `${systemLines.length} lines${lastLogRefresh ? ` · refreshed ${lastLogRefresh.toLocaleTimeString()}` : ""}`
              : `${monitorLogs.length} entries · ${connected ? "live via WebSocket" : "WebSocket disconnected"}`}
          </span>
        </div>

        {/* Log output */}
        <div className="h-[60vh] overflow-y-auto font-mono text-xs p-3 space-y-0.5">
          {logTab === "system" ? (
            systemLoading && systemLines.length === 0 ? (
              <div className="flex items-center justify-center h-full text-gray-500">
                <RefreshCw className="w-4 h-4 animate-spin mr-2" /> Loading system logs...
              </div>
            ) : systemLines.length === 0 ? (
              <div className="flex items-center justify-center h-full text-gray-600">No logs available</div>
            ) : (
              systemLines.map((line, i) => {
                const lvl = sysLogLevel(line);
                return (
                  <div key={i} className={`px-2 py-0.5 rounded border ${logLevelBg(lvl)} leading-relaxed`}>
                    <span className={logLevelColor(lvl)}>{line}</span>
                  </div>
                );
              })
            )
          ) : (
            monitorLoading && monitorLogs.length === 0 ? (
              <div className="flex items-center justify-center h-full text-gray-500">
                <RefreshCw className="w-4 h-4 animate-spin mr-2" /> Loading monitoring logs...
              </div>
            ) : monitorLogs.length === 0 ? (
              <div className="flex items-center justify-center h-full text-gray-600">
                No monitoring logs yet — start the scheduler to see activity here
              </div>
            ) : (
              monitorLogs.map((entry, i) => (
                <div key={i} className={`px-2 py-0.5 rounded border ${logLevelBg(entry.level)} leading-relaxed`}>
                  <span className="text-gray-600">{formatTs(entry.ts)} </span>
                  <span className={`font-semibold ${logLevelColor(entry.level)}`}>[{entry.level?.toUpperCase() || "INFO"}] </span>
                  {entry.branch && <span className="text-primary-400/70">[{entry.branch}] </span>}
                  <span className="text-gray-200 break-all whitespace-pre-wrap">{entry.message}</span>
                </div>
              ))
            )
          )}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
}
