"use client";

import { useCallback, useEffect, useState } from "react";
import { Bell, CheckCheck, Clock, CreditCard, Mail, RefreshCw, Trash2 } from "lucide-react";
import { adminApi } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";

export default function AdminNotificationsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "unread" | "payment" | "inquiry">("unread");
  const { lastMessage, connected } = useWebSocket(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const unreadOnly = filter === "unread";
      const category = filter === "payment" || filter === "inquiry" ? filter : "";
      const data = await adminApi.getNotifications(1, unreadOnly, category);
      setItems(data?.items || []);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const id = setInterval(() => {
      load();
    }, 15000);
    return () => clearInterval(id);
  }, [load]);

  useEffect(() => {
    if (!lastMessage) return;
    if (["new_payment", "new_inquiry"].includes(lastMessage.type)) {
      load();
    }
  }, [lastMessage, load]);

  const markRead = async (id: number) => {
    await adminApi.markNotificationRead(id);
    setItems((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true, read_at: new Date().toISOString() } : n)));
  };

  const markAll = async () => {
    const category = filter === "payment" || filter === "inquiry" ? filter : "";
    await adminApi.markAllNotificationsRead(category);
    load();
  };

  const deleteOne = async (id: number) => {
    await adminApi.deleteNotification(id);
    setItems((prev) => prev.filter((n) => n.id !== id));
  };

  const deleteRead = async () => {
    const category = filter === "payment" || filter === "inquiry" ? filter : "";
    await adminApi.deleteNotifications(category, true);
    load();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-display font-bold flex items-center gap-2"><Bell className="w-6 h-6 text-primary-400" /> Notifications</h1>
          <p className="text-sm text-gray-400 mt-1">Live admin notifications for payments and inquiries ({connected ? "live" : "disconnected"})</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} className="btn-secondary px-3 py-2 text-sm inline-flex items-center gap-2"><RefreshCw className="w-4 h-4" /> Refresh</button>
          <button onClick={markAll} className="btn-gradient px-3 py-2 text-sm inline-flex items-center gap-2"><CheckCheck className="w-4 h-4" /> Mark all read</button>
          <button onClick={deleteRead} className="btn-secondary px-3 py-2 text-sm inline-flex items-center gap-2 text-red-300"><Trash2 className="w-4 h-4" /> Delete read</button>
        </div>
      </div>

      <div className="glass-card p-3 flex gap-2 flex-wrap">
        {[
          { key: "unread", label: "Unread" },
          { key: "all", label: "All" },
          { key: "payment", label: "Payments" },
          { key: "inquiry", label: "Inquiries" },
        ].map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key as any)}
            className={`px-3 py-1.5 rounded-lg text-sm ${filter === f.key ? "bg-primary-500/20 text-primary-300" : "text-gray-400 hover:text-white hover:bg-white/5"}`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="glass-card overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-400">Loading notifications...</div>
        ) : items.length === 0 ? (
          <div className="p-8 text-center text-gray-500">No notifications</div>
        ) : (
          <div className="divide-y divide-white/5">
            {items.map((n) => (
              <div key={n.id} className={`p-4 ${n.is_read ? "opacity-70" : "bg-white/[0.02]"}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3 min-w-0">
                    <div className="mt-0.5 text-primary-400">
                      {n.category === "payment" ? <CreditCard className="w-4 h-4" /> : n.category === "inquiry" ? <Mail className="w-4 h-4" /> : <Bell className="w-4 h-4" />}
                    </div>
                    <div className="min-w-0">
                      <div className="font-semibold text-white truncate">{n.title}</div>
                      <div className="text-sm text-gray-300 break-words">{n.message}</div>
                      <div className="text-xs text-gray-500 mt-1 flex items-center gap-1"><Clock className="w-3 h-3" /> {new Date(n.created_at).toLocaleString()}</div>
                    </div>
                  </div>
                  {!n.is_read && (
                    <button onClick={() => markRead(n.id)} className="text-xs px-2.5 py-1.5 rounded-lg bg-primary-500/20 text-primary-300 hover:bg-primary-500/30">
                      Mark read
                    </button>
                  )}
                  <button onClick={() => deleteOne(n.id)} className="text-xs px-2.5 py-1.5 rounded-lg bg-red-500/15 text-red-300 hover:bg-red-500/25 inline-flex items-center gap-1">
                    <Trash2 className="w-3.5 h-3.5" /> Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

