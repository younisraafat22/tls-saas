"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { monitoringApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import {
  Bell, Mail, Smartphone, CheckCircle2,
  XCircle, AlertCircle, Filter, ChevronDown,
} from "lucide-react";

const channelIcons: Record<string, React.ReactNode> = {
  email: <Mail className="w-4 h-4" />,
  web_push: <Smartphone className="w-4 h-4" />,
};

const channelColors: Record<string, string> = {
  email: "text-blue-400",
  web_push: "text-purple-400",
};

export default function NotificationsPage() {
  const { t } = useLanguage();
  const tn = t.notifs;
  const [notifications, setNotifications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");
  const [showFilter, setShowFilter] = useState(false);

  useEffect(() => {
    loadNotifications();
  }, []);

  const loadNotifications = async () => {
    try {
      const data = await monitoringApi.getNotifications(100);
      setNotifications(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const filtered = filter === "all" ? notifications : notifications.filter((n) => n.channel === filter);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="spinner w-10 h-10" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold">{tn.title}</h1>
          <p className="text-gray-400 text-sm mt-1">{tn.sub}</p>
        </div>
        <div className="relative">
          <button
            onClick={() => setShowFilter(!showFilter)}
            className="flex items-center gap-2 px-3 py-2 bg-dark-700 border border-white/10 rounded-xl text-sm hover:bg-dark-600 transition-colors"
          >
            <Filter className="w-4 h-4 text-gray-400" />
            {filter === "all" ? tn.allChannels : filter === "web_push" ? tn.push : filter.charAt(0).toUpperCase() + filter.slice(1)}
            <ChevronDown className="w-3 h-3 text-gray-400" />
          </button>
          {showFilter && (
            <motion.div
              initial={{ opacity: 0, y: -5 }}
              animate={{ opacity: 1, y: 0 }}
              className="absolute right-0 top-full mt-2 bg-dark-700 border border-white/10 rounded-xl overflow-hidden shadow-xl z-10 min-w-[160px]"
            >
              {["all", "email", "web_push"].map((ch) => (
                <button
                  key={ch}
                  onClick={() => { setFilter(ch); setShowFilter(false); }}
                  className={`w-full px-4 py-2.5 text-left text-sm hover:bg-white/5 transition-colors flex items-center gap-2 ${
                    filter === ch ? "text-primary-400" : "text-gray-300"
                  }`}
                >
                  {ch !== "all" && <span className={channelColors[ch]}>{channelIcons[ch]}</span>}
                  {ch === "all" ? tn.allChannels : ch === "web_push" ? tn.push : "Email"}
                </button>
              ))}
            </motion.div>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        {(["email", "telegram", "web_push"] as const).map((ch) => {
          const count = notifications.filter((n) => n.channel === ch).length;
          return (
            <motion.div
              key={ch}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="stat-card"
            >
              <div className={`flex items-center gap-2 text-sm mb-1 ${channelColors[ch]}`}>
                {channelIcons[ch]}
                {ch === "web_push" ? tn.push : ch === "telegram" ? "Telegram" : "Email"}
              </div>
              <div className="text-2xl font-bold">{count}</div>
            </motion.div>
          );
        })}
      </div>

      {/* Notification list */}
      {filtered.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <Bell className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <h3 className="font-semibold text-lg mb-2">{tn.emptyTitle}</h3>
          <p className="text-gray-400 text-sm">{tn.emptyBody}</p>
        </div>
      ) : (
        <div className="glass-card overflow-hidden">
          <div className="divide-y divide-white/5">
            {filtered.map((n, i) => (
              <motion.div
                key={n.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.03 }}
                className="p-4 flex items-center justify-between hover:bg-white/[0.02] transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className={`${channelColors[n.channel]}`}>
                    {channelIcons[n.channel] || <Bell className="w-4 h-4" />}
                  </div>
                  <div>
                    <div className="text-sm font-medium">
                      {n.branch_name || "System Notification"}
                    </div>
                    <div className="text-xs text-gray-500">
                      {new Date(n.sent_at).toLocaleString()}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {n.status === "sent" ? (
                    <span className="text-accent-green flex items-center gap-1 text-xs">
                      <CheckCircle2 className="w-3 h-3" /> {tn.sent}
                    </span>
                  ) : (
                    <span className="text-red-400 flex items-center gap-1 text-xs">
                      <XCircle className="w-3 h-3" /> {tn.failed}
                    </span>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
