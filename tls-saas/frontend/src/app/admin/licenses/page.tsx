"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { adminApi } from "@/lib/api";
import {
  KeyRound, Monitor, Copy, CheckCircle2, Clock, Loader2,
  XCircle, Search, RefreshCw,
} from "lucide-react";

const statusConfig: Record<string, { color: string; bg: string; icon: React.ReactNode }> = {
  pending: { color: "text-amber-400", bg: "bg-amber-500/10", icon: <Clock className="w-3 h-3" /> },
  approved: { color: "text-accent-green", bg: "bg-accent-green/10", icon: <CheckCircle2 className="w-3 h-3" /> },
  rejected: { color: "text-red-400", bg: "bg-red-500/10", icon: <XCircle className="w-3 h-3" /> },
};

export default function AdminLicensesPage() {
  const [payments, setPayments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("pending");
  const [search, setSearch] = useState("");
  const [processing, setProcessing] = useState<number | null>(null);
  const [toast, setToast] = useState<{ type: "success" | "error"; msg: string } | null>(null);
  const [generatedKeys, setGeneratedKeys] = useState<Record<number, string>>({});
  const [copied, setCopied] = useState<number | null>(null);

  useEffect(() => {
    loadPayments();
  }, []);

  const loadPayments = async () => {
    setLoading(true);
    try {
      const data = await adminApi.getDesktopPayments();
      setPayments(data.items || data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateLicense = async (paymentId: number) => {
    setProcessing(paymentId);
    try {
      const result = await adminApi.generateLicense(paymentId);
      setGeneratedKeys((prev) => ({ ...prev, [paymentId]: result.license_key }));
      setPayments((prev) =>
        prev.map((p) =>
          p.id === paymentId
            ? { ...p, status: "approved", license_key: result.license_key }
            : p
        )
      );
      showToast("success", `License key generated! Send to: ${result.submitter_email}`);
    } catch (err: any) {
      showToast("error", err?.detail || "Failed to generate license");
    } finally {
      setProcessing(null);
    }
  };

  const handleCopy = (text: string, paymentId: number) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(paymentId);
      setTimeout(() => setCopied(null), 2000);
    });
  };

  const showToast = (type: "success" | "error", msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 5000);
  };

  const filtered = payments.filter((p) => {
    if (filter !== "all" && p.status !== filter) return false;
    if (search) {
      const s = search.toLowerCase();
      return (
        p.submitter_email?.toLowerCase().includes(s) ||
        p.submitter_name?.toLowerCase().includes(s) ||
        p.hardware_id?.toLowerCase().includes(s) ||
        p.plan_key?.toLowerCase().includes(s) ||
        p.license_key?.toLowerCase().includes(s)
      );
    }
    return true;
  });

  const pendingCount = payments.filter((p) => p.status === "pending").length;

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
            className={`fixed top-4 right-4 z-50 px-6 py-3 rounded-xl font-medium shadow-lg max-w-md ${
              toast.type === "success" ? "bg-accent-green text-black" : "bg-red-500 text-white"
            }`}
          >
            {toast.msg}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold flex items-center gap-2">
            <KeyRound className="w-6 h-6 text-primary-400" /> License Management
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            {pendingCount > 0 ? (
              <span className="text-amber-400">{pendingCount} pending license generation</span>
            ) : (
              "Desktop app payment submissions"
            )}
          </p>
        </div>
        <button
          onClick={loadPayments}
          className="p-2 text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Info box */}
      <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4 text-sm text-blue-300">
        <strong>How it works:</strong> Desktop app users submit payment here. Review the payment,
        then click <em>Generate License Key</em> to create a hardware-bound key for their device.
        Copy and email the key to the buyer.
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, email, hardware ID, plan..."
            className="input-field !pl-10"
          />
        </div>
        <div className="flex gap-2">
          {(["pending", "approved", "rejected", "all"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`px-3 py-2 rounded-xl text-sm border transition-all ${
                filter === s
                  ? "bg-primary-500/10 border-primary-500/50 text-primary-400"
                  : "border-white/10 text-gray-400 hover:border-white/20"
              }`}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
              {s === "pending" && pendingCount > 0 && (
                <span className="ml-1.5 bg-amber-500 text-black text-xs w-5 h-5 rounded-full inline-flex items-center justify-center">
                  {pendingCount}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className="glass-card overflow-hidden">
        {filtered.length === 0 ? (
          <div className="p-12 text-center">
            <KeyRound className="w-12 h-12 text-gray-600 mx-auto mb-4" />
            <h3 className="font-semibold text-lg mb-2">No desktop payments found</h3>
            <p className="text-gray-400 text-sm">
              {filter === "pending"
                ? "No payments waiting for license generation"
                : "No desktop payments match your filter"}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-white/5">
            {filtered.map((p) => {
              const st = statusConfig[p.status] || statusConfig.pending;
              const isProcessing = processing === p.id;
              const licenseKey = p.license_key || generatedKeys[p.id];

              return (
                <motion.div key={p.id} layout className="p-5">
                  <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                    {/* User info */}
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                      <div className="w-10 h-10 rounded-xl bg-blue-500/15 flex items-center justify-center shrink-0">
                        <Monitor className="w-5 h-5 text-blue-400" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="font-medium text-sm flex flex-wrap items-center gap-2">
                          {p.submitter_name || "—"}
                          <span className={`text-xs px-2 py-0.5 rounded-full flex items-center gap-1 ${st.bg} ${st.color}`}>
                            {st.icon}{p.status}
                          </span>
                          {p.plan_key && (
                            <span className="text-xs bg-white/10 text-gray-300 px-2 py-0.5 rounded-full">
                              {p.plan_key.replace(/_/g, " ")}
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-gray-400 mt-1">{p.submitter_email}</div>
                        <div className="mt-2 space-y-1">
                          <div className="text-xs">
                            <span className="text-gray-500">Amount: </span>
                            <span className="font-bold text-amber-400">{p.amount} EGP</span>
                            <span className="text-gray-500 ml-3">Method: </span>
                            <span className="text-gray-300">{p.method?.replace(/_/g, " ")}</span>
                          </div>
                          <div className="text-xs">
                            <span className="text-gray-500">Hardware ID: </span>
                            <span className="font-mono text-blue-300 break-all">{p.hardware_id}</span>
                          </div>
                          {p.reference && (
                            <div className="text-xs">
                              <span className="text-gray-500">Reference: </span>
                              <span className="font-mono">{p.reference}</span>
                            </div>
                          )}
                          <div className="text-xs text-gray-500">
                            Submitted: {new Date(p.created_at).toLocaleString()}
                          </div>
                          {p.has_screenshot && (
                            <div className="text-xs text-primary-400">📎 Payment screenshot attached</div>
                          )}
                        </div>

                        {/* Generated license key */}
                        {licenseKey && (
                          <div className="mt-3 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
                            <div className="text-amber-400 text-xs mb-1 font-medium">License Key</div>
                            <div className="flex items-center gap-2">
                              <code className="font-mono text-sm text-amber-300 flex-1 break-all">
                                {licenseKey}
                              </code>
                              <button
                                onClick={() => handleCopy(licenseKey, p.id)}
                                className="shrink-0 p-1.5 text-amber-400 hover:text-amber-300 hover:bg-amber-500/20 rounded-lg transition-colors"
                                title="Copy license key"
                              >
                                {copied === p.id ? (
                                  <CheckCircle2 className="w-4 h-4 text-accent-green" />
                                ) : (
                                  <Copy className="w-4 h-4" />
                                )}
                              </button>
                            </div>
                            <div className="text-xs text-gray-400 mt-1">
                              Send this key to: <span className="text-gray-300">{p.submitter_email}</span>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2 lg:shrink-0">
                      {p.status === "pending" && (
                        <button
                          onClick={() => handleGenerateLicense(p.id)}
                          disabled={isProcessing}
                          className="flex items-center gap-2 px-4 py-2 bg-primary-500/10 text-primary-400 border border-primary-500/30 rounded-xl text-sm font-medium hover:bg-primary-500/20 transition-colors disabled:opacity-50"
                        >
                          {isProcessing ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <KeyRound className="w-4 h-4" />
                          )}
                          Generate License Key
                        </button>
                      )}
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
