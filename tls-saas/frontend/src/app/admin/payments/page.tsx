"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { adminApi } from "@/lib/api";
import {
  CreditCard, CheckCircle2, XCircle, Clock, Search,
  Loader2, Eye, Trash2, X, Monitor, RefreshCw,
  ChevronLeft, ChevronRight, Send, Calendar,
} from "lucide-react";

const statusConfig: Record<string, { color: string; bg: string; icon: React.ReactNode }> = {
  pending: { color: "text-amber-400", bg: "bg-amber-500/10", icon: <Clock className="w-3 h-3" /> },
  approved: { color: "text-accent-green", bg: "bg-accent-green/10", icon: <CheckCircle2 className="w-3 h-3" /> },
  rejected: { color: "text-red-400", bg: "bg-red-500/10", icon: <XCircle className="w-3 h-3" /> },
};

// Rejection reason modal
function RejectModal({
  payment,
  onClose,
  onRejected,
}: {
  payment: any;
  onClose: () => void;
  onRejected: () => void;
}) {
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await adminApi.rejectPayment(payment.id, reason.trim() || "Payment rejected by admin");
      onRejected();
      onClose();
    } catch (err: any) {
      alert(err?.detail || err?.message || "Failed to reject");
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="glass-card w-full max-w-md p-6 space-y-4"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold flex items-center gap-2">
            <XCircle className="w-5 h-5 text-red-400" /> Reject Payment #{payment.id}
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <p className="text-sm text-gray-400">
          From:{" "}
          <span className="text-white">{payment.submitter_name || payment.user_name}</span>{" "}
          ({payment.submitter_email || payment.user_email})
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">Reason for rejection</label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Screenshot not clear, wrong amount, invalid reference..."
              rows={3}
              className="input-field resize-none"
              autoFocus
            />
            <p className="text-xs text-gray-500 mt-1">
              This reason will be included in the rejection notification.
            </p>
          </div>
          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="flex-1 btn-secondary py-2.5">
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-2.5 rounded-xl text-sm font-medium bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
              Reject Payment
            </button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  );
}

export default function AdminPaymentsPage() {
  const [payments, setPayments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("pending");
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [processing, setProcessing] = useState<number | null>(null);
  const [toast, setToast] = useState<{ type: "success" | "error"; msg: string } | null>(null);
  const [detailPayment, setDetailPayment] = useState<any>(null);
  const [rejectPayment, setRejectPayment] = useState<any>(null);
  const [selectedPayments, setSelectedPayments] = useState<Set<number>>(new Set());

  const showToast = (type: "success" | "error", msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 5000);
  };

  const loadPayments = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.getPayments(page, filter === "all" ? "" : filter);
      setPayments(data.items || data);
      setTotal(data.total || (data.items || data).length);
      setPages(data.pages || 1);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [page, filter]);

  useEffect(() => { setPage(1); }, [filter]);
  useEffect(() => { loadPayments(); }, [loadPayments]);

  const handleApprove = async (payment: any) => {
    setProcessing(payment.id);
    try {
      if (payment.hardware_id) {
        const result = await adminApi.generateLicense(payment.id);
        showToast(
          "success",
          result.email_sent
            ? `License generated and emailed to ${result.submitter_email}`
            : `License: ${result.license_key} — send manually to ${result.submitter_email || "customer"}`
        );
      } else {
        await adminApi.approvePayment(payment.id);
        showToast("success", "Payment approved! Subscription activated.");
      }
      loadPayments();
    } catch (err: any) {
      showToast("error", err?.message || err?.detail || "Failed to approve");
    } finally {
      setProcessing(null);
    }
  };

  const handleDelete = async (paymentId: number) => {
    if (!confirm(`Permanently delete payment #${paymentId}? This cannot be undone.`)) return;
    setProcessing(paymentId);
    try {
      await adminApi.deletePayment(paymentId);
      showToast("success", `Payment #${paymentId} deleted.`);
      loadPayments();
    } catch (err: any) {
      showToast("error", err?.detail || "Failed to delete");
    } finally {
      setProcessing(null);
    }
  };

  const handleResend = async (paymentId: number) => {
    try {
      const res = await adminApi.resendLicenseEmail(paymentId);
      showToast("success", res.message || "License email resent!");
    } catch (err: any) {
      showToast("error", err?.detail || "Failed to resend email");
    }
  };

  const togglePaymentSelect = (id: number) => {
    setSelectedPayments((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleSelectAllApproved = () => {
    if (selectedPayments.size === resendablePayments.length && resendablePayments.length > 0) {
      setSelectedPayments(new Set());
    } else {
      setSelectedPayments(new Set(resendablePayments.map((p) => p.id)));
    }
  };

  const handleBulkResend = async () => {
    const ids = Array.from(selectedPayments);
    setSelectedPayments(new Set());
    let sent = 0;
    for (const id of ids) {
      try { await adminApi.resendLicenseEmail(id); sent++; } catch {}
    }
    showToast(sent > 0 ? "success" : "error", sent > 0 ? `Resent ${sent} license email(s)` : "Failed to resend emails");
  };

  // Client-side search + date filter applied on top of server status/page filter
  const filtered = payments.filter((p) => {
    if (search) {
      const s = search.toLowerCase();
      const match =
        p.user_email?.toLowerCase().includes(s) ||
        p.reference?.toLowerCase().includes(s) ||
        p.user_name?.toLowerCase().includes(s) ||
        p.submitter_email?.toLowerCase().includes(s) ||
        p.submitter_name?.toLowerCase().includes(s) ||
        p.hardware_id?.toLowerCase().includes(s);
      if (!match) return false;
    }
    if (dateFrom && p.created_at && new Date(p.created_at) < new Date(dateFrom)) return false;
    if (dateTo && p.created_at && new Date(p.created_at) > new Date(dateTo + "T23:59:59")) return false;
    return true;
  });

  const resendablePayments = filtered.filter((p) => p.status === "approved" && p.license_key);

  return (
    <div className="space-y-6">
      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ x: 100, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 100, opacity: 0 }}
            className={`fixed top-4 right-4 z-50 px-6 py-3 rounded-xl font-medium shadow-xl max-w-md ${
              toast.type === "success" ? "bg-accent-green text-black" : "bg-red-500 text-white"
            }`}
          >
            {toast.msg}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Bulk resend action bar */}
      <AnimatePresence>
        {selectedPayments.size > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            className="flex items-center justify-between p-3 bg-blue-500/10 border border-blue-500/30 rounded-xl"
          >
            <span className="text-sm text-blue-400 font-medium">{selectedPayments.size} selected</span>
            <div className="flex gap-2">
              <button
                onClick={handleBulkResend}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-500/10 text-blue-400 border border-blue-500/30 rounded-xl text-xs font-medium hover:bg-blue-500/20 transition-colors"
              >
                <Send className="w-3.5 h-3.5" /> Resend Selected
              </button>
              <button
                onClick={() => setSelectedPayments(new Set())}
                className="p-1.5 text-gray-400 hover:text-white rounded-lg transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Reject Modal */}
      <AnimatePresence>
        {rejectPayment && (
          <RejectModal
            payment={rejectPayment}
            onClose={() => setRejectPayment(null)}
            onRejected={() => { showToast("success", "Payment rejected."); loadPayments(); }}
          />
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
                  {(
                    [
                      ["Name", detailPayment.submitter_name || detailPayment.user_name || "—"],
                      ["Email", detailPayment.submitter_email || detailPayment.user_email || "—"],
                      ["Plan", detailPayment.plan_key || "—"],
                      ["Amount", `${detailPayment.amount} EGP`],
                      ["Method", detailPayment.method?.replace(/_/g, " ") || "—"],
                      ["Status", detailPayment.status],
                    ] as [string, string][]
                  ).map(([label, val]) => (
                    <div key={label} className="bg-white/5 rounded-lg p-3">
                      <div className="text-gray-400 text-xs mb-1">{label}</div>
                      <div
                        className={`font-medium ${
                          label === "Amount"
                            ? "text-amber-400"
                            : label === "Status"
                            ? statusConfig[detailPayment.status]?.color
                            : ""
                        }`}
                      >
                        {val}
                      </div>
                    </div>
                  ))}
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
                    <div className="flex items-center justify-between mb-1">
                      <div className="text-amber-400 text-xs">Generated License Key</div>
                      {(detailPayment.submitter_email || detailPayment.user_email) && (
                        <button
                          onClick={() => handleResend(detailPayment.id)}
                          className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
                        >
                          <Send className="w-3 h-3" /> Resend Email
                        </button>
                      )}
                    </div>
                    <div className="font-mono text-sm break-all">{detailPayment.license_key}</div>
                  </div>
                )}

                {detailPayment.admin_notes && (
                  <div className="bg-white/5 rounded-lg p-3">
                    <div className="text-gray-400 text-xs mb-1">Admin Notes / Rejection Reason</div>
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

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold">Payment Management</h1>
          <p className="text-gray-400 text-sm mt-1">
            {total > 0 ? `${total} total` : "No payments"}
            {filter === "pending" && total > 0 && (
              <span className="text-amber-400"> · {total} pending approval</span>
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

      {/* Filters */}
      <div className="space-y-3">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name, email, hardware ID, reference..."
              className="input-field !pl-10"
            />
          </div>
          <div className="flex gap-2 flex-wrap">
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
                {s === "pending" && filter === "pending" && total > 0 && (
                  <span className="ml-1.5 bg-amber-500 text-black text-xs w-5 h-5 rounded-full inline-flex items-center justify-center font-bold">
                    {total}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Date range filter */}
        <div className="flex items-center gap-3 flex-wrap">
          <Calendar className="w-4 h-4 text-gray-400 shrink-0" />
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="input-field !py-1.5 !px-3 text-sm w-auto"
          />
          <span className="text-gray-500 text-sm">to</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="input-field !py-1.5 !px-3 text-sm w-auto"
          />
          {(dateFrom || dateTo) && (
            <button
              onClick={() => { setDateFrom(""); setDateTo(""); }}
              className="text-xs text-gray-400 hover:text-white transition-colors"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Payment list */}
      <div className="glass-card overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="spinner w-8 h-8" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center">
            <CreditCard className="w-12 h-12 text-gray-600 mx-auto mb-4" />
            <h3 className="font-semibold text-lg mb-2">No payments found</h3>
            <p className="text-gray-400 text-sm">
              {filter === "pending" ? "No payments awaiting approval" : "No payments match your filter"}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-white/5">
            {/* Select-all row for approved licensed payments */}
            {filter === "approved" && resendablePayments.length > 0 && (
              <div className="px-4 py-2 border-b border-white/5 flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={selectedPayments.size === resendablePayments.length && resendablePayments.length > 0}
                  onChange={toggleSelectAllApproved}
                  className="w-3.5 h-3.5 accent-primary-400 cursor-pointer"
                />
                <span className="text-xs text-gray-500">Select all with license keys ({resendablePayments.length})</span>
              </div>
            )}
            {filtered.map((p) => {
              const st = statusConfig[p.status] || statusConfig.pending;
              const isProcessing = processing === p.id;
              const isDesktop = !!p.hardware_id;
              const displayName = p.submitter_name || p.user_name || p.user_email;
              const displayEmail = p.submitter_email || p.user_email;

              return (
                <motion.div key={p.id} layout className="p-4 hover:bg-white/[0.02] transition-colors">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      {p.status === "approved" && p.license_key && (
                        <input
                          type="checkbox"
                          checked={selectedPayments.has(p.id)}
                          onChange={() => togglePaymentSelect(p.id)}
                          className="w-3.5 h-3.5 accent-primary-400 cursor-pointer shrink-0"
                        />
                      )}
                      <div
                        className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
                          isDesktop ? "bg-blue-500/15" : "bg-dark-700"
                        }`}
                      >
                        {isDesktop ? (
                          <Monitor className="w-5 h-5 text-blue-400" />
                        ) : (
                          <CreditCard className="w-5 h-5 text-gray-400" />
                        )}
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm font-medium flex items-center gap-2">
                          {displayName}
                          {isDesktop && (
                            <span className="text-xs bg-blue-500/15 text-blue-400 px-2 py-0.5 rounded-full">
                              Desktop
                            </span>
                          )}
                          {p.plan_key && (
                            <span className="text-xs bg-white/10 text-gray-300 px-2 py-0.5 rounded-full">
                              {p.plan_key.replace(/_/g, " ")}
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-gray-500 flex flex-wrap items-center gap-x-2 gap-y-0.5">
                          <span>{displayEmail}</span>
                          <span>&middot;</span>
                          <span>{p.method?.replace(/_/g, " ")}</span>
                          <span>&middot;</span>
                          <span>{new Date(p.created_at).toLocaleDateString()}</span>
                        </div>
                        <div className="text-xs text-gray-400 mt-0.5 flex flex-wrap items-center gap-x-2">
                          {p.reference && (
                            <span>
                              Ref: <span className="font-mono">{p.reference}</span>
                            </span>
                          )}
                          {p.hardware_id && (
                            <span className="text-blue-400 font-mono">
                              HW: {p.hardware_id.slice(0, 8).toUpperCase()}
                            </span>
                          )}
                          {p.screenshot_data && <span className="text-primary-400">Screenshot</span>}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-lg font-bold">{p.amount} EGP</span>
                      <span
                        className={`text-xs font-medium px-2.5 py-1 rounded-full flex items-center gap-1 ${st.bg} ${st.color}`}
                      >
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

                      {p.status === "approved" && p.license_key && (
                        <button
                          onClick={() => handleResend(p.id)}
                          title="Resend license email"
                          disabled={isProcessing}
                          className="p-1.5 text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 rounded-lg transition-colors disabled:opacity-50"
                        >
                          <Send className="w-3.5 h-3.5" />
                        </button>
                      )}

                      {p.status === "pending" && (
                        <>
                          <button
                            onClick={() => handleApprove(p)}
                            disabled={isProcessing}
                            className="px-3 py-1.5 bg-accent-green/10 text-accent-green rounded-lg text-xs font-medium hover:bg-accent-green/20 transition-colors disabled:opacity-50 flex items-center gap-1"
                          >
                            {isProcessing ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              <CheckCircle2 className="w-3 h-3" />
                            )}
                            Approve
                          </button>
                          <button
                            onClick={() => setRejectPayment(p)}
                            disabled={isProcessing}
                            className="px-3 py-1.5 bg-red-500/10 text-red-400 rounded-lg text-xs font-medium hover:bg-red-500/20 transition-colors disabled:opacity-50 flex items-center gap-1"
                          >
                            <XCircle className="w-3 h-3" /> Reject
                          </button>
                        </>
                      )}

                      <button
                        onClick={() => handleDelete(p.id)}
                        disabled={isProcessing}
                        title="Delete this payment record"
                        className="p-1.5 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors disabled:opacity-50"
                      >
                        {isProcessing ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Trash2 className="w-3.5 h-3.5" />
                        )}
                      </button>
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
        <div className="flex items-center justify-between text-sm text-gray-400">
          <span>
            Page {page} of {pages} &middot; {total} total
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-1.5 rounded-lg hover:bg-white/5 disabled:opacity-30 transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-3 py-1 bg-white/5 rounded-lg">
              {page} / {pages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
              disabled={page === pages}
              className="p-1.5 rounded-lg hover:bg-white/5 disabled:opacity-30 transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
