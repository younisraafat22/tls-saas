"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { monitoringApi } from "@/lib/api";
import { Monitor, CheckCircle2, XCircle, Clock, Sparkles } from "lucide-react";

export default function BranchStatusPage() {
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
        <h1 className="text-2xl font-display font-bold">Monitoring Status</h1>
        <p className="text-gray-400 text-sm mt-1">Real-time status of your assigned TLS branch</p>
      </div>

      {branches.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <Monitor className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <h3 className="font-semibold text-lg mb-2">No branch assigned yet</h3>
          <p className="text-gray-400 text-sm">
            {status?.payment_pending
              ? "Your payment is under review. Your branch will be assigned once approved."
              : "Subscribe and select your branch during payment to start monitoring."}
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
                  <h2 className="text-lg font-semibold">{branch.branch_name}</h2>
                  <p className="text-sm text-gray-400 capitalize">{branch.service_type} service</p>
                </div>
                {branch.last_slots_available ? (
                  <span className="flex items-center gap-1.5 text-accent-green text-sm font-semibold bg-accent-green/10 px-3 py-1.5 rounded-full">
                    <Sparkles className="w-4 h-4" /> Slots Available!
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5 text-gray-400 text-sm bg-white/5 px-3 py-1.5 rounded-full">
                    <XCircle className="w-4 h-4" /> No Slots
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                <div className="bg-dark-700 rounded-xl p-3">
                  <div className="text-xs text-gray-500 mb-1 flex items-center gap-1">
                    <Clock className="w-3 h-3" /> Last Check
                  </div>
                  <div className="text-sm font-medium">
                    {branch.last_check ? new Date(branch.last_check).toLocaleTimeString() : "Pending"}
                  </div>
                </div>
                <div className="bg-dark-700 rounded-xl p-3">
                  <div className="text-xs text-gray-500 mb-1 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Checks Today
                  </div>
                  <div className="text-sm font-medium">{branch.checks_today ?? 0}</div>
                </div>
                <div className="bg-dark-700 rounded-xl p-3">
                  <div className="text-xs text-gray-500 mb-1 flex items-center gap-1">
                    <Monitor className="w-3 h-3" /> Status
                  </div>
                  <div className={`text-sm font-medium ${branch.is_active ? "text-accent-green" : "text-gray-400"}`}>
                    {branch.is_active ? "Active" : "Inactive"}
                  </div>
                </div>
              </div>

              {branch.last_slot_details && (
                <div className="mt-4 bg-accent-green/5 border border-accent-green/20 rounded-xl p-4">
                  <div className="text-sm font-semibold text-accent-green mb-2 flex items-center gap-2">
                    <Sparkles className="w-4 h-4" /> Available Appointment Slots
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

      <p className="text-xs text-gray-600 text-center">Auto-refreshes every 30 seconds</p>
    </div>
  );
}
