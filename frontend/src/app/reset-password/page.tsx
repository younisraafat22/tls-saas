"use client";

import { useState, Suspense } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { authApi } from "@/lib/api";
import { Loader2, Lock, CheckCircle, Eye, EyeOff, AlertCircle } from "lucide-react";

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  if (!token) {
    return (
      <div className="text-center">
        <AlertCircle className="w-16 h-16 text-red-400 mx-auto mb-4" />
        <h1 className="text-2xl font-display font-bold mb-2">Invalid Link</h1>
        <p className="text-gray-400 text-sm mb-6">
          This password reset link is invalid or has expired. Please request a new one.
        </p>
        <Link
          href="/forgot-password"
          className="btn-gradient inline-flex items-center gap-2 px-6 py-3"
        >
          Request New Link
        </Link>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setLoading(true);
    try {
      await authApi.resetPassword(token, password);
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || "Failed to reset password. The link may have expired.");
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="text-center">
        <CheckCircle className="w-16 h-16 text-green-400 mx-auto mb-4" />
        <h1 className="text-2xl font-display font-bold mb-2">Password Reset!</h1>
        <p className="text-gray-400 text-sm mb-6">
          Your password has been updated successfully. You can now log in with your new password.
        </p>
        <Link
          href="/login"
          className="btn-gradient inline-flex items-center gap-2 px-6 py-3"
        >
          Go to Login
        </Link>
      </div>
    );
  }

  return (
    <>
      <div className="text-center mb-8">
        <Lock className="w-12 h-12 text-primary-400 mx-auto mb-4" />
        <h1 className="text-2xl font-display font-bold mb-2">Set New Password</h1>
        <p className="text-gray-400 text-sm">
          Enter your new password below.
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
          <label className="text-sm text-gray-400 mb-1 block">New Password</label>
          <div className="relative">
            <input
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-field pr-12"
              placeholder="At least 8 characters"
              required
              autoFocus
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
            type={showPassword ? "text" : "password"}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="input-field"
            placeholder="Re-enter your password"
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
            "Reset Password"
          )}
        </button>
      </form>
    </>
  );
}

export default function ResetPasswordPage() {
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
          <Suspense fallback={<div className="text-center"><Loader2 className="w-8 h-8 animate-spin mx-auto text-primary-400" /></div>}>
            <ResetPasswordForm />
          </Suspense>
        </div>
      </motion.div>
    </div>
  );
}
