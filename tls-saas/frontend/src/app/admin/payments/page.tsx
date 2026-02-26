"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { adminApi } from "@/lib/api";
import {
  CreditCard, CheckCircle2, XCircle, Clock, Search,
  Loader2, Eye, Trash2, X, Monitor,
} from "lucide-react";

const statusConfig: Record<string, { color: string; bg: string; icon: React.ReactNode }> = {
  pending: { color: "text-amber-400", bg: "bg-amber-500/10", icon: <Clock className="w-3 h-3" /> },
  approved: { color: "text-accent-green", bg: "bg-accent-green/10", icon: <CheckCircle2 className="w-3 h-3" /> },
  rejected: { color: "text-red-400", bg: "bg-red-500/10", icon: <XCircle className="w-3 h-3" /> },
};

export default function AdminPaymentsPage() {
  const [payments, setPayments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("pending");
  const [search, setSearch] = useState("");
  const [processing, setProcessing] = useState<number | null>(null);
  const [toast, setToast] = useState<{ type: "success" | "error"; msg: string } | null>(null);
  const [detailPayment, setDetailPayment] = useState<any>(null);

  useEffect(() => {
    loadPayments();
  }, []);

  const loadPayments = async () => {
    try {
      const data = await adminApi.getPayments();
      setPayments(data.items || data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (paymentId: number) => {
    setProcessing(paymentId);
    try {
      await adminApi.approvePayment(paymentId);
      setPayments((prev) => prev.map((p) => (p.id === paymentId ? { ...p, status: "approved" } : p)));
      showToast("success", "Payment approved! Subscription activated.");
    } catch (err: any) {
      showToast("error", err?.detail || "Failed to approve");
    } finally {
      setProcessing(null);
    }
  };

  const handleReject = async (paymentId: number) => {
    setProcessing(paymentId);
    try {
      await adminApi.rejectPayment(paymentId, "Payment rejected by admin");
      setPayments((prev) => prev.map((p) => (p.id === paymentId ? { ...p, status: "rejected" } : p)));
      showToast("success", "Payment rejected.");
    } catch (err: any) {
      showToast("error", err?.detail || "Failed to reject");
    } finally {
      setProcessing(null);
    }
  };

  const handleDelete = async (paymentId: number) => {
    if (!confirm(`Permanently delete payment #${paymentId}? This cannot be undone.`)) return;
    setProcessing(paymentId);
    try {
      await adminApi.deletePayment(paymentId);
      setPayments((prev) => prev.filter((p) => p.id !== paymentId));
      showToast("success", `Payment #${paymentId} deleted.`);
    } catch (err: any) {
      showToast("error", err?.detail || "Failed to delete");
    } finally {
      setProcessing(null);
    }
  };

  const showToast = (type: "success" | "error", msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 4000);
  };

  const filtered = payments.filter((p) => {
    if (filter !== "all" && p.status !== filter) return false;
    if (search) {
      const s = search.toLowerCase();
      return (
        p.user_email?.toLowerCase().includes(s) ||
        p.reference?.toLowerCase().includes(s) ||
        p.user_name?.toLowerCase().includes(s) ||
        p.submitter_email?.toLowerCase().includes(s) ||
        p.submitter_name?.toLowerCase().includes(s) ||
        p.hardware_id?.toLowerCase().includes(s)
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
            className={`fixed top-4 right-4 z-50 px-6 py-3 rounded-xl font-medium shadow-lg ${
              toast.type === "success" ? "bg-accent-green text-black" : "bg-red-500 text-white"
            }`}
          >
            {toast.msg}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Detail Modal */}
      <AnimatePresence>
        {detailPayment && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70"
            onClick={() => setDetailPayment(null)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="glass-card p-6 max-w-xl w-full max-h-[90vh] overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-bold">Payment #{detailPayment.id}</h2>
                <button onClick={() => setDetailPayment(null)} className="text-gray-400 hover:text-white">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-3 text-sm">
                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-white/5 rounded-lg p-3">
                    <div className="text-gray-400 text-xs mb-1">Name</div>
                    <div className="font-medium">{detailPayment.submitter_name || detailPayment.user_name || "â€”"}</div>
                  </div>
                  <div className="bg-white/5 rounded-lg p-3">
                    <div className="text-gray-400 text-xs mb-1">Email</div>
                    <div className="font-medium break-all">{detailPayment.submitter_email || detailPayment.user_email || "â€”"}</div>
                  </div>
                  <div className="bg-white/5 rounded-lg p-3">
                    <div className="text-gray-400 text-xs mb-1">Plan</div>
                    <div className="font-medium">{detailPayment.plan_key || "â€”"}</div>
                  </div>
                  <div className="bg-white/5 rounded-lg p-3">
                    <div className="text-gray-400 text-xs mb-1">Amount</div>
                    <div className="font-bold text-amber-400">{detailPayment.amount} EGP</div>
                  </div>
                  <div className="bg-white/5 rounded-lg p-3">
                    <div className="text-gray-400 text-xs mb-1">Method</div>
                    <div className="font-medium">{detailPayment.method?.replace(/_/g, " ")}</div>
                  </div>
                  <div className="bg-white/5 rounded-lg p-3">
                    <div className="text-gray-400 text-xs mb-1">Status</div>
                    <div className={`font-medium ${statusConfig[detailPayment.status]?.color}`}>
                      {detailPayment.status}
                    </div>
                  </div>
                </div>

                {detailPayment.reference && (
                  <div className="bg-white/5 rounded-lg p-3">
                    <div className="text-gray-400 text-xs mb-1">Transaction Reference</div>
                    <div className="font-mono">{detailPayment.reference}</div>
                  </div>
                )}

                {detailPayment.hardware_id && (
                  <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-blue-400 text-xs mb-1">
                      <Monitor className="w-3 h-3" /> Hardware ID (Desktop Payment)
                    </div>
                    <div className="font-mono text-xs break-all">{detailPayment.hardware_id}</div>
                  </div>
                )}

                {detailPayment.license_key && (
                  <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
                    <div className="text-amber-400 text-xs mb-1">Generated License Key</div>
                    <div className="font-mono text-sm break-all">{detailPayment.license_key}</div>
                  </div>
                )}

                {detailPayment.admin_notes && (
                  <div className="bg-white/5 rounded-lg p-3">
                    <div className="text-gray-400 text-xs mb-1">Admin Notes</div>
                    <div>{detailPayment.admin_notes}</div>
                  </div>
                )}

                {detailPayment.screenshot_data && (
                  <div className="space-y-2">
                    <div className="text-gray-400 text-xs">Payment Screenshot</div>
                    <img
                      src={
                        detailPayment.screenshot_data.startsWith("data:")
                          ? detailPayment.screenshot_data
                          : `data:image/png;base64,${detailPayment.screenshot_data}`
                      }
                      alt="Payment receipt"
                      className="w-full rounded-lg border border-white/10"
                    />
                  </div>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold">Payment Management</h1>
          <p className="text-gray-400 text-sm mt-1">
            {pendingCount > 0 ? (
              <span className="text-amber-400">{pendingCount} pending approval</span>
            ) : (
              "No pending payments"
            )}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by user, email, hardware ID, reference..."
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

      {/* Payment list */}
      <div className="glass-card overflow-hidden">
        {filtered.length === 0 ? (
          <div className="p-12 text-center">
            <CreditCard className="w-12 h-12 text-gray-600 mx-auto mb-4" />
            <h3 className="font-semibold text-lg mb-2">No payments found</h3>
            <p className="text-gray-400 text-sm">
              {filter === "pending"
                ? "No payments awaiting approval"
                : "No payments match your filter"}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-white/5">
            {filtered.map((p) => {
              const st = statusConfig[p.status] || statusConfig.pending;
              const isProcessing = processing === p.id;
              const isDesktop = !!p.hardware_id;
              const displayName = p.submitter_name || p.user_name || p.user_email;
              const displayEmail = p.submitter_email || p.user_email;

              return (
                <motion.div
                  key={p.id}
                  layout
                  className="p-4 hover:bg-white/[0.02] transition-colors"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${isDesktop ? "bg-blue-500/15" : "bg-dark-700"}`}>
                        {isDesktop ? <Monitor className="w-5 h-5 text-blue-400" /> : <CreditCard className="w-5 h-5 text-gray-400" />}
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm font-medium flex items-center gap-2">
                          {displayName}
                          {isDesktop && <span className="text-xs bg-blue-500/15 text-blue-400 px-2 py-0.5 rounded-full">Desktop</span>}
                          {p.plan_key && <span className="text-xs bg-white/10 text-gray-300 px-2 py-0.5 rounded-full">{p.plan_key}</span>}
                        </div>
                        <div className="text-xs text-gray-500 flex flex-wrap items-center gap-x-2 gap-y-0.5">
                          <span>{displayEmail}</span>
                          <span>&middot;</span>
                          <span>{p.method?.replace(/_/g, " ")}</span>
                          <span>&middot;</span>
                          <span>{new Date(p.created_at).toLocaleDateString()}</span>
                        </div>
                        <div className="text-xs text-gray-400 mt-0.5 flex flex-wrap items-center gap-x-2">
                          {p.reference && <span>Ref: <span className="font-mono">{p.reference}</span></span>}
                          {p.hardware_id && <span className="text-blue-400 font-mono">HW: {p.hardware_id.slice(0, 8).toUpperCase()}</span>}
                          {p.screenshot_data && <span className="text-primary-400">ðŸ“Ž Screenshot</span>}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <span className="text-lg font-bold">{p.amount} EGP</span>
                      <span className={`text-xs font-medium px-2.5 py-1 rounded-full flex items-center gap-1 ${st.bg} ${st.color}`}>
                        {st.icon}
                        {p.status.charAt(0).toUpperCase() + p.status.slice(1)}
                      </span>

                      <button
                        onClick={() => setDetailPayment(p)}
                        title="View details"
                        className="p-1.5 text-gray-400 hover:text-primary-400 hover:bg-primary-500/10 rounded-lg transition-colors"
                      >
                        <Eye className="w-3.5 h-3.5" />
                      </button>

                      {p.status === "pending" && (
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleApprove(p.id)}
                            disabled={isProcessing}
                            className="px-3 py-1.5 bg-accent-green/10 text-accent-green rounded-lg text-xs font-medium hover:bg-accent-green/20 transition-colors disabled:opacity-50 flex items-center gap-1"
                          >
                            {isProcessing ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
                            Approve
                          </button>
                          <button
                            onClick={() => handleReject(p.id)}
                            disabled={isProcessing}
                            className="px-3 py-1.5 bg-red-500/10 text-red-400 rounded-lg text-xs font-medium hover:bg-red-500/20 transition-colors disabled:opacity-50 flex items-center gap-1"
                          >
                            {isProcessing ? <Loader2 className="w-3 h-3 animate-spin" /> : <XCircle className="w-3 h-3" />}
                            Reject
                          </button>
                        </div>
                      )}
                      <button
                        onClick={() => handleDelete(p.id)}
                        disabled={isProcessing}
                        title="Delete this payment record"
                        className="ml-1 p-1.5 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors disabled:opacity-50"
                      >
                        {isProcessing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                      </button>
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
