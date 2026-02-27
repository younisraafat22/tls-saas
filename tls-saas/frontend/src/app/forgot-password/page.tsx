"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { authApi } from "@/lib/api";
import { ArrowLeft, Loader2, Mail, CheckCircle } from "lucide-react";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await authApi.forgotPassword(email);
      setSent(true);
    } catch (err: any) {
      setError(err.message || "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-hero-gradient relative overflow-hidden">
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
          {sent ? (
            <div className="text-center">
              <CheckCircle className="w-16 h-16 text-green-400 mx-auto mb-4" />
              <h1 className="text-2xl font-display font-bold mb-2">Check Your Email</h1>
              <p className="text-gray-400 text-sm mb-6">
                If an account with <strong className="text-white">{email}</strong> exists, 
                we&apos;ve sent a password reset link. The link expires in 15 minutes.
              </p>
              <Link
                href="/login"
                className="btn-gradient inline-flex items-center gap-2 px-6 py-3"
              >
                <ArrowLeft className="w-4 h-4" /> Back to Login
              </Link>
            </div>
          ) : (
            <>
              <div className="text-center mb-8">
                <Mail className="w-12 h-12 text-primary-400 mx-auto mb-4" />
                <h1 className="text-2xl font-display font-bold mb-2">Forgot Password?</h1>
                <p className="text-gray-400 text-sm">
                  Enter your email address and we&apos;ll send you a link to reset your password.
                </p>
              </div>

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
                  <label className="text-sm text-gray-400 mb-1 block">Email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="input-field"
                    placeholder="you@example.com"
                    required
                    autoFocus
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
                    "Send Reset Link"
                  )}
                </button>
              </form>

              <p className="text-center text-gray-500 text-sm mt-6">
                Remember your password?{" "}
                <Link href="/login" className="text-primary-400 hover:text-primary-300 font-medium">
                  Log In
                </Link>
              </p>
            </>
          )}
        </div>
      </motion.div>
    </div>
  );
}
