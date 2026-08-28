"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import Link from "next/link";
import {
  LayoutDashboard, Bell, Settings, CreditCard,
  LogOut, Shield, ChevronDown, Mail,
} from "lucide-react";
import { useLanguage, localeLabels, type Locale } from "@/lib/i18n";

function LangSwitcher({ openUp = false }: { openUp?: boolean }) {
  const { locale, setLocale } = useLanguage();
  const [lsOpen, setLsOpen] = useState(false);
  const locales: Locale[] = ['en', 'ar', 'de'];
  return (
    <div className="relative z-[60]">
      <button onClick={() => setLsOpen(!lsOpen)} className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold text-gray-300 hover:text-white hover:bg-white/10 transition-all border border-white/10">
        {localeLabels[locale]} <ChevronDown className="w-3 h-3" />
      </button>
      {lsOpen && (
        <div className={`absolute ${openUp ? "bottom-full mb-1" : "top-full mt-1"} right-0 bg-dark-900 border border-white/10 rounded-xl shadow-xl overflow-hidden min-w-[80px]`}>
          {locales.map((l) => (
            <button key={l} onClick={() => { setLocale(l); setLsOpen(false); }} className={`w-full text-left px-3 py-2 text-xs hover:bg-white/10 transition-colors ${locale === l ? "text-primary-400 font-semibold" : "text-gray-300"}`}>
              {localeLabels[l]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

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
    { href: "/contact?from=dashboard", icon: Mail, label: sb.contact },
  ];

  return (
    <div className="watch-console min-h-screen bg-dark-800 flex overflow-x-hidden">
      {/* Sidebar */}
      <aside className="watch-console-sidebar w-64 border-r border-white/5 bg-dark-700/50 hidden lg:flex flex-col">
        <div className="p-6">
          <Link href="/" className="flex items-center gap-2">
            <span className="watch-console-mark" aria-hidden="true">W</span>
            <span className="font-display font-bold">WATCH<small>CONTROL DESK</small></span>
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
          <div className="flex items-center justify-between">
            <button
              onClick={logout}
              className="flex items-center gap-2 text-gray-500 hover:text-red-400 transition-colors text-sm"
            >
              <LogOut className="w-4 h-4" /> {sb.logOut}
            </button>
            <LangSwitcher openUp={true} />
          </div>
        </div>
      </aside>

      {/* Mobile top nav */}
      <div className="watch-mobile-header lg:hidden fixed top-0 left-0 right-0 z-50 bg-dark-800/95 border-b border-white/5 ">
        <div className="grid grid-cols-3 items-center px-4 h-14">
          <div className="justify-self-start">
            <LangSwitcher />
          </div>
          <Link href="/" className="justify-self-center flex items-center gap-2 min-w-0">
            <span className="watch-console-mark" aria-hidden="true">W</span>
            <span className="font-display font-bold text-sm truncate">WATCH</span>
          </Link>
          <div className="justify-self-end flex items-center gap-3 min-w-[28px] justify-end">
            <Link href="/contact?from=dashboard" className="text-gray-400 hover:text-primary-400 transition-colors" title={sb.contact}>
              <Mail className="w-5 h-5" />
            </Link>
            {user.is_admin && (
              <Link href="/admin" className="text-amber-400">
                <Shield className="w-5 h-5" />
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* Mobile bottom nav */}
      <div className="lg:hidden fixed bottom-0 left-0 right-0 bg-dark-800/95 backdrop-blur-xl border-t border-white/5 flex gap-1 px-2 overflow-x-auto whitespace-nowrap z-50">
          {navItems.map((item) => (
            <Link key={item.href} href={item.href} className="flex flex-col items-center gap-1 text-gray-500 hover:text-white p-2 min-w-[64px] shrink-0">
              <item.icon className="w-5 h-5" />
              <span className="text-xs">{item.label}</span>
            </Link>
          ))}
          {user.is_admin && (
            <Link href="/admin" className="flex flex-col items-center gap-1 text-amber-400 hover:text-amber-300 p-2 min-w-[64px] shrink-0">
              <Shield className="w-5 h-5" />
              <span className="text-xs">{sb.adminPanel}</span>
            </Link>
          )}
          <button onClick={logout} className="flex flex-col items-center gap-1 text-gray-500 hover:text-red-400 p-2 min-w-[64px] shrink-0">
            <LogOut className="w-5 h-5" />
            <span className="text-xs">{sb.logOut}</span>
          </button>
        </div>

      {/* Main content */}
      <main className="watch-console-main flex-1 min-h-screen lg:pt-0 pt-14 pb-20 lg:pb-0 overflow-x-hidden w-full">
        <div className="bg-amber-500/10 border-b border-amber-500/20 text-amber-200/90 py-2 sm:py-3 px-4 text-xs sm:text-sm text-center">
          <p
            dangerouslySetInnerHTML={{
              __html:
                (t.features as any)?.notice ||
                (t.hero as any)?.notice ||
                "<strong>IMPORTANT NOTICE:</strong> TLS Appointment Checker is <strong>monitoring only</strong>. No auto-booking, and it does not guarantee appointments. It is a tool to help you find open slots by checking the TLS website automatically.",
            }}
          />
        </div>
        <div className="p-4 sm:p-6 lg:p-8 max-w-6xl mx-auto w-full min-w-0">
          {children}
        </div>
      </main>
    </div>
  );
}
