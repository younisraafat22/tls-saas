"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useAuth } from "@/lib/auth-context";
import { authApi, credentialApi } from "@/lib/api";
import { usePushNotifications } from "@/hooks/usePushNotifications";
import {
  User, Lock, Bell, Save,
  Eye, EyeOff, Loader2, Shield,
} from "lucide-react";
import { useLanguage } from "@/lib/i18n";

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const { t } = useLanguage();
  const ts = t.settings;
  const [activeTab, setActiveTab] = useState("profile");

  // Profile form
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [profileSaving, setProfileSaving] = useState(false);

  // Password form
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPasswords, setShowPasswords] = useState(false);
  const [passwordSaving, setPasswordSaving] = useState(false);

  // Toast
  const [toast, setToast] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  // TLS Credentials
  const [savedCreds, setSavedCreds] = useState<any[]>([]);
  const [credForm, setCredForm] = useState<{ [key: string]: { email: string; password: string; showPw: boolean } }>({
    legalization: { email: "", password: "", showPw: false },
    visa: { email: "", password: "", showPw: false },
  });
  const [credSaving, setCredSaving] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      setFullName(user.full_name || "");
      setPhone(user.phone || "");
    }
    loadCredentials();
  }, [user]);

  const loadCredentials = async () => {
    try {
      const data = await credentialApi.getAll();
      setSavedCreds(data);
    } catch {}
  };

  const handleSaveCredential = async (serviceType: string) => {
    const form = credForm[serviceType];
    if (!form.email.trim() || !form.password.trim()) {
      showToast("error", "Please enter both email and password");
      return;
    }
    setCredSaving(serviceType);
    try {
      await credentialApi.save({ service_type: serviceType, tls_email: form.email.trim(), tls_password: form.password.trim() });
      await loadCredentials();
      setCredForm(prev => ({ ...prev, [serviceType]: { email: "", password: "", showPw: false } }));
      showToast("success", "TLS credentials saved successfully");
    } catch (err: any) {
      showToast("error", err?.detail || "Failed to save credentials");
    } finally {
      setCredSaving(null);
    }
  };

  const handleRemoveCredential = async (serviceType: string) => {
    try {
      await credentialApi.remove(serviceType);
      await loadCredentials();
      showToast("success", "Credentials removed");
    } catch (err: any) {
      showToast("error", err?.detail || "Failed to remove credentials");
    }
  };

  const showToast = (type: "success" | "error", msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 4000);
  };

  const handleProfileSave = async () => {
    setProfileSaving(true);
    try {
      await authApi.updateProfile({ full_name: fullName, phone: phone || undefined });
      await refreshUser();
      showToast("success", ts.profileSaved);
    } catch (err: any) {
      showToast("error", err?.detail || "Failed to update profile");
    } finally {
      setProfileSaving(false);
    }
  };

  const handlePasswordChange = async () => {
    if (newPassword !== confirmPassword) {
      showToast("error", ts.passwordsDontMatch);
      return;
    }
    if (newPassword.length < 8) {
      showToast("error", "Password must be at least 8 characters");
      return;
    }
    setPasswordSaving(true);
    try {
      await authApi.changePassword({ current_password: currentPassword, new_password: newPassword });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      showToast("success", ts.passwordChanged);
    } catch (err: any) {
      showToast("error", err?.detail || "Failed to change password");
    } finally {
      setPasswordSaving(false);
    }
  };

  const tabs = [
    { id: "profile", label: ts.tabProfile, icon: <User className="w-4 h-4" /> },
    { id: "password", label: ts.tabPassword, icon: <Lock className="w-4 h-4" /> },
    { id: "notifications", label: ts.tabNotifications, icon: <Bell className="w-4 h-4" /> },
    { id: "credentials", label: ts.tabCredentials, icon: <Shield className="w-4 h-4" /> },
  ];

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
        <h1 className="text-2xl font-display font-bold">{ts.title}</h1>
        <p className="text-gray-400 text-sm mt-1">{ts.sub}</p>
      </div>

      {/* Tab navigation */}
      <div className="grid gap-1 bg-dark-800 p-1 rounded-xl" style={{ gridTemplateColumns: `repeat(${tabs.length}, 1fr)` }}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex flex-col sm:flex-row items-center justify-center gap-1 sm:gap-2 px-1 py-2 rounded-lg text-xs font-medium transition-all ${
              activeTab === tab.id ? "bg-primary-500 text-white" : "text-gray-400 hover:text-gray-200"
            }`}
          >
            {tab.icon} <span className="leading-tight text-center">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Profile tab */}
      {activeTab === "profile" && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass-card p-6 space-y-5">
          <h2 className="font-semibold flex items-center gap-2">
            <User className="w-5 h-5 text-primary-400" /> {ts.profileTitle}
          </h2>
          <div className="space-y-4">
            <div>
              <label className="text-sm text-gray-400 mb-1.5 block">{ts.emailLabel}</label>
              <input type="email" value={user?.email || ""} disabled className="input-field opacity-50 cursor-not-allowed" />
              <p className="text-xs text-gray-500 mt-1">{ts.emailNote}</p>
            </div>
            <div>
              <label className="text-sm text-gray-400 mb-1.5 block">{ts.fullName}</label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="input-field"
              />
            </div>
            <div>
              <label className="text-sm text-gray-400 mb-1.5 block">{ts.phone}</label>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="01XXXXXXXXX"
                className="input-field"
              />
            </div>
          </div>
          <button
            onClick={handleProfileSave}
            disabled={profileSaving}
            className="btn-gradient flex items-center gap-2 disabled:opacity-50"
          >
            {profileSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {ts.saveChanges}
          </button>
        </motion.div>
      )}

      {/* Password tab */}
      {activeTab === "password" && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass-card p-6 space-y-5">
          <h2 className="font-semibold flex items-center gap-2">
            <Lock className="w-5 h-5 text-primary-400" /> {ts.passwordTitle}
          </h2>
          <div className="space-y-4">
            <div>
              <label className="text-sm text-gray-400 mb-1.5 block">{ts.currentPassword}</label>
              <div className="relative">
                <input
                  type={showPasswords ? "text" : "password"}
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="input-field pr-10"
                />
                <button
                  onClick={() => setShowPasswords(!showPasswords)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white"
                >
                  {showPasswords ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <div>
              <label className="text-sm text-gray-400 mb-1.5 block">{ts.newPassword}</label>
              <input
                type={showPasswords ? "text" : "password"}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="input-field"
              />
            </div>
            <div>
              <label className="text-sm text-gray-400 mb-1.5 block">{ts.confirmPassword}</label>
              <input
                type={showPasswords ? "text" : "password"}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="input-field"
              />
              {confirmPassword && newPassword !== confirmPassword && (
                <p className="text-xs text-red-400 mt-1">{ts.passwordsDontMatch}</p>
              )}
            </div>
          </div>
          <button
            onClick={handlePasswordChange}
            disabled={passwordSaving || !currentPassword || !newPassword}
            className="btn-gradient flex items-center gap-2 disabled:opacity-50"
          >
            {passwordSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}
            {ts.changePassword}
          </button>
        </motion.div>
      )}

      {/* Notifications tab */}
      {activeTab === "notifications" && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass-card p-6 space-y-5">
          <h2 className="font-semibold flex items-center gap-2">
            <Bell className="w-5 h-5 text-primary-400" /> {ts.notifTitle}
          </h2>
          <div className="space-y-3">
            <NotifToggle icon={<Bell className="w-4 h-4" />} label={ts.emailNotifLabel} description={ts.emailNotifDesc} defaultOn={true} />
            <PushNotifToggle />
          </div>
          <p className="text-xs text-gray-500">{ts.notifFooter}</p>
        </motion.div>
      )}

      {/* TLS Credentials tab */}
      {activeTab === "credentials" && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-5">
          <div className="glass-card p-5 border-amber-500/20 bg-amber-500/5">
            <div className="flex items-start gap-3">
              <Shield className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold text-amber-400 text-sm mb-1">{ts.credInfoTitle}</div>
                <p className="text-xs text-gray-400 leading-relaxed">{ts.credInfoDesc}</p>
              </div>
            </div>
          </div>

          {(["legalization", "visa"] as const).map((svcType) => {
            const saved = savedCreds.find((c: any) => c.service_type === svcType);
            const form = credForm[svcType];
            return (
              <div key={svcType} className="glass-card p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold flex items-center gap-2">
                    <Shield className="w-4 h-4 text-primary-400" />
                    {svcType === "legalization" ? ts.credLegalization : ts.credVisa}
                  </h3>
                  {saved && (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-accent-green bg-accent-green/10 px-2 py-0.5 rounded-full">
                        {ts.credSaved}: {saved.email_masked}
                      </span>
                      <button
                        onClick={() => handleRemoveCredential(svcType)}
                        className="text-xs text-red-400 hover:text-red-300 transition-colors"
                      >
                        {ts.credRemove}
                      </button>
                    </div>
                  )}
                </div>
                <div className="space-y-3">
                  <div>
                    <label className="text-xs text-gray-500 mb-1.5 block">{ts.credTlsEmail}</label>
                    <input
                      type="email"
                      value={form.email}
                      onChange={(e) => setCredForm(p => ({ ...p, [svcType]: { ...p[svcType], email: e.target.value } }))}
                      placeholder={saved ? `${ts.credUpdatePlaceholder}: ${saved.email_masked}` : "your-tls-email@example.com"}
                      className="input-field"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 mb-1.5 block">{ts.credTlsPassword}</label>
                    <div className="relative">
                      <input
                        type={form.showPw ? "text" : "password"}
                        value={form.password}
                        onChange={(e) => setCredForm(p => ({ ...p, [svcType]: { ...p[svcType], password: e.target.value } }))}
                        placeholder={ts.credNewPasswordPlaceholder}
                        className="input-field pr-12"
                      />
                      <button
                        type="button"
                        onClick={() => setCredForm(p => ({ ...p, [svcType]: { ...p[svcType], showPw: !p[svcType].showPw } }))}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                      >
                        {form.showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => handleSaveCredential(svcType)}
                  disabled={credSaving === svcType || !form.email.trim() || !form.password.trim()}
                  className="btn-gradient flex items-center gap-2 text-sm disabled:opacity-50"
                >
                  {credSaving === svcType ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  {saved ? ts.credUpdate : ts.credSave}
                </button>
              </div>
            );
          })}
        </motion.div>
      )}

    </div>
  );
}

function NotifToggle({
  icon,
  label,
  description,
  defaultOn,
  disabled,
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  description: string;
  defaultOn: boolean;
  disabled?: boolean;
  hint?: string;
}) {
  const [enabled, setEnabled] = useState(defaultOn);

  return (
    <div
      className={`flex items-center justify-between p-4 bg-dark-800 rounded-xl ${
        disabled ? "opacity-50" : ""
      }`}
    >
      <div className="flex items-center gap-3">
        <span className="text-gray-400">{icon}</span>
        <div>
          <div className="text-sm font-medium">{label}</div>
          <div className="text-xs text-gray-500">{description}</div>
          {hint && <div className="text-xs text-amber-400 mt-0.5">{hint}</div>}
        </div>
      </div>
      <button
        onClick={() => !disabled && setEnabled(!enabled)}
        disabled={disabled}
        className={`w-11 h-6 rounded-full transition-colors relative ${
          enabled ? "bg-primary-500" : "bg-dark-600"
        }`}
      >
        <div
          className={`w-5 h-5 rounded-full bg-white shadow-sm absolute top-0.5 transition-all ${
            enabled ? "left-[22px]" : "left-0.5"
          }`}
        />
      </button>
    </div>
  );
}

function PushNotifToggle() {
  const { supported, subscribed, loading, permission, subscribe, unsubscribe } = usePushNotifications(
    process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY || ""
  );

  if (!supported) {
    return (
      <div className="flex items-center justify-between p-4 bg-dark-800 rounded-xl opacity-50">
        <div className="flex items-center gap-3">
          <span className="text-gray-400"><Bell className="w-4 h-4" /></span>
          <div>
            <div className="text-sm font-medium">Browser Push</div>
            <div className="text-xs text-gray-500">Not supported in this browser</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between p-4 bg-dark-800 rounded-xl">
      <div className="flex items-center gap-3">
        <span className="text-gray-400"><Bell className="w-4 h-4" /></span>
        <div>
          <div className="text-sm font-medium">Browser Push Notifications</div>
          <div className="text-xs text-gray-500">
            {subscribed ? "Enabled — you'll get push alerts" : "Get instant alerts even when the app is closed"}
          </div>
          {permission === "denied" && (
            <div className="text-xs text-red-400 mt-0.5">Permission denied — enable in browser settings</div>
          )}
        </div>
      </div>
      <button
        onClick={() => subscribed ? unsubscribe() : subscribe()}
        disabled={loading || permission === "denied"}
        className={`w-11 h-6 rounded-full transition-colors relative ${
          subscribed ? "bg-primary-500" : "bg-dark-600"
        } ${loading ? "opacity-50" : ""}`}
      >
        <div className={`w-5 h-5 rounded-full bg-white shadow-sm absolute top-0.5 transition-all ${
          subscribed ? "left-[22px]" : "left-0.5"
        }`} />
      </button>
    </div>
  );
}
