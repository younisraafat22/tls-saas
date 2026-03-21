"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { paymentApi, subscriptionApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import {
  CreditCard, Upload, Clock, CheckCircle2, XCircle,
  AlertCircle, Copy, ArrowRight, Loader2, Sparkles, Eye, EyeOff, KeyRound, Hash,
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
  const [payments, setPayments] = useState<any[]>([]);
  const [activeSub, setActiveSub] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"subscribe" | "history">("subscribe");
  const { t, locale } = useLanguage();
  const dateLocale = locale === 'ar' ? 'ar-EG' : locale === 'de' ? 'de-DE' : 'en-GB';
  const getPlanName = (planType: string, fallback: string) => t.planNames[planType] ?? fallback;
  const getPlanDesc = (planType: string, fallback: string) => t.planDesc[planType] ?? fallback;

  // Payment form
  const [selectedPlan, setSelectedPlan] = useState<number | null>(null);
  const [paymentMethod, setPaymentMethod] = useState("vodafone_cash");
  const [reference, setReference] = useState("");
  const [screenshotData, setScreenshotData] = useState<string | null>(null);
  const [screenshotName, setScreenshotName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  // TLS credentials (Premium)
  const [tlsEmail, setTlsEmail] = useState("");
  const [tlsPassword, setTlsPassword] = useState("");
  const [showTlsPassword, setShowTlsPassword] = useState(false);

  // Device ID for desktop license binding
  const [hardwareId, setHardwareId] = useState("");

  // Branch selection
  const [branches, setBranches] = useState<any[]>([]);
  const [selectedBranch, setSelectedBranch] = useState<number | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [plansData, paymentsData, subData, branchesData] = await Promise.all([
        subscriptionApi.getPlans(),
        paymentApi.getMyPayments(),
        subscriptionApi.getActiveSubscription().catch(() => null),
        subscriptionApi.getBranches().catch(() => []),
      ]);
      setPlans(plansData);
      setPayments(paymentsData);
      setActiveSub(subData?.subscription || null);
      setBranches(branchesData || []);
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
  const isPremium = selectedPlanType === "premium";
  const isAllInOne = selectedPlanType === "all_in_one";

  // Service type selection (for premium and all_in_one)
  const [selectedServiceType, setSelectedServiceType] = useState<"legalization" | "visa">("legalization");

  // Reset branch selection when plan changes
  useEffect(() => { setSelectedBranch(null); setSelectedServiceType("legalization"); }, [selectedPlan]);

  // Filter branches by selected plan type and deduplicate by URL (legalization Normal+Students share same URL)
  const filteredBranches = (() => {
    if (!selectedPlanType) return [];
    // For premium/all_in_one: use selectedServiceType; for single plans: derive from plan type
    let serviceType: string;
    if (isPremium || isAllInOne) {
      serviceType = selectedServiceType;
    } else {
      serviceType = selectedPlanType === "visa" ? "visa" : "legalization";
    }
    const matching = branches.filter((b: any) => b.service_type === serviceType);
    // Deduplicate by URL and clean display names
    const seen = new Set<string>();
    return matching.reduce((acc: any[], b: any) => {
      if (!seen.has(b.url)) {
        seen.add(b.url);
        acc.push({
          ...b,
          displayName: b.name
            .replace(/ - Normal Legalization$/, "")
            .replace(/ - Students Legalization$/, "")
            .replace(/ \([Ll]egalization\)$/, "") // catch (Legalization) or (legalization)
            .replace(/ - Visa$/, ""),
        });
      }
      return acc;
    }, []);
  })();

  const handleSubmitPayment = async () => {
    if (!selectedPlan) {
      setToast({ type: "error", msg: t.payment.errSelectPlanBranch });
      setTimeout(() => setToast(null), 4000);
      return;
    }
    if (!isAllInOne && filteredBranches.length > 0 && !selectedBranch) {
      setToast({ type: "error", msg: "Please select a branch." });
      setTimeout(() => setToast(null), 4000);
      return;
    }
    if (isPremium && (!tlsEmail.trim() || !tlsPassword.trim())) {
      setToast({ type: "error", msg: "Please enter your TLS email and password for the Premium plan." });
      setTimeout(() => setToast(null), 4000);
      return;
    }
    if (!reference.trim() && !screenshotData) {
      setToast({ type: "error", msg: t.payment.errRequireProof });
      setTimeout(() => setToast(null), 4000);
      return;
    }

    setSubmitting(true);
    try {
      const plan = plans.find((p) => p.id === selectedPlan);
      await paymentApi.submit({
        plan_type: plan?.plan_type || "",
        amount: plan?.price_monthly || 0,
        method: paymentMethod,
        reference: reference.trim(),
        screenshot_data: screenshotData || undefined,
        tls_email: isPremium ? tlsEmail.trim() : undefined,
        tls_password: isPremium ? tlsPassword.trim() : undefined,
        hardware_id: hardwareId.trim() || undefined,
        branch_id: selectedBranch || undefined,
      });
      setToast({ type: "success", msg: t.payment.successSubmit });
      setReference("");
      setScreenshotData(null);
      setScreenshotName("");
      setSelectedPlan(null);
      setSelectedBranch(null);
      setTlsEmail("");
      setTlsPassword("");
      setHardwareId("");
      loadData();
    } catch (err: any) {
      setToast({ type: "error", msg: err?.message || err?.detail || t.payment.errSubmitFail });
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
                  {getPlanName(activeSub.plan?.plan_type ?? "", activeSub.plan?.display_name ?? "")} &middot; {(t.payment as any).expiresLabel || 'Expires'} {new Date(activeSub.expires_at).toLocaleDateString(dateLocale, { day: 'numeric', month: 'short', year: 'numeric' })}
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
          <div className="grid sm:grid-cols-2 gap-4">
            {plans.filter(p => p.is_active).sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0)).map((plan) => {
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
                      {plan.price_monthly.toLocaleString(locale === "ar" ? "ar-EG" : locale === "de" ? "de-DE" : "en-US")} <span className="text-sm font-normal text-gray-400">{(t.pricing as any)?.currencyEGP || "EGP"}{(t.pricing as any)?.perMonth || "/mo"}</span>
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

          {/* Service type selection — shown for premium only */}
          {selectedPlan && isPremium && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-6 space-y-3">
              <h3 className="font-semibold flex items-center gap-2 text-sm">
                <AlertCircle className="w-4 h-4 text-primary-400" /> {t.payment.premiumServiceTypeTitle || "Select Service Type"}
              </h3>
              <p className="text-xs text-gray-400">{t.payment.premiumServiceTypeDesc || "Choose whether you want to monitor Visa or Legalization appointments."}</p>
              <div className="flex gap-3">
                {(["legalization", "visa"] as const).map((st) => (
                  <button
                    key={st}
                    onClick={() => { setSelectedServiceType(st); setSelectedBranch(null); }}
                    className={`px-5 py-2.5 rounded-xl text-sm font-medium border transition-all capitalize ${
                      selectedServiceType === st
                        ? "bg-primary-500/10 border-primary-500/50 text-primary-400 ring-1 ring-primary-500/30"
                        : "border-white/10 text-gray-400 hover:border-white/20"
                    }`}
                  >
                    {(t.payment.serviceTypes as Record<string, string>)[st] ?? st}
                  </button>
                ))}
              </div>
            </motion.div>
          )}

          {/* Branch selection — shown for non-combo plans */}
          {selectedPlan && !isAllInOne && filteredBranches.length > 0 && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-6 space-y-3">
              <h3 className="font-semibold flex items-center gap-2 text-sm">
                <AlertCircle className="w-4 h-4 text-primary-400" /> {t.payment.selectBranchTitle}
              </h3>
              <p className="text-xs text-gray-400">{t.payment.selectBranchDesc}</p>
              <div className="grid sm:grid-cols-2 gap-3">
                {filteredBranches.map((branch: any) => {
                  const isSelected = selectedBranch === branch.id;
                  return (
                    <button
                      key={branch.id}
                      onClick={() => setSelectedBranch(branch.id)}
                      className={`p-4 rounded-xl text-left transition-all border ${
                        isSelected
                          ? "border-primary-500/50 bg-primary-500/10 ring-1 ring-primary-500/30"
                          : "border-white/5 bg-dark-700/50 hover:border-white/10"
                      }`}
                    >
                        <div className="font-medium text-sm">{t.branchNames?.[branch.displayName] || branch.displayName}</div>
                      <div className="text-xs text-gray-500 capitalize mt-0.5">{(t.payment.serviceTypes as Record<string,string>)[branch.service_type] ?? branch.service_type}</div>
                      {isSelected && (
                        <div className="mt-2 text-primary-400 text-xs flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" /> {t.payment.selectedLabel}
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>
            </motion.div>
          )}

          {/* Payment instructions */}
          {selectedPlan && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-6 space-y-5">
              <h3 className="font-semibold flex items-center gap-2">
                <CreditCard className="w-5 h-5 text-primary-400" /> {t.payment.paymentDetailsTitle}
              </h3>

              {/* TLS Credentials for Premium */}
              {isPremium && (
                <div className="space-y-3 p-4 rounded-xl bg-amber-500/5 border border-amber-500/20">
                  <div className="flex items-center gap-2 text-amber-400 text-sm font-semibold">
                    <KeyRound className="w-4 h-4" /> {t.payment.premiumTlsCredTitle || "Your TLS Account Credentials"}
                  </div>
                  <p className="text-xs text-gray-400">{t.payment.premiumTlsCredDesc || "Required so our server can monitor appointments on your behalf. Stored encrypted."}</p>
                  <div>
                    <label className="text-xs text-gray-500 mb-1.5 block">{t.payment.tlsEmailLabel}</label>
                    <input
                      type="email"
                      value={tlsEmail}
                      onChange={(e) => setTlsEmail(e.target.value)}
                      placeholder={t.payment.premiumTlsEmailPlaceholder || "your@email.com"}
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
                        placeholder={t.payment.premiumTlsPasswordPlaceholder || "********"}
                        className="input-field !pr-10"
                      />
                      <button
                        type="button"
                        onClick={() => setShowTlsPassword(!showTlsPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                      >
                        {showTlsPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Device ID for Desktop License — not needed for Premium (server-monitored) */}
              {(!isPremium || isAllInOne) && (
              <div className="space-y-3 p-4 rounded-xl bg-primary-500/5 border border-primary-500/20">
                <div className="flex items-center gap-2 text-primary-400 text-sm font-semibold">
                  <Hash className="w-4 h-4" /> {t.payment.deviceIdTitle}
                </div>
                <p className="text-xs text-gray-400" dangerouslySetInnerHTML={{ __html: t.payment.deviceIdDesc }} />
                <div>
                  <label className="text-xs text-gray-500 mb-1.5 block">{t.payment.deviceIdLabel}</label>
                  <input
                    type="text"
                    value={hardwareId}
                    onChange={(e) => setHardwareId(e.target.value)}
                    placeholder="e.g. A1B2C3D4E5F6..."
                    className="input-field font-mono"
                  />
                </div>
              </div>
              )}

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
                          {(plans.find((p) => p.id === selectedPlan)?.price_monthly || 0).toLocaleString(locale === "ar" ? "ar-EG" : locale === "de" ? "de-DE" : "en-US")} {(t.pricing as any)?.currencyEGP || "EGP"}
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
                          {(plans.find((p) => p.id === selectedPlan)?.price_monthly || 0).toLocaleString(locale === "ar" ? "ar-EG" : locale === "de" ? "de-DE" : "en-US")} {(t.pricing as any)?.currencyEGP || "EGP"}
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

              <button
                onClick={handleSubmitPayment}
                disabled={
                  submitting ||
                  (!reference.trim() && !screenshotData)
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
                        {new Date(p.created_at).toLocaleDateString(dateLocale, { day: 'numeric', month: 'short', year: 'numeric' })} &middot; {p.method.replace("_", " ")}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                      <span className="font-semibold">{p.amount} {(t.pricing as any)?.currencyEGP || "EGP"}</span>
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

