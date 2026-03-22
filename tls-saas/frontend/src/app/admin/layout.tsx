"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useLanguage } from "@/lib/i18n";
import { useWebSocket } from "@/hooks/useWebSocket";
import { adminApi } from "@/lib/api";
import {
  LayoutDashboard, Users, CreditCard, Activity,
  Settings, ArrowLeft, Shield, KeyRound, Star, Bell, Mail
} from "lucide-react";

const adminNav = [
  { href: "/admin", label: "Dashboard", icon: LayoutDashboard },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/payments", label: "Payments", icon: CreditCard },
  { href: "/admin/inquiries", label: "Inquiries", icon: Mail },
  { href: "/admin/notifications", label: "Notifications", icon: Bell },
  { href: "/admin/licenses", label: "Licenses", icon: KeyRound },
  { href: "/admin/monitoring", label: "Monitoring", icon: Activity },
  { href: "/admin/reviews", label: "Reviews", icon: Star },
  { href: "/admin/settings", label: "Settings", icon: Settings },
];

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const { t } = useLanguage();
  const { lastMessage } = useWebSocket(true);
  const [notifCounts, setNotifCounts] = useState<{ unread_total: number; unread_payments: number; unread_inquiries: number }>({
    unread_total: 0,
    unread_payments: 0,
    unread_inquiries: 0,
  });

  const loadNotifCounts = useCallback(async () => {
    try {
      const data = await adminApi.getNotificationCounts();
      setNotifCounts({
        unread_total: Number(data?.unread_total || 0),
        unread_payments: Number(data?.unread_payments || 0),
        unread_inquiries: Number(data?.unread_inquiries || 0),
      });
    } catch {}
  }, []);

  useEffect(() => {
    if (!loading && (!user || !user.is_admin)) {
      router.replace("/dashboard");
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (user?.is_admin) loadNotifCounts();
  }, [user?.is_admin, loadNotifCounts]);

  useEffect(() => {
    if (!user?.is_admin) return;
    const id = setInterval(() => {
      loadNotifCounts();
    }, 15000);
    return () => clearInterval(id);
  }, [user?.is_admin, loadNotifCounts]);

  useEffect(() => {
    if (!lastMessage) return;
    if (["new_payment", "new_inquiry"].includes(lastMessage.type)) {
      loadNotifCounts();
    }
  }, [lastMessage, loadNotifCounts]);

  if (loading || !user?.is_admin) {
    return (
      <div className="min-h-screen bg-dark-900 flex items-center justify-center">
        <div className="spinner w-10 h-10" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-dark-900 flex overflow-x-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-dark-800 border-r border-white/5 flex flex-col fixed h-full z-20 max-lg:hidden">
        <div className="p-5 border-b border-white/5">
          <div className="flex items-center gap-2 text-primary-400 font-display font-bold text-lg">
            <img src="/icons/icon-192-white.png" alt="" className="w-6 h-6 rounded" /> Admin Panel
          </div>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {adminNav.map((item) => {
            const isActive = pathname === item.href;
            const badgeCount =
              item.href === "/admin/payments"
                ? notifCounts.unread_payments
                : item.href === "/admin/inquiries"
                  ? notifCounts.unread_inquiries
                  : item.href === "/admin/notifications"
                    ? notifCounts.unread_total
                    : 0;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`sidebar-link flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? "bg-primary-500/10 text-primary-400"
                    : "text-gray-400 hover:bg-white/5 hover:text-white"
                }`}
              >
                <item.icon className="w-4 h-4" />
                <span className="flex-1">{item.label}</span>
                {badgeCount > 0 && (
                  <span className="min-w-[20px] h-5 px-1.5 rounded-full bg-primary-500/20 text-primary-300 text-xs font-semibold inline-flex items-center justify-center">
                    {badgeCount > 99 ? "99+" : badgeCount}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
        <div className="p-3 border-t border-white/5">
          <Link href="/dashboard" className="flex items-center gap-2 px-3 py-2.5 rounded-xl text-sm text-gray-400 hover:text-white hover:bg-white/5 transition-all">
            <ArrowLeft className="w-4 h-4" /> Back to Dashboard
          </Link>
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="lg:hidden fixed top-0 left-0 right-0 bg-dark-800 border-b border-white/5 z-20 px-4 py-3 flex items-center justify-between overflow-x-hidden">
        <div className="flex items-center gap-2 text-primary-400 font-display font-bold text-lg">
          <Shield className="w-5 h-5" /> Admin
        </div>
        <Link href="/dashboard" className="text-sm text-gray-400">
          <ArrowLeft className="w-5 h-5" />
        </Link>
      </div>

      {/* Mobile bottom nav */}
      <div className="lg:hidden fixed bottom-0 left-0 right-0 bg-dark-800 border-t border-white/5 z-20 flex gap-1 px-2 py-2 overflow-x-auto whitespace-nowrap">
        {adminNav.map((item) => {
          const isActive = pathname === item.href;
          const badgeCount =
            item.href === "/admin/payments"
              ? notifCounts.unread_payments
              : item.href === "/admin/inquiries"
                ? notifCounts.unread_inquiries
                : item.href === "/admin/notifications"
                  ? notifCounts.unread_total
                  : 0;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex flex-col items-center gap-0.5 p-2 rounded-lg text-xs min-w-[68px] shrink-0 ${
                isActive ? "text-primary-400" : "text-gray-500"
              }`}
            >
              <span className="relative">
                <item.icon className="w-5 h-5" />
                {badgeCount > 0 && (
                  <span className="absolute -top-1.5 -right-2 min-w-[16px] h-4 px-1 rounded-full bg-primary-500 text-black text-[10px] font-bold inline-flex items-center justify-center">
                    {badgeCount > 9 ? "9+" : badgeCount}
                  </span>
                )}
              </span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>

      {/* Main content */}
      <main className="flex-1 lg:ml-64 max-lg:pt-14 max-lg:pb-20 overflow-x-hidden w-full">
        <div className="bg-amber-500/10 border-b border-amber-500/20 text-amber-200/90 py-2 sm:py-3 px-4 text-xs sm:text-sm text-center">
          {(t.hero as any).notice || "⚠️ IMPORTANT NOTICE: TLS Appointment Checker is monitoring only. No auto-booking, and it does not guarantee appointments. It is a tool to help you find open slots by checking the TLS website automatically."}
        </div>
        <div className="max-w-6xl mx-auto p-4 sm:p-6 w-full min-w-0">
          {children}
        </div>
      </main>
    </div>
  );
}
