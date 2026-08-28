"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useAuth } from "@/lib/auth-context";
import { authApi, credentialApi, monitoringApi } from "@/lib/api";
import { usePushNotifications } from "@/hooks/usePushNotifications";
import {
  User, Lock, Bell, Save, Key,
  Eye, EyeOff, Loader2, Trash2, Plus, AlertTriangle,
} from "lucide-react";
import { useLanguage } from "@/lib/i18n";
import Cookies from "js-cookie";

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const { t } = useLanguage();
  const ts = t.settings;
  const [activeTab, setActiveTab] = useState("profile");
  const [premiumByStatus, setPremiumByStatus] = useState<boolean | null>(null);
  const planKeys = [
    user?.active_plan || "",
    ...((user?.active_plans || []) as string[]),
  ]
    .map((p) => String(p || "").toLowerCase())
    .filter(Boolean);
  const hasPremiumFromProfile = planKeys.some((p) => p.includes("premium") || p.includes("بريميوم"));
  const hasPremiumPlan = hasPremiumFromProfile || premiumByStatus === true;

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

  // Delete account
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);


  useEffect(() => {
    if (user) {
      setFullName(user.full_name || "");
      setPhone(user.phone || "");
    }
  }, [user]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const status = await monitoringApi.getStatus();
        const types: string[] = Array.isArray(status?.plan_types) ? status.plan_types : [];
        const premium = types.some((p) => String(p || "").toUpperCase() === "PREMIUM");
        if (!cancelled) setPremiumByStatus(premium);
      } catch {
        if (!cancelled) setPremiumByStatus(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!hasPremiumPlan && activeTab === "credentials") {
      setActiveTab("profile");
    }
  }, [activeTab, hasPremiumPlan]);

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

  const handleDeleteAccount = async () => {
    if (deleteConfirmText !== "DELETE") {
      showToast("error", 'Please type "DELETE" to confirm');
      return;
    }
    if (!deletePassword) {
      showToast("error", "Please enter your password");
      return;
    }
    setDeleting(true);
    try {
      await authApi.deleteAccount(deletePassword);
      Cookies.remove("access_token");
      Cookies.remove("refresh_token");
      window.location.href = "/";
    } catch (err: any) {
      showToast("error", err?.message || "Failed to delete account");
      setDeleting(false);
    }
  };

  const tabs = [
    { id: "profile", label: ts.tabProfile, icon: <User className="w-4 h-4" /> },
    ...(hasPremiumPlan
      ? [{ id: "credentials", label: (ts as any).tlsTab || "TLS Credentials", icon: <Key className="w-4 h-4" /> }]
      : []),
    { id: "password", label: ts.tabPassword, icon: <Lock className="w-4 h-4" /> },
    { id: "notifications", label: ts.tabNotifications, icon: <Bell className="w-4 h-4" /> },
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

      {/* TLS Credentials tab */}
      {hasPremiumPlan && activeTab === "credentials" && (
        <TLSCredentialsTab showToast={showToast} />
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

      {/* Danger Zone */}
      <div className="border border-red-500/30 rounded-xl p-6 space-y-4">
        <h2 className="font-semibold flex items-center gap-2 text-red-400">
          <AlertTriangle className="w-5 h-5" /> {(ts as any).dangerZoneTitle || "Danger Zone"}
        </h2>
        <p className="text-sm text-gray-400">
          {(ts as any).dangerZoneDesc || "Permanently delete your account and all associated data. This action cannot be undone."}
        </p>
        <button
          onClick={() => setShowDeleteModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-red-500/10 border border-red-500/40 text-red-400 hover:bg-red-500/20 hover:border-red-500/60 rounded-lg text-sm font-medium transition"
        >
          <Trash2 className="w-4 h-4" /> {(ts as any).deleteAccountBtn || "Delete My Account"}
        </button>
      </div>

      {/* Delete Account Modal */}
      <AnimatePresence>
        {showDeleteModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
            onClick={(e) => e.target === e.currentTarget && setShowDeleteModal(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-dark-800 border border-red-500/30 rounded-2xl p-6 w-full max-w-md space-y-5"
            >
              <div className="flex items-center gap-3">
                <div className="p-2 bg-red-500/10 rounded-lg">
                  <AlertTriangle className="w-6 h-6 text-red-400" />
                </div>
                <h3 className="text-lg font-semibold">Delete Account</h3>
              </div>
              <p className="text-sm text-gray-400">
                This will permanently delete your account, subscription history, and all data. You will lose access immediately.
              </p>
              <div className="space-y-3">
                <div>
                  <label className="text-sm text-gray-400 mb-1.5 block">
                    Type <span className="text-red-400 font-mono font-bold">DELETE</span> to confirm
                  </label>
                  <input
                    type="text"
                    value={deleteConfirmText}
                    onChange={(e) => setDeleteConfirmText(e.target.value)}
                    placeholder="DELETE"
                    className="input-field"
                    autoComplete="off"
                  />
                </div>
                <div>
                  <label className="text-sm text-gray-400 mb-1.5 block">Your password</label>
                  <input
                    type="password"
                    value={deletePassword}
                    onChange={(e) => setDeletePassword(e.target.value)}
                    placeholder="Enter your password"
                    className="input-field"
                    autoComplete="current-password"
                  />
                </div>
              </div>
              <div className="flex gap-3 pt-1">
                <button
                  onClick={() => { setShowDeleteModal(false); setDeletePassword(""); setDeleteConfirmText(""); }}
                  className="flex-1 px-4 py-2 bg-dark-700 hover:bg-dark-600 rounded-lg text-sm font-medium transition"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDeleteAccount}
                  disabled={deleting || deleteConfirmText !== "DELETE" || !deletePassword}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition"
                >
                  {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                  Delete Account
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

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
  const { t } = useLanguage();
  const ts = t.settings;
  const { supported, subscribed, loading, permission, subscribe, unsubscribe } = usePushNotifications(
    process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY || ""
  );

  if (!supported) {
    return (
      <div className="flex items-center justify-between p-4 bg-dark-800 rounded-xl opacity-50">
        <div className="flex items-center gap-3">
          <span className="text-gray-400"><Bell className="w-4 h-4" /></span>
          <div>
            <div className="text-sm font-medium">{(ts as any).browserPushTitle || "Browser Push"}</div>
            <div className="text-xs text-gray-500">{(ts as any).browserPushNotSupported || "Not supported in this browser"}</div>
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
          <div className="text-sm font-medium">{(ts as any).browserPushTitle || "Browser Push Notifications"}</div>
          <div className="text-xs text-gray-500">
            {subscribed ? ((ts as any).browserPushDescOn || "Enabled — you'll get push alerts") : ((ts as any).browserPushDescOff || "Get instant alerts even when the app is closed")}
          </div>
          {permission === "denied" && (
            <div className="text-xs text-red-400 mt-0.5">{(ts as any).browserPushDenied || "Permission denied — enable in browser settings"}</div>
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


function TLSCredentialsTab({ showToast }: { showToast: (type: "success" | "error", msg: string) => void }) {
  const { t } = useLanguage();
  const ts = t.settings;
  const [credentials, setCredentials] = useState<Array<{ service_type: string; tls_email: string }>>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // Form state
  const [serviceType, setServiceType] = useState("legalization");
  const [tlsEmail, setTlsEmail] = useState("");
  const [tlsPassword, setTlsPassword] = useState("");

  const fetchCredentials = async () => {
    try {
      const data = await credentialApi.getAll();
      setCredentials(data || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCredentials();
  }, []);

  const handleSave = async () => {
    if (!tlsEmail || !tlsPassword) {
      showToast("error", (ts as any).credFillRequired || "Please fill in both email and password");
      return;
    }
    setSaving(true);
    try {
      await credentialApi.save({ service_type: serviceType, tls_email: tlsEmail, tls_password: tlsPassword });
      showToast("success", (ts as any).credSavedSuccess || "TLS credentials saved successfully");
      setTlsEmail("");
      setTlsPassword("");
      setShowForm(false);
      await fetchCredentials();
    } catch (err: any) {
      showToast("error", err?.detail || (ts as any).credSaveFailed || "Failed to save credentials");
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async (serviceType: string) => {
    try {
      await credentialApi.remove(serviceType);
      showToast("success", (ts as any).credRemovedSuccess || "Credentials removed");
      await fetchCredentials();
    } catch (err: any) {
      showToast("error", err?.detail || (ts as any).credRemoveFailed || "Failed to remove credentials");
    }
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass-card p-6 space-y-5">
      <h2 className="font-semibold flex items-center gap-2">
        <Key className="w-5 h-5 text-primary-400" /> {(ts as any).credInfoTitle || "TLS Website Credentials"}
      </h2>
      <p className="text-sm text-gray-400">
        {(ts as any).credInfoDesc || "Enter your TLS website login credentials for server-side monitoring. Your credentials are encrypted and stored securely. This is required for premium plans where the server checks appointments on your behalf."}
      </p>

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-primary-400" />
        </div>
      ) : (
        <>
          {/* Existing credentials */}
          {credentials.length > 0 && (
            <div className="space-y-3">
              {credentials.map((cred) => (
                <div key={cred.service_type} className="flex items-center justify-between p-4 bg-dark-800 rounded-xl">
                  <div>
                    <div className="text-sm font-medium">
                      {cred.service_type === "legalization"
                        ? ((ts as any).serviceTypeLegalization || "Legalization")
                        : cred.service_type === "visa"
                        ? ((ts as any).serviceTypeVisa || "Visa")
                        : cred.service_type}
                    </div>
                    <div className="text-xs text-gray-500">{cred.tls_email}</div>
                  </div>
                  <button
                    onClick={() => handleRemove(cred.service_type)}
                    className="text-red-400 hover:text-red-300 p-2 rounded-lg hover:bg-red-500/10 transition"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Add/Edit form */}
          {showForm ? (
            <div className="space-y-4 p-4 bg-dark-800 rounded-xl">
              <div>
                <label className="text-sm text-gray-400 mb-1.5 block">{(ts as any).credServiceType || "Service Type"}</label>
                <select
                  value={serviceType}
                  onChange={(e) => setServiceType(e.target.value)}
                  className="input-field"
                >
                  <option value="legalization">{(ts as any).serviceTypeLegalization || "Legalization"}</option>
                  <option value="visa">{(ts as any).serviceTypeVisa || "Visa"}</option>
                </select>
              </div>
              <div>
                <label className="text-sm text-gray-400 mb-1.5 block">{(ts as any).credTlsEmail || "TLS Email"}</label>
                <input
                  type="email"
                  value={tlsEmail}
                  onChange={(e) => setTlsEmail(e.target.value)}
                  placeholder={(ts as any).credEmailPlaceholder || "your-tls-email@example.com"}
                  className="input-field"
                />
              </div>
              <div>
                <label className="text-sm text-gray-400 mb-1.5 block">{(ts as any).credTlsPassword || "TLS Password"}</label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={tlsPassword}
                    onChange={(e) => setTlsPassword(e.target.value)}
                    placeholder={(ts as any).credPasswordPlaceholder || "Your TLS website password"}
                    className="input-field pr-10"
                  />
                  <button
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="btn-gradient flex items-center gap-2 disabled:opacity-50"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  {(ts as any).credSave || "Save Credentials"}
                </button>
                <button
                  onClick={() => setShowForm(false)}
                  className="px-4 py-2 text-sm text-gray-400 hover:text-white rounded-lg border border-white/10 hover:border-white/20 transition"
                >
                  {(ts as any).cancel || "Cancel"}
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowForm(true)}
              className="btn-gradient flex items-center gap-2"
            >
              <Plus className="w-4 h-4" /> {(ts as any).addTlsCredentialsBtn || "Add TLS Credentials"}
            </button>
          )}
        </>
      )}
    </motion.div>
  );
}
