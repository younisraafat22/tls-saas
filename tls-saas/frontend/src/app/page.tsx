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
        scrolled ? "bg-dark-800/95 backdrop-blur-xl shadow-lg shadow-black/20 border-b border-white/5" : ""
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 sm:h-20">
          <Link href="/" className="flex items-center gap-2">
            <img src="/icons/icon-192-white.png" alt="TLS Appointment Checker" className="w-8 h-8 rounded-lg" />
            <span className="font-display font-bold text-lg hidden sm:block">TLS Appointment Checker</span>
          </Link>

          <div className="hidden md:flex items-center gap-8">
            <a href="#features" className="text-gray-400 hover:text-white transition-colors text-sm">Features</a>
            <a href="#how-it-works" className="text-gray-400 hover:text-white transition-colors text-sm">How It Works</a>
            <a href="#pricing" className="text-gray-400 hover:text-white transition-colors text-sm">Pricing</a>
            <a href="#faq" className="text-gray-400 hover:text-white transition-colors text-sm">FAQ</a>
          </div>

          <div className="flex items-center gap-3">
            {user ? (
              <Link href={user.is_admin ? "/admin" : "/dashboard"} className="btn-gradient text-sm !py-2 !px-5">
                Dashboard
              </Link>
            ) : (
              <>
                <Link href="/login" className="text-gray-400 hover:text-white transition-colors text-sm hidden sm:block">
                  Log In
                </Link>
                <Link href="/register" className="btn-gradient text-sm !py-2 !px-5">
                  Get Started
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

        {/* Mobile menu */}
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="md:hidden pb-4 border-t border-white/5"
          >
            <div className="flex flex-col gap-2 pt-4">
              <a href="#features" className="px-4 py-2 text-gray-400 hover:text-white" onClick={() => setMobileOpen(false)}>Features</a>
              <a href="#how-it-works" className="px-4 py-2 text-gray-400 hover:text-white" onClick={() => setMobileOpen(false)}>How It Works</a>
              <a href="#pricing" className="px-4 py-2 text-gray-400 hover:text-white" onClick={() => setMobileOpen(false)}>Pricing</a>
              <a href="#faq" className="px-4 py-2 text-gray-400 hover:text-white" onClick={() => setMobileOpen(false)}>FAQ</a>
            </div>
          </motion.div>
        )}
      </div>
    </motion.nav>
  );
}

// ── Hero Section ────────────────────────────────────────

function Hero() {
  return (
    <section className="relative min-h-screen flex items-center pt-20 overflow-hidden">
      <Particles />
      <div className="bg-radial-glow absolute inset-0" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <motion.div initial="hidden" animate="visible" variants={staggerContainer}>
            <motion.div variants={fadeUp} className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary-500/10 border border-primary-500/20 mb-6">
              <span className="status-dot active" />
              <span className="text-primary-400 text-sm font-medium">Live Monitoring Active</span>
            </motion.div>

            <motion.h1 variants={fadeUp} className="text-4xl sm:text-5xl lg:text-6xl font-display font-bold leading-tight mb-6">
              Never Miss Your{" "}
              <span className="bg-gradient-to-r from-primary-400 to-blue-500 bg-clip-text text-transparent">
                TLS Appointment
              </span>{" "}
              Again
            </motion.h1>

            <motion.p variants={fadeUp} className="text-lg text-gray-400 mb-8 max-w-lg">
              24/7 automated monitoring for German document legalization appointments in Egypt.
            </motion.p>

            <motion.div variants={fadeUp} className="flex flex-wrap gap-4 mb-10">
              <Link href="/register" className="btn-gradient text-base flex items-center gap-2 !px-8 !py-4">
                Start Monitoring <ArrowRight className="w-5 h-5" />
              </Link>
              <a href="#how-it-works" className="btn-outline text-base !px-8 !py-4">
                Learn More
              </a>
            </motion.div>

            <motion.div variants={fadeUp} className="flex flex-wrap gap-6 text-sm text-gray-400">
              {["Email Alerts", "Works on Phone"].map((item) => (
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
                    <span className="text-sm font-medium">Monitoring Active</span>
                  </div>
                  <span className="text-xs text-gray-500">Live</span>
                </div>

                {/* Branch cards */}
                {[
                  { name: "Sheikh Zayed", type: "Legalization", status: "Checking...", color: "text-primary-400" },
                  { name: "Hurghada", type: "Legalization", status: "No slots", color: "text-gray-400" },
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
                  🎉 Slots Open!
                </motion.div>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Stats bar */}
        <AnimatedSection className="grid grid-cols-2 md:grid-cols-4 gap-6 mt-20 pt-10 border-t border-white/5">
          {[
            { value: 2, suffix: "", label: "Branches Monitored" },
            { value: 24, suffix: "/7", label: "Monitoring" },
            { value: 30, suffix: "min", label: "Check Interval" },
            { value: 3, suffix: "", label: "Alert Channels" },
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
  const features = [
    { icon: Bell, title: "Instant Notifications", desc: "Email and browser push — get alerted the second a slot opens, even on your phone." },
    { icon: Shield, title: "Secure & Private", desc: "Your data stays safe. Encrypted credentials, secure auth, and no data sharing. Ever." },
    { icon: Globe, title: "Both Branches", desc: "Monitor Sheikh Zayed & Hurghada legalization branches — both covered under one subscription." },
    { icon: Zap, title: "Lightning Fast", desc: "Our server checks every 30 minutes. When slots appear, you know within seconds." },
    { icon: Clock, title: "24/7 Monitoring", desc: "Our server never sleeps. It checks around the clock so you don't have to." },
    { icon: Smartphone, title: "Mobile Friendly", desc: "Check your dashboard from any device. Your phone, tablet, or computer." },
  ];

  return (
    <section id="features" className="py-24 relative">
      <div className="bg-grid absolute inset-0 opacity-50" />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
        <AnimatedSection className="text-center mb-16">
          <motion.h2 variants={fadeUp} className="text-3xl sm:text-4xl font-display font-bold mb-4">
            Why Choose <span className="text-primary-400">TLS Appointment Checker</span>?
          </motion.h2>
          <motion.p variants={fadeUp} className="text-gray-400 max-w-2xl mx-auto">
            Stop refreshing the TLS website manually. Let our server do the work while you live your life.
          </motion.p>
        </AnimatedSection>

        <AnimatedSection className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((f) => (
            <motion.div key={f.title} variants={scaleIn} className="glass-card p-6 group">
              <div className="w-12 h-12 rounded-xl bg-primary-500/10 flex items-center justify-center mb-4 group-hover:bg-primary-500/20 transition-colors">
                <f.icon className="w-6 h-6 text-primary-400" />
              </div>
              <h3 className="font-semibold text-lg mb-2">{f.title}</h3>
              <p className="text-gray-400 text-sm leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </AnimatedSection>
      </div>
    </section>
  );
}

// ── How It Works ────────────────────────────────────────

function HowItWorks() {
  const steps = [
    { num: "01", title: "Create Account", desc: "Sign up in seconds with just your email. No downloads, no installations." },
    { num: "02", title: "Subscribe", desc: "One simple plan for document legalization monitoring. Pay via Vodafone Cash or Instapay." },
    { num: "03", title: "Select Branches", desc: "Choose which TLS branches to monitor. Our server handles the rest." },
    { num: "04", title: "Get Notified", desc: "Receive instant alerts via email or push notification when slots open." },
  ];

  return (
    <section id="how-it-works" className="py-24 bg-dark-700/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimatedSection className="text-center mb-16">
          <motion.h2 variants={fadeUp} className="text-3xl sm:text-4xl font-display font-bold mb-4">
            How It <span className="text-primary-400">Works</span>
          </motion.h2>
          <motion.p variants={fadeUp} className="text-gray-400 max-w-2xl mx-auto">
            Get started in under 2 minutes. No software to install — everything runs in your browser.
          </motion.p>
        </AnimatedSection>

        <AnimatedSection className="grid md:grid-cols-4 gap-8">
          {steps.map((step, i) => (
            <motion.div key={step.num} variants={fadeUp} className="relative text-center">
              {/* Connector line */}
              {i < steps.length - 1 && (
                <div className="hidden md:block absolute top-8 left-[60%] w-[80%] h-px bg-gradient-to-r from-primary-500/50 to-transparent" />
              )}

              <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-primary-500 to-blue-600 flex items-center justify-center mb-4 text-xl font-bold">
                {step.num}
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
            Simple, <span className="text-primary-400">Transparent</span> Pricing
          </motion.h2>
          <motion.p variants={fadeUp} className="text-gray-400 max-w-2xl mx-auto">
            Choose the plan that fits your needs. No hidden fees, cancel anytime.
          </motion.p>
        </AnimatedSection>

        <AnimatedSection className="grid md:grid-cols-1 gap-8 max-w-lg mx-auto">
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
                  <span className="text-gray-400 text-sm">{plan.currency}/mo</span>
                </div>

                <ul className="space-y-3 mb-8">
                  {(plan.features || []).map((feat: string) => (
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
                  Get Started
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
          Pay via Vodafone Cash or Instapay. Subscription activated within a few hours.
        </motion.p>
      </div>
    </section>
  );
}

// ── FAQ ─────────────────────────────────────────────────

function FAQ() {
  const faqs = [
    { q: "How does monitoring work?", a: "Our server checks TLS appointment availability every 30 minutes for all branches. When a slot opens, all subscribers monitoring that branch are instantly notified via email and web push." },
    { q: "Do I need to keep my computer on?", a: "No! Everything runs on our server 24/7. You just need an internet connection to receive notifications — on your phone, tablet, or any device." },
    { q: "How fast will I be notified?", a: "Within seconds of detecting available slots. Our system sends notifications via multiple channels simultaneously to maximize your chances of booking." },
    { q: "What payment methods do you accept?", a: "We currently accept Vodafone Cash and Instapay. After payment, our team verifies and activates your subscription, usually within a few hours." },
    { q: "Can I monitor multiple branches?", a: "Yes! Your legalization subscription covers both Sheikh Zayed and Hurghada branches simultaneously." },
    { q: "What happens when my subscription expires?", a: "Monitoring stops and you won't receive notifications. You can renew at any time to resume monitoring." },
    { q: "Is this an early access service?", a: "Yes — this is an early access release. While we strive for reliability, we cannot guarantee 100% uptime or uninterrupted monitoring. By using the service you agree to our Terms & Conditions." },
  ];

  const [open, setOpen] = useState<number | null>(null);

  return (
    <section id="faq" className="py-24 bg-dark-700/30">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimatedSection className="text-center mb-12">
          <motion.h2 variants={fadeUp} className="text-3xl sm:text-4xl font-display font-bold mb-4">
            Frequently Asked <span className="text-primary-400">Questions</span>
          </motion.h2>
        </AnimatedSection>

        <AnimatedSection className="space-y-3">
          {faqs.map((faq, i) => (
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
  return (
    <section className="py-24 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-r from-primary-500/10 via-blue-600/10 to-purple-600/10" />
      <div className="max-w-4xl mx-auto px-4 text-center relative z-10">
        <AnimatedSection>
          <motion.h2 variants={fadeUp} className="text-3xl sm:text-4xl font-display font-bold mb-4">
            Ready to Stop Refreshing?
          </motion.h2>
          <motion.p variants={fadeUp} className="text-gray-400 mb-8 text-lg">
            Join others who are getting instant notifications when TLS appointment slots open.
          </motion.p>
          <motion.div variants={fadeUp}>
            <Link href="/register" className="btn-gradient text-lg !px-10 !py-4 inline-flex items-center gap-2">
              Get Started Now <ArrowRight className="w-5 h-5" />
            </Link>
          </motion.div>
        </AnimatedSection>
      </div>
    </section>
  );
}

// ── Footer ──────────────────────────────────────────────

function Footer() {
  return (
    <footer className="py-12 border-t border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid md:grid-cols-3 gap-8">
          <div>
            <div className="flex items-center gap-2 mb-4">
              <img src="/icons/icon-192-white.png" alt="TLS Appointment Checker" className="w-8 h-8 rounded-lg" />
              <span className="font-display font-bold">TLS Appointment Checker</span>
            </div>
            <p className="text-gray-500 text-sm">Automated appointment monitoring for German document legalization services in Egypt.</p>
            <div className="flex items-center gap-3 mt-4">
              <Link href="/ios" className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-sm text-gray-300 hover:text-white hover:border-white/20 transition-all">
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg>
                iOS
              </Link>
              <Link href="/android" className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-sm text-gray-300 hover:text-white hover:border-white/20 transition-all">
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M17.6 9.48l1.84-3.18c.16-.31.04-.69-.27-.86-.31-.16-.69-.04-.86.27l-1.86 3.22c-1.44-.65-3.05-1.01-4.76-1.01-1.71 0-3.32.36-4.76 1.01L5.08 5.71c-.16-.31-.55-.43-.86-.27-.31.16-.43.55-.27.86l1.84 3.18C2.72 11.4.63 14.48.63 18h22.74c0-3.52-2.09-6.6-5.13-8.52zM7 15.25c-.69 0-1.25-.56-1.25-1.25s.56-1.25 1.25-1.25 1.25.56 1.25 1.25-.56 1.25-1.25 1.25zm10 0c-.69 0-1.25-.56-1.25-1.25s.56-1.25 1.25-1.25 1.25.56 1.25 1.25-.56 1.25-1.25 1.25z"/></svg>
                Android
              </Link>
            </div>
          </div>

          <div>
            <h4 className="font-semibold mb-4">Quick Links</h4>
            <ul className="space-y-2 text-sm text-gray-400">
              <li><a href="#features" className="hover:text-white transition-colors">Features</a></li>
              <li><a href="#pricing" className="hover:text-white transition-colors">Pricing</a></li>
              <li><a href="#faq" className="hover:text-white transition-colors">FAQ</a></li>
              <li><Link href="/login" className="hover:text-white transition-colors">Log In</Link></li>
              <li><Link href="/ios" className="hover:text-white transition-colors">iOS App</Link></li>
              <li><Link href="/android" className="hover:text-white transition-colors">Android App</Link></li>
            </ul>
          </div>

          <div>
            <h4 className="font-semibold mb-4">Legal</h4>
            <ul className="space-y-2 text-sm text-gray-400">
              <li><Link href="/terms" className="hover:text-white transition-colors">Terms &amp; Conditions</Link></li>
              <li><Link href="/privacy" className="hover:text-white transition-colors">Privacy Policy</Link></li>
              <li><Link href="/contact" className="flex items-center gap-2 hover:text-white transition-colors"><Mail className="w-4 h-4" /> Contact Form</Link></li>
              <li className="flex items-center gap-2"><Mail className="w-4 h-4" /> tlsappointmentchecker@gmail.com</li>
            </ul>
          </div>
        </div>

        <div className="border-t border-white/5 mt-8 pt-8 text-center text-gray-500 text-xs">
          &copy; {new Date().getFullYear()} TLS Appointment Checker. All rights reserved.
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
