"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Eye, EyeOff, ArrowRight, Loader2, Check, CheckCircle2, Mail } from "lucide-react";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState({ fullName: "", email: "", phone: "", password: "", confirmPassword: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const update = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [field]: e.target.value });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (form.password !== form.confirmPassword) {
      setError("Passwords don't match");
      return;
    }
    if (form.password.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }

    setLoading(true);
    try {
      await register(form.email, form.password, form.fullName, form.phone);
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 py-12 bg-hero-gradient relative overflow-hidden">
        <div className="absolute inset-0 bg-grid opacity-30" />
        <div className="bg-radial-glow absolute inset-0" />
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-md relative z-10"
        >
          <div className="glass-card p-10 text-center space-y-5">
            <div className="w-16 h-16 rounded-full bg-accent-green/10 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-8 h-8 text-accent-green" />
            </div>
            <h1 className="text-2xl font-display font-bold">Account Created!</h1>
            <p className="text-gray-400 text-sm leading-relaxed">
              Welcome, <strong className="text-white">{form.fullName}</strong>! Your account is ready.
            </p>
            <div className="flex items-start gap-3 bg-dark-800 rounded-xl p-4 text-left">
              <Mail className="w-5 h-5 text-primary-400 shrink-0 mt-0.5" />
              <p className="text-sm text-gray-400">
                A confirmation email has been sent to <strong className="text-white">{form.email}</strong>.
              </p>
            </div>
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 text-left">
              <p className="text-xs text-amber-300 leading-relaxed">
                <strong>Next step:</strong> Go to the dashboard, choose your subscription plan, and send payment via InstaPay or Vodafone Cash. Your subscription will be activated after manual confirmation.
              </p>
            </div>
            <button
              onClick={() => router.push("/dashboard")}
              className="btn-gradient w-full flex items-center justify-center gap-2 !py-3.5"
            >
              Go to Dashboard <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 bg-hero-gradient relative overflow-hidden">
      <div className="absolute inset-0 bg-grid opacity-30" />
      <div className="bg-radial-glow absolute inset-0" />

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md relative z-10"
      >
        <Link href="/" className="flex items-center justify-center gap-2 mb-8">
          <img src="/icons/icon-192-white.png" alt="TLS Appointment Checker" className="w-10 h-10 rounded-xl" />
          <span className="font-display font-bold text-xl">TLS Appointment Checker</span>
        </Link>

        <div className="glass-card p-8">
          <h1 className="text-2xl font-display font-bold mb-2 text-center">Create Account</h1>
          <p className="text-gray-400 text-sm text-center mb-8">Start monitoring TLS appointments today</p>

          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center"
            >
              {error}
            </motion.div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-sm text-gray-400 mb-1 block">Full Name</label>
              <input
                type="text"
                value={form.fullName}
                onChange={update("fullName")}
                className="input-field"
                placeholder="Ahmed Mohamed"
                required
                autoFocus
              />
            </div>

            <div>
              <label className="text-sm text-gray-400 mb-1 block">Email</label>
              <input
                type="email"
                value={form.email}
                onChange={update("email")}
                className="input-field"
                placeholder="you@example.com"
                required
              />
            </div>

            <div>
              <label className="text-sm text-gray-400 mb-1 block">Phone <span className="text-gray-600">(optional)</span></label>
              <input
                type="tel"
                value={form.phone}
                onChange={update("phone")}
                className="input-field"
                placeholder="+20 1X XXXX XXXX"
              />
            </div>

            <div>
              <label className="text-sm text-gray-400 mb-1 block">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={form.password}
                  onChange={update("password")}
                  className="input-field pr-12"
                  placeholder="At least 6 characters"
                  required
                  minLength={6}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <div>
              <label className="text-sm text-gray-400 mb-1 block">Confirm Password</label>
              <input
                type="password"
                value={form.confirmPassword}
                onChange={update("confirmPassword")}
                className="input-field"
                placeholder="••••••••"
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-gradient w-full flex items-center justify-center gap-2 !py-3.5 disabled:opacity-50"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <>Create Account <ArrowRight className="w-4 h-4" /></>
              )}
            </button>
          </form>

          <div className="mt-4 text-xs text-gray-500 text-center">
            By signing up, you agree to our Terms of Service.
          </div>

          <p className="text-center text-gray-500 text-sm mt-6">
            Already have an account?{" "}
            <Link href="/login" className="text-primary-400 hover:text-primary-300 font-medium">
              Log In
            </Link>
          </p>
        </div>

        {/* Benefits sidebar */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="mt-6 space-y-3"
        >
          {[
            "24/7 automated monitoring",
            "Instant email & push alerts",
            "No software to install — works on phone",
          ].map((b) => (
            <div key={b} className="flex items-center gap-2 text-sm text-gray-400">
              <Check className="w-4 h-4 text-accent-green" />
              <span>{b}</span>
            </div>
          ))}
        </motion.div>
      </motion.div>
    </div>
  );
}
