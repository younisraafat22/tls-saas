"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import Link from "next/link";
import {
  LayoutDashboard, Bell, Settings, CreditCard,
  LogOut, Monitor, Shield,
} from "lucide-react";
import { useLanguage } from "@/lib/i18n";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const { t } = useLanguage();
  const sb = t.sidebar;
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.push("/login");
  }, [user, loading, router]);

  if (loading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-dark-800">
        <div className="spinner w-10 h-10" />
      </div>
    );
  }

  const navItems = [
    { href: "/dashboard", icon: LayoutDashboard, label: sb.overview },
    { href: "/dashboard/notifications", icon: Bell, label: sb.notifications },
    { href: "/dashboard/payments", icon: CreditCard, label: sb.payments },
    { href: "/dashboard/settings", icon: Settings, label: sb.settings },
  ];

  return (
    <div className="min-h-screen bg-dark-800 flex">
      {/* Sidebar */}
      <aside className="w-64 border-r border-white/5 bg-dark-700/50 hidden lg:flex flex-col">
        <div className="p-6">
          <Link href="/" className="flex items-center gap-2">
            <img src="/icons/icon-192-white.png" alt="TLS Appointment Checker" className="w-8 h-8 rounded-lg" />
            <span className="font-display font-bold">TLS Appointment Checker</span>
          </Link>
        </div>

        <nav className="flex-1 px-3 space-y-1">
          {navItems.map((item) => (
            <Link key={item.href} href={item.href} className="sidebar-link">
              <item.icon className="w-5 h-5" />
              <span>{item.label}</span>
            </Link>
          ))}
          {user.is_admin && (
            <Link href="/admin" className="sidebar-link text-amber-400">
              <Shield className="w-5 h-5" />
              <span>{sb.adminPanel}</span>
            </Link>
          )}
        </nav>

        <div className="p-4 border-t border-white/5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-primary-500/20 flex items-center justify-center text-sm font-bold text-primary-400">
              {user.full_name?.[0]?.toUpperCase() || "U"}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{user.full_name}</div>
              <div className="text-xs text-gray-500 truncate">{user.email}</div>
            </div>
          </div>
          <button
            onClick={logout}
            className="flex items-center gap-2 text-gray-500 hover:text-red-400 transition-colors text-sm w-full"
          >
            <LogOut className="w-4 h-4" /> {sb.logOut}
          </button>
        </div>
      </aside>

      {/* Mobile top nav */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-50 bg-dark-800/95 backdrop-blur-xl border-b border-white/5">
        <div className="flex items-center justify-between px-4 h-14">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-primary-500 to-blue-600 flex items-center justify-center">
              <Monitor className="w-4 h-4 text-white" />
            </div>
            <span className="font-display font-bold text-sm">TLS Appointment Checker</span>
          </Link>
          <div className="flex items-center gap-4">
            {user.is_admin && (
              <Link href="/admin" className="text-amber-400">
                <Shield className="w-5 h-5" />
              </Link>
            )}
          </div>
        </div>
        {/* Mobile bottom nav */}
        <div className="fixed bottom-0 left-0 right-0 bg-dark-800/95 backdrop-blur-xl border-t border-white/5 flex justify-around py-2 z-50">
          {navItems.map((item) => (
            <Link key={item.href} href={item.href} className="flex flex-col items-center gap-1 text-gray-500 hover:text-white p-2">
              <item.icon className="w-5 h-5" />
              <span className="text-xs">{item.label}</span>
            </Link>
          ))}
          <button onClick={logout} className="flex flex-col items-center gap-1 text-gray-500 hover:text-red-400 p-2">
            <LogOut className="w-5 h-5" />
            <span className="text-xs">{sb.logOut}</span>
          </button>
        </div>
      </div>

      {/* Main content */}
      <main className="flex-1 min-h-screen lg:pt-0 pt-14 pb-20 lg:pb-0 overflow-x-hidden">
        <div className="p-4 sm:p-6 lg:p-8 max-w-6xl mx-auto">
          {children}
        </div>
      </main>
    </div>
  );
}
