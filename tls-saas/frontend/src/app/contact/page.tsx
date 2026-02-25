"use client";

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Mail, Send, CheckCircle2, ArrowLeft, MessageCircle, Loader2 } from "lucide-react";
import { contactApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

export default function ContactPage() {
  const { t } = useLanguage();
  const tr = t.contact;
  const [form, setForm] = useState({ name: "", email: "", subject: "", message: "" });
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name || !form.email || !form.message) {
      setError(tr.errorRequired);
      return;
    }
    setError("");
    setLoading(true);
    try {
      await contactApi.submit(form);
      setSent(true);
    } catch (err: any) {
      setError(err?.detail || "Failed to send message. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-dark-900 text-white">
      {/* Header */}
      <header className="border-b border-white/5 bg-dark-800/80 backdrop-blur-lg sticky top-0 z-30">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <img src="/icons/icon-192-white.png" alt="TLS Appointment Checker" className="w-8 h-8 rounded-lg" />
            <span className="font-display font-bold text-lg">TLS Appointment Checker</span>
          </Link>
          <Link href="/login" className="btn-gradient text-sm !py-2 !px-4">{tr.openApp}</Link>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-12">
          <Link href="/" className="inline-flex items-center gap-1 text-gray-400 hover:text-white text-sm mb-8 transition-colors">
          <ArrowLeft className="w-4 h-4" /> {tr.backHome}
        </Link>

        {sent ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="glass-card p-12 text-center space-y-4"
          >
            <CheckCircle2 className="w-16 h-16 text-accent-green mx-auto" />
            <h1 className="text-2xl font-display font-bold">{tr.sentTitle}</h1>
            <p className="text-gray-400">{tr.sentBody}</p>
            <Link href="/" className="btn-gradient inline-flex items-center gap-2 !px-6 !py-2.5 mt-4">
              {tr.backHome}
            </Link>
          </motion.div>
        ) : (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-8"
          >
            <div className="text-center space-y-3">
              <div className="inline-flex items-center gap-2 bg-white/5 border border-white/10 rounded-full px-4 py-1.5 text-sm text-gray-300">
                <Mail className="w-4 h-4" /> {tr.badge}
              </div>
              <h1 className="text-3xl font-display font-bold">{tr.title}</h1>
              <p className="text-gray-400 max-w-md mx-auto">{tr.sub}</p>
            </div>

            <form onSubmit={handleSubmit} className="glass-card p-6 sm:p-8 space-y-5">
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1.5">{tr.nameLabel} {tr.required}</label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="input-field"
                    placeholder={tr.namePlaceholder}
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1.5">{tr.emailLabel} {tr.required}</label>
                  <input
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    className="input-field"
                    placeholder={tr.emailPlaceholder}
                    required
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">{tr.subjectLabel}</label>
                <input
                  type="text"
                  value={form.subject}
                  onChange={(e) => setForm({ ...form, subject: e.target.value })}
                  className="input-field"
                  placeholder={tr.subjectPlaceholder}
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">{tr.messageLabel} {tr.required}</label>
                <textarea
                  value={form.message}
                  onChange={(e) => setForm({ ...form, message: e.target.value })}
                  className="input-field min-h-[140px] resize-y"
                  placeholder={tr.messagePlaceholder}
                  required
                />
              </div>

              {error && (
                <div className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-2">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="btn-gradient w-full flex items-center justify-center gap-2 !py-3 disabled:opacity-50"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                {loading ? tr.sending : tr.send}
              </button>
            </form>

            {/* Alternative contact */}
            <div className="text-center space-y-3 text-sm text-gray-500">
              <p>{tr.orReach}</p>
              <div className="flex items-center justify-center gap-6">
                <a href="mailto:tlsappointmentchecker@gmail.com" className="flex items-center gap-1.5 text-gray-400 hover:text-white transition-colors">
                  <Mail className="w-4 h-4" /> tlsappointmentchecker@gmail.com
                </a>
              </div>
            </div>
          </motion.div>
        )}
      </main>
    </div>
  );
}
