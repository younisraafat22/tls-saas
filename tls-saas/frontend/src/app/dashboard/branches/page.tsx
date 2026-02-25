"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { monitoringApi } from "@/lib/api";
import { Monitor, CheckCircle2, XCircle, Clock, Sparkles } from "lucide-react";
import { useLanguage } from "@/lib/i18n";

export default function BranchStatusPage() {
  const { t } = useLanguage();
  const getBranchName = (name: string) => t.branchNames[name] ?? name;
  const tb = t.branches;
  const serviceLabel: Record<string, string> = {
    legalization: t.serviceTypes.legalization,
    visa: t.serviceTypes.visa,
    students: t.serviceTypes.students,
  };
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    monitoringApi.getStatus().then(setStatus).catch(console.error).finally(() => setLoading(false));
    const interval = setInterval(() => {
      monitoringApi.getStatus().then(setStatus).catch(console.error);
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="spinner w-10 h-10" />
      </div>
    );
  }

  const branches = status?.monitored_branches || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-display font-bold">{tb.title}</h1>
        <p className="text-gray-400 text-sm mt-1">{tb.sub}</p>
      </div>

      {branches.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <Monitor className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <h3 className="font-semibold text-lg mb-2">{tb.noBranchTitle}</h3>
          <p className="text-gray-400 text-sm">
            {status?.payment_pending
              ? tb.noBranchPending
              : tb.noBranchSub}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {branches.map((branch: any) => (
            <motion.div
              key={branch.branch_id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-card p-6"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="text-lg font-semibold">{getBranchName(branch.branch_name)}</h2>
                  <p className="text-sm text-gray-400">{serviceLabel[branch.service_type] ?? branch.service_type} {tb.service}</p>
                </div>
                {branch.last_slots_available ? (
                  <span className="flex items-center gap-1.5 text-accent-green text-sm font-semibold bg-accent-green/10 px-3 py-1.5 rounded-full">
                    <Sparkles className="w-4 h-4" /> {tb.slotsAvailable}
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5 text-gray-400 text-sm bg-white/5 px-3 py-1.5 rounded-full">
                    <XCircle className="w-4 h-4" /> {tb.noSlots}
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                <div className="bg-dark-700 rounded-xl p-3">
                  <div className="text-xs text-gray-500 mb-1 flex items-center gap-1">
                    <Clock className="w-3 h-3" /> {tb.lastCheck}
                  </div>
                  <div className="text-sm font-medium">
                    {branch.last_check ? new Date(branch.last_check).toLocaleTimeString() : tb.pending}
                  </div>
                </div>
                <div className="bg-dark-700 rounded-xl p-3">
                  <div className="text-xs text-gray-500 mb-1 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> {tb.checksToday}
                  </div>
                  <div className="text-sm font-medium">{branch.checks_today ?? 0}</div>
                </div>
                <div className="bg-dark-700 rounded-xl p-3">
                  <div className="text-xs text-gray-500 mb-1 flex items-center gap-1">
                    <Monitor className="w-3 h-3" /> {tb.statusLabel}
                  </div>
                  <div className={`text-sm font-medium ${branch.is_active ? "text-accent-green" : "text-gray-400"}`}>
                    {branch.is_active ? tb.active : tb.inactive}
                  </div>
                </div>
              </div>

              {branch.last_slot_details && (
                <div className="mt-4 bg-accent-green/5 border border-accent-green/20 rounded-xl p-4">
                  <div className="text-sm font-semibold text-accent-green mb-2 flex items-center gap-2">
                    <Sparkles className="w-4 h-4" /> {tb.availableSlots}
                  </div>
                  <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono">
                    {JSON.stringify(branch.last_slot_details, null, 2)}
                  </pre>
                </div>
              )}
            </motion.div>
          ))}
        </div>
      )}

      <p className="text-xs text-gray-600 text-center">{tb.autoRefresh}</p>
    </div>
  );
}
