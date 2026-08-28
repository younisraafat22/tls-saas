"use client";

import { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { useAuth } from "@/lib/auth-context";
import { monitoringApi, paymentApi } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";
import Link from "next/link";
import { useLanguage } from "@/lib/i18n";
import {
  Activity, Bell, Clock, Globe, CheckCircle2,
  XCircle, AlertCircle, ArrowRight, Wifi, WifiOff,
  Sparkles, Calendar, Wrench, Key, Copy, Check,
  ShieldCheck, Monitor, Download, ChevronLeft, ChevronRight,
  Hash, Image as ImageIcon, X as XIcon, Timer,
} from "lucide-react";

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
};

function useCountdown(targetIso: string | null | undefined) {
  const [display, setDisplay] = useState("—");
  useEffect(() => {
    if (!targetIso) { setDisplay("—"); return; }
    const update = () => {
      const diff = new Date(targetIso.includes("Z") || targetIso.includes("+") ? targetIso : targetIso + "Z").getTime() - Date.now();
      if (diff <= 0) { setDisplay("Soon"); return; }
      const h = Math.floor(diff / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      setDisplay(h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m ${s}s` : `${s}s`);
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [targetIso]);
  return display;
}

export default function DashboardPage() {
  const { user } = useAuth();
  const { t, locale } = useLanguage();
  const td = t.dash;
  const dateLocale = locale === "ar" ? "ar-EG" : locale === "de" ? "de-DE" : "en-GB";
  const { connected, lastMessage } = useWebSocket();
  const [status, setStatus] = useState<any>(null);
  const [resultsData, setResultsData] = useState<{ total: number; results: any[] }>({ total: 0, results: [] });
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<string | null>(null);
  const [licenseKey, setLicenseKey] = useState<string | null>(null);
  const [licensePlan, setLicensePlan] = useState<string | null>(null);
  const [desktopLicenses, setDesktopLicenses] = useState<{ license_key: string; plan_key?: string }[]>([]);
  const [copied, setCopied] = useState<string | null>(null);
  const [resultsPage, setResultsPage] = useState(0);
  const [apiBase, setApiBase] = useState("");
  const [downloadUrl, setDownloadUrl] = useState<string>("");
  const [screenshotModal, setScreenshotModal] = useState<string | null>(null);
  const PAGE_SIZE = 10;

  const countdown = useCountdown(status?.worker_next_run);

  const resolveApiUrl = async () => {
    let apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
    if (!apiUrl) {
      const backendRes = await fetch("/api/backend-url");
      if (backendRes.ok) {
        const backendData = await backendRes.json();
        apiUrl = backendData?.url || "";
      }
    }
    return apiUrl;
  };

  useEffect(() => {
    loadAll();
    const interval = setInterval(loadAll, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    loadResults();
  }, [resultsPage]);

  useEffect(() => {
    if (!lastMessage) return;
    if (lastMessage.type === "check_result") {
      loadAll();
      if (lastMessage.slots_available) {
        setToast(`🎉 Slots available at ${lastMessage.branch}!`);
        setTimeout(() => setToast(null), 10000);
      }
    }
    if (lastMessage.type === "subscription_activated") {
      setToast(lastMessage.message);
      setTimeout(() => setToast(null), 8000);
      loadAll();
    }
  }, [lastMessage]);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const apiUrl = await resolveApiUrl();
        if (!apiUrl) return;
        setApiBase(apiUrl);

        const response = await fetch(`${apiUrl}/api/app/download-info`);
        if (!response.ok) return;

        const data = await response.json();
        if (!cancelled && data?.download_url) {
          setDownloadUrl(data.download_url);
        }
      } catch {
        // Leave the dashboard fallback link in place.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const copyLicenseKey = async (key: string) => {
    if (!key) return;
    await navigator.clipboard.writeText(key);
    setCopied(key);
    setTimeout(() => setCopied(null), 2000);
  };

  const loadResults = async () => {
    try {
      const data = await monitoringApi.getResults(undefined, PAGE_SIZE, resultsPage * PAGE_SIZE);
      setResultsData(data);
    } catch (err) {
      console.error("Failed to load results:", err);
    }
  };

  const loadAll = async () => {
    try {
      const [statusData, paymentsData] = await Promise.all([
        monitoringApi.getStatus(),
        paymentApi.getMyPayments().catch(() => null),
      ]);
      setStatus(statusData);
      const ov = statusData?.overview;
      const fromOverview = ov?.desktop?.licenses;
      if (Array.isArray(fromOverview) && fromOverview.length > 0) {
        setDesktopLicenses(fromOverview);
        setLicenseKey(fromOverview[0].license_key);
        setLicensePlan(fromOverview[0].plan_key ?? null);
      } else if (paymentsData !== null) {
        const approvedPayment = Array.isArray(paymentsData)
          ? paymentsData.find((p: any) => p.license_key && p.status === "approved")
          : null;
        if (approvedPayment?.license_key) {
          setDesktopLicenses([{ license_key: approvedPayment.license_key, plan_key: approvedPayment.plan_key }]);
          setLicenseKey(approvedPayment.license_key);
          setLicensePlan(approvedPayment.plan_key ?? null);
        } else {
          setDesktopLicenses([]);
        }
      } else {
        setDesktopLicenses([]);
      }
    } catch (err) {
      console.error("Failed to load data:", err);
    } finally {
      setLoading(false);
    }
    loadResults();
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
  const planTypes: string[] = status?.plan_types || [];
  const isPremium = planTypes.some((p: string) => p.toUpperCase() === "PREMIUM");
  const totalChecks: number = status?.total_checks ?? 0;
  const totalPages = Math.ceil(resultsData.total / PAGE_SIZE);

  const ov = status?.overview;
  const serverOn = ov?.server?.active;
  const deskOn = ov?.desktop?.active;
  const splitOverview = !!(serverOn && deskOn);

  const primaryBranches = splitOverview
    ? monitoredBranches
    : serverOn
    ? (ov?.server?.monitored_branches ?? monitoredBranches)
    : deskOn
    ? (ov?.desktop?.monitored_branches ?? monitoredBranches)
    : monitoredBranches;

  const primaryTotalChecks = splitOverview
    ? totalChecks
    : serverOn
    ? (ov?.server?.total_checks ?? totalChecks)
    : deskOn
    ? (ov?.desktop?.total_checks ?? totalChecks)
    : totalChecks;

  const primaryExpires =
    splitOverview
      ? status?.expires_at
      : serverOn
      ? ov?.server?.expires_at
      : deskOn
      ? ov?.desktop?.expires_at
      : status?.expires_at;

  const serverBranches = ov?.server?.monitored_branches ?? [];
  const desktopBranches = ov?.desktop?.monitored_branches ?? [];

  const renderBranchRows = (branches: any[]) =>
    branches.map((branch: any) => {
      const lastCheckDate = branch.last_check
        ? new Date(branch.last_check.includes("Z") || branch.last_check.includes("+") ? branch.last_check : branch.last_check + "Z")
        : null;
      const ageMs = lastCheckDate ? Date.now() - lastCheckDate.getTime() : Infinity;
      const isStale = ageMs > 60 * 60 * 1000;
      const checkTimeStr = lastCheckDate ? lastCheckDate.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : null;
      return (
        <div key={branch.branch_id} className="p-4 hover:bg-white/[0.02] transition-colors">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className={`w-2 h-2 rounded-full ${
                  branch.last_slots_available && !isStale
                    ? "bg-accent-green shadow-lg shadow-accent-green/50"
                    : branch.last_slots_available
                    ? "bg-yellow-400"
                    : "bg-gray-500"
                }`}
              />
              <div>
                <div className="font-medium text-sm">{(t.branchNames as Record<string, string>)[branch.branch_name] ?? branch.branch_name}</div>
                <div className="text-xs text-gray-500">{(t.serviceTypes as Record<string, string>)[branch.service_type] ?? branch.service_type}</div>
              </div>
            </div>
            <div className="text-right">
              {branch.last_slots_available && !isStale ? (
                <span className="text-accent-green text-sm font-semibold flex items-center gap-1">
                  <Sparkles className="w-4 h-4" /> {td.slotsAvailable}
                </span>
              ) : branch.last_slots_available && isStale ? (
                <span className="text-yellow-400 text-xs font-medium flex items-center gap-1">
                  <Sparkles className="w-3 h-3" /> {td.slotsFoundAs} {checkTimeStr})
                </span>
              ) : checkTimeStr ? (
                <span className="text-gray-500 text-xs">
                  {td.lastCheckAt} {checkTimeStr}
                </span>
              ) : (
                <span className="text-gray-600 text-xs">{td.pendingFirstCheck}</span>
              )}
            </div>
          </div>
        </div>
      );
    });

  return (
    <div className="space-y-6">
      {/* Screenshot modal */}
      {screenshotModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
          onClick={() => setScreenshotModal(null)}
        >
          <div className="relative max-w-4xl w-full" onClick={e => e.stopPropagation()}>
            <button
              onClick={() => setScreenshotModal(null)}
              className="absolute -top-10 right-0 text-gray-400 hover:text-white"
            >
              <XIcon className="w-6 h-6" />
            </button>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`data:image/png;base64,${screenshotModal}`} alt="Slot screenshot" className="rounded-xl w-full" />
          </div>
        </div>
      )}

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
            <span className="flex items-center gap-1.5 text-gray-500" title="Page refreshes automatically every 30 seconds">
              <WifiOff className="w-4 h-4" /> Auto-refresh (30s)
            </span>
          )}
        </div>
      </div>

      {/* No subscription banner */}
      {!hasActiveSubscription && !pendingPayment && !licenseKey && (
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

      {/* License Key + Download Card (hidden when split overview — keys appear under Desktop section) */}
      {licenseKey && !splitOverview && (
        <motion.div initial={fadeUp.hidden} animate={fadeUp.visible} className="glass-card p-6 border-accent-green/30 bg-accent-green/5">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-accent-green/10 flex items-center justify-center">
              <ShieldCheck className="w-5 h-5 text-accent-green" />
            </div>
            <div>
              <div className="font-semibold text-accent-green">{td.licenseKeyTitle}</div>
              <div className="text-xs text-gray-400">
                {licensePlan ? licensePlan.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : "Desktop Plan"} • {td.licenseKeySubtitle}
              </div>
            </div>
          </div>
          {(desktopLicenses.length > 0 ? desktopLicenses : licenseKey ? [{ license_key: licenseKey, plan_key: licensePlan ?? undefined }] : []).map((lic) => (
            <div key={lic.license_key} className="flex items-center gap-3 bg-black/30 rounded-xl px-4 py-3 border border-white/10 mb-3 last:mb-4">
              <Key className="w-4 h-4 text-accent-green shrink-0" />
              <code className="flex-1 text-sm font-mono text-accent-green tracking-wider break-all">{lic.license_key}</code>
              <button
                type="button"
                onClick={() => copyLicenseKey(lic.license_key)}
                className="ml-2 p-1.5 rounded-lg hover:bg-white/10 transition-colors shrink-0"
                title="Copy license key"
              >
                {copied === lic.license_key ? (
                  <Check className="w-4 h-4 text-accent-green" />
                ) : (
                  <Copy className="w-4 h-4 text-gray-400" />
                )}
              </button>
            </div>
          ))}
          {downloadUrl ? (
            <a
              href={apiBase ? `${apiBase}/api/app/download` : downloadUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-accent-green/10 border border-accent-green/30 text-accent-green text-sm font-medium hover:bg-accent-green/20 transition-colors"
            >
              <Download className="w-4 h-4" /> {td.downloadDesktop}
            </a>
          ) : (
            <Link
              href="/#download"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-accent-green/10 border border-accent-green/30 text-accent-green text-sm font-medium hover:bg-accent-green/20 transition-colors"
            >
              <Download className="w-4 h-4" /> {td.downloadDesktop}
            </Link>
          )}
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

      {/* Split overview: Premium server + Desktop app */}
      {splitOverview && (
        <div className="space-y-6">
          <motion.div initial={fadeUp.hidden} animate={fadeUp.visible} className="glass-card overflow-hidden border-primary-500/20">
            <div className="p-4 border-b border-white/5 bg-primary-500/5">
              <h2 className="font-display font-semibold text-lg">{(td as any).overviewServerTitle}</h2>
              <p className="text-xs text-gray-500 mt-0.5">{(td as any).overviewServerSubtitle}</p>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 p-4 border-b border-white/5">
              <div className="stat-card">
                <div className="flex items-center gap-2 text-gray-400 text-xs mb-1">{td.branchesLabel}</div>
                <div className="text-xl font-bold">{serverBranches.length.toLocaleString(locale === "ar" ? "ar-EG" : locale === "de" ? "de-DE" : "en-US")}</div>
              </div>
              <div className="stat-card">
                <div className="flex items-center gap-2 text-gray-400 text-xs mb-1">{td.totalChecksLabel}</div>
                <div className="text-xl font-bold">{(ov?.server?.total_checks ?? 0).toLocaleString(locale === "ar" ? "ar-EG" : locale === "de" ? "de-DE" : "en-US")}</div>
              </div>
              <div className="stat-card">
                <div className="flex items-center gap-2 text-gray-400 text-xs mb-1">{td.expiresLabel}</div>
                <div className="text-sm font-medium">
                  {ov?.server?.expires_at
                    ? new Date(ov.server.expires_at.includes("Z") || ov.server.expires_at.includes("+") ? ov.server.expires_at : ov.server.expires_at + "Z").toLocaleDateString(dateLocale, { day: "numeric", month: "short", year: "numeric" })
                    : "—"}
                </div>
              </div>
              <div className="stat-card">
                <div className="flex items-center gap-2 text-gray-400 text-xs mb-1">{td.nextCheckLabel}</div>
                <div className="text-lg font-bold tabular-nums text-accent-green">{countdown}</div>
              </div>
            </div>
            {serverBranches.length > 0 ? (
              <div className="divide-y divide-white/5">{renderBranchRows(serverBranches)}</div>
            ) : (
              <div className="p-6 text-sm text-gray-500 text-center">{td.noBranchTitle}</div>
            )}
            {hasActiveSubscription && serverOn && (
              <div className="px-4 py-3 border-t border-white/5 bg-accent-green/5">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-accent-green animate-pulse" />
                  <span className="text-xs text-accent-green font-medium">{(td as any).monitoringActiveSubtitle || "Monitoring active"}</span>
                </div>
              </div>
            )}
          </motion.div>

          <motion.div initial={fadeUp.hidden} animate={fadeUp.visible} className="glass-card overflow-hidden border-accent-green/25">
            <div className="p-4 border-b border-white/5 bg-accent-green/5">
              <h2 className="font-display font-semibold text-lg text-accent-green">{(td as any).overviewDesktopTitle}</h2>
              <p className="text-xs text-gray-500 mt-0.5">{(td as any).overviewDesktopSubtitle}</p>
            </div>
            {desktopLicenses.length > 0 && (
              <div className="p-4 border-b border-white/5 space-y-3">
                <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide">{td.licenseKeyTitle}</div>
                {desktopLicenses.map((lic) => (
                  <div key={lic.license_key} className="flex items-center gap-2 bg-black/30 rounded-xl px-3 py-2 border border-white/10">
                    <code className="flex-1 text-xs font-mono text-accent-green break-all">{lic.license_key}</code>
                    <button type="button" onClick={() => copyLicenseKey(lic.license_key)} className="p-1.5 rounded-lg hover:bg-white/10 shrink-0">
                      {copied === lic.license_key ? <Check className="w-4 h-4 text-accent-green" /> : <Copy className="w-4 h-4 text-gray-400" />}
                    </button>
                  </div>
                ))}
                {downloadUrl && (
                  <a
                    href={apiBase ? `${apiBase}/api/app/download` : downloadUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-accent-green/10 border border-accent-green/30 text-accent-green text-xs font-medium"
                  >
                    <Download className="w-4 h-4" /> {td.downloadDesktop}
                  </a>
                )}
              </div>
            )}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 p-4 border-b border-white/5">
              <div className="stat-card">
                <div className="text-gray-400 text-xs mb-1">{td.branchesLabel}</div>
                <div className="text-xl font-bold">{desktopBranches.length.toLocaleString(locale === "ar" ? "ar-EG" : locale === "de" ? "de-DE" : "en-US")}</div>
              </div>
              <div className="stat-card">
                <div className="text-gray-400 text-xs mb-1">{td.totalChecksLabel}</div>
                <div className="text-xl font-bold">{(ov?.desktop?.total_checks ?? 0).toLocaleString(locale === "ar" ? "ar-EG" : locale === "de" ? "de-DE" : "en-US")}</div>
              </div>
              <div className="stat-card">
                <div className="text-gray-400 text-xs mb-1">{td.expiresLabel}</div>
                <div className="text-sm font-medium">
                  {ov?.desktop?.expires_at
                    ? new Date(ov.desktop.expires_at.includes("Z") || ov.desktop.expires_at.includes("+") ? ov.desktop.expires_at : ov.desktop.expires_at + "Z").toLocaleDateString(dateLocale, { day: "numeric", month: "short", year: "numeric" })
                    : "—"}
                </div>
              </div>
            </div>
            {desktopBranches.length > 0 ? (
              <div className="divide-y divide-white/5">{renderBranchRows(desktopBranches)}</div>
            ) : (
              <div className="p-6 text-sm text-gray-500 text-center">{td.desktopMonitorBody}</div>
            )}
          </motion.div>
        </div>
      )}

      {/* Status cards (single entitlement) */}
      {!splitOverview && (
        <>
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
          <div className="text-2xl font-bold">{primaryBranches.length.toLocaleString(locale === "ar" ? "ar-EG" : locale === "de" ? "de-DE" : "en-US")}</div>
        </motion.div>

        <motion.div variants={fadeUp} className="stat-card">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
            <Hash className="w-4 h-4" /> {td.totalChecksLabel}
          </div>
          <div className="text-2xl font-bold">{primaryTotalChecks.toLocaleString(locale === "ar" ? "ar-EG" : locale === "de" ? "de-DE" : "en-US")}</div>
        </motion.div>

        {hasActiveSubscription && isPremium && (
          <motion.div variants={fadeUp} className="stat-card">
            <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
              <Timer className="w-4 h-4" /> {td.nextCheckLabel}
            </div>
            <div className="text-lg font-bold tabular-nums text-accent-green">{countdown}</div>
          </motion.div>
        )}

        <motion.div variants={fadeUp} className="stat-card">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
            <Calendar className="w-4 h-4" /> {td.expiresLabel}
          </div>
          <div className="text-sm font-medium">
            {primaryExpires
              ? new Date(primaryExpires.includes('Z') || primaryExpires.includes('+') ? primaryExpires : primaryExpires + 'Z').toLocaleDateString(dateLocale, { day: 'numeric', month: 'short', year: 'numeric' })
              : "—"}
          </div>
        </motion.div>
      </motion.div>

      {/* Monitored branches */}
      {primaryBranches.length > 0 && (
        <div className="glass-card overflow-hidden">
          <div className="p-4 border-b border-white/5 flex items-center justify-between">
            <h2 className="font-semibold">{td.monitoredBranches}</h2>
          </div>
          <div className="divide-y divide-white/5">
            {renderBranchRows(primaryBranches)}
          </div>
          {hasActiveSubscription && (
            <div className="px-4 py-3 border-t border-white/5 bg-accent-green/5">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-accent-green animate-pulse" />
                <span className="text-xs text-accent-green font-medium">{(td as any).monitoringActiveSubtitle || "Monitoring active — you will be notified as soon as a slot opens"}</span>
              </div>
              <p className="text-[11px] text-gray-500 mt-1.5 ml-4">TIP / {(td as any).spamTip || "Appointment notification emails may land in your Spam / Junk folder — please check there and mark them as \"Not Spam\"."}</p>
            </div>
          )}
        </div>
      )}
        </>
      )}

      {/* Recent check results */}
      {resultsData.results.length > 0 && (
        <div className="glass-card overflow-hidden">
          <div className="p-4 border-b border-white/5 flex items-center justify-between">
            <h2 className="font-semibold">{td.recentChecks}</h2>
            <span className="text-xs text-gray-500">{resultsData.total} total</span>
          </div>
          <div className="divide-y divide-white/5">
            {resultsData.results.map((r: any) => (
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
                      {new Date(r.checked_at.includes('Z') || r.checked_at.includes('+') ? r.checked_at : r.checked_at + 'Z').toLocaleString()} &middot; {r.duration_seconds}s
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {r.slots_available && r.screenshot_b64 && (
                    <button
                      onClick={() => setScreenshotModal(r.screenshot_b64)}
                      className="p-1.5 rounded-lg hover:bg-white/10 transition-colors text-accent-green"
                      title="View screenshot"
                    >
                      <ImageIcon className="w-4 h-4" />
                    </button>
                  )}
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
              </div>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="p-4 border-t border-white/5 flex items-center justify-between">
              <button
                onClick={() => setResultsPage(p => Math.max(0, p - 1))}
                disabled={resultsPage === 0}
                className="flex items-center gap-1 text-sm text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft className="w-4 h-4" /> Previous
              </button>
              <span className="text-xs text-gray-500">
                Page {resultsPage + 1} of {totalPages}
              </span>
              <button
                onClick={() => setResultsPage(p => Math.min(totalPages - 1, p + 1))}
                disabled={resultsPage >= totalPages - 1}
                className="flex items-center gap-1 text-sm text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                Next <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      )}

      {/* Empty state — desktop license but no checks yet */}
      {!hasActiveSubscription && licenseKey && resultsData.results.length === 0 && (
        <div className="glass-card p-12 text-center">
          <Monitor className="w-12 h-12 text-accent-green mx-auto mb-4" />
          <h3 className="font-semibold text-lg mb-2 text-accent-green">Desktop App Connected</h3>
          <p className="text-gray-400 text-sm mb-2">Your license key is ready. Install and activate it in the desktop app to start monitoring.</p>
          <p className="text-gray-500 text-xs">Check results from the desktop app will appear here automatically.</p>
<p className="text-gray-500 text-xs mt-3">TIP / {(td as any).spamTip || "Appointment notification emails may land in your Spam / Junk folder — please check there and mark them as \"Not Spam\"."}</p>
        </div>
      )}

      {/* Empty state — active subscription but no branch assigned yet */}
      {hasActiveSubscription && primaryBranches.length === 0 && !splitOverview && (
        <div className="glass-card p-12 text-center">
          {isPremium ? (
            <>
              <ShieldCheck className="w-12 h-12 text-accent-green mx-auto mb-4" />
              <h3 className="font-semibold text-lg mb-2 text-accent-green">{td.premiumMonitorTitle}</h3>
              <p className="text-gray-400 text-sm mb-6">{td.premiumMonitorBody}</p>
            </>
          ) : (
            <>
              <Monitor className="w-12 h-12 text-accent-green mx-auto mb-4" />
              <h3 className="font-semibold text-lg mb-2 text-accent-green">{td.desktopMonitorTitle}</h3>
              <p className="text-gray-400 text-sm mb-6">{td.desktopMonitorBody}</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
