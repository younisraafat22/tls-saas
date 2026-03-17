"use client";

import { motion, useInView } from "framer-motion";
import { useRef, useState, useEffect } from "react";
import Link from "next/link";
import {
  Bell, Shield, Globe, Zap, Clock, Smartphone,
  Check, ChevronDown, ChevronUp, ArrowRight,
  Mail, Monitor, Download, Laptop, HardDrive, Star,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { subscriptionApi } from "@/lib/api";
import { useLanguage, localeLabels, type Locale } from "@/lib/i18n";

// -- Language Switcher -----------------------------------

function LangSwitcher() {
  const { locale, setLocale } = useLanguage();
  const [lsOpen, setLsOpen] = useState(false);
  const locales: Locale[] = ["en", "ar", "de"];
  return (
    <div className="relative">
      <button
        onClick={() => setLsOpen(!lsOpen)}
        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold text-gray-300 hover:text-white hover:bg-white/10 transition-all border border-white/10"
      >
        {localeLabels[locale]}
        <ChevronDown className="w-3 h-3" />
      </button>
      {lsOpen && (
        <div className="absolute right-0 top-full mt-1 bg-dark-900 border border-white/10 rounded-xl shadow-xl overflow-hidden z-50 min-w-[80px]">
          {locales.map((l) => (
            <button
              key={l}
              onClick={() => { setLocale(l); setLsOpen(false); }}
              className={`w-full text-left px-3 py-2 text-xs hover:bg-white/10 transition-colors ${
                locale === l ? "text-primary-400 font-semibold" : "text-gray-300"
              }`}
            >
              {localeLabels[l]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
const fadeUp = {
  hidden: { opacity: 0, y: 40 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } },
};

const fadeIn = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.6, ease: "easeOut" } },
};

const staggerContainer = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.15 } },
};

const scaleIn = {
  hidden: { opacity: 0, scale: 0.8 },
  visible: { opacity: 1, scale: 1, transition: { duration: 0.5, ease: "easeOut" } },
};

const slideInLeft = {
  hidden: { opacity: 0, x: -60 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.6, ease: "easeOut" } },
};

const slideInRight = {
  hidden: { opacity: 0, x: 60 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.6, ease: "easeOut" } },
};

// -- Animated Section wrapper ----------------------------

function AnimatedSection({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });
  return (
    <motion.div
      ref={ref}
      initial="hidden"
      animate={isInView ? "visible" : "hidden"}
      variants={staggerContainer}
      className={className}
    >
      {children}
    </motion.div>
  );
}

// -- Particle Background ---------------------------------

function Particles() {
  return (
    <div className="particles">
      {Array.from({ length: 30 }).map((_, i) => (
        <div
          key={i}
          className="particle"
          style={{
            left: `${Math.random() * 100}%`,
            animationDuration: `${8 + Math.random() * 12}s`,
            animationDelay: `${Math.random() * 8}s`,
            width: `${2 + Math.random() * 4}px`,
            height: `${2 + Math.random() * 4}px`,
          }}
        />
      ))}
    </div>
  );
}

// -- Counter Animation -----------------------------------

function Counter({ target, suffix = "", language = "en" }: { target: number; suffix?: string; language?: string }) {
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true });

  useEffect(() => {
    if (!isInView) return;
    let start = 0;
    const step = target / 40;
    const interval = setInterval(() => {
      start += step;
      if (start >= target) {
        setCount(target);
        clearInterval(interval);
      } else {
        setCount(Math.floor(start));
      }
    }, 30);
    return () => clearInterval(interval);
  }, [isInView, target]);

  const formattedCount = count.toLocaleString(language === 'ar' ? 'ar-EG' : 'en-US');
  let formattedSuffix = suffix;
  if (language === 'ar' && suffix === '/7') {
    formattedSuffix = '/\u0667';
  }
  
  if (language === 'ar') {
    return (
        <span ref={ref} dir="ltr" className="inline-block">
            {formattedCount}{formattedSuffix && <span className="mr-1">{formattedSuffix}</span>}
        </span>
    );
  }
  return <span ref={ref}>{formattedCount}{suffix}</span>;
}

// -- Navbar ----------------------------------------------

function Navbar() {
  const { user, logout } = useAuth();
  const { t, locale } = useLanguage();
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <motion.nav
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      transition={{ duration: 0.6, ease: "easeOut" }}
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        mobileOpen
          ? "bg-dark-900 shadow-lg shadow-black/30 border-b border-white/5"
          : scrolled
          ? "bg-dark-800/95 backdrop-blur-xl shadow-lg shadow-black/20 border-b border-white/5"
          : ""
      }`}
    >
      <div className="bg-amber-500/10 border-b border-amber-500/20 py-2 px-4 text-center text-xs md:text-sm text-amber-200">
        <p dangerouslySetInnerHTML={{ __html: (t.features as any)?.notice || (t.hero as any)?.notice || '<strong>⚠️ IMPORTANT NOTICE:</strong> TLS Appointment Checker is <strong>monitoring only</strong>. No auto-booking, and it does not guarantee appointments. It is a tool to help you find open slots by checking the TLS website automatically.' }} />
      </div>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 sm:h-20">
          <Link href="/" className="flex items-center gap-2">
            <img src="/icons/icon-192-white.png" alt="TLS Appointment Checker" className="w-8 h-8 rounded-lg" />
            <span className="font-display font-bold text-lg hidden sm:block">TLS Appointment Checker</span>
          </Link>

          <div className="hidden md:flex items-center gap-8">
            <a href="#features" className="text-gray-400 hover:text-white transition-colors text-sm">{t.nav.features}</a>
            <a href="#how-it-works" className="text-gray-400 hover:text-white transition-colors text-sm">{t.nav.howItWorks}</a>
            <a href="#pricing" className="text-gray-400 hover:text-white transition-colors text-sm">{t.nav.pricing}</a>
            <a href="#download" className="text-gray-400 hover:text-white transition-colors text-sm">{t.nav.download}</a>
            <a href="#guide" className="text-gray-400 hover:text-white transition-colors text-sm">{t.nav.guide}</a>
            <a href="#faq" className="text-gray-400 hover:text-white transition-colors text-sm">{t.nav.faq}</a>
          </div>

          <div className="flex items-center gap-2">
            <LangSwitcher />
            {user ? (
              <Link href={user.is_admin ? "/admin" : "/dashboard"} className="hidden md:inline-flex btn-gradient text-sm !py-2 !px-5">
                {t.nav.dashboard}
              </Link>
            ) : (
              <>
                <Link href="/login" className="text-gray-400 hover:text-white transition-colors text-sm hidden sm:block">
                  {t.nav.logIn}
                </Link>
                <Link href="/register" className="btn-gradient text-sm !py-2 !px-5">
                  {t.nav.getStarted}
                </Link>
              </>
            )}
            <button className="md:hidden text-gray-400" onClick={() => setMobileOpen(!mobileOpen)}>
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={mobileOpen ? "M6 18L18 6M6 6l12 12" : "M4 6h16M4 12h16M4 18h16"} />
              </svg>
            </button>
          </div>
        </div>

        {/* Mobile menu � nav has bg-dark-900 when mobileOpen */}
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="md:hidden pb-4 border-t border-white/10"
          >
            <div className="flex flex-col gap-1 pt-3">
              <a href="#features" className="px-4 py-2.5 text-gray-300 hover:text-white hover:bg-white/5 rounded-lg transition-colors" onClick={() => setMobileOpen(false)}>{t.nav.features}</a>
              <a href="#how-it-works" className="px-4 py-2.5 text-gray-300 hover:text-white hover:bg-white/5 rounded-lg transition-colors" onClick={() => setMobileOpen(false)}>{t.nav.howItWorks}</a>
              <a href="#pricing" className="px-4 py-2.5 text-gray-300 hover:text-white hover:bg-white/5 rounded-lg transition-colors" onClick={() => setMobileOpen(false)}>{t.nav.pricing}</a>
              <a href="#download" className="px-4 py-2.5 text-gray-300 hover:text-white hover:bg-white/5 rounded-lg transition-colors" onClick={() => setMobileOpen(false)}>{t.nav.download}</a>
              <a href="#guide" className="px-4 py-2.5 text-gray-300 hover:text-white hover:bg-white/5 rounded-lg transition-colors" onClick={() => setMobileOpen(false)}>{t.nav.guide}</a>
              <a href="#faq" className="px-4 py-2.5 text-gray-300 hover:text-white hover:bg-white/5 rounded-lg transition-colors" onClick={() => setMobileOpen(false)}>{t.nav.faq}</a>
              {user ? (
                <>
                  <Link href={user.is_admin ? "/admin" : "/dashboard"} className="px-4 py-2.5 text-gray-300 hover:text-white hover:bg-white/5 rounded-lg transition-colors" onClick={() => setMobileOpen(false)}>{t.nav.dashboard}</Link>
                  <button onClick={() => { logout(); setMobileOpen(false); }} className="px-4 py-2.5 text-left text-red-400 hover:text-red-300 hover:bg-white/5 rounded-lg transition-colors w-full">{t.sidebar.logOut}</button>
                </>
              ) : (
                <Link href="/login" className="px-4 py-2.5 text-gray-300 hover:text-white hover:bg-white/5 rounded-lg transition-colors" onClick={() => setMobileOpen(false)}>{t.nav.logIn}</Link>
              )}
            </div>
          </motion.div>
        )}
      </div>
    </motion.nav>
  );
}

// -- Hero Section ----------------------------------------

function Hero() {
  const { t, locale } = useLanguage();
  return (
    <section className="relative min-h-screen flex items-center pt-32 overflow-hidden">
      <Particles />
      <div className="bg-radial-glow absolute inset-0" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <motion.div initial="hidden" animate="visible" variants={staggerContainer}>
            <motion.div variants={fadeUp} className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary-500/10 border border-primary-500/20 mb-6">
              <span className="status-dot active" />
              <span className="text-primary-400 text-sm font-medium">{t.hero.badge}</span>
            </motion.div>

            <motion.h1 variants={fadeUp} className="text-4xl sm:text-5xl lg:text-6xl font-display font-bold leading-tight mb-6">
              {t.hero.headline1}{" "}
              <span className="bg-gradient-to-r from-primary-400 to-blue-500 bg-clip-text text-transparent">
                {t.hero.headline2}
              </span>{" "}
              {t.hero.headline3}
            </motion.h1>

            <motion.p variants={fadeUp} className="text-lg text-gray-400 mb-8 max-w-lg">
              {t.hero.sub}
            </motion.p>

            <motion.div variants={fadeUp} className="flex flex-wrap gap-4 mb-10">
              <Link href="/register" className="btn-gradient text-base flex items-center gap-2 !px-8 !py-4">
                {t.hero.cta} <ArrowRight className="w-5 h-5" />
              </Link>
              <a href="#how-it-works" className="btn-outline text-base !px-8 !py-4">
                {t.hero.learnMore}
              </a>
            </motion.div>

            <motion.div variants={fadeUp} className="flex flex-wrap gap-6 text-sm text-gray-400">
              {[t.hero.emailAlerts, t.hero.mobileReady].map((item) => (
                <div key={item} className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-accent-green" />
                  <span>{item}</span>
                </div>
              ))}
            </motion.div>
          </motion.div>

          {/* Hero visual � animated dashboard mockup */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9, x: 40 }}
            animate={{ opacity: 1, scale: 1, x: 0 }}
            transition={{ duration: 0.8, delay: 0.3 }}
            className="hidden lg:block"
          >
            <div className="relative">
              {/* Glow behind */}
              <div className="absolute inset-0 bg-primary-500/20 blur-3xl rounded-full" />

              {/* Mock dashboard card */}
              <div className="relative glass-card p-6 glow-border">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <div className="status-dot active" />
                    <span className="text-sm font-medium">{t.hero.monitoringActive}</span>
                  </div>
                  <span className="text-xs text-gray-500">{t.hero.live}</span>
                </div>

                {/* Branch cards */}
                {[
                  { name: t.branchNames["Sheikh Zayed"], type: t.serviceTypes.legalization, status: t.hero.checking, color: "text-primary-400" },
                  { name: t.branchNames["Hurghada"], type: t.serviceTypes.legalization, status: t.hero.noSlots, color: "text-gray-400" },
                  { name: t.branchNames["New Cairo"], type: t.serviceTypes.visa, status: t.hero.noSlots, color: "text-gray-400" },
                  { name: t.branchNames["Alexandria"], type: t.serviceTypes.visa, status: t.hero.noSlots, color: "text-gray-400" },
                ].map((branch, i) => (
                  <motion.div
                    key={branch.name}
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.8 + i * 0.2 }}
                    className="flex items-center justify-between p-3 rounded-xl bg-white/5 mb-2 last:mb-0"
                  >
                    <div>
                      <div className="font-medium text-sm">{branch.name}</div>
                      <div className="text-xs text-gray-500">{branch.type}</div>
                    </div>
                    <span className={`text-xs font-semibold ${branch.color}`}>{branch.status}</span>
                  </motion.div>
                ))}

                {/* Floating notification */}
                <motion.div
                  initial={{ opacity: 0, y: 20, x: 20 }}
                  animate={{ opacity: 1, y: 0, x: 0 }}
                  transition={{ delay: 1.5, type: "spring" }}
                  className="absolute -top-4 -right-4 bg-accent-green text-black px-4 py-2 rounded-xl text-xs font-bold shadow-lg shadow-accent-green/30"
                >
                  {t.hero.slotsOpen}
                </motion.div>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Stats bar */}
        <AnimatedSection className="grid grid-cols-2 md:grid-cols-4 gap-6 mt-20 pt-10 border-t border-white/5">
          {[
            { value: 4, suffix: "", label: t.stats.branches },
            { value: 24, suffix: (t.stats as any).suffix2 || "/7", label: t.stats.monitoring },
            { value: 60, suffix: (t.stats as any).suffix3 || "min", label: t.stats.checkInterval },
            { value: 2, suffix: "", label: t.stats.alertChannels },
          ].map((stat) => (
            <motion.div key={stat.label} variants={fadeUp} className="text-center">
              <div className="text-3xl font-display font-bold text-primary-400">
                <Counter target={stat.value} suffix={stat.suffix} language={locale} />
              </div>
              <div className="text-sm text-gray-500 mt-1">{stat.label}</div>
            </motion.div>
          ))}
        </AnimatedSection>
      </div>
    </section>
  );
}

// -- Features Section ------------------------------------

function Features() {
  const { t, locale } = useLanguage();
  const icons = [Bell, Shield, Globe, Zap, Clock, Smartphone];

  return (
    <section id="features" className="py-24 relative">
      <div className="bg-grid absolute inset-0 opacity-50" />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
        <AnimatedSection className="text-center mb-16">
          <motion.h2 variants={fadeUp} className="text-3xl sm:text-4xl font-display font-bold mb-4">
            {t.features.title} <span className="text-primary-400">{t.features.titleHighlight}</span>{t.features.titleEnd}
          </motion.h2>
          <motion.p variants={fadeUp} className="text-gray-400 max-w-2xl mx-auto">
            {t.features.sub}
          </motion.p>
        </AnimatedSection>

        <AnimatedSection className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {t.features.items.map((f, i) => {
            const Icon = icons[i];
            return (
              <motion.div key={f.title} variants={scaleIn} className="glass-card p-6 group">
                <div className="w-12 h-12 rounded-xl bg-primary-500/10 flex items-center justify-center mb-4 group-hover:bg-primary-500/20 transition-colors">
                  <Icon className="w-6 h-6 text-primary-400" />
                </div>
                <h3 className="font-semibold text-lg mb-2">{f.title}</h3>
                <p className="text-gray-400 text-sm leading-relaxed">{f.desc}</p>
              </motion.div>
            );
          })}
        </AnimatedSection>
      </div>
    </section>
  );
}

// -- How It Works ----------------------------------------

function HowItWorks() {
  const { t, locale } = useLanguage();

  return (
    <section id="how-it-works" className="py-24 bg-dark-700/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimatedSection className="text-center mb-16">
          <motion.h2 variants={fadeUp} className="text-3xl sm:text-4xl font-display font-bold mb-4">
            {t.howItWorks.title} <span className="text-primary-400">{t.howItWorks.titleHighlight}</span>
          </motion.h2>
          <motion.p variants={fadeUp} className="text-gray-400 max-w-2xl mx-auto">
            {t.howItWorks.sub}
          </motion.p>
        </AnimatedSection>

        <AnimatedSection className="grid md:grid-cols-4 gap-8">
          {t.howItWorks.steps.map((step, i) => (
            <motion.div key={step.title} variants={fadeUp} className="relative text-center">
              {i < t.howItWorks.steps.length - 1 && (
                <div className="hidden md:block absolute top-8 left-[60%] w-[80%] h-px bg-gradient-to-r from-primary-500/50 to-transparent" />
              )}
              <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-primary-500 to-blue-600 flex items-center justify-center mb-4 text-xl font-bold">
                {String(i + 1).padStart(2, "0")}
              </div>
              <h3 className="font-semibold text-lg mb-2">{step.title}</h3>
              <p className="text-gray-400 text-sm">{step.desc}</p>
            </motion.div>
          ))}
        </AnimatedSection>
      </div>
    </section>
  );
}

// -- Pricing Section -------------------------------------

function Pricing() {
  const { t, locale } = useLanguage();
  const fallbackPlans = [
    {
      id: 0,
      plan_type: "trial",
      display_name: "Free Trial",
      price_monthly: 0,
      currency: "EGP",
      features: [
        "3 checks - 1-day trial only",
        "Email notifications",
        "Real-time dashboard",
        "No payment needed",
        "Desktop app - PC must stay on",
      ],
      sort_order: 0,
    },
    {
      id: 1,
      plan_type: "legalization",
      display_name: "Legalization Monitor",
      price_monthly: 300,
      currency: "EGP",
      features: [
        "One branch of your choice",
        "Email & web push notifications",
        "Real-time dashboard",
        "60-minute check interval",
        "No TLS credentials needed",
        "Desktop app - PC must stay on",
      ],
      sort_order: 1,
    },
    {
      id: 2,
      plan_type: "visa",
      display_name: "Visa Monitor",
      price_monthly: 300,
      currency: "EGP",
      features: [
        "One branch of your choice",
        "Individual check using your TLS credentials",
        "Email & web push notifications",
        "Real-time dashboard",
        "60-minute check interval",
        "Desktop app - PC must stay on",
      ],
      sort_order: 2,
    },
    {
      id: 4,
      plan_type: "all_in_one",
      display_name: "Legalization + Visa",
      price_monthly: 500,
      currency: "EGP",
      features: [
        "Both legalization & visa monitoring",
        "Switch service type anytime",
        "All branches available",
        "Email & web push notifications",
        "Real-time dashboard",
        "60-minute check interval",
        "Desktop app - PC must stay on",
      ],
      sort_order: 3,
    },
    {
      id: 3,
      plan_type: "premium",
      display_name: "Premium - Server Monitored",
      price_monthly: 2500,
      currency: "EGP",
      features: [
        "Server-based monitoring - no PC needed",
        "1 service: legalization or visa (your choice)",
        "Email & web push notifications",
        "Real-time dashboard",
        "Priority support",
        "60-minute check interval",
        "⚠️ Premium server is limited to 5 users per month",
      ],
      sort_order: 4,
    },
  ];

  const [plans, setPlans] = useState<any[]>(fallbackPlans);

  useEffect(() => {
    subscriptionApi.getPlans()
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setPlans([fallbackPlans[0], ...data]);
        }
      })
      .catch(() => {
        // Keep fallback cards on network/API errors.
      });
  }, []);

  return (
    <section id="pricing" className="py-24 relative">
      <div className="bg-radial-glow absolute inset-0" />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
        <AnimatedSection className="text-center mb-16">
          <motion.h2 variants={fadeUp} className="text-3xl sm:text-4xl font-display font-bold mb-4">
            {t.pricing.title} <span className="text-primary-400">{t.pricing.titleHighlight}</span> {t.pricing.titleEnd}
          </motion.h2>
          <motion.p variants={fadeUp} className="text-gray-400 max-w-2xl mx-auto">
            {t.pricing.sub}
          </motion.p>
        </AnimatedSection>

        <AnimatedSection className="grid grid-cols-1 sm:grid-cols-2 gap-6 max-w-5xl mx-auto">
          {[...plans].sort((a, b) => a.sort_order - b.sort_order).map((plan) => {
            const isPremium = plan.plan_type === "premium";
            const isTrial = plan.plan_type === "trial";
            const isAllInOne = plan.plan_type === "all_in_one";
            return (
              <motion.div
                key={plan.id}
                variants={scaleIn}
                className={`glass-card p-8 relative flex flex-col h-full ${isPremium ? "border-amber-500/50 ring-2 ring-amber-500/30" : isAllInOne ? "border-emerald-500/50 ring-2 ring-emerald-500/30" : isTrial ? "border-cyan-500/50 ring-1 ring-cyan-500/20" : "border-primary-500/30 ring-1 ring-primary-500/20"}`}
              >
                {isPremium ? (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-gradient-to-r from-amber-500 to-orange-500 text-white text-xs font-bold px-4 py-1 rounded-full whitespace-nowrap">
                    {t.pricing.serverMonitored || "SERVER MONITORED"}
                  </div>
                ) : isAllInOne ? (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-gradient-to-r from-emerald-500 to-teal-500 text-white text-xs font-bold px-4 py-1 rounded-full whitespace-nowrap">
                    {t.pricing.bestValue || "BEST VALUE"}
                  </div>
                ) : isTrial ? (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-gradient-to-r from-cyan-500 to-teal-500 text-white text-xs font-bold px-4 py-1 rounded-full whitespace-nowrap">
                    {t.pricing.freeTrialBadge || "FREE TRIAL"}
                  </div>
                ) : (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-gradient-to-r from-primary-500 to-blue-600 text-white text-xs font-bold px-4 py-1 rounded-full whitespace-nowrap">
                    {t.pricing.desktopApp || "DESKTOP APP"}
                  </div>
                )}

                <h3 className="font-display font-bold text-xl mb-2">{t.planNames?.[plan.plan_type] ?? plan.display_name}</h3>
                <div className="flex items-baseline gap-1 mb-6">
                  {isTrial ? (
                    <span className="text-4xl font-display font-bold text-cyan-400">{t.pricing.freeWord || "FREE"}</span>
                  ) : (
                    <>
                      <span className={`text-4xl font-display font-bold ${isPremium ? "text-amber-400" : isAllInOne ? "text-emerald-400" : ""}`}>{plan.price_monthly.toLocaleString(locale === "ar" ? "ar-EG" : locale === "de" ? "de-DE" : "en-US")}</span>
                        <span className="text-gray-400 text-sm">{plan.currency === "EGP" ? (t.pricing.currencyEGP || "EGP") : plan.currency}{t.pricing.perMonth}</span>
                    </>
                  )}
                </div>

                <ul className="space-y-3 mb-8 flex-1">
                  {(t.planFeaturesMap?.[plan.plan_type] ?? plan.features ?? t.planFeatures).map((feat: string) => (
                    <li key={feat} className="flex items-start gap-2 text-sm">
                      <Check className={`w-4 h-4 mt-0.5 shrink-0 ${isPremium ? "text-amber-400" : isAllInOne ? "text-emerald-400" : "text-accent-green"}`} />
                      <span className="text-gray-300">{feat}</span>
                    </li>
                  ))}
                </ul>

                <Link
                  href="/register"
                  className={`block mt-auto w-full text-center py-3 rounded-xl font-semibold transition-all ${
                    isPremium
                      ? "bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 text-white"
                      : isAllInOne
                      ? "bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-white"
                      : isTrial
                      ? "bg-gradient-to-r from-cyan-500 to-teal-500 hover:from-cyan-400 hover:to-teal-400 text-white"
                      : "btn-gradient"
                  }`}
                >
                  {isTrial ? (t.pricing.startTrial ?? "Start Free Trial") : t.pricing.getStarted}
                </Link>
              </motion.div>
            );
          })}
        </AnimatedSection>

        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="text-center text-gray-500 text-sm mt-8"
        >
          {t.pricing.footer}
        </motion.p>
      </div>
    </section>
  );
}

// -- Download App Section --------------------------------

function DownloadApp() {
  const { t, locale } = useLanguage();
  const dl = t.downloadSection;
  const [downloadInfo, setDownloadInfo] = useState<{
    version: string;
    download_url: string;
    size_mb: string;
    requirements: string;
  }>({ version: "1.0.0", download_url: "", size_mb: "~260", requirements: "Windows 10/11" });

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://192.168.1.108:8000";
    fetch(`${apiUrl}/api/app/download-info`)
      .then((r) => r.json())
      .then((data) =>
        setDownloadInfo({
          version: data.version ?? "2.0.0",
          download_url: data.download_url ?? "",
          size_mb: data.size_mb ?? "~80",
          requirements: data.requirements ?? "Windows 10/11",
        })
      )
      .catch(() => {/* keep defaults on network error */});
  }, []);

  return (
    <section id="download" className="py-24 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-primary-500/5 via-transparent to-transparent" />
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <AnimatedSection>
          <motion.div variants={fadeUp} className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-display font-bold mb-4">
              {dl.title} <span className="text-primary-400">{dl.titleHighlight}</span>
            </h2>
            <p className="text-gray-400 max-w-2xl mx-auto">{dl.sub}</p>
          </motion.div>

          <div className="grid md:grid-cols-2 gap-8 items-center">
            {/* Left: Features list */}
            <motion.div variants={fadeUp} className="space-y-6">
              {dl.features.map((feat: string, i: number) => (
                <div key={i} className="flex items-start gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary-500/20 flex items-center justify-center mt-0.5">
                    <Check className="w-3.5 h-3.5 text-primary-400" />
                  </div>
                  <p className="text-gray-300 text-sm">{feat}</p>
                </div>
              ))}

              {/* Privacy callout */}
              <div className="mt-6 p-4 rounded-xl bg-green-500/10 border border-green-500/20">
                <div className="flex items-center gap-2 mb-2">
                  <Shield className="w-5 h-5 text-green-400" />
                  <span className="font-semibold text-green-300 text-sm">{dl.whyLocal}</span>
                </div>
                <p className="text-green-200/70 text-xs">{dl.whyLocalDesc}</p>
              </div>
            </motion.div>

            {/* Right: Download card */}
            <motion.div variants={fadeUp} className="glass p-8 rounded-2xl text-center">
              <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-primary-500/20 to-blue-600/20 flex items-center justify-center">
                <Laptop className="w-10 h-10 text-primary-400" />
              </div>

              <h3 className="text-2xl font-bold mb-2">TLS Appointment Checker</h3>
              <p className="text-gray-400 text-sm mb-1">{dl.version} {downloadInfo.version}</p>
              <p className="text-gray-500 text-xs mb-6">{downloadInfo.requirements}</p>

              {downloadInfo.download_url ? (
                <a
                  href={downloadInfo.download_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-gradient text-lg !px-8 !py-3 inline-flex items-center gap-2 w-full justify-center"
                >
                  <Download className="w-5 h-5" />
                  {dl.downloadBtn}
                </a>
              ) : (
                <div className="px-8 py-3 rounded-xl bg-white/5 border border-white/10 text-gray-400 text-sm">
                  {dl.comingSoon}
                </div>
              )}

              <div className="mt-6 flex items-center justify-center gap-6 text-xs text-gray-500">
                <span className="flex items-center gap-1"><HardDrive className="w-3.5 h-3.5" /> {downloadInfo.size_mb} MB</span>
                <span className="flex items-center gap-1"><Monitor className="w-3.5 h-3.5" /> Windows 10/11</span>
              </div>

              {downloadInfo.download_url && (
                <div className="mt-5 p-3 rounded-xl bg-yellow-500/10 border border-yellow-500/20 text-left">
                  <p className="text-yellow-300/80 text-xs leading-relaxed">
                    ?? {dl.smartscreenNote}
                  </p>
                </div>
              )}
            </motion.div>
          </div>
        </AnimatedSection>
      </div>
    </section>
  );
}
// -- User Guide --------------------------------------------------

function UserGuide() {
  const { t, locale } = useLanguage();
  const [tab, setTab] = useState<"app" | "server">("server");
  const g = t.guide;

  return (
    <section id="guide" className="py-24 relative bg-dark-700/20">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimatedSection>
          <motion.div variants={fadeUp} className="text-center mb-12">
            <h2 className="text-3xl sm:text-4xl font-display font-bold mb-4">
              {g.title} <span className="text-primary-400">{g.titleHighlight}</span>
            </h2>
            <p className="text-gray-400 max-w-xl mx-auto">{g.sub}</p>
          </motion.div>

          <motion.div variants={fadeUp} className="flex justify-center gap-3 mb-10 flex-wrap">
            <button
              onClick={() => setTab("app")}
              className={`flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-medium transition-all ${
                tab === "app"
                  ? "bg-primary-500/20 border border-primary-500/40 text-primary-300"
                  : "bg-white/5 border border-white/10 text-gray-400 hover:text-white"
              }`}
            >
              <Laptop className="w-4 h-4" /> {g.appTab}
            </button>
            <button
              onClick={() => setTab("server")}
              className={`flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-medium transition-all ${
                tab === "server"
                  ? "bg-primary-500/20 border border-primary-500/40 text-primary-300"
                  : "bg-white/5 border border-white/10 text-gray-400 hover:text-white"
              }`}
            >
              <Globe className="w-4 h-4" /> {g.serverTab}
            </button>
          </motion.div>

          <motion.div
            key={tab}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className="glass rounded-2xl p-8"
          >
            {(() => {
              const plan = tab === "app" ? g.app : g.server;
              return (
                <>
                  <div className="mb-6">
                    <span className="text-xs font-medium text-primary-400 bg-primary-500/10 border border-primary-500/20 px-3 py-1 rounded-full inline-block mb-3">
                      {plan.badge}
                    </span>
                    <h3 className="text-xl font-bold">{plan.title}</h3>
                    <p className="text-gray-400 text-sm mt-2 max-w-lg">{plan.desc}</p>
                  </div>

                  {tab === "server" && (
                    <div className="mb-6 p-4 rounded-xl bg-yellow-500/10 border border-yellow-500/20">
                      <p className="text-yellow-300/90 text-sm">{g.server.limitNote}</p>
                    </div>
                  )}

                  <ol className="space-y-5">
                    {plan.steps.map((step: { n: string; title: string; body: string }, i: number) => (
                      <li key={i} className="flex gap-4">
                        <span className="flex-shrink-0 w-8 h-8 rounded-full bg-primary-500/20 border border-primary-500/30 flex items-center justify-center text-primary-400 text-sm font-bold">
                          {step.n}
                        </span>
                        <div>
                          <p className="font-medium text-white">{step.title}</p>
                          <p className="text-gray-400 text-sm mt-0.5">{step.body}</p>
                        </div>
                      </li>
                    ))}
                  </ol>

                  <div className="mt-6 p-3 rounded-xl bg-white/5 border border-white/10">
                    <p className="text-gray-400 text-xs">{plan.note}</p>
                  </div>
                </>
              );
            })()}
          </motion.div>
        </AnimatedSection>
      </div>
    </section>
  );
}
// -- FAQ -------------------------------------------------

function FAQ() {
  const { t, locale } = useLanguage();
  const [open, setOpen] = useState<number | null>(null);

  return (
    <section id="faq" className="py-24 bg-dark-700/30">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimatedSection className="text-center mb-12">
          <motion.h2 variants={fadeUp} className="text-3xl sm:text-4xl font-display font-bold mb-4">
            {t.faq.title} <span className="text-primary-400">{t.faq.titleHighlight}</span>
          </motion.h2>
        </AnimatedSection>

        <AnimatedSection className="space-y-3">
          {t.faq.items.map((faq, i) => (
            <motion.div key={i} variants={fadeUp} className="glass-card overflow-hidden">
              <button
                onClick={() => setOpen(open === i ? null : i)}
                className="w-full flex items-center justify-between p-5 text-left"
              >
                <span className="font-medium pr-4">{faq.q}</span>
                <motion.span animate={{ rotate: open === i ? 180 : 0 }} transition={{ duration: 0.2 }}>
                  <ChevronDown className="w-5 h-5 text-gray-400 shrink-0" />
                </motion.span>
              </button>
              <motion.div
                initial={false}
                animate={{ height: open === i ? "auto" : 0, opacity: open === i ? 1 : 0 }}
                transition={{ duration: 0.3 }}
                className="overflow-hidden"
              >
                <p className="px-5 pb-5 text-gray-400 text-sm leading-relaxed">{faq.a}</p>
              </motion.div>
            </motion.div>
          ))}
        </AnimatedSection>
      </div>
    </section>
  );
}

﻿// -- Rating ----------------------------------------------

function RatingComponent() {
  const { t } = useLanguage();
  const [rating, setRating] = useState(0);
  const [hovered, setHovered] = useState(0);
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (rating === 0) return;
    setSubmitting(true);
    try {
      await fetch((process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000") + "/metrics/rate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating, comment, source: "website" }),
      });
      setSubmitted(true);
    } catch (err) {
      console.error(err);
    }
    setSubmitting(false);
  };

  if (submitted) {
    return (
      <section id="rating" className="py-24 relative overflow-hidden">
        <div className="max-w-2xl mx-auto px-4 text-center">
          <motion.div variants={scaleIn} initial="hidden" animate="visible" className="glass-card p-12 rounded-2xl border border-primary-500/20 bg-primary-500/5">
            <Check className="w-16 h-16 text-primary-400 mx-auto mb-6" />
            <h3 className="text-3xl font-display font-bold text-white mb-4">{t.rating?.thanks ?? "Thank you for your feedback!"}</h3>
          </motion.div>
        </div>
      </section>
    );
  }

  return (
    <section id="rating" className="py-24 relative overflow-hidden">
      <div className="max-w-2xl mx-auto px-4">
        <AnimatedSection className="glass-card p-8 md:p-12 rounded-2xl border border-white/10 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-primary-500/10 via-transparent to-transparent pointer-events-none" />
          <div className="text-center mb-8">
            <h2 className="text-3xl font-display font-bold text-white mb-3">{t.rating?.title ?? "Rate Your Experience"}</h2>
            <p className="text-gray-400">{t.rating?.sub ?? "Let us know how the service works for you!"}</p>
          </div>
          
          <div className="flex justify-center gap-2 mb-8">
            {[1, 2, 3, 4, 5].map((star) => (
              <button
                key={star}
                type="button"
                className="focus:outline-none transition-transform hover:scale-110"
                onMouseEnter={() => setHovered(star)}
                onMouseLeave={() => setHovered(0)}
                onClick={() => setRating(star)}
              >
                <Star
                  className={"" + "w-10 h-10 transition-colors " + ((hovered || rating) >= star ? "fill-primary-400 text-primary-400" : "text-gray-600")}
                />
              </button>
            ))}
          </div>

          <div className="space-y-4">
            <textarea
              className="w-full bg-dark-800/50 border border-white/10 rounded-xl p-4 text-white placeholder:text-gray-500 focus:outline-none focus:border-primary-500/50 transition-colors resize-none"
              rows={3}
              placeholder={t.rating?.placeholder ?? "Optional feedback..."}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
            <button
              onClick={handleSubmit}
              disabled={submitting || rating === 0}
              className="w-full btn-gradient py-4 rounded-xl font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {submitting ? "..." : (t.rating?.submit ?? "Submit Rating")}
            </button>
          </div>
        </AnimatedSection>
      </div>
    </section>
  );
}


// -- CTA Section -----------------------------------------

function CTA() {
  const { t, locale } = useLanguage();
  return (
    <section className="py-24 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-r from-primary-500/10 via-blue-600/10 to-purple-600/10" />
      <div className="max-w-4xl mx-auto px-4 text-center relative z-10">
        <AnimatedSection>
          <motion.h2 variants={fadeUp} className="text-3xl sm:text-4xl font-display font-bold mb-4">
            {t.cta.title}
          </motion.h2>
          <motion.p variants={fadeUp} className="text-gray-400 mb-8 text-lg">
            {t.cta.sub}
          </motion.p>
          <motion.div variants={fadeUp}>
            <Link href="/register" className="btn-gradient text-lg !px-10 !py-4 inline-flex items-center gap-2">
              {t.cta.button} <ArrowRight className="w-5 h-5" />
            </Link>
          </motion.div>
        </AnimatedSection>
      </div>
    </section>
  );
}

// -- Footer ----------------------------------------------

function Footer() {
  const { t, locale } = useLanguage();
  return (
    <footer className="py-12 border-t border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid md:grid-cols-3 gap-8">
          <div>
            <div className="flex items-center gap-2 mb-4">
              <img src="/icons/icon-192-white.png" alt="TLS Appointment Checker" className="w-8 h-8 rounded-lg" />
              <span className="font-display font-bold">TLS Appointment Checker</span>
            </div>
            <p className="text-gray-400 text-sm">{t.footer.desc}</p>
          </div>

          <div>
            <h3 className="font-semibold mb-4">{t.footer.quickLinks}</h3>
            <ul className="space-y-2 text-sm text-gray-400">
              <li><a href="#features" className="hover:text-white transition-colors">{t.footer.features}</a></li>
              <li><a href="#pricing" className="hover:text-white transition-colors">{t.footer.pricing}</a></li>
              <li><a href="#download" className="hover:text-white transition-colors">{t.nav.download}</a></li>
              <li><a href="#faq" className="hover:text-white transition-colors">{t.footer.faq}</a></li>
              <li><Link href="/login" className="hover:text-white transition-colors">{t.footer.logIn}</Link></li>
            </ul>
          </div>

          <div>
            <h3 className="font-semibold mb-4">{t.footer.legal}</h3>
            <ul className="space-y-2 text-sm text-gray-400">
              <li><Link href="/terms" className="hover:text-white transition-colors">{t.footer.terms}</Link></li>
              <li><Link href="/privacy" className="hover:text-white transition-colors">{t.footer.privacy}</Link></li>
              <li><Link href="/contact" className="flex items-center gap-2 hover:text-white transition-colors"><Mail className="w-4 h-4" /> {t.footer.contact}</Link></li>
              <li className="flex items-center gap-2"><Mail className="w-4 h-4" /> tlsappointmentchecker@gmail.com</li>
            </ul>
          </div>
        </div>

        <div className="border-t border-white/5 mt-8 pt-8 text-center text-gray-400 text-xs">
          &copy; {new Date().getFullYear()} TLS Appointment Checker. {t.footer.rights}
        </div>
      </div>
    </footer>
  );
}
// -- Reviews Display -------------------------------------------------

function ReviewsSection() {
  const { t, locale } = useLanguage();
  const [reviews, setReviews] = useState<any[]>([]);

  useEffect(() => {
    fetch("/api/ratings?limit=3")
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) setReviews(data);
      })
      .catch(console.error);
  }, []);

  if (reviews.length === 0) return null;

  return (
    <section className="py-32 relative bg-dark-700/20 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-t from-dark-800 via-transparent to-transparent pointer-events-none" />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <AnimatedSection className="text-center mb-16">
          <motion.h2 variants={fadeUp} className="text-4xl sm:text-5xl font-display font-bold mb-4 tracking-tight">
            {locale === "ar" ? "ماذا يقول عملاؤنا" : locale === "de" ? "Was unsere Kunden sagen" : "What Our Customers Say"}
          </motion.h2>
          <motion.div variants={fadeUp} className="w-24 h-1 bg-gradient-to-r from-primary-400 to-cyan-400 mx-auto rounded-full mt-6" />
        </AnimatedSection>
        <div className="grid gap-8 md:grid-cols-3 mb-16">
          {reviews.map((r: any, i: number) => (
            <AnimatedSection key={r.id}>
              <motion.div variants={fadeUp} className="glass-card p-8 border border-white/5 shadow-2xl rounded-2xl h-full flex flex-col pt-10 bg-white/[0.02] backdrop-blur-xl hover:bg-white/[0.04] transition-all duration-500">
                <div className="flex text-[#FFD700] mb-6 space-x-1" dir="ltr">
                  {[...Array(5)].map((_, j) => (
                    <Star key={j} className="w-5 h-5 drop-shadow-md" fill={j < r.rating ? "currentColor" : "none"} />
                  ))}
                </div>
                <p className="text-gray-200 mb-8 flex-1 italic text-lg leading-relaxed font-medium">"{r.comment}"</p>
                <div className="text-xs text-gray-400 font-semibold border-t border-white/10 pt-5 flex justify-between items-center mt-auto tracking-wide">
                  <span className="flex items-center gap-1.5">{r.source === "desktop" ? "🖥️ Desktop App" : "🌐 Website"}</span>
                  <span className="opacity-70">{new Date(r.created_at).toLocaleDateString(locale === 'ar' ? 'ar-EG' : locale === 'de' ? 'de-DE' : 'en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
                </div>
              </motion.div>
            </AnimatedSection>
          ))}
        </div>
        <div className="text-center mt-12">
          <Link href="/reviews" className="group inline-flex items-center justify-center gap-3 px-8 h-14 rounded-full font-bold transition-all duration-300 bg-white/5 hover:bg-white/10 border border-white/10 text-white shadow-lg overflow-hidden relative">
            <span className="absolute inset-0 w-full h-full bg-gradient-to-r from-primary-500/20 to-cyan-500/20 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            <span className="relative z-10">{locale === "ar" ? "عرض جميع التقييمات" : locale === "de" ? "Alle Bewertungen ansehen" : "See All Reviews"}</span>
            <span className="relative z-10 group-hover:translate-x-1 transition-transform duration-300" dir="ltr">
            →
            </span>
          </Link>
        </div>
      </div>
    </section>
  );
}
// -- Page ------------------------------------------------

export default function LandingPage() {
  return (
    <main>
      <Navbar />
      <Hero />
      <Features />
      <HowItWorks />
      <Pricing />
      <ReviewsSection />
      <DownloadApp />
      <UserGuide />
      <FAQ />
      <RatingComponent />
      <CTA />
      <Footer />
    </main>
  );
}

