"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { useAuth } from "@/lib/auth-context";
import { monitoringApi, subscriptionApi } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";
import Link from "next/link";
import { useLanguage } from "@/lib/i18n";
import {
  Activity, Bell, Clock, Globe, CheckCircle2,
  XCircle, AlertCircle, ArrowRight, Wifi, WifiOff,
  Sparkles, Calendar, Wrench,
} from "lucide-react";

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
};

export default function DashboardPage() {
  const { user } = useAuth();
  const { t } = useLanguage();
  const td = t.dash;
  const { connected, lastMessage } = useWebSocket();
  const [status, setStatus] = useState<any>(null);
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  // Handle real-time WebSocket messages
  useEffect(() => {
    if (!lastMessage) return;
    if (lastMessage.type === "check_result") {
      loadData(); // Refresh data
      if (lastMessage.slots_available) {
        setToast(`🎉 Slots available at ${lastMessage.branch}!`);
        setTimeout(() => setToast(null), 10000);
      }
    }
    if (lastMessage.type === "subscription_activated") {
      setToast(lastMessage.message);
      setTimeout(() => setToast(null), 8000);
      loadData();
    }
  }, [lastMessage]);

  const loadData = async () => {
    try {
      const [statusData, resultsData] = await Promise.all([
        monitoringApi.getStatus(),
        monitoringApi.getResults(undefined, 10),
      ]);
      setStatus(statusData);
      setResults(resultsData);
    } catch (err) {
      console.error("Failed to load data:", err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="spinner w-10 h-10" />
      </div>
    );
  }

  const hasActiveSubscription = status?.subscription_active;
  const monitoredBranches = status?.monitored_branches || [];
  const pendingPayment = status?.payment_pending;
  const maintenanceMode = status?.maintenance_mode;

  return (
    <div className="space-y-6">
      {/* Toast notification */}
      {toast && (
        <motion.div
          initial={{ x: 100, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 100, opacity: 0 }}
          className="fixed top-4 right-4 z-50 bg-accent-green text-black px-6 py-3 rounded-xl font-medium shadow-lg shadow-accent-green/30 toast-enter"
        >
          {toast}
        </motion.div>
      )}

      {/* Maintenance Mode Banner */}
      {maintenanceMode && (
        <motion.div initial={fadeUp.hidden} animate={fadeUp.visible} className="glass-card p-6 border-orange-500/30 bg-orange-500/5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-orange-500/10 flex items-center justify-center">
              <Wrench className="w-5 h-5 text-orange-400" />
            </div>
            <div>
              <div className="font-semibold text-orange-400">{td.maintenanceTitle}</div>
              <div className="text-sm text-gray-400">{td.maintenanceBody}</div>
            </div>
          </div>
        </motion.div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold">{td.title}</h1>
          <p className="text-gray-400 text-sm mt-1">
            {td.welcome}, {user?.full_name?.split(" ")[0] || ""}
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          {connected ? (
            <span className="flex items-center gap-1.5 text-accent-green">
              <Wifi className="w-4 h-4" /> {td.live}
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-gray-500">
              <WifiOff className="w-4 h-4" /> {td.autoRefresh}
            </span>
          )}
        </div>
      </div>

      {/* No subscription banner */}
      {!hasActiveSubscription && !pendingPayment && (
        <motion.div initial={fadeUp.hidden} animate={fadeUp.visible} className="glass-card p-6 border-amber-500/20">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center">
                <AlertCircle className="w-5 h-5 text-amber-400" />
              </div>
              <div>
                <div className="font-semibold">{td.noSubTitle}</div>
                <div className="text-sm text-gray-400">{td.noSubBody}</div>
              </div>
            </div>
            <Link href="/dashboard/payments" className="btn-gradient text-sm !py-2.5 flex items-center gap-2">
              {td.subscribeNow} <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </motion.div>
      )}

      {/* Pending payment banner */}
      {!hasActiveSubscription && pendingPayment && (
        <motion.div initial={fadeUp.hidden} animate={fadeUp.visible} className="glass-card p-6 border-blue-500/20">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
              <Clock className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <div className="font-semibold text-blue-400">{td.pendingTitle}</div>
              <div className="text-sm text-gray-400">{td.pendingBody}</div>
            </div>
          </div>
        </motion.div>
      )}

      {/* Status cards */}
      <motion.div
        initial="hidden"
        animate="visible"
        variants={{ visible: { transition: { staggerChildren: 0.1 } } }}
        className="grid grid-cols-2 lg:grid-cols-4 gap-4"
      >
        <motion.div variants={fadeUp} className="stat-card">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
            <Activity className="w-4 h-4" /> {td.statusLabel}
          </div>
          <div className="flex items-center gap-2">
            <div className={`status-dot ${hasActiveSubscription ? "active" : "inactive"}`} />
            <span className="font-semibold">{hasActiveSubscription ? td.active : td.inactive}</span>
          </div>
        </motion.div>

        <motion.div variants={fadeUp} className="stat-card">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
            <Globe className="w-4 h-4" /> {td.branchesLabel}
          </div>
          <div className="text-2xl font-bold">{monitoredBranches.length}</div>
        </motion.div>

        <motion.div variants={fadeUp} className="stat-card">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
            <Clock className="w-4 h-4" /> {td.expiresLabel}
          </div>
          <div className="text-sm font-medium">
            {status?.expires_at
              ? new Date(status.expires_at).toLocaleDateString()
              : "—"}
          </div>
        </motion.div>

        <motion.div variants={fadeUp} className="stat-card">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
            <Bell className="w-4 h-4" /> {td.planLabel}
          </div>
          <div className="text-sm font-medium">{(t.planNames as Record<string, string>)[user?.active_plan ?? ""] ?? user?.active_plan ?? "—"}</div>
        </motion.div>
      </motion.div>

      {/* Monitored branches */}
      {monitoredBranches.length > 0 && (
        <div className="glass-card overflow-hidden">
          <div className="p-4 border-b border-white/5 flex items-center justify-between">
            <h2 className="font-semibold">{td.monitoredBranches}</h2>
          </div>
          <div className="divide-y divide-white/5">
            {monitoredBranches.map((branch: any) => (
              <div key={branch.branch_id} className="p-4 flex items-center justify-between hover:bg-white/[0.02] transition-colors">
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full ${
                    branch.last_slots_available ? "bg-accent-green shadow-lg shadow-accent-green/50" : "bg-gray-500"
                  }`} />
                  <div>
                    <div className="font-medium text-sm">{(t.branchNames as Record<string, string>)[branch.branch_name] ?? branch.branch_name}</div>
                    <div className="text-xs text-gray-500">{(t.serviceTypes as Record<string, string>)[branch.service_type] ?? branch.service_type}</div>
                  </div>
                </div>
                <div className="text-right">
                  {branch.last_slots_available ? (
                    <span className="text-accent-green text-sm font-semibold flex items-center gap-1">
                      <Sparkles className="w-4 h-4" /> {td.slotsAvailable}
                    </span>
                  ) : branch.last_check ? (
                    <span className="text-gray-500 text-xs">
                      {new Date(branch.last_check).toLocaleTimeString()}
                    </span>
                  ) : (
                    <span className="text-gray-600 text-xs">{td.pendingFirstCheck}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent check results */}
      {results.length > 0 && (
        <div className="glass-card overflow-hidden">
          <div className="p-4 border-b border-white/5">
            <h2 className="font-semibold">{td.recentChecks}</h2>
          </div>
          <div className="divide-y divide-white/5">
            {results.map((r: any) => (
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
                    <div className="text-sm font-medium">{(t.branchNames as Record<string, string>)[r.branch_name] ?? r.branch_name}</div>
                    <div className="text-xs text-gray-500">
                      {new Date(r.checked_at).toLocaleString()} &middot; {r.duration_seconds}s
                    </div>
                  </div>
                </div>
                <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${
                  r.slots_available
                    ? "bg-accent-green/10 text-accent-green"
                    : r.error
                    ? "bg-amber-500/10 text-amber-400"
                    : "bg-gray-500/10 text-gray-400"
                }`}>
                  {r.slots_available ? td.available : r.error ? td.error : td.noSlots}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state — active subscription but no branch assigned yet */}
      {hasActiveSubscription && monitoredBranches.length === 0 && (
        <div className="glass-card p-12 text-center">
          <Globe className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <h3 className="font-semibold text-lg mb-2">{td.noBranchTitle}</h3>
          <p className="text-gray-400 text-sm mb-6">{td.noBranchBody}</p>
        </div>
      )}
    </div>
  );
}
