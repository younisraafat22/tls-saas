"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { adminApi } from "@/lib/api";
import {
  Users, Search, Shield, ShieldOff,
  Ban, CheckCircle2, Trash2, Eye, X,
  CreditCard, KeyRound, RefreshCw,
  ChevronLeft, ChevronRight,
} from "lucide-react";

function UserDetailModal({
  user,
  onClose,
  onUserChanged,
}: {
  user: any;
  onClose: () => void;
  onUserChanged: () => void;
}) {
  const [payments, setPayments] = useState<any[]>([]);
  const [loadingPayments, setLoadingPayments] = useState(true);
  const [subscriptions, setSubscriptions] = useState<any[]>([]);
  const [activeSubscriptions, setActiveSubscriptions] = useState<any[]>([]);
  const [loadingSubscriptions, setLoadingSubscriptions] = useState(true);
  const [processingSubId, setProcessingSubId] = useState<number | null>(null);
  const [actionConfirm, setActionConfirm] = useState<null | {
    type: "revoke" | "remove";
    subscription: any;
  }>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const loadSubscriptions = useCallback(async () => {
    setLoadingSubscriptions(true);
    try {
      const data = await adminApi.getUserSubscriptions(user.id);
      setSubscriptions(data.history || []);
      setActiveSubscriptions(data.active_subscriptions || []);
    } catch {
      setSubscriptions([]);
      setActiveSubscriptions([]);
    } finally {
      setLoadingSubscriptions(false);
    }
  }, [user.id]);

  useEffect(() => {
    adminApi.getUserPayments(user.id)
      .then((data) => setPayments(data.payments || data || []))
      .catch(() => setPayments([]))
      .finally(() => setLoadingPayments(false));
  }, [user.id]);

  useEffect(() => {
    loadSubscriptions();
  }, [loadSubscriptions]);

  const revokeSubscription = async (subscriptionId: number) => {
    setActionError(null);
    setProcessingSubId(subscriptionId);
    try {
      await adminApi.revokeUserSubscription(user.id, subscriptionId);
      await loadSubscriptions();
      onUserChanged();
      setActionConfirm(null);
    } catch (err: any) {
      setActionError(err?.message || "Failed to revoke subscription");
    } finally {
      setProcessingSubId(null);
    }
  };

  const deleteSubscription = async (subscriptionId: number) => {
    setActionError(null);
    setProcessingSubId(subscriptionId);
    try {
      await adminApi.deleteUserSubscription(user.id, subscriptionId);
      await loadSubscriptions();
      onUserChanged();
      setActionConfirm(null);
    } catch (err: any) {
      setActionError(err?.message || "Failed to delete subscription");
    } finally {
      setProcessingSubId(null);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <motion.div
        initial={{ y: 100, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 100, opacity: 0 }}
        className="glass-card w-full sm:max-w-xl max-h-[90vh] overflow-y-auto rounded-t-2xl sm:rounded-2xl p-6 space-y-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-primary-500/15 flex items-center justify-center text-primary-400 font-bold text-lg shrink-0">
              {user.full_name?.charAt(0)?.toUpperCase() || "?"}
            </div>
            <div>
              <div className="font-bold flex items-center gap-2">
                {user.full_name}
                {user.is_admin && <Shield className="w-4 h-4 text-amber-400" />}
              </div>
              <div className="text-sm text-gray-400">{user.email}</div>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* User info grid */}
        <div className="grid grid-cols-2 gap-2 text-sm">
          {[
            ["Phone", user.phone || "—"],
            ["Status", user.is_active ? "Active" : "Disabled"],
            ["Subscription", user.subscription_status?.replace(/_/g, " ") || "None"],
            ["Plan", user.plan_name || "—"],
            ["Joined", new Date(user.created_at).toLocaleDateString()],
            ["Last Login", user.last_login ? new Date(user.last_login).toLocaleDateString() : "—"],
          ].map(([label, val]) => (
            <div key={label} className="bg-white/5 rounded-lg p-3">
              <div className="text-gray-400 text-xs mb-1">{label}</div>
              <div className="font-medium capitalize">{val}</div>
            </div>
          ))}
        </div>

        {Array.isArray(user.entitlements) && user.entitlements.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <KeyRound className="w-4 h-4 text-gray-400" /> Entitlements
            </h3>
            <div className="flex flex-wrap gap-2">
              {user.entitlements.map((ent: any, idx: number) => (
                <div
                  key={`${ent.source}-${ent.plan_key}-${idx}`}
                  className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs"
                >
                  <span className="text-gray-300">{ent.plan_name || ent.plan_key}</span>
                  <span className="text-gray-500"> · {ent.source}</span>
                  <span className={`ml-1 ${ent.status === "active" ? "text-accent-green" : "text-amber-400"}`}>
                    ({ent.status === "active" ? "active" : "pending"})
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Active subscriptions */}
        <div>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-gray-400" /> Active Subscriptions
          </h3>
          {loadingSubscriptions ? (
            <div className="flex justify-center py-6"><div className="spinner w-6 h-6" /></div>
          ) : activeSubscriptions.length === 0 ? (
            <div className="text-center py-4 text-gray-500 text-sm">No active subscriptions</div>
          ) : (
            <div className="space-y-2">
              {activeSubscriptions.map((s: any) => (
                <div key={`active-sub-${s.id}`} className="p-3 rounded-lg bg-accent-green/5 border border-accent-green/20 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <div className="font-medium">{s.plan_name || s.plan_key || "Subscription"}</div>
                      <div className="text-xs text-gray-400">
                        Expires {s.expires_at ? new Date(s.expires_at).toLocaleString() : "never"}
                      </div>
                    </div>
                    <span className="text-xs px-2 py-1 rounded-full bg-accent-green/15 text-accent-green">active</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Subscription history */}
        <div>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <RefreshCw className="w-4 h-4 text-gray-400" /> Subscription History
          </h3>
          {loadingSubscriptions ? (
            <div className="flex justify-center py-6"><div className="spinner w-6 h-6" /></div>
          ) : subscriptions.length === 0 ? (
            <div className="text-center py-6 text-gray-500 text-sm">No subscription history found</div>
          ) : (
            <div className="space-y-2">
              {subscriptions.map((s: any) => {
                const status = String(s.status || "unknown");
                const statusClass =
                  status === "active"
                    ? "text-accent-green bg-accent-green/10"
                    : status === "cancelled"
                      ? "text-red-400 bg-red-500/10"
                      : "text-amber-400 bg-amber-500/10";
                const canRevoke = status === "active";
                const busy = processingSubId === s.id;

                return (
                  <div key={`hist-sub-${s.id}`} className="p-3 rounded-lg bg-white/5 border border-white/10 text-sm space-y-2">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-medium">{s.plan_name || s.plan_key || "Subscription"}</div>
                        <div className="text-xs text-gray-400">
                          #{s.id} · {s.created_at ? new Date(s.created_at).toLocaleString() : "unknown"}
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          {s.starts_at ? `Start: ${new Date(s.starts_at).toLocaleDateString()} · ` : ""}
                          {s.expires_at ? `Expire: ${new Date(s.expires_at).toLocaleDateString()}` : "No expiry"}
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          Linked payments: {s.linked_payments_count ?? 0}
                        </div>
                      </div>
                      <span className={`text-xs px-2 py-1 rounded-full capitalize ${statusClass}`}>{status}</span>
                    </div>

                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => {
                          setActionError(null);
                          setActionConfirm({ type: "revoke", subscription: s });
                        }}
                        disabled={!canRevoke || busy}
                        className="px-2.5 py-1.5 rounded-lg text-xs bg-amber-500/10 text-amber-300 border border-amber-500/30 disabled:opacity-40"
                      >
                        {busy && canRevoke ? "Revoking..." : "Revoke"}
                      </button>
                      <button
                        onClick={() => {
                          setActionError(null);
                          setActionConfirm({ type: "remove", subscription: s });
                        }}
                        disabled={busy}
                        className="px-2.5 py-1.5 rounded-lg text-xs bg-red-500/10 text-red-300 border border-red-500/30 disabled:opacity-40"
                      >
                        {busy ? "Removing..." : "Remove"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Payment history */}
        <div>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <CreditCard className="w-4 h-4 text-gray-400" /> Payment History
          </h3>
          {loadingPayments ? (
            <div className="flex justify-center py-6"><div className="spinner w-6 h-6" /></div>
          ) : payments.length === 0 ? (
            <div className="text-center py-6 text-gray-500 text-sm">No payments found</div>
          ) : (
            <div className="space-y-2">
              {payments.map((p: any) => (
                <div key={p.id} className={`flex items-center justify-between p-3 rounded-lg bg-white/5 text-sm`}>
                  <div>
                    <div className="font-medium">{p.plan_key?.replace(/_/g, " ") || p.method?.replace(/_/g, " ")}</div>
                    <div className="text-xs text-gray-500">{new Date(p.created_at).toLocaleDateString()}</div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-amber-400">{p.amount} EGP</div>
                    <div className={`text-xs ${
                      p.status === "approved" ? "text-accent-green" : p.status === "rejected" ? "text-red-400" : "text-amber-400"
                    }`}>
                      {p.status}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <AnimatePresence>
          {actionConfirm && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-[60] bg-black/75 backdrop-blur-sm flex items-center justify-center p-4"
              onClick={(e) => e.target === e.currentTarget && setActionConfirm(null)}
            >
              <motion.div
                initial={{ y: 24, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: 24, opacity: 0 }}
                className="w-full max-w-md rounded-2xl border border-white/10 bg-[#0f1116] p-5 space-y-4"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="space-y-1">
                  <h4 className="text-base font-semibold">
                    {actionConfirm.type === "revoke" ? "Revoke subscription" : "Remove subscription history"}
                  </h4>
                  <p className="text-sm text-gray-400">
                    #{actionConfirm.subscription.id} · {actionConfirm.subscription.plan_name || actionConfirm.subscription.plan_key || "Subscription"}
                  </p>
                </div>

                {actionConfirm.type === "revoke" ? (
                  <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
                    Revoking cancels access immediately. The record stays in history for audit and can still be reviewed later.
                  </div>
                ) : (
                  <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
                    Removing permanently deletes this subscription row from history. This action cannot be undone.
                  </div>
                )}

                {actionError && (
                  <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-2.5 text-sm text-red-200">
                    {actionError}
                  </div>
                )}

                <div className="flex items-center justify-end gap-2">
                  <button
                    onClick={() => setActionConfirm(null)}
                    disabled={processingSubId === actionConfirm.subscription.id}
                    className="px-3 py-2 rounded-lg text-sm border border-white/15 text-gray-300 hover:bg-white/5 disabled:opacity-40"
                  >
                    Cancel
                  </button>
                  {actionConfirm.type === "revoke" ? (
                    <button
                      onClick={() => revokeSubscription(actionConfirm.subscription.id)}
                      disabled={processingSubId === actionConfirm.subscription.id}
                      className="px-3 py-2 rounded-lg text-sm bg-amber-500/15 text-amber-200 border border-amber-500/35 disabled:opacity-40"
                    >
                      {processingSubId === actionConfirm.subscription.id ? "Revoking..." : "Confirm Revoke"}
                    </button>
                  ) : (
                    <button
                      onClick={() => deleteSubscription(actionConfirm.subscription.id)}
                      disabled={processingSubId === actionConfirm.subscription.id}
                      className="px-3 py-2 rounded-lg text-sm bg-red-500/15 text-red-200 border border-red-500/35 disabled:opacity-40"
                    >
                      {processingSubId === actionConfirm.subscription.id ? "Removing..." : "Confirm Remove"}
                    </button>
                  )}
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </motion.div>
  );
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"created_at" | "email" | "subscription_status">("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [filterStatus, setFilterStatus] = useState<"all" | "active" | "pending" | "none">("all");
  const [toast, setToast] = useState<{ type: "success" | "error"; msg: string } | null>(null);
  const [selectedUser, setSelectedUser] = useState<any>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);

  const showToast = (type: "success" | "error", msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 4000);
  };

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.getUsers(page);
      setUsers(data.items || data);
      setTotal(data.total || (data.items || data).length);
      setPages(data.pages || 1);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => { loadUsers(); }, [loadUsers]);

  const toggleAdmin = async (userId: number, isAdmin: boolean) => {
    try {
      await adminApi.updateUser(userId, { is_admin: !isAdmin });
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, is_admin: !isAdmin } : u)));
      showToast("success", `User ${!isAdmin ? "promoted to" : "removed from"} admin`);
    } catch (err) {
      console.error(err);
    }
  };

  const toggleActive = async (userId: number, isActive: boolean) => {
    try {
      await adminApi.updateUser(userId, { is_active: !isActive });
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, is_active: !isActive } : u)));
      showToast("success", `User ${!isActive ? "activated" : "deactivated"}`);
    } catch (err) {
      console.error(err);
    }
  };

  const deleteUser = async (userId: number, email: string) => {
    if (!confirm(`Permanently delete ${email}? This cannot be undone.`)) return;
    try {
      await adminApi.deleteUser(userId);
      setUsers((prev) => prev.filter((u) => u.id !== userId));
      showToast("success", "User deleted");
    } catch (err: any) {
      showToast("error", err?.message || "Failed to delete user");
    }
  };

  const filtered = useMemo(() => {
    let list = [...users];
    if (search) {
      const s = search.toLowerCase();
      list = list.filter(
        (u) =>
          u.email.toLowerCase().includes(s) ||
          u.full_name?.toLowerCase().includes(s) ||
          u.phone?.toLowerCase().includes(s)
      );
    }
    if (filterStatus === "active") list = list.filter((u) => u.subscription_status === "active");
    if (filterStatus === "pending") list = list.filter((u) => u.subscription_status === "pending_payment");
    if (filterStatus === "none") list = list.filter((u) => u.subscription_status === "none");

    list.sort((a, b) => {
      if (sortBy === "subscription_status") {
        const order: Record<string, number> = { active: 0, pending_payment: 1 };
        const valA = order[a.subscription_status ?? ""] ?? 2;
        const valB = order[b.subscription_status ?? ""] ?? 2;
        return sortDir === "asc" ? valA - valB : valB - valA;
      }
      const valA = a[sortBy] || "";
      const valB = b[sortBy] || "";
      return sortDir === "asc" ? (valA > valB ? 1 : -1) : valA < valB ? 1 : -1;
    });
    return list;
  }, [users, search, filterStatus, sortBy, sortDir]);

  if (loading && page === 1) {
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
            className={`fixed top-4 right-4 z-50 px-6 py-3 rounded-xl font-medium shadow-xl max-w-sm ${
              toast.type === "success" ? "bg-accent-green text-black" : "bg-red-500 text-white"
            }`}
          >
            {toast.msg}
          </motion.div>
        )}
      </AnimatePresence>

      {/* User detail modal */}
      <AnimatePresence>
        {selectedUser && (
          <UserDetailModal
            user={selectedUser}
            onClose={() => setSelectedUser(null)}
            onUserChanged={loadUsers}
          />
        )}
      </AnimatePresence>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold">User Management</h1>
          <p className="text-gray-400 text-sm mt-1">{total > 0 ? `${total} total users` : `${users.length} users`}</p>
        </div>
        <button
          onClick={loadUsers}
          className="p-2 text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, email, phone..."
            className="input-field !pl-10"
          />
        </div>
        <div className="flex gap-2 flex-wrap">
          {(["all", "active", "pending", "none"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setFilterStatus(s)}
              className={`px-3 py-2 rounded-xl text-sm border transition-all ${
                filterStatus === s
                  ? "bg-primary-500/10 border-primary-500/50 text-primary-400"
                  : "border-white/10 text-gray-400 hover:border-white/20"
              }`}
            >
              {s === "all" ? "All" : s === "active" ? "Active" : s === "pending" ? "Pending" : "No Sub"}
            </button>
          ))}
        </div>
      </div>

      {/* User table */}
      <div className="glass-card overflow-hidden">
        {/* Table header */}
        <div className="hidden sm:grid grid-cols-12 gap-4 p-4 border-b border-white/5 text-xs text-gray-400 uppercase tracking-wider font-medium">
          <button
            className="col-span-4 text-left flex items-center gap-1 hover:text-white transition-colors"
            onClick={() => { setSortBy("email"); setSortDir((d) => sortBy === "email" ? (d === "asc" ? "desc" : "asc") : "asc"); }}
          >
            User {sortBy === "email" && (sortDir === "asc" ? "↑" : "↓")}
          </button>
          <button
            className="col-span-4 text-left flex items-center gap-1 hover:text-white transition-colors"
            onClick={() => { setSortBy("subscription_status"); setSortDir((d) => sortBy === "subscription_status" ? (d === "asc" ? "desc" : "asc") : "asc"); }}
          >
            Subscription {sortBy === "subscription_status" && (sortDir === "asc" ? "↑" : "↓")}
          </button>
          <button
            className="col-span-2 text-left flex items-center gap-1 hover:text-white transition-colors"
            onClick={() => { setSortBy("created_at"); setSortDir((d) => sortBy === "created_at" ? (d === "asc" ? "desc" : "asc") : "desc"); }}
          >
            Joined {sortBy === "created_at" && (sortDir === "asc" ? "↑" : "↓")}
          </button>
          <div className="col-span-2 text-right">Actions</div>
        </div>

        {filtered.length === 0 ? (
          <div className="p-12 text-center text-gray-500">No users found</div>
        ) : (
          <div className="divide-y divide-white/5">
            {filtered.map((user) => (
              <div
                key={user.id}
                className="p-4 hover:bg-white/[0.02] transition-colors cursor-pointer"
                onClick={() => setSelectedUser(user)}
              >
                <div className="sm:grid grid-cols-12 gap-4 items-center">
                  {/* User info */}
                  <div className="col-span-4 flex items-center gap-3 mb-2 sm:mb-0">
                    <div className="w-9 h-9 rounded-xl bg-primary-500/10 flex items-center justify-center text-primary-400 font-bold text-sm shrink-0">
                      {user.full_name?.charAt(0)?.toUpperCase() || "?"}
                    </div>
                    <div className="min-w-0">
                      <div className="font-medium text-sm truncate flex items-center gap-1.5">
                        {user.full_name}
                        {user.is_admin && (
                          <Shield className="w-3 h-3 text-amber-400" />
                        )}
                      </div>
                      <div className="text-xs text-gray-500 truncate">{user.email}</div>
                    </div>
                  </div>

                  {/* Subscription status */}
                  <div className="col-span-4 mb-2 sm:mb-0">
                    {user.subscription_status === "active" ? (
                      <div className="space-y-0.5">
                        <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full bg-accent-green/10 text-accent-green">
                          <div className="w-1.5 h-1.5 rounded-full bg-accent-green" />
                          Active
                        </span>
                        {user.plan_name && (
                          <div className="text-xs text-gray-400 pl-1">{user.plan_name}</div>
                        )}
                      </div>
                    ) : user.subscription_status === "pending_payment" ? (
                      <div className="space-y-0.5">
                        <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full bg-amber-500/10 text-amber-400">
                          <div className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                          Pending Payment
                        </span>
                        {user.plan_name && (
                          <div className="text-xs text-gray-400 pl-1">{user.plan_name}</div>
                        )}
                      </div>
                    ) : (
                      <span className="text-xs text-gray-500">None</span>
                    )}
                  </div>

                  {/* Joined date */}
                  <div className="col-span-2 text-sm text-gray-400 mb-2 sm:mb-0">
                    {new Date(user.created_at).toLocaleDateString("en-GB", { day: "2-digit", month: "short" })}
                  </div>

                  {/* Actions */}
                  <div className="col-span-2 flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => setSelectedUser(user)}
                      className="p-1.5 text-gray-400 hover:text-primary-400 hover:bg-primary-500/10 rounded-lg transition-colors"
                      title="View details"
                    >
                      <Eye className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => toggleAdmin(user.id, user.is_admin)}
                      className={`p-1.5 rounded-lg transition-colors ${
                        user.is_admin ? "text-amber-400 hover:bg-amber-400/10" : "text-gray-500 hover:bg-white/5"
                      }`}
                      title={user.is_admin ? "Remove admin" : "Make admin"}
                    >
                      {user.is_admin ? <ShieldOff className="w-3.5 h-3.5" /> : <Shield className="w-3.5 h-3.5" />}
                    </button>
                    <button
                      onClick={() => toggleActive(user.id, user.is_active)}
                      className={`p-1.5 rounded-lg transition-colors ${
                        user.is_active ? "text-red-400 hover:bg-red-400/10" : "text-accent-green hover:bg-accent-green/10"
                      }`}
                      title={user.is_active ? "Disable user" : "Enable user"}
                    >
                      {user.is_active ? <Ban className="w-3.5 h-3.5" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                    </button>
                    {!user.is_admin && (
                      <button
                        onClick={() => deleteUser(user.id, user.email)}
                        className="p-1.5 rounded-lg text-gray-600 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                        title="Delete user permanently"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-between text-sm text-gray-400">
          <span>Page {page} of {pages} &middot; {total} total</span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-1.5 rounded-lg hover:bg-white/5 disabled:opacity-30 transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-3 py-1 bg-white/5 rounded-lg">{page} / {pages}</span>
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
