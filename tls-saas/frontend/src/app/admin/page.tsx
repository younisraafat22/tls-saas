"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { adminApi } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";
import {
  Users, CreditCard, Activity, TrendingUp,
  CheckCircle2, Clock, AlertCircle, Wifi, WifiOff,
  ArrowUpRight, DollarSign, KeyRound, RefreshCw,
  Loader2, Eye, Download, Star, Trophy, Bell,
} from "lucide-react";
import Link from "next/link";

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
};

export default function AdminDashboard() {
  const [stats, setStats] = useState<any>(null);
  const [notifCounts, setNotifCounts] = useState<{ unread_total: number }>({ unread_total: 0 });
  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState<number | null>(null);
  const { connected, lastMessage } = useWebSocket(true);

  useEffect(() => {
    loadStats();
    loadNotifCounts();
  }, []);

  useEffect(() => {
    if (lastMessage) {
      loadStats();
      loadNotifCounts();
    }
  }, [lastMessage]);

  const loadStats = async () => {
    try {
      const data = await adminApi.getDashboard();
      setStats(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadNotifCounts = async () => {
    try {
      const data = await adminApi.getNotificationCounts();
      setNotifCounts({ unread_total: Number(data?.unread_total || 0) });
    } catch {
      setNotifCounts({ unread_total: 0 });
    }
  };

  const handleQuickApprove = async (paymentId: number, hasHardwareId: boolean) => {
    setApproving(paymentId);
    try {
      if (hasHardwareId) {
        await adminApi.generateLicense(paymentId);
      } else {
        await adminApi.approvePayment(paymentId);
      }
      loadStats();
    } catch (err) {
      console.error(err);
    } finally {
      setApproving(null);
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
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold">Admin Dashboard</h1>
          <p className="text-gray-400 text-sm mt-1">System overview and quick actions</p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/admin/notifications"
            className="relative p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
            title="Notifications"
          >
            <Bell className="w-4 h-4" />
            {notifCounts.unread_total > 0 && (
              <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-bold inline-flex items-center justify-center">
                {notifCounts.unread_total > 99 ? "99+" : notifCounts.unread_total}
              </span>
            )}
          </Link>
          <button
            onClick={loadStats}
            className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          {connected ? (
            <span className="flex items-center gap-1.5 text-sm text-accent-green">
              <Wifi className="w-4 h-4" /> Connected
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-sm text-gray-500">
              <WifiOff className="w-4 h-4" /> Disconnected
            </span>
          )}
        </div>
      </div>

      {/* Stat cards */}
      <motion.div
        initial="hidden"
        animate="visible"
        variants={{ visible: { transition: { staggerChildren: 0.08 } } }}
        className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4"
      >
        <StatCard
          icon={<Users className="w-5 h-5" />}
          iconColor="text-primary-400"
          label="Total Users"
          value={stats?.total_users || 0}
        />
        <StatCard
          icon={<CheckCircle2 className="w-5 h-5" />}
          iconColor="text-accent-green"
          label="Active Subs"
          value={stats?.active_subscriptions || 0}
        />
        <StatCard
          icon={<Clock className="w-5 h-5" />}
          iconColor="text-amber-400"
          label="Pending Payments"
          value={stats?.pending_payments || 0}
          href="/admin/payments"
        />
        <StatCard
          icon={<DollarSign className="w-5 h-5" />}
          iconColor="text-green-400"
          label="Revenue (EGP)"
          value={stats?.total_revenue || 0}
        />
        <StatCard
          icon={<KeyRound className="w-5 h-5" />}
          iconColor="text-blue-400"
          label="Total Licenses"
          value={stats?.total_licenses ?? "—"}
          href="/admin/licenses"
        />
        <StatCard
          icon={<CheckCircle2 className="w-5 h-5" />}
          iconColor="text-accent-green"
          label="Active Licenses"
          value={stats?.active_licenses ?? "—"}
          href="/admin/licenses"
        />
        <StatCard
          icon={<Clock className="w-5 h-5" />}
          iconColor="text-amber-400"
          label="Pending Licenses"
          value={stats?.pending_licenses ?? "—"}
          href="/admin/licenses"
        />
        <StatCard
          icon={<Download className="w-5 h-5" />}
          iconColor="text-purple-400"
          label="App Downloads"
          value={stats?.total_downloads ?? 0}
        />
        <StatCard
          icon={<Star className="w-5 h-5" />}
          iconColor="text-yellow-400"
          label="Avg Rating"
          value={stats?.average_rating ? stats.average_rating.toFixed(1) : "0.0"}
        />
        <StatCard
          icon={<Trophy className="w-5 h-5" />}
          iconColor="text-teal-400"
          label="Appt. Found"
          value={stats?.total_appointments_found ?? 0}
        />
      </motion.div>

      {/* Quick actions & recent activity */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Pending payments */}
        <div className="glass-card overflow-hidden">
          <div className="p-4 border-b border-white/5 flex items-center justify-between">
            <h2 className="font-semibold">Pending Payments</h2>
            <Link href="/admin/payments" className="text-primary-400 text-sm hover:text-primary-300 flex items-center gap-1">
              View All <ArrowUpRight className="w-3 h-3" />
            </Link>
          </div>
          {stats?.recent_pending_payments?.length > 0 ? (
            <div className="divide-y divide-white/5">
              {stats.recent_pending_payments.slice(0, 5).map((p: any) => (
                <div key={p.id} className="p-4 flex items-center justify-between gap-3 hover:bg-white/[0.02] transition-colors">
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium truncate">{p.user_email}</div>
                    <div className="text-xs text-gray-500">
                      {p.method?.replace("_", " ")} &middot; Ref: {p.reference}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-sm font-semibold text-amber-400">{p.amount} EGP</span>
                    <button
                      onClick={() => handleQuickApprove(p.id, !!p.hardware_id)}
                      disabled={approving === p.id}
                      className="flex items-center gap-1 px-2 py-1 text-xs bg-accent-green/10 text-accent-green rounded-lg hover:bg-accent-green/20 transition-colors disabled:opacity-50"
                    >
                      {approving === p.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
                      Approve or Renew
                    </button>
                    <Link
                      href="/admin/payments"
                      className="p-1.5 text-gray-400 hover:text-primary-400 hover:bg-primary-500/10 rounded-lg transition-colors"
                      title="View in payments"
                    >
                      <Eye className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-8 text-center text-gray-500 text-sm">No pending payments</div>
          )}
        </div>

        {/* System status */}
        <div className="glass-card overflow-hidden">
          <div className="p-4 border-b border-white/5 flex items-center justify-between">
            <h2 className="font-semibold">System Status</h2>
            <Link href="/admin/monitoring" className="text-primary-400 text-sm hover:text-primary-300 flex items-center gap-1">
              Manage <ArrowUpRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="p-4 space-y-3">
            <StatusRow label="Scheduler" active={stats?.scheduler_running} />
            <StatusRow label="Service Accounts" value={`${stats?.service_accounts || 0}`} active={(stats?.service_accounts || 0) > 0} />
            <StatusRow label="Checks Today" value={`${stats?.checks_today || 0}`} active={true} />
            <StatusRow label="Slots Found Today" value={`${stats?.slots_found_today || 0}`} active={(stats?.slots_found_today || 0) > 0} />
          </div>
        </div>
      </div>

      {/* Recent activity */}
      {stats?.recent_activity?.length > 0 && (
        <div className="glass-card overflow-hidden">
          <div className="p-4 border-b border-white/5">
            <h2 className="font-semibold">Recent Activity</h2>
          </div>
          <div className="divide-y divide-white/5">
            {stats.recent_activity.slice(0, 8).map((a: any, i: number) => (
              <div key={i} className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Activity className="w-4 h-4 text-gray-500" />
                  <div>
                    <div className="text-sm">{a.action}</div>
                    <div className="text-xs text-gray-500">
                      {a.user_email} &middot; {new Date(a.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ icon, iconColor, label, value, href }: {
  icon: React.ReactNode;
  iconColor: string;
  label: string;
  value: number | string;
  href?: string;
}) {
  const content = (
    <motion.div variants={fadeUp} className="stat-card group">
      <div className={`flex items-center gap-2 text-sm mb-2 ${iconColor}`}>
        {icon} <span className="text-gray-400">{label}</span>
      </div>
      <div className="text-2xl font-bold">{value}</div>
      {href && (
        <ArrowUpRight className="w-4 h-4 text-gray-600 absolute top-3 right-3 group-hover:text-primary-400 transition-colors" />
      )}
    </motion.div>
  );

  return href ? <Link href={href}>{content}</Link> : content;
}

function StatusRow({ label, active, value }: { label: string; active: boolean; value?: string }) {
  return (
    <div className="flex items-center justify-between py-1">
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${active ? "bg-accent-green" : "bg-red-400"}`} />
        <span className="text-sm text-gray-300">{label}</span>
      </div>
      <span className="text-sm text-gray-400">{value ?? (active ? "Running" : "Stopped")}</span>
    </div>
  );
}
