"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useLanguage } from "@/lib/i18n";
import { Eye, EyeOff, ArrowRight, Loader2 } from "lucide-react";

export default function LoginPage() {
  const { login } = useAuth();
  const { t } = useLanguage();
  const tl = t.login;
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err: any) {
      // Network / server-down errors
      if (
        err instanceof TypeError ||
        err?.message?.toLowerCase().includes("failed to fetch") ||
        err?.message?.toLowerCase().includes("networkerror") ||
        err?.message?.toLowerCase().includes("load failed")
      ) {
        setError("Cannot reach the server. Please check your internet connection or try again later.");
      } else if (err?.status === 403) {
        setError("Your account has been deactivated. Please contact support.");
      } else {
        setError(err.message || tl.errorDefault);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell bg-hero-gradient">
      <aside className="auth-brand-panel" aria-label="WATCH platform status">
        <Link href="/" className="auth-wordmark">WATCH<span>®</span></Link>
        <div className="auth-manifesto">
          <p className="auth-kicker">APPOINTMENT INTELLIGENCE / 24×7</p>
          <h2>YOUR WATCH<br/>STARTS HERE.</h2>
          <p>One operational console for monitoring TLS appointment availability and acting when the signal changes.</p>
        </div>
        <div className="auth-status"><span /> SYSTEM ONLINE <b>EU-CENTRAL</b></div>
      </aside>

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="auth-form-panel"
      >
        <div className="auth-sequence"><span>01</span><i/><b>ACCESS TERMINAL</b></div>

        <div className="glass-card auth-card p-8">
          <h1 className="text-2xl font-display font-bold mb-2">{tl.title}</h1>
          <p className="text-gray-400 text-sm mb-8">{tl.sub}</p>

          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="auth-error mb-4 p-3 text-red-400 text-sm"
              role="alert"
            >
              {error}
            </motion.div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="login-email" className="text-sm text-gray-400 mb-1 block">{tl.emailLabel}</label>
              <input
                id="login-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input-field"
                placeholder="you@example.com"
                required
                autoFocus
                autoComplete="email"
              />
            </div>

            <div>
              <label htmlFor="login-password" className="text-sm text-gray-400 mb-1 block">{tl.passwordLabel}</label>
              <div className="relative">
                <input
                  id="login-password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input-field pr-12"
                  placeholder="••••••••"
                  required
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-gradient w-full flex items-center justify-center gap-2 !py-3.5 disabled:opacity-50"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <>{tl.submit} <ArrowRight className="w-4 h-4" /></>
              )}
            </button>
          </form>

          <div className="auth-secondary flex items-center justify-between mt-4">
            <Link href="/forgot-password" className="text-primary-400 hover:text-primary-300 text-sm">
              Forgot password?
            </Link>
          </div>

          <p className="text-center text-gray-500 text-sm mt-4">
            {tl.noAccount}{" "}
            <Link href="/register" className="text-primary-400 hover:text-primary-300 font-medium">
              {tl.signUp}
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
}
