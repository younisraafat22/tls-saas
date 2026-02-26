"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { paymentApi, subscriptionApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import {
  CreditCard, Upload, Clock, CheckCircle2, XCircle,
  AlertCircle, Copy, ArrowRight, Loader2, Sparkles, Eye, EyeOff, Shield,
} from "lucide-react";

const statusColors: Record<string, string> = {
  pending: "bg-amber-500/10 text-amber-400",
  approved: "bg-accent-green/10 text-accent-green",
  rejected: "bg-red-500/10 text-red-400",
};

const statusIcons: Record<string, React.ReactNode> = {
  pending: <Clock className="w-3 h-3" />,
  approved: <CheckCircle2 className="w-3 h-3" />,
  rejected: <XCircle className="w-3 h-3" />,
};

export default function PaymentsPage() {
  const [plans, setPlans] = useState<any[]>([]);
  const [branches, setBranches] = useState<any[]>([]);
  const [payments, setPayments] = useState<any[]>([]);
  const [activeSub, setActiveSub] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"subscribe" | "history">("subscribe");
  const { t } = useLanguage();
  const getBranchName = (name: string) => t.branchNames[name] ?? name;
  const getPlanName = (planType: string, fallback: string) => t.planNames[planType] ?? fallback;
  const getPlanDesc = (planType: string, fallback: string) => t.planDesc[planType] ?? fallback;

  // Payment form
  const [selectedPlan, setSelectedPlan] = useState<number | null>(null);
  const [selectedBranch, setSelectedBranch] = useState<number | null>(null);
  const [paymentMethod, setPaymentMethod] = useState("vodafone_cash");
  const [reference, setReference] = useState("");
  const [screenshotData, setScreenshotData] = useState<string | null>(null);
  const [screenshotName, setScreenshotName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<{ type: "success" | "error"; msg: string } | null>(null);
  // TLS credentials
  const [tlsEmail, setTlsEmail] = useState("");
  const [tlsPassword, setTlsPassword] = useState("");
  const [showTlsPassword, setShowTlsPassword] = useState(false);
  const [activeAppConfirmed, setActiveAppConfirmed] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [plansData, branchesData, paymentsData, subData] = await Promise.all([
        subscriptionApi.getPlans(),
        subscriptionApi.getBranches(),
        paymentApi.getMyPayments(),
        subscriptionApi.getActiveSubscription().catch(() => null),
      ]);
      setPlans(plansData);
      setBranches(branchesData);
      setPayments(paymentsData);
      setActiveSub(subData?.subscription || null);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleScreenshotChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setScreenshotName(file.name);
    const reader = new FileReader();
    reader.onload = () => setScreenshotData(reader.result as string);
    reader.readAsDataURL(file);
  };

  const selectedPlanType = plans.find((p) => p.id === selectedPlan)?.plan_type ?? "";
  const needsTlsCreds = selectedPlanType === "visa";

  const handleSubmitPayment = async () => {
    if (!selectedPlan || !selectedBranch) {
      setToast({ type: "error", msg: t.payment.errSelectPlanBranch });
      setTimeout(() => setToast(null), 4000);
      return;
    }
    if (!reference.trim() && !screenshotData) {
      setToast({ type: "error", msg: t.payment.errRequireProof });
      setTimeout(() => setToast(null), 4000);
      return;
    }
    if (needsTlsCreds && (!tlsEmail.trim() || !tlsPassword.trim())) {
      setToast({ type: "error", msg: t.payment.errTlsCredentials });
      setTimeout(() => setToast(null), 4000);
      return;
    }
    if (needsTlsCreds && !activeAppConfirmed) {
      setToast({ type: "error", msg: t.payment.errActiveApp });
      setTimeout(() => setToast(null), 4000);
      return;
    }

    setSubmitting(true);
    try {
      const plan = plans.find((p) => p.id === selectedPlan);
      await paymentApi.submit({
        plan_type: plan?.plan_type || "",
        branch_id: selectedBranch,
        amount: plan?.price_monthly || 0,
        method: paymentMethod,
        reference: reference.trim(),
        screenshot_data: screenshotData || undefined,
        tls_email: needsTlsCreds ? tlsEmail.trim() : undefined,
        tls_password: needsTlsCreds ? tlsPassword.trim() : undefined,
      });
      setToast({ type: "success", msg: t.payment.successSubmit });
      setReference("");
      setScreenshotData(null);
      setScreenshotName("");
      setSelectedPlan(null);
      setSelectedBranch(null);
      setTlsEmail("");
      setTlsPassword("");
      setActiveAppConfirmed(false);
      loadData();
    } catch (err: any) {
      setToast({ type: "error", msg: err?.detail || t.payment.errSubmitFail });
    } finally {
      setSubmitting(false);
      setTimeout(() => setToast(null), 5000);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setToast({ type: "success", msg: t.payment.copied });
    setTimeout(() => setToast(null), 2000);
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

      <div>
        <h1 className="text-2xl font-display font-bold">{t.payment.title}</h1>
        <p className="text-gray-400 text-sm mt-1">{t.payment.sub}</p>
      </div>

      {/* Active subscription banner */}
      {activeSub && activeSub.status === "active" && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-5 border-accent-green/20">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-accent-green/10 flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-accent-green" />
              </div>
              <div>
                <div className="font-semibold text-accent-green">{t.payment.activeSubLabel}</div>
                <div className="text-sm text-gray-400">
                  {getPlanName(activeSub.plan?.plan_type ?? "", activeSub.plan?.display_name ?? "")} &middot; Expires {new Date(activeSub.expires_at).toLocaleDateString()}
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-dark-800 p-1 rounded-xl w-fit">
        {(["subscribe", "history"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === tab ? "bg-primary-500 text-white" : "text-gray-400 hover:text-gray-200"
            }`}
          >
            {tab === "subscribe" ? t.payment.tabSubscribe : t.payment.tabHistory}
          </button>
        ))}
      </div>

      {activeTab === "subscribe" && (
        <div className="space-y-6">
          {/* Early Access Warning Banner */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card border-amber-500/30 bg-amber-500/5 p-4 flex gap-3 items-start"
          >
            <span className="text-amber-400 text-xl shrink-0 mt-0.5">⚠️</span>
            <div>
              <div className="font-semibold text-amber-400 text-sm mb-1">{t.payment.earlyAccessTitle}</div>
              <p className="text-gray-400 text-xs leading-relaxed">{t.payment.earlyAccessBody}</p>
            </div>
          </motion.div>
          {/* Plans */}
          <div className="grid sm:grid-cols-3 gap-4">
            {plans.filter(p => p.is_active).map((plan) => {
              const isSelected = selectedPlan === plan.id;
              return (
                <motion.button
                  key={plan.id}
                  onClick={() => setSelectedPlan(plan.id)}
                  className={`glass-card p-5 text-left transition-all ${
                    isSelected
                      ? "border-primary-500/50 ring-1 ring-primary-500/30"
                      : "hover:border-white/10"
                  }`}
                  whileTap={{ scale: 0.98 }}
                >
                  <h3 className="font-semibold mb-1">{getPlanName(plan.plan_type, plan.display_name)}</h3>
                  <p className="text-sm text-gray-400 mb-3">{getPlanDesc(plan.plan_type, plan.description)}</p>
                  <div className="text-2xl font-bold text-primary-400">
                    {plan.price_monthly} <span className="text-sm font-normal text-gray-400">EGP/mo</span>
                  </div>
                  {isSelected && (
                    <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} className="mt-3 text-primary-400 text-sm flex items-center gap-1">
                      <CheckCircle2 className="w-4 h-4" /> {t.payment.selectedLabel}
                    </motion.div>
                  )}
                </motion.button>
              );
            })}
          </div>

          {/* Branch / Embassy selection */}
          {selectedPlan && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-primary-500/20 text-primary-400 text-xs flex items-center justify-center font-bold">2</span>
                {t.payment.selectBranchTitle}
              </h3>
              <p className="text-sm text-gray-400">
                {plans.find(p => p.id === selectedPlan)?.plan_type === "visa"
                  ? t.payment.selectBranchDesc_visa
                  : t.payment.selectBranchDesc}
              </p>
              <div className="grid sm:grid-cols-2 gap-3">
                {branches.filter((b: any) => {
                  const plan = plans.find((p) => p.id === selectedPlan);
                  return b.is_active && b.service_type === (plan?.plan_type || "legalization");
                }).map((branch: any) => {
                  const isSelected = selectedBranch === branch.id;
                  const isStudents = branch.name.toLowerCase().includes("students");
                  return (
                    <button
                      key={branch.id}
                      onClick={() => setSelectedBranch(branch.id)}
                      className={`glass-card p-4 text-left transition-all ${
                        isSelected ? "border-primary-500/50 ring-1 ring-primary-500/30" : "hover:border-white/10"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-medium text-sm">{getBranchName(branch.name)}</div>
                          <div className={`text-xs mt-1 px-2 py-0.5 rounded-full inline-block ${
                            isStudents
                              ? "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                              : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          }`}>
                            {isStudents ? t.payment.studentsLabel : t.payment.normalLabel}
                          </div>
                        </div>
                        {isSelected && <CheckCircle2 className="w-5 h-5 text-primary-400" />}
                      </div>
                    </button>
                  );
                })}
              </div>
            </motion.div>
          )}

          {/* Payment instructions */}
          {selectedPlan && selectedBranch && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-6 space-y-5">
              <h3 className="font-semibold flex items-center gap-2">
                <CreditCard className="w-5 h-5 text-primary-400" /> {t.payment.paymentDetailsTitle}
              </h3>

              {/* Method selection */}
              <div>
                <label className="text-sm text-gray-400 mb-2 block">{t.payment.methodLabel}</label>
                <div className="flex gap-3">
                  {[
                    { value: "vodafone_cash", label: "Vodafone Cash" },
                    { value: "instapay", label: "InstaPay" },
                  ].map((m) => (
                    <button
                      key={m.value}
                      onClick={() => setPaymentMethod(m.value)}
                      className={`px-4 py-2.5 rounded-xl text-sm font-medium border transition-all ${
                        paymentMethod === m.value
                          ? "bg-primary-500/10 border-primary-500/50 text-primary-400"
                          : "border-white/10 text-gray-400 hover:border-white/20"
                      }`}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Payment info */}
              <div className="bg-dark-800 rounded-xl p-4 space-y-3">
                {paymentMethod === "vodafone_cash" ? (
                  <>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-400">{t.payment.sendToNumber}</span>
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-semibold">01065080242</span>
                        <button onClick={() => copyToClipboard("01065080242")} className="text-gray-500 hover:text-white transition-colors">
                          <Copy className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-400">{t.payment.amount}</span>
                      <span className="font-semibold text-accent-green">
                        {plans.find((p) => p.id === selectedPlan)?.price_monthly} EGP
                      </span>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-400">{t.payment.instaPayUsername}</span>
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-semibold">01060263887</span>
                        <button onClick={() => copyToClipboard("01060263887")} className="text-gray-500 hover:text-white transition-colors">
                          <Copy className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-400">{t.payment.amount}</span>
                      <span className="font-semibold text-accent-green">
                        {plans.find((p) => p.id === selectedPlan)?.price_monthly} EGP
                      </span>
                    </div>
                  </>
                )}
              </div>

              {/* Reference + Screenshot */}
              <div className="space-y-3">
                <p className="text-sm text-gray-400">{t.payment.proofIntro}</p>

                {/* Reference number */}
                <div>
                  <label className="text-xs text-gray-500 mb-1.5 block">{t.payment.referenceLabel}</label>
                  <input
                    type="text"
                    value={reference}
                    onChange={(e) => setReference(e.target.value)}
                    placeholder="e.g. 1234567890"
                    className="input-field"
                  />
                </div>

                <div className="flex items-center gap-3">
                  <div className="flex-1 h-px bg-white/5" />
                  <span className="text-xs text-gray-500">OR</span>
                  <div className="flex-1 h-px bg-white/5" />
                </div>

                {/* Screenshot upload */}
                <div>
                  <label className="text-xs text-gray-500 mb-1.5 block">{t.payment.screenshotLabel}</label>
                  <label className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${
                    screenshotData
                      ? "border-primary-500/40 bg-primary-500/5"
                      : "border-white/10 hover:border-white/20 bg-dark-700/50"
                  }`}>
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={handleScreenshotChange}
                    />
                    <Upload className="w-4 h-4 text-gray-400 shrink-0" />
                    <span className="text-sm text-gray-400 truncate">
                      {screenshotName || t.payment.uploadClick}
                    </span>
                    {screenshotData && <CheckCircle2 className="w-4 h-4 text-primary-400 ml-auto shrink-0" />}
                  </label>
                  {/* Preview */}
                  {screenshotData && (
                    <div className="mt-2 relative">
                      <img src={screenshotData} alt="Payment proof" className="w-full max-h-48 object-contain rounded-lg border border-white/10" />
                      <button
                        onClick={() => { setScreenshotData(null); setScreenshotName(""); }}
                        className="absolute top-2 right-2 w-6 h-6 bg-red-500/80 rounded-full flex items-center justify-center text-white text-xs hover:bg-red-500 transition-colors"
                      >✕</button>
                    </div>
                  )}
                </div>
              </div>

              {/* Active Application Warning — visa plan only */}
              {needsTlsCreds && (
                <div className="bg-amber-500/8 border border-amber-500/25 rounded-xl p-4 space-y-3">
                  <div className="flex items-start gap-3">
                    <Shield className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                    <div>
                      <div className="font-semibold text-amber-400 text-sm mb-1">{t.payment.activeAppTitle}</div>
                      <p className="text-xs text-gray-400 leading-relaxed">{t.payment.activeAppBody}</p>
                    </div>
                  </div>
                  <label className="flex items-start gap-3 cursor-pointer group">
                    <input
                      type="checkbox"
                      checked={activeAppConfirmed}
                      onChange={(e) => setActiveAppConfirmed(e.target.checked)}
                      className="mt-0.5 accent-amber-400"
                    />
                    <span className="text-xs text-gray-300 group-hover:text-white transition-colors">
                      {t.payment.activeAppConfirm}
                    </span>
                  </label>
                </div>
              )}

              {/* TLS Credentials — visa plan only */}
              {needsTlsCreds && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Shield className="w-4 h-4 text-primary-400" />
                    <h4 className="font-semibold text-sm">{t.payment.tlsCredTitle}</h4>
                  </div>
                  <p className="text-xs text-gray-400 leading-relaxed">{t.payment.tlsCredDesc}</p>
                  <div>
                    <label className="text-xs text-gray-500 mb-1.5 block">{t.payment.tlsEmailLabel}</label>
                    <input
                      type="email"
                      value={tlsEmail}
                      onChange={(e) => setTlsEmail(e.target.value)}
                      placeholder="your.email@example.com"
                      className="input-field"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 mb-1.5 block">{t.payment.tlsPasswordLabel}</label>
                    <div className="relative">
                      <input
                        type={showTlsPassword ? "text" : "password"}
                        value={tlsPassword}
                        onChange={(e) => setTlsPassword(e.target.value)}
                        placeholder={t.payment.tlsPasswordPlaceholder}
                        className="input-field pr-12"
                      />
                      <button
                        type="button"
                        onClick={() => setShowTlsPassword(!showTlsPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                      >
                        {showTlsPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                </div>
              )}

              <button
                onClick={handleSubmitPayment}
                disabled={
                  submitting ||
                  (!reference.trim() && !screenshotData) ||
                  !selectedBranch ||
                  (needsTlsCreds && (!tlsEmail.trim() || !tlsPassword.trim() || !activeAppConfirmed))
                }
                className="btn-gradient w-full flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {submitting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Upload className="w-4 h-4" />
                )}
                {t.payment.submitBtn}
              </button>
            </motion.div>
          )}
        </div>
      )}

      {activeTab === "history" && (
        <div className="glass-card overflow-hidden">
          {payments.length === 0 ? (
            <div className="p-12 text-center">
              <CreditCard className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <h3 className="font-semibold text-lg mb-2">{t.payment.noPayments}</h3>
              <p className="text-gray-400 text-sm">{t.payment.noPaymentsDesc}</p>
            </div>
          ) : (
            <div className="divide-y divide-white/5">
              {payments.map((p: any) => (
                <div key={p.id} className="p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-dark-700 flex items-center justify-center">
                      <CreditCard className="w-5 h-5 text-gray-400" />
                    </div>
                    <div>
                      <div className="text-sm font-medium">{p.plan_name || "Subscription"}</div>
                      <div className="text-xs text-gray-500">
                        {new Date(p.created_at).toLocaleDateString()} &middot; {p.method.replace("_", " ")}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-semibold">{p.amount} EGP</span>
                    <span className={`text-xs font-medium px-2.5 py-1 rounded-full flex items-center gap-1 ${statusColors[p.status]}`}>
                      {statusIcons[p.status]}
                      {p.status.charAt(0).toUpperCase() + p.status.slice(1)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
