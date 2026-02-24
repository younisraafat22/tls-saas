"use client";

import { useState, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { adminApi } from "@/lib/api";
import {
  Users, Search, Shield, ShieldOff,
  Ban, CheckCircle2, MapPin, Trash2,
} from "lucide-react";

export default function AdminUsersPage() {
  const [users, setUsers] = useState<any[]>([]);
  const [branches, setBranches] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"created_at" | "email">("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [filterStatus, setFilterStatus] = useState<"all" | "active" | "pending" | "none">("all");
  const [toast, setToast] = useState<string | null>(null);
  const [assigningBranch, setAssigningBranch] = useState<{ userId: number; selectedBranch: number } | null>(null);

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      const [usersData, branchesData] = await Promise.all([
        adminApi.getUsers(),
        adminApi.getBranches(),
      ]);
      setUsers(usersData.items || usersData);
      setBranches(branchesData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const assignBranch = async (userId: number, branchId: number) => {
    try {
      await adminApi.assignBranch(userId, branchId);
      setToast("Branch assigned! User will now be monitored.");
      setAssigningBranch(null);
    } catch (err) {
      console.error(err);
    }
    setTimeout(() => setToast(null), 3000);
  };

  const toggleAdmin = async (userId: number, isAdmin: boolean) => {
    try {
      await adminApi.updateUser(userId, { is_admin: !isAdmin });
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, is_admin: !isAdmin } : u)));
      setToast(`User ${!isAdmin ? "promoted to" : "removed from"} admin`);
      setTimeout(() => setToast(null), 3000);
    } catch (err) {
      console.error(err);
    }
  };

  const toggleActive = async (userId: number, isActive: boolean) => {
    try {
      await adminApi.updateUser(userId, { is_active: !isActive });
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, is_active: !isActive } : u)));
      setToast(`User ${!isActive ? "activated" : "deactivated"}`);
      setTimeout(() => setToast(null), 3000);
    } catch (err) {
      console.error(err);
    }
  };

  const deleteUser = async (userId: number, email: string) => {
    if (!confirm(`Permanently delete ${email}? This cannot be undone.`)) return;
    try {
      await adminApi.deleteUser(userId);
      setUsers((prev) => prev.filter((u) => u.id !== userId));
      setToast("User deleted");
      setTimeout(() => setToast(null), 3000);
    } catch (err: any) {
      setToast(err?.detail || "Failed to delete user");
      setTimeout(() => setToast(null), 3000);
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
      const valA = a[sortBy] || "";
      const valB = b[sortBy] || "";
      return sortDir === "asc" ? (valA > valB ? 1 : -1) : valA < valB ? 1 : -1;
    });
    return list;
  }, [users, search, filterStatus, sortBy, sortDir]);

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
            className="fixed top-4 right-4 z-50 bg-accent-green text-black px-6 py-3 rounded-xl font-medium shadow-lg"
          >
            {toast}
          </motion.div>
        )}
      </AnimatePresence>

      <div>
        <h1 className="text-2xl font-display font-bold">User Management</h1>
        <p className="text-gray-400 text-sm mt-1">{users.length} total users</p>
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
        <div className="flex gap-2">
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
          <div className="col-span-4">User</div>
          <div className="col-span-3">Subscription</div>
          <div className="col-span-2">Monitoring</div>
          <div className="col-span-1">Joined</div>
          <div className="col-span-2 text-right">Actions</div>
        </div>

        {filtered.length === 0 ? (
          <div className="p-12 text-center text-gray-500">No users found</div>
        ) : (
          <div className="divide-y divide-white/5">
            {filtered.map((user) => (
              <div key={user.id} className="p-4 hover:bg-white/[0.02] transition-colors">
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
                  <div className="col-span-3 mb-2 sm:mb-0">
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

                  {/* Monitoring */}
                  <div className="col-span-2 mb-2 sm:mb-0">
                    {user.subscription_status === "active" ? (
                      <div className="space-y-0.5">
                        <span className={`inline-flex items-center gap-1 text-xs font-medium ${
                          user.monitored_branches > 0 ? "text-accent-green" : "text-gray-500"
                        }`}>
                          <div className={`w-1.5 h-1.5 rounded-full ${
                            user.monitored_branches > 0 ? "bg-accent-green" : "bg-gray-500"
                          }`} />
                          {user.monitored_branches > 0 ? `${user.monitored_branches} branch${user.monitored_branches > 1 ? "es" : ""}` : "No branches"}
                        </span>
                      </div>
                    ) : user.subscription_status === "pending_payment" ? (
                      <span className="text-xs text-amber-400">Awaiting approval</span>
                    ) : (
                      <span className="text-xs text-gray-600">—</span>
                    )}
                  </div>

                  {/* Joined date */}
                  <div className="col-span-1 text-sm text-gray-400 mb-2 sm:mb-0">
                    {new Date(user.created_at).toLocaleDateString("en-GB", { day: "2-digit", month: "short" })}
                  </div>

                  {/* Actions */}
                  <div className="col-span-2 flex items-center justify-end gap-2">
                    {user.subscription_status === "active" && (
                      <div className="relative">
                        {assigningBranch?.userId === user.id ? (
                          <div className="flex items-center gap-1">
                            <select
                              className="text-xs bg-dark-700 border border-white/10 rounded-lg px-2 py-1.5 text-white"
                              value={assigningBranch?.selectedBranch || ""}
                              onChange={(e) => setAssigningBranch({ userId: user.id, selectedBranch: Number(e.target.value) })}
                            >
                              <option value="">Pick branch…</option>
                              {branches.filter((b: any) => b.is_active).map((b: any) => (
                                <option key={b.id} value={b.id}>{b.name}</option>
                              ))}
                            </select>
                            <button
                              onClick={() => assigningBranch?.selectedBranch && assignBranch(user.id, assigningBranch.selectedBranch)}
                              className="text-xs px-2 py-1.5 bg-accent-green/10 text-accent-green rounded-lg hover:bg-accent-green/20"
                            >OK</button>
                            <button onClick={() => setAssigningBranch(null)} className="text-xs px-2 py-1.5 bg-white/5 text-gray-400 rounded-lg">✕</button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setAssigningBranch({ userId: user.id, selectedBranch: 0 })}
                            className="p-2 rounded-lg text-gray-500 hover:bg-white/5 transition-colors"
                            title="Assign branch to monitor"
                          >
                            <MapPin className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    )}
                    <button
                      onClick={() => toggleAdmin(user.id, user.is_admin)}
                      className={`p-2 rounded-lg transition-colors ${
                        user.is_admin ? "text-amber-400 hover:bg-amber-400/10" : "text-gray-500 hover:bg-white/5"
                      }`}
                      title={user.is_admin ? "Remove admin" : "Make admin"}
                    >
                      {user.is_admin ? <ShieldOff className="w-4 h-4" /> : <Shield className="w-4 h-4" />}
                    </button>
                    <button
                      onClick={() => toggleActive(user.id, user.is_active)}
                      className={`p-2 rounded-lg transition-colors ${
                        user.is_active ? "text-red-400 hover:bg-red-400/10" : "text-accent-green hover:bg-accent-green/10"
                      }`}
                      title={user.is_active ? "Disable user" : "Enable user"}
                    >
                      {user.is_active ? <Ban className="w-4 h-4" /> : <CheckCircle2 className="w-4 h-4" />}
                    </button>
                    {!user.is_admin && (
                      <button
                        onClick={() => deleteUser(user.id, user.email)}
                        className="p-2 rounded-lg text-gray-600 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                        title="Delete user permanently"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
