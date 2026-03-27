"use client";

import { useEffect, useState } from "react";
import { adminApi } from "@/lib/api";
import { AlertTriangle, Clock, ImageOff, Mail, RefreshCw } from "lucide-react";

type ErrorRow = {
  id: number;
  checked_at: string | null;
  branch_name: string;
  service_type: string;
  user_id: number | null;
  user_email: string;
  source: string;
  duration_seconds: number;
  error: string;
  screenshot_b64: string;
  has_screenshot: boolean;
};

export default function AdminErrorsPage() {
  const [rows, setRows] = useState<ErrorRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const data = await adminApi.getCheckErrors(120);
      setRows(Array.isArray(data) ? data : []);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="spinner w-10 h-10" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold">Error Screenshots</h1>
          <p className="text-sm text-gray-400 mt-1">
            Recent checker failures with screenshot evidence, user, branch, and error details.
          </p>
        </div>
        <button
          onClick={() => load(true)}
          disabled={refreshing}
          className="px-4 py-2 rounded-xl text-sm font-medium flex items-center gap-2 bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 border border-primary-500/20 disabled:opacity-60"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {rows.length === 0 ? (
        <div className="glass-card p-8 text-center text-gray-400">No error records found.</div>
      ) : (
        <div className="grid gap-4">
          {rows.map((r) => (
            <div key={r.id} className="glass-card p-4 sm:p-5 border border-red-500/20 bg-red-500/5">
              <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs sm:text-sm text-gray-300">
                <span className="inline-flex items-center gap-1.5"><AlertTriangle className="w-4 h-4 text-red-400" /> #{r.id}</span>
                <span className="inline-flex items-center gap-1.5"><Clock className="w-4 h-4 text-gray-400" /> {r.checked_at ? new Date(r.checked_at).toLocaleString("en-GB", { hour12: false }) : "—"}</span>
                <span className="inline-flex items-center gap-1.5"><Mail className="w-4 h-4 text-gray-400" /> {r.user_email || "Unknown user"}</span>
                <span>{r.branch_name} ({r.service_type})</span>
                <span>Source: {r.source || "worker"}</span>
                <span>{Math.round(Number(r.duration_seconds || 0))}s</span>
              </div>

              <div className="mt-2 text-red-200 text-sm break-words">{r.error || "Unknown error"}</div>

              <div className="mt-3">
                {r.has_screenshot && r.screenshot_b64 ? (
                  <a
                    href={`data:image/png;base64,${r.screenshot_b64}`}
                    target="_blank"
                    rel="noreferrer"
                    className="block"
                    title="Open full screenshot"
                  >
                    <img
                      src={`data:image/png;base64,${r.screenshot_b64}`}
                      alt={`Error screenshot ${r.id}`}
                      className="w-full max-w-2xl rounded-xl border border-white/10"
                    />
                  </a>
                ) : (
                  <div className="inline-flex items-center gap-2 text-gray-500 text-sm">
                    <ImageOff className="w-4 h-4" /> No screenshot captured for this error.
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

