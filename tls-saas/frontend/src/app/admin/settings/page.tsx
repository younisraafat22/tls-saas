"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { adminApi } from "@/lib/api";
import {
  Settings, Save, DollarSign, Clock, Bell, Mail,
  Shield, Loader2, RefreshCw, Send,
} from "lucide-react";

interface Setting {
  key: string;
  value: string;
  label: string;
  type: "text" | "number" | "toggle";
  category: string;
  description: string;
}

const settingsDef: Setting[] = [
  { key: "check_interval_minutes", value: "5", label: "Check Interval (minutes)", type: "number", category: "Checker", description: "How often to check each branch for appointments" },
  { key: "max_retries", value: "3", label: "Max Check Retries", type: "number", category: "Checker", description: "Max retries if a check fails" },
  { key: "vodafone_number", value: "", label: "Vodafone Cash Number", type: "text", category: "Payments", description: "Vodafone Cash number shown to users for payments" },
  { key: "instapay_username", value: "", label: "InstaPay Username", type: "text", category: "Payments", description: "InstaPay username shown to users for payments" },
  { key: "smtp_from_email", value: "", label: "Email From Address", type: "text", category: "Email", description: "Sender address shown to recipients (e.g. noreply@yourdomain.com)" },
  { key: "smtp_server", value: "", label: "SMTP Server", type: "text", category: "Email", description: "e.g. smtp.gmail.com or smtp.sendgrid.net" },
  { key: "smtp_port", value: "587", label: "SMTP Port", type: "number", category: "Email", description: "Usually 587 (TLS) or 465 (SSL)" },
  { key: "smtp_password", value: "", label: "SMTP Password", type: "text", category: "Email", description: "App password or SMTP API key" },
  { key: "telegram_bot_token", value: "", label: "Telegram Bot Token", type: "text", category: "Notifications", description: "From @BotFather on Telegram" },
  { key: "maintenance_mode", value: "false", label: "Maintenance Mode", type: "toggle", category: "System", description: "Disable all checking and show maintenance message to users" },
];

export default function AdminSettingsPage() {
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savingToggles, setSavingToggles] = useState<Record<string, boolean>>({});
  const [toast, setToast] = useState<{ type: "success" | "error"; msg: string } | null>(null);
  const [testingEmail, setTestingEmail] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const data = await adminApi.getSettings();
      const map: Record<string, string> = {};
      if (Array.isArray(data)) {
        data.forEach((s: any) => { map[s.key] = s.value; });
      } else if (typeof data === "object") {
        Object.entries(data).forEach(([key, value]) => {
          map[key] = String(value);
        });
      }
      // Merge defaults
      settingsDef.forEach((s) => {
        if (!(s.key in map)) map[s.key] = s.value;
      });
      setSettings(map);
    } catch (err) {
      console.error(err);
      // Use defaults
      const map: Record<string, string> = {};
      settingsDef.forEach((s) => { map[s.key] = s.value; });
      setSettings(map);
    } finally {
      setLoading(false);
    }
  };

  const handleTestEmail = async () => {
    setTestingEmail(true);
    try {
      await adminApi.testAppointmentEmail();
      setToast({ type: "success", msg: "Test email sent successfully!" });
    } catch (err: any) {
      setToast({ type: "error", msg: err?.detail || "Failed to send test email" });
    } finally {
      setTestingEmail(false);
      setTimeout(() => setToast(null), 4000);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await adminApi.updateSettings(settings);
      setToast({ type: "success", msg: "Settings saved!" });
    } catch (err: any) {
      setToast({ type: "error", msg: err?.detail || "Failed to save settings" });
    } finally {
      setSaving(false);
      setTimeout(() => setToast(null), 4000);
    }
  };

  const handleToggle = async (key: string) => {
    const oldValue = settings[key] === "true" ? "true" : "false";
    const nextValue = oldValue === "true" ? "false" : "true";
    setSettings((prev) => ({ ...prev, [key]: nextValue }));
    setSavingToggles((prev) => ({ ...prev, [key]: true }));
    try {
      await adminApi.updateSetting(key, nextValue);
      setToast({ type: "success", msg: "Setting saved!" });
    } catch (err: any) {
      setSettings((prev) => ({ ...prev, [key]: oldValue }));
      setToast({ type: "error", msg: err?.detail || "Failed to save setting" });
    } finally {
      setSavingToggles((prev) => ({ ...prev, [key]: false }));
      setTimeout(() => setToast(null), 3000);
    }
  };

  const categories = Array.from(new Set(settingsDef.map((s) => s.category)));

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

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold">System Settings</h1>
          <p className="text-gray-400 text-sm mt-1">Configure checker, notifications, and payment details</p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="btn-gradient flex items-center gap-2 disabled:opacity-50"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Save All
        </button>
      </div>

      {categories.map((cat) => {
        const catIcon = cat === "Checker" ? <Clock className="w-4 h-4" /> :
                       cat === "Payments" ? <DollarSign className="w-4 h-4" /> :
                       cat === "Email" ? <Mail className="w-4 h-4" /> :
                       cat === "Notifications" ? <Bell className="w-4 h-4" /> :
                       <Shield className="w-4 h-4" />;

        return (
          <div key={cat} className="glass-card overflow-hidden">
            <div className="p-4 border-b border-white/5 flex items-center justify-between">
              <div className="flex items-center gap-2 text-primary-400">
                {catIcon}
                <h2 className="font-semibold text-white">{cat}</h2>
              </div>
              {cat === "Email" && (
                <button
                  onClick={handleTestEmail}
                  disabled={testingEmail}
                  className="flex items-center gap-1.5 text-xs text-primary-400 hover:text-primary-300 disabled:opacity-50 transition-colors"
                >
                  {testingEmail ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
                  Send Test Email
                </button>
              )}
            </div>
            <div className="p-4 space-y-4">
              {settingsDef
                .filter((s) => s.category === cat)
                .map((setting) => (
                  <div key={setting.key} className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="sm:flex-1">
                      <label className="text-sm font-medium">{setting.label}</label>
                      <p className="text-xs text-gray-500">{setting.description}</p>
                    </div>
                    <div className="sm:w-64">
                      {setting.type === "toggle" ? (
                        <button
                          onClick={() => handleToggle(setting.key)}
                          disabled={!!savingToggles[setting.key]}
                          className={`w-11 h-6 rounded-full transition-colors relative ${
                            settings[setting.key] === "true" ? "bg-primary-500" : "bg-dark-600"
                          } ${savingToggles[setting.key] ? "opacity-70 cursor-not-allowed" : ""}`}
                        >
                          <div className={`w-5 h-5 rounded-full bg-white shadow-sm absolute top-0.5 transition-all ${
                            settings[setting.key] === "true" ? "left-[22px]" : "left-0.5"
                          }`} />
                        </button>
                      ) : (
                        <input
                          type={setting.type}
                          value={settings[setting.key] || ""}
                          onChange={(e) =>
                            setSettings((prev) => ({ ...prev, [setting.key]: e.target.value }))
                          }
                          className="input-field text-sm"
                        />
                      )}
                    </div>
                  </div>
                ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
