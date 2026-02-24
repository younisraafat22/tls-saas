"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { paymentApi, subscriptionApi } from "@/lib/api";
import {
  CreditCard, Upload, Clock, CheckCircle2, XCircle,
  AlertCircle, Copy, ArrowRight, Loader2, Sparkles,
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

  // Payment form
  const [selectedPlan, setSelectedPlan] = useState<number | null>(null);
  const [selectedBranch, setSelectedBranch] = useState<number | null>(null);
  const [paymentMethod, setPaymentMethod] = useState("vodafone_cash");
  const [reference, setReference] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<{ type: "success" | "error"; msg: string } | null>(null);

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

  const handleSubmitPayment = async () => {
    if (!selectedPlan || !selectedBranch || !reference.trim()) {
      setToast({ type: "error", msg: "Please select a plan, a TLS branch, and enter payment reference" });
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
      });
      setToast({ type: "success", msg: "Payment submitted! Awaiting admin approval." });
      setReference("");
      setSelectedPlan(null);
      setSelectedBranch(null);
      loadData();
    } catch (err: any) {
      setToast({ type: "error", msg: err?.detail || "Failed to submit payment" });
    } finally {
      setSubmitting(false);
      setTimeout(() => setToast(null), 5000);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setToast({ type: "success", msg: "Copied!" });
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
        <h1 className="text-2xl font-display font-bold">Payments & Subscription</h1>
        <p className="text-gray-400 text-sm mt-1">Manage your subscription and payment history</p>
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
                <div className="font-semibold text-accent-green">Active Subscription</div>
                <div className="text-sm text-gray-400">
                  {activeSub.plan?.display_name} &middot; Expires {new Date(activeSub.expires_at).toLocaleDateString()}
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
            {tab === "subscribe" ? "Subscribe / Renew" : "Payment History"}
          </button>
        ))}
      </div>

      {activeTab === "subscribe" && (
        <div className="space-y-6">
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
                  <h3 className="font-semibold mb-1">{plan.display_name}</h3>
                  <p className="text-sm text-gray-400 mb-3">{plan.description}</p>
                  <div className="text-2xl font-bold text-primary-400">
                    {plan.price_monthly} <span className="text-sm font-normal text-gray-400">EGP/mo</span>
                  </div>
                  {isSelected && (
                    <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} className="mt-3 text-primary-400 text-sm flex items-center gap-1">
                      <CheckCircle2 className="w-4 h-4" /> Selected
                    </motion.div>
                  )}
                </motion.button>
              );
            })}
          </div>

          {/* Branch / Embassy selection */}
          {selectedPlan && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-primary-500/20 text-primary-400 text-xs flex items-center justify-center font-bold">2</span>
                Select Your TLS Branch
              </h3>
              <div className="grid sm:grid-cols-2 gap-3">
                {branches.filter((b: any) => b.is_active && b.service_type !== "visa").map((branch: any) => {
                  const isSelected = selectedBranch === branch.id;
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
                          <div className="font-medium text-sm">{branch.name}</div>
                          <div className="text-xs text-gray-500 capitalize mt-0.5">{branch.service_type} service</div>
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
                <CreditCard className="w-5 h-5 text-primary-400" /> Payment Details
              </h3>

              {/* Method selection */}
              <div>
                <label className="text-sm text-gray-400 mb-2 block">Payment Method</label>
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
                      <span className="text-sm text-gray-400">Send to number:</span>
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-semibold">01065080242</span>
                        <button onClick={() => copyToClipboard("01065080242")} className="text-gray-500 hover:text-white transition-colors">
                          <Copy className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-400">Amount:</span>
                      <span className="font-semibold text-accent-green">
                        {plans.find((p) => p.id === selectedPlan)?.price_monthly} EGP
                      </span>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-400">InstaPay Username:</span>
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-semibold">01060263887</span>
                        <button onClick={() => copyToClipboard("01060263887")} className="text-gray-500 hover:text-white transition-colors">
                          <Copy className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-400">Amount:</span>
                      <span className="font-semibold text-accent-green">
                        {plans.find((p) => p.id === selectedPlan)?.price_monthly} EGP
                      </span>
                    </div>
                  </>
                )}
              </div>

              {/* Reference input */}
              <div>
                <label className="text-sm text-gray-400 mb-2 block">Transaction Reference / Screenshot Description</label>
                <input
                  type="text"
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                  placeholder="Enter the transaction ID or reference number"
                  className="input-field"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Enter the reference number from your payment confirmation
                </p>
              </div>

              <button
                onClick={handleSubmitPayment}
                disabled={submitting || !reference.trim() || !selectedBranch}
                className="btn-gradient w-full flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {submitting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Upload className="w-4 h-4" />
                )}
                Submit Payment for Approval
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
              <h3 className="font-semibold text-lg mb-2">No payments yet</h3>
              <p className="text-gray-400 text-sm">Your payment history will appear here.</p>
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
