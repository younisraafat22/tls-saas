"use client";

import { motion, useInView } from "framer-motion";
import { useRef, useState, useEffect } from "react";
import Link from "next/link";
import {
  Bell, Shield, Globe, Zap, Clock, Smartphone,
  Check, ChevronDown, ChevronUp, ArrowRight,
  Mail, Monitor,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { subscriptionApi } from "@/lib/api";
import { useLanguage, localeLabels, type Locale } from "@/lib/i18n";

// ── Language Switcher ───────────────────────────────────

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

// ── Animation Variants ─────────────────────────────────

const fadeUp = {
  hidden: { opacity: 0, y: 40 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } },
};

const fadeIn = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.8 } },
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

// ── Animated Section wrapper ────────────────────────────

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

// ── Particle Background ─────────────────────────────────

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

// ── Counter Animation ───────────────────────────────────

function Counter({ target, suffix = "" }: { target: number; suffix?: string }) {
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

  return <span ref={ref}>{count}{suffix}</span>;
}

// ── Navbar ──────────────────────────────────────────────

function Navbar() {
  const { user } = useAuth();
  const { t } = useLanguage();
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
            <a href="#faq" className="text-gray-400 hover:text-white transition-colors text-sm">{t.nav.faq}</a>
          </div>

          <div className="flex items-center gap-2">
            <LangSwitcher />
            {user ? (
              <Link href={user.is_admin ? "/admin" : "/dashboard"} className="btn-gradient text-sm !py-2 !px-5">
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

        {/* Mobile menu — nav has bg-dark-900 when mobileOpen */}
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
              <a href="#faq" className="px-4 py-2.5 text-gray-300 hover:text-white hover:bg-white/5 rounded-lg transition-colors" onClick={() => setMobileOpen(false)}>{t.nav.faq}</a>
              {!user && (
                <Link href="/login" className="px-4 py-2.5 text-gray-300 hover:text-white hover:bg-white/5 rounded-lg transition-colors" onClick={() => setMobileOpen(false)}>{t.nav.logIn}</Link>
              )}
            </div>
          </motion.div>
        )}
      </div>
    </motion.nav>
  );
}

// ── Hero Section ────────────────────────────────────────

function Hero() {
  const { t } = useLanguage();
  return (
    <section className="relative min-h-screen flex items-center pt-20 overflow-hidden">
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

          {/* Hero visual — animated dashboard mockup */}
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
            { value: 24, suffix: "/7", label: t.stats.monitoring },
            { value: 30, suffix: "min", label: t.stats.checkInterval },
            { value: 3, suffix: "", label: t.stats.alertChannels },
          ].map((stat) => (
            <motion.div key={stat.label} variants={fadeUp} className="text-center">
              <div className="text-3xl font-display font-bold text-primary-400">
                <Counter target={stat.value} suffix={stat.suffix} />
              </div>
              <div className="text-sm text-gray-500 mt-1">{stat.label}</div>
            </motion.div>
          ))}
        </AnimatedSection>
      </div>
    </section>
  );
}

// ── Features Section ────────────────────────────────────

function Features() {
  const { t } = useLanguage();
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

// ── How It Works ────────────────────────────────────────

function HowItWorks() {
  const { t } = useLanguage();

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

// ── Pricing Section ─────────────────────────────────────

function Pricing() {
  const { t } = useLanguage();
  const [plans, setPlans] = useState<any[]>([]);

  useEffect(() => {
    subscriptionApi.getPlans().then(setPlans).catch(() => {
      // Fallback plans if API not reachable
      setPlans([
        { id: 1, plan_type: "legalization", display_name: "Legalization Monitor", price_monthly: 500, currency: "EGP", features: ["Sheikh Zayed & Hurghada branches", "Email notifications", "Web push notifications", "Real-time dashboard", "30-minute check interval"], sort_order: 1 },
      ]);
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

        <AnimatedSection className="grid md:grid-cols-2 gap-8 max-w-3xl mx-auto">
          {plans.sort((a, b) => a.sort_order - b.sort_order).map((plan) => {
            return (
              <motion.div
                key={plan.id}
                variants={scaleIn}
                className="glass-card p-8 relative border-primary-500/30 ring-1 ring-primary-500/20"
              >
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-gradient-to-r from-primary-500 to-blue-600 text-white text-xs font-bold px-4 py-1 rounded-full">
                  EARLY ACCESS
                </div>

                <h3 className="font-display font-bold text-xl mb-2">{plan.display_name}</h3>
                <div className="flex items-baseline gap-1 mb-6">
                  <span className="text-4xl font-display font-bold">{plan.price_monthly}</span>
                  <span className="text-gray-400 text-sm">{plan.currency}{t.pricing.perMonth}</span>
                </div>

                <ul className="space-y-3 mb-8">
                  {t.planFeatures.map((feat) => (
                    <li key={feat} className="flex items-start gap-2 text-sm">
                      <Check className="w-4 h-4 text-accent-green mt-0.5 shrink-0" />
                      <span className="text-gray-300">{feat}</span>
                    </li>
                  ))}
                </ul>

                <Link
                  href="/register"
                  className="block w-full text-center py-3 rounded-xl font-semibold transition-all btn-gradient"
                >
                  {t.pricing.getStarted}
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

// ── FAQ ─────────────────────────────────────────────────

function FAQ() {
  const { t } = useLanguage();
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

// ── CTA Section ─────────────────────────────────────────

function CTA() {
  const { t } = useLanguage();
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

// ── Footer ──────────────────────────────────────────────

function Footer() {
  const { t } = useLanguage();
  return (
    <footer className="py-12 border-t border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid md:grid-cols-3 gap-8">
          <div>
            <div className="flex items-center gap-2 mb-4">
              <img src="/icons/icon-192-white.png" alt="TLS Appointment Checker" className="w-8 h-8 rounded-lg" />
              <span className="font-display font-bold">TLS Appointment Checker</span>
            </div>
            <p className="text-gray-500 text-sm">{t.footer.desc}</p>
          </div>

          <div>
            <h4 className="font-semibold mb-4">{t.footer.quickLinks}</h4>
            <ul className="space-y-2 text-sm text-gray-400">
              <li><a href="#features" className="hover:text-white transition-colors">{t.footer.features}</a></li>
              <li><a href="#pricing" className="hover:text-white transition-colors">{t.footer.pricing}</a></li>
              <li><a href="#faq" className="hover:text-white transition-colors">{t.footer.faq}</a></li>
              <li><Link href="/login" className="hover:text-white transition-colors">{t.footer.logIn}</Link></li>
            </ul>
          </div>

          <div>
            <h4 className="font-semibold mb-4">{t.footer.legal}</h4>
            <ul className="space-y-2 text-sm text-gray-400">
              <li><Link href="/terms" className="hover:text-white transition-colors">{t.footer.terms}</Link></li>
              <li><Link href="/privacy" className="hover:text-white transition-colors">{t.footer.privacy}</Link></li>
              <li><Link href="/contact" className="flex items-center gap-2 hover:text-white transition-colors"><Mail className="w-4 h-4" /> {t.footer.contact}</Link></li>
              <li className="flex items-center gap-2"><Mail className="w-4 h-4" /> tlsappointmentchecker@gmail.com</li>
            </ul>
          </div>
        </div>

        <div className="border-t border-white/5 mt-8 pt-8 text-center text-gray-500 text-xs">
          &copy; {new Date().getFullYear()} TLS Appointment Checker. {t.footer.rights}
        </div>
      </div>
    </footer>
  );
}

// ── Page ────────────────────────────────────────────────

export default function LandingPage() {
  return (
    <main>
      <Navbar />
      <Hero />
      <Features />
      <HowItWorks />
      <Pricing />
      <FAQ />
      <CTA />
      <Footer />
    </main>
  );
}
