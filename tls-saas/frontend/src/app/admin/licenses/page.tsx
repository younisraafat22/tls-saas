"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { adminApi, subscriptionApi } from "@/lib/api";
import {
  KeyRound, Monitor, Copy, CheckCircle2, Clock, Loader2,
  XCircle, Search, RefreshCw, Plus, X, AlertTriangle,
  RotateCcw, Trash2, Shield, ChevronLeft, ChevronRight,
  Info, Mail, Send,
} from "lucide-react";

interface LicenseRecord {
  id: number;
  submitter_name: string;
  submitter_email: string;
  hardware_id: string;
  plan_key: string;
  amount: number;
  currency: string;
  method: string;
  reference: string;
  has_screenshot: boolean;
  screenshot_data?: string;
  status: "pending" | "approved" | "rejected";
  admin_notes: string;
  license_key: string;
  created_at: string;
  processed_at?: string;
  direct_issue: boolean;
}

const PLAN_OPTIONS = [
  { value: "legalization", label: "Legalization" },
  { value: "visa", label: "Visa" },
  { value: "all_in_one", label: "Legalization + Visa" },
  { value: "premium", label: "Premium" },
  { value: "test_1d", label: "Test (1 Day)" },
];

const statusConfig: Record<string, { label: string; color: string; bg: string; icon: React.ReactNode }> = {
  pending: {
    label: "Pending",
    color: "text-amber-400",
    bg: "bg-amber-500/10 border-amber-500/30",
    icon: <Clock className="w-3 h-3" />,
  },
  approved: {
    label: "Active",
    color: "text-emerald-400",
    bg: "bg-emerald-500/10 border-emerald-500/30",
    icon: <CheckCircle2 className="w-3 h-3" />,
  },
  rejected: {
    label: "Revoked",
    color: "text-red-400",
    bg: "bg-red-500/10 border-red-500/30",
    icon: <XCircle className="w-3 h-3" />,
  },
};

function Toast({ toast }: { toast: { type: "success" | "error"; msg: string } | null }) {
  return (
    <AnimatePresence>
      {toast && (
        <motion.div
          initial={{ x: 100, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 100, opacity: 0 }}
          className={`fixed top-4 right-4 z-50 px-6 py-3 rounded-xl font-medium shadow-xl max-w-md ${
            toast.type === "success" ? "bg-emerald-500 text-white" : "bg-red-500 text-white"
          }`}
        >
          {toast.msg}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

interface CreateModalProps {
  onClose: () => void;
  onCreated: (key: string, email: string) => void;
}

function CreateLicenseModal({ onClose, onCreated }: CreateModalProps) {
  const [form, setForm] = useState({
    hardware_id: "",
    plan_key: "legalization",
    customer_name: "",
    customer_email: "",
    notes: "",
    branch_id: null as number | null,
    user_id: null as number | null,
  });
  const [branches, setBranches] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ key: string; email: string } | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    subscriptionApi.getBranches().then((data: any) => setBranches(Array.isArray(data) ? data : [])).catch(() => {});
    adminApi.getUsers().then((data: any) => setUsers(Array.isArray(data?.items) ? data.items : [])).catch(() => {});
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.hardware_id.trim()) { setError("Hardware ID is required"); return; }
    if (!form.plan_key) { setError("Plan is required"); return; }
    if ((form.plan_key === "visa" || form.plan_key === "legalization") && !form.branch_id) {
      setError("Branch is required for this plan"); return;
    }
    setError("");
    setLoading(true);
    try {
      const res = await adminApi.createLicense(form);
      setResult({ key: res.license_key, email: res.customer_email });
      onCreated(res.license_key, res.customer_email);
    } catch (err: any) {
      setError(err?.detail || err?.message || "Failed to create license");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (!result) return;
    navigator.clipboard.writeText(result.key).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={(e) => e.target === e.currentTarget && !result && onClose()}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="glass-card w-full max-w-lg p-6 space-y-5"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Shield className="w-5 h-5 text-primary-400" />
            Generate License Key
          </h2>
          <button onClick={onClose} className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {!result ? (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-3 text-xs text-blue-300 flex gap-2">
              <Info className="w-4 h-4 shrink-0 mt-0.5" />
              <span>Create a license directly for any device without waiting for a payment submission.</span>
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                Hardware ID <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={form.hardware_id}
                onChange={(e) => setForm({ ...form, hardware_id: e.target.value })}
                placeholder="e.g. A1B2C3D4E5F6..."
                className="input-field font-mono text-sm"
                autoFocus
              />
              <p className="text-xs text-gray-500 mt-1">Found in the desktop app purchase screen.</p>
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                Plan <span className="text-red-400">*</span>
              </label>
              <select
                value={form.plan_key}
                onChange={(e) => setForm({ ...form, plan_key: e.target.value, branch_id: null })}
                className="input-field"
              >
                {PLAN_OPTIONS.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>

            {(form.plan_key === "visa" || form.plan_key === "legalization") && (
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">
                  Branch <span className="text-red-400">*</span>
                </label>
                <select
                  value={form.branch_id ?? ""}
                  onChange={(e) => setForm({ ...form, branch_id: e.target.value ? Number(e.target.value) : null })}
                  className="input-field"
                >
                  <option value="">— Select branch —</option>
                  {branches
                    .filter((b: any) => b.is_active && b.service_type === (form.plan_key === "visa" ? "visa" : "legalization"))
                    .map((b: any) => (
                      <option key={b.id} value={b.id}>{b.name}</option>
                    ))}
                </select>
              </div>
            )}

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">Assign to User (Optional)</label>
              <select
                value={form.user_id ?? ""}
                onChange={(e) => {
                  const userId = e.target.value ? Number(e.target.value) : null;
                  const selectedUser = userId ? users.find((u: any) => u.id === userId) : null;
                  setForm({
                    ...form,
                    user_id: userId,
                    customer_name: selectedUser?.full_name || "",
                    customer_email: selectedUser?.email || "",
                  });
                }}
                className="input-field"
              >
                <option value="">— No specific user —</option>
                {users.map((u: any) => (
                  <option key={u.id} value={u.id}>{u.email} {u.full_name ? `(${u.full_name})` : ""}</option>
                ))}
              </select>
              <p className="text-xs text-gray-500 mt-1">Selecting a user will auto-fill their name and email.</p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">Customer Name</label>
                <input
                  type="text"
                  value={form.customer_name}
                  onChange={(e) => setForm({ ...form, customer_name: e.target.value })}
                  placeholder="Optional"
                  className="input-field"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">Customer Email</label>
                <input
                  type="email"
                  value={form.customer_email}
                  onChange={(e) => setForm({ ...form, customer_email: e.target.value })}
                  placeholder="Optional"
                  className="input-field"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">Notes</label>
              <input
                type="text"
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                placeholder="Internal notes (optional)"
                className="input-field"
              />
            </div>

            {error && (
              <div className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2">
                {error}
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <button type="button" onClick={onClose} className="flex-1 btn-secondary py-2.5">
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="flex-1 btn-primary py-2.5 flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
                Generate
              </button>
            </div>
          </form>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-3 p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl">
              <CheckCircle2 className="w-6 h-6 text-emerald-400 shrink-0" />
              <div>
                <div className="font-semibold text-emerald-400">License created!</div>
                <div className="text-sm text-gray-400 mt-0.5">Copy and send to the customer.</div>
              </div>
            </div>
            <div>
              <div className="text-xs text-amber-400 font-medium mb-2">License Key</div>
              <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl">
                <code className="font-mono text-amber-300 text-sm break-all leading-relaxed">{result.key}</code>
              </div>
            </div>
            {result.email && (
              <div className="text-sm text-gray-400">
                Send to: <span className="text-white">{result.email}</span>
              </div>
            )}
            <div className="flex gap-3">
              <button
                onClick={handleCopy}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-amber-500/10 border border-amber-500/30 text-amber-400 rounded-xl text-sm font-medium hover:bg-amber-500/20 transition-colors"
              >
                {copied ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                {copied ? "Copied!" : "Copy Key"}
              </button>
              <button onClick={onClose} className="flex-1 btn-primary py-2.5">Done</button>
            </div>
          </div>
        )}
      </motion.div>
    </motion.div>
  );
}

function ConfirmDialog({
  message, onConfirm, onCancel, danger = true,
}: { message: string; onConfirm: () => void; onCancel: () => void; danger?: boolean }) {
  return (
    <motion.div
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
    >
      <motion.div initial={{ scale: 0.9 }} animate={{ scale: 1 }} className="glass-card w-full max-w-sm p-6 space-y-5">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${danger ? "bg-red-500/15" : "bg-amber-500/15"}`}>
            <AlertTriangle className={`w-5 h-5 ${danger ? "text-red-400" : "text-amber-400"}`} />
          </div>
          <p className="text-sm text-gray-300">{message}</p>
        </div>
        <div className="flex gap-3">
          <button onClick={onCancel} className="flex-1 btn-secondary py-2">Cancel</button>
          <button
            onClick={onConfirm}
            className={`flex-1 py-2 rounded-xl text-sm font-medium transition-colors ${
              danger
                ? "bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20"
                : "btn-primary"
            }`}
          >
            Confirm
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

interface ImportModalProps {
  onClose: () => void;
  onImported: () => void;
}

function ImportLicenseModal({ onClose, onImported }: ImportModalProps) {
  const [form, setForm] = useState({ license_key: "", customer_name: "", customer_email: "", notes: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.license_key.trim()) { setError("License key is required"); return; }
    setError("");
    setLoading(true);
    try {
      await adminApi.importLicense(form);
      onImported();
      onClose();
    } catch (err: any) {
      setError(err?.detail || err?.message || "Failed to import license");
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.9, opacity: 0 }}
        className="glass-card w-full max-w-lg p-6 space-y-5"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Shield className="w-5 h-5 text-amber-400" />
            Import Existing License
          </h2>
          <button onClick={onClose} className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-3 text-xs text-amber-300 flex gap-2">
            <Info className="w-4 h-4 shrink-0 mt-0.5" />
            <span>Register a license key that was generated outside this system. The HMAC signature is verified before importing. Once imported you can revoke or manage it normally.</span>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1.5">
              License Key <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={form.license_key}
              onChange={(e) => setForm({ ...form, license_key: e.target.value })}
              placeholder="e.g. ALL_IN_ONE-26D19C80-4AD385C8-11105D53C4558AFF"
              className="input-field font-mono text-sm"
              autoFocus
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">Customer Name</label>
              <input type="text" value={form.customer_name} onChange={(e) => setForm({ ...form, customer_name: e.target.value })} placeholder="Optional" className="input-field" />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">Customer Email</label>
              <input type="email" value={form.customer_email} onChange={(e) => setForm({ ...form, customer_email: e.target.value })} placeholder="Optional" className="input-field" />
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1.5">Notes</label>
            <input type="text" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="e.g. Issued before migration" className="input-field" />
          </div>

          {error && (
            <div className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2">{error}</div>
          )}

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="flex-1 btn-secondary py-2.5">Cancel</button>
            <button type="submit" disabled={loading} className="flex-1 btn-primary py-2.5 flex items-center justify-center gap-2 disabled:opacity-50">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Shield className="w-4 h-4" />}
              Import
            </button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  );
}

function TestLicenseModal({ onClose }: { onClose: () => void }) {
  const [hardwareId, setHardwareId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ license_key: string; note: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!hardwareId.trim()) { setError("Hardware ID is required"); return; }
    setError("");
    setLoading(true);
    try {
      const res = await adminApi.generateTestLicense(hardwareId.trim());
      setResult(res);
    } catch (err: any) {
      setError(err?.detail || err?.message || "Failed to generate test license");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (!result) return;
    navigator.clipboard.writeText(result.license_key).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <motion.div
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.9, opacity: 0 }}
        className="glass-card w-full max-w-md p-6 space-y-5"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Clock className="w-5 h-5 text-amber-400" />
            Generate Test License (1 Day)
          </h2>
          <button onClick={onClose} className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {result ? (
          <div className="space-y-4">
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 text-center">
              <div className="text-xs text-amber-400 font-medium mb-2">TEST LICENSE — expires in 1 day</div>
              <code className="font-mono text-sm text-amber-300 break-all">{result.license_key}</code>
            </div>
            {result.note && <div className="text-xs text-center text-gray-500">{result.note}</div>}
            <div className="flex gap-3">
              <button
                onClick={handleCopy}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-amber-500/10 border border-amber-500/30 text-amber-400 rounded-xl text-sm font-medium hover:bg-amber-500/20 transition-colors"
              >
                {copied ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                {copied ? "Copied!" : "Copy Key"}
              </button>
              <button onClick={onClose} className="flex-1 btn-secondary py-2.5">Done</button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-3 text-xs text-amber-300 flex gap-2">
              <Info className="w-4 h-4 shrink-0 mt-0.5" />
              <span>Generates a temporary license valid for 1 day. Use this to verify expiry behavior quickly.</span>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                Hardware ID <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={hardwareId}
                onChange={(e) => setHardwareId(e.target.value)}
                placeholder="Paste the user's hardware ID"
                className="input-field font-mono text-sm"
                autoFocus
              />
            </div>
            {error && (
              <div className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2">{error}</div>
            )}
            <div className="flex gap-3 pt-2">
              <button type="button" onClick={onClose} className="flex-1 btn-secondary py-2.5">Cancel</button>
              <button type="submit" disabled={loading} className="flex-1 btn-primary py-2.5 flex items-center justify-center gap-2 disabled:opacity-50">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Clock className="w-4 h-4" />}
                Generate
              </button>
            </div>
          </form>
        )}
      </motion.div>
    </motion.div>
  );
}

function RecoverModal({ onClose }: { onClose: () => void }) {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [results, setResults] = useState<{ license_key: string; plan: string }[] | null>(null);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) { setError("Email is required"); return; }
    setError("");
    setLoading(true);
    try {
      const res = await adminApi.recoverLicensesByEmail(email.trim());
      setResults(res.licenses || []);
    } catch (err: any) {
      setError(err?.detail || err?.message || "Lookup failed");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = (key: string, idx: number) => {
    navigator.clipboard.writeText(key).then(() => {
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 2000);
    });
  };

  return (
    <motion.div
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.9, opacity: 0 }}
        className="glass-card w-full max-w-lg p-6 space-y-5"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Mail className="w-5 h-5 text-blue-400" />
            Recover License by Email
          </h2>
          <button onClick={onClose} className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Customer email address"
            className="input-field flex-1"
            autoFocus
          />
          <button type="submit" disabled={loading} className="btn-primary px-4 flex items-center gap-2 disabled:opacity-50">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
          </button>
        </form>

        {error && (
          <div className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2">{error}</div>
        )}

        {results !== null && (
          results.length === 0 ? (
            <div className="text-center py-6 text-gray-400 text-sm">No active licenses found for this email.</div>
          ) : (
            <div className="space-y-2">
              <div className="text-xs text-gray-400">{results.length} license{results.length > 1 ? "s" : ""} found</div>
              {results.map((lic, idx) => (
                <div key={idx} className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl">
                  <div className="text-xs text-gray-400 mb-1">{lic.plan.replace(/_/g, " ")}</div>
                  <div className="flex items-center gap-2">
                    <code className="font-mono text-sm text-amber-300 flex-1 break-all">{lic.license_key}</code>
                    <button
                      onClick={() => handleCopy(lic.license_key, idx)}
                      className="shrink-0 p-1.5 text-amber-400 hover:text-amber-300 hover:bg-amber-500/20 rounded-lg transition-colors"
                    >
                      {copiedIdx === idx ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )
        )}

        <div className="flex justify-end pt-1">
          <button onClick={onClose} className="btn-secondary px-6 py-2">Close</button>
        </div>
      </motion.div>
    </motion.div>
  );
}

export default function AdminLicensesPage() {
  const [licenses, setLicenses] = useState<LicenseRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [showDirectOnly, setShowDirectOnly] = useState(false);
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [processing, setProcessing] = useState<number | null>(null);
  const [toast, setToast] = useState<{ type: "success" | "error"; msg: string } | null>(null);
  const [copied, setCopied] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [showTest, setShowTest] = useState(false);
  const [showRecover, setShowRecover] = useState(false);
  const [confirm, setConfirm] = useState<{ id: number; action: "revoke" | "delete" | "regenerate" } | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 400);
    return () => clearTimeout(t);
  }, [search]);

  const loadLicenses = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.getLicenses(page, filter === "all" ? "" : filter, debouncedSearch);
      setLicenses(data.items || []);
      setTotal(data.total || 0);
      setPages(data.pages || 1);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [page, filter, debouncedSearch]);

  useEffect(() => { setPage(1); }, [filter, debouncedSearch]);
  useEffect(() => { loadLicenses(); }, [loadLicenses]);

  const showToast = (type: "success" | "error", msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 5000);
  };

  const handleCopy = (text: string, id: number) => {
    navigator.clipboard.writeText(text).then(() => { setCopied(id); setTimeout(() => setCopied(null), 2000); });
  };

  const handleGenerate = async (id: number, mode: "approve" | "renew" = "approve") => {
    setProcessing(id);
    try {
      const res = await adminApi.generateLicense(id);
      if (mode === "renew") {
        showToast("success", `License renewed. Key kept: ${res.license_key}`);
      } else {
        showToast("success", `Key generated! Send to: ${res.submitter_email || "buyer"}`);
      }
      loadLicenses();
    } catch (err: any) {
      showToast("error", err?.message || err?.detail || (mode === "renew" ? "Failed to renew" : "Failed to generate"));
    } finally { setProcessing(null); }
  };

  const handleRevoke = async (id: number) => {
    setConfirm(null); setProcessing(id);
    try {
      await adminApi.revokeLicense(id);
      showToast("success", "License revoked");
      loadLicenses();
    } catch (err: any) {
      showToast("error", err?.message || err?.detail || "Failed to revoke");
    } finally { setProcessing(null); }
  };

  const handleRegenerate = async (id: number) => {
    setConfirm(null); setProcessing(id);
    try {
      const res = await adminApi.regenerateLicense(id);
      showToast("success", "New key: " + res.license_key);
      loadLicenses();
    } catch (err: any) {
      showToast("error", err?.message || err?.detail || "Failed to regenerate");
    } finally { setProcessing(null); }
  };

  const handleDelete = async (id: number) => {
    setConfirm(null); setProcessing(id);
    try {
      await adminApi.deletePayment(id);
      showToast("success", "Record deleted");
      loadLicenses();
    } catch (err: any) {
      showToast("error", err?.message || err?.detail || "Failed to delete");
    } finally { setProcessing(null); }
  };

  const handleConfirm = () => {
    if (!confirm) return;
    if (confirm.action === "revoke") handleRevoke(confirm.id);
    else if (confirm.action === "delete") handleDelete(confirm.id);
    else handleRegenerate(confirm.id);
  };

  const handleResend = async (id: number) => {
    try {
      const res = await adminApi.resendLicenseEmail(id);
      showToast("success", res.message || "License email resent!");
    } catch (err: any) {
      showToast("error", err?.detail || "Failed to resend");
    }
  };

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selected.size === licenses.length) setSelected(new Set());
    else setSelected(new Set(licenses.map((l) => l.id)));
  };

  const handleBulkRevoke = async () => {
    if (!window.confirm(`Revoke ${selected.size} selected license(s)?`)) return;
    const ids = Array.from(selected);
    setSelected(new Set());
    for (const id of ids) {
      try { await adminApi.revokeLicense(id); } catch {}
    }
    showToast("success", `Revoked ${ids.length} licenses`);
    loadLicenses();
  };

  const handleBulkDelete = async () => {
    if (!window.confirm(`Permanently delete ${selected.size} selected record(s)?`)) return;
    const ids = Array.from(selected);
    setSelected(new Set());
    for (const id of ids) {
      try { await adminApi.deletePayment(id); } catch {}
    }
    showToast("success", `Deleted ${ids.length} records`);
    loadLicenses();
  };

  const activeCount = licenses.filter((l) => l.status === "approved" && l.license_key).length;
  const pendingCount = licenses.filter((l) => l.status === "pending").length;
  const displayedLicenses = showDirectOnly ? licenses.filter((l) => l.direct_issue) : licenses;

  const filterTabs = [
    { key: "all", label: "All" },
    { key: "approved", label: "Active" },
    { key: "pending", label: "Pending", count: pendingCount > 0 ? pendingCount : null },
    { key: "rejected", label: "Revoked" },
  ];

  return (
    <div className="space-y-6">
      <Toast toast={toast} />

      <AnimatePresence>
        {confirm && (
          <ConfirmDialog
            message={
              confirm.action === "revoke"
                ? "Revoke this license? The key will stop working immediately."
                : confirm.action === "delete"
                ? "Permanently delete this record? This cannot be undone."
                : "Regenerate a new license key? The old key will no longer work."
            }
            danger={confirm.action !== "regenerate"}
            onConfirm={handleConfirm}
            onCancel={() => setConfirm(null)}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showCreate && (
          <CreateLicenseModal
            onClose={() => { setShowCreate(false); loadLicenses(); }}
            onCreated={(key, email) => showToast("success", `License created!${email ? ` Send to ${email}` : ""}`)}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showImport && (
          <ImportLicenseModal
            onClose={() => setShowImport(false)}
            onImported={() => { showToast("success", "License imported and is now manageable"); loadLicenses(); }}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showTest && <TestLicenseModal onClose={() => setShowTest(false)} />}
      </AnimatePresence>

      <AnimatePresence>
        {showRecover && <RecoverModal onClose={() => setShowRecover(false)} />}
      </AnimatePresence>

      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold flex items-center gap-2">
            <KeyRound className="w-6 h-6 text-primary-400" /> License Management
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            {total > 0 ? (
              <span>
                {total} total &nbsp;&middot;&nbsp;
                <span className="text-emerald-400">{activeCount} active</span>
                {pendingCount > 0 && <> &nbsp;&middot;&nbsp; <span className="text-amber-400">{pendingCount} pending</span></>}
              </span>
            ) : "No licenses yet"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:justify-end">
          <button onClick={loadLicenses} className="p-2 text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors" title="Refresh">
            <RefreshCw className="w-4 h-4" />
          </button>
          <button onClick={() => setShowRecover(true)} className="flex items-center gap-2 px-4 py-2 bg-blue-500/10 border border-blue-500/30 text-blue-400 rounded-xl text-sm font-medium hover:bg-blue-500/20 transition-colors">
            <Mail className="w-4 h-4" /> Recover by Email
          </button>
          <button onClick={() => setShowTest(true)} className="flex items-center gap-2 px-4 py-2 bg-amber-500/10 border border-amber-500/30 text-amber-400 rounded-xl text-sm font-medium hover:bg-amber-500/20 transition-colors">
            <Clock className="w-4 h-4" /> Test (1 Day)
          </button>
          <button onClick={() => setShowImport(true)} className="flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 text-gray-300 rounded-xl text-sm font-medium hover:bg-white/10 transition-colors">
            <Shield className="w-4 h-4" /> Import Key
          </button>
          <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2 px-4 py-2">
            <Plus className="w-4 h-4" /> Generate License
          </button>
        </div>
      </div>

      {/* Info */}
      <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4 text-sm text-blue-300 flex gap-3">
        <Info className="w-4 h-4 shrink-0 mt-0.5" />
        <div>
          <strong>Full license control:</strong> Create licenses instantly for any hardware ID.
          Renew approvals keep the same key when available. Regenerate creates a new key and invalidates the old one.
          Approve pending submissions, revoke, regenerate, or delete any license record.
        </div>
      </div>

      {/* Bulk action bar */}
      <AnimatePresence>
        {selected.size > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            className="flex items-center justify-between p-3 bg-primary-500/10 border border-primary-500/30 rounded-xl"
          >
            <span className="text-sm text-primary-400 font-medium">{selected.size} selected</span>
            <div className="flex gap-2">
              <button
                onClick={handleBulkRevoke}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-500/10 text-amber-400 border border-amber-500/30 rounded-xl text-xs font-medium hover:bg-amber-500/20 transition-colors"
              >
                <XCircle className="w-3.5 h-3.5" /> Revoke Selected
              </button>
              <button
                onClick={handleBulkDelete}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-red-500/10 text-red-400 border border-red-500/30 rounded-xl text-xs font-medium hover:bg-red-500/20 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" /> Delete Selected
              </button>
              <button
                onClick={() => setSelected(new Set())}
                className="p-1.5 text-gray-400 hover:text-white rounded-lg transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Filters + Search */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text" value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, email, hardware ID, plan, license key"
            className="input-field !pl-10"
          />
        </div>
        <div className="flex gap-2 flex-wrap">
          {filterTabs.map((tab) => (
            <button
              key={tab.key} onClick={() => setFilter(tab.key)}
              className={`px-3 py-2 rounded-xl text-sm border transition-all flex items-center gap-1.5 ${
                filter === tab.key
                  ? "bg-primary-500/10 border-primary-500/50 text-primary-400"
                  : "border-white/10 text-gray-400 hover:border-white/20"
              }`}
            >
              {tab.label}
              {"count" in tab && tab.count != null && (
                <span className="bg-amber-500 text-black text-xs w-5 h-5 rounded-full inline-flex items-center justify-center font-bold">
                  {tab.count}
                </span>
              )}
            </button>
          ))}
          <button
            onClick={() => setShowDirectOnly((v) => !v)}
            className={`px-3 py-2 rounded-xl text-sm border transition-all flex items-center gap-1.5 ${
              showDirectOnly
                ? "bg-primary-500/10 border-primary-500/50 text-primary-400"
                : "border-white/10 text-gray-400 hover:border-white/20"
            }`}
          >
            <Shield className="w-3.5 h-3.5" /> Direct Issue
          </button>
        </div>
      </div>

      {/* List */}
      <div className="glass-card overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-48"><div className="spinner w-8 h-8" /></div>
        ) : licenses.length === 0 ? (
          <div className="p-12 text-center">
            <KeyRound className="w-12 h-12 text-gray-600 mx-auto mb-4" />
            <h3 className="font-semibold text-lg mb-2">No licenses found</h3>
            <p className="text-gray-400 text-sm mb-4">
              {filter === "pending" ? "No pending submissions waiting for license generation."
                : search ? "No results match your search."
                : "No license records yet."}
            </p>
            <button onClick={() => setShowCreate(true)} className="btn-primary px-4 py-2 text-sm flex items-center gap-2 mx-auto">
              <Plus className="w-4 h-4" /> Generate License
            </button>
          </div>
        ) : (
          <div className="divide-y divide-white/5">
            {/* Select-all header */}
            <div className="px-5 py-2 border-b border-white/5 flex items-center gap-3">
              <input
                type="checkbox"
                checked={selected.size === displayedLicenses.length && displayedLicenses.length > 0}
                onChange={toggleSelectAll}
                className="w-3.5 h-3.5 accent-primary-400 cursor-pointer"
              />
              <span className="text-xs text-gray-500">Select all on this page</span>
            </div>
            {displayedLicenses.map((lic) => {
              const st = statusConfig[lic.status] || statusConfig.pending;
              const isProcessing = processing === lic.id;
              const isSelected = selected.has(lic.id);

              return (
                <motion.div key={lic.id} layout className={`p-5 transition-colors ${isSelected ? "bg-primary-500/5" : ""}`}>
                  <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSelect(lic.id)}
                        className="mt-1 w-3.5 h-3.5 accent-primary-400 cursor-pointer shrink-0"
                      />
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${lic.direct_issue ? "bg-primary-500/15" : "bg-blue-500/15"}`}>
                        {lic.direct_issue ? <Shield className="w-5 h-5 text-primary-400" /> : <Monitor className="w-5 h-5 text-blue-400" />}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="font-medium text-sm flex flex-wrap items-center gap-2">
                          {lic.submitter_name || ""}
                          <span className={`text-xs px-2 py-0.5 rounded-full border flex items-center gap-1 ${st.bg} ${st.color}`}>
                            {st.icon} {st.label}
                          </span>
                          {lic.plan_key && (
                            <span className="text-xs bg-white/10 text-gray-300 px-2 py-0.5 rounded-full">
                              {lic.plan_key.replace(/_/g, " ")}
                            </span>
                          )}
                          {lic.direct_issue && (
                            <span className="text-xs bg-primary-500/10 text-primary-400 border border-primary-500/30 px-2 py-0.5 rounded-full">
                              Direct Issue
                            </span>
                          )}
                        </div>

                        {lic.submitter_email && (
                          <div className="text-xs text-gray-400 mt-1">{lic.submitter_email}</div>
                        )}

                        <div className="mt-2 space-y-1.5">
                          <div className="text-xs flex flex-wrap gap-x-4 gap-y-1">
                            <span>
                              <span className="text-gray-500">Hardware ID: </span>
                              <span className="font-mono text-blue-300 break-all">{lic.hardware_id}</span>
                            </span>
                            {lic.amount > 0 && (
                              <span>
                                <span className="text-gray-500">Amount: </span>
                                <span className="font-bold text-amber-400">{lic.amount} {lic.currency}</span>
                                <span className="text-gray-500 ml-2">via </span>
                                <span className="text-gray-300">{lic.method?.replace(/_/g, " ")}</span>
                              </span>
                            )}
                          </div>
                          {lic.reference && lic.reference !== "admin-direct" && (
                            <div className="text-xs">
                              <span className="text-gray-500">Ref: </span>
                              <span className="font-mono text-gray-300 break-all">{lic.reference}</span>
                            </div>
                          )}
                          <div className="text-xs text-gray-500">
                            Created: {new Date(lic.created_at).toLocaleString()}
                            {lic.processed_at && <> &middot; Processed: {new Date(lic.processed_at).toLocaleString()}</>}
                          </div>
                          {lic.admin_notes && <div className="text-xs text-gray-500 italic">{lic.admin_notes}</div>}
                          {lic.has_screenshot && <div className="text-xs text-primary-400"> Payment screenshot attached</div>}
                        </div>

                        {lic.license_key && (
                          <div className="mt-3 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
                            <div className="text-amber-400 text-xs mb-1 font-medium">License Key</div>
                            <div className="flex items-center gap-2">
                              <code className="font-mono text-sm text-amber-300 flex-1 break-all">{lic.license_key}</code>
                              <button
                                onClick={() => handleCopy(lic.license_key, lic.id)}
                                className="shrink-0 p-1.5 text-amber-400 hover:text-amber-300 hover:bg-amber-500/20 rounded-lg transition-colors"
                              >
                                {copied === lic.id ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex flex-wrap items-center gap-2 lg:shrink-0">
                      {isProcessing ? (
                        <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
                      ) : (
                        <>
                          {lic.status === "pending" && (
                            <button
                              onClick={() => handleGenerate(lic.id)}
                              className="flex items-center gap-1.5 px-3 py-1.5 bg-primary-500/10 text-primary-400 border border-primary-500/30 rounded-xl text-xs font-medium hover:bg-primary-500/20 transition-colors"
                            >
                              <KeyRound className="w-3.5 h-3.5" /> Approve
                            </button>
                          )}
                          {lic.status === "approved" && lic.license_key && (
                            <>
                              <button
                                onClick={() => handleCopy(lic.license_key, lic.id)}
                                className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 text-gray-300 border border-white/10 rounded-xl text-xs font-medium hover:bg-white/10 transition-colors"
                              >
                                {copied === lic.id ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                                Copy
                              </button>
                              {lic.submitter_email && (
                                <button
                                  onClick={() => handleResend(lic.id)}
                                  className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-500/10 text-blue-400 border border-blue-500/30 rounded-xl text-xs font-medium hover:bg-blue-500/20 transition-colors"
                                  title="Resend license email"
                                >
                                  <Send className="w-3.5 h-3.5" /> Email
                                </button>
                              )}
                              <button
                                onClick={() => setConfirm({ id: lic.id, action: "regenerate" })}
                                className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-500/10 text-blue-400 border border-blue-500/30 rounded-xl text-xs font-medium hover:bg-blue-500/20 transition-colors"
                              >
                                <RotateCcw className="w-3.5 h-3.5" /> Regenerate
                              </button>
                              <button
                                onClick={() => handleGenerate(lic.id, "renew")}
                                className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 rounded-xl text-xs font-medium hover:bg-emerald-500/20 transition-colors"
                              >
                                <RefreshCw className="w-3.5 h-3.5" /> Renew
                              </button>
                              <button
                                onClick={() => setConfirm({ id: lic.id, action: "revoke" })}
                                className="flex items-center gap-1.5 px-3 py-1.5 bg-red-500/10 text-red-400 border border-red-500/30 rounded-xl text-xs font-medium hover:bg-red-500/20 transition-colors"
                              >
                                <XCircle className="w-3.5 h-3.5" /> Revoke
                              </button>
                            </>
                          )}
                          {lic.status === "rejected" && (
                            <button
                              onClick={() => setConfirm({ id: lic.id, action: "regenerate" })}
                              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-500/10 text-blue-400 border border-blue-500/30 rounded-xl text-xs font-medium hover:bg-blue-500/20 transition-colors"
                            >
                              <RotateCcw className="w-3.5 h-3.5" /> Reissue
                            </button>
                          )}
                          <button
                            onClick={() => setConfirm({ id: lic.id, action: "delete" })}
                            className="p-1.5 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                            title="Delete record"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between text-sm text-gray-400">
          <span>Showing {(page - 1) * 30 + 1}{Math.min(page * 30, total)} of {total}</span>
          <div className="flex items-center gap-2">
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="p-1.5 rounded-lg hover:bg-white/5 disabled:opacity-30 transition-colors">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-3 py-1 bg-white/5 rounded-lg">{page} / {pages}</span>
            <button onClick={() => setPage((p) => Math.min(pages, p + 1))} disabled={page === pages} className="p-1.5 rounded-lg hover:bg-white/5 disabled:opacity-30 transition-colors">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}