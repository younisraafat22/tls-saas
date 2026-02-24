"use client";

import { useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { motion } from "framer-motion";
import { Smartphone, Download, Share, Plus, ArrowRight } from "lucide-react";

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
};

export default function IOSInstallPage() {
  return (
    <div className="min-h-screen bg-dark-900 text-white">
      {/* Header */}
      <header className="border-b border-white/5 bg-dark-800/80 backdrop-blur-lg sticky top-0 z-30">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <img src="/icons/icon-192-white.png" alt="TLS Appointment Checker" className="w-8 h-8 rounded-lg" />
            <span className="font-display font-bold text-lg">TLS Appointment Checker</span>
          </Link>
          <Link href="/login" className="btn-gradient text-sm !py-2 !px-4">
            Open App
          </Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-12 space-y-12">
        {/* Hero */}
        <motion.div initial={fadeUp.hidden} animate={fadeUp.visible} className="text-center space-y-4">
          <div className="inline-flex items-center gap-2 bg-white/5 border border-white/10 rounded-full px-4 py-1.5 text-sm text-gray-300">
            <Smartphone className="w-4 h-4" /> iOS App
          </div>
          <h1 className="text-4xl font-display font-bold">
            Install on Your iPhone
          </h1>
          <p className="text-gray-400 text-lg max-w-lg mx-auto">
            Get TLS Appointment Checker as a native-like app on your iPhone or iPad.
            No App Store download required.
          </p>
        </motion.div>

        {/* App Preview */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
          className="glass-card p-8 text-center"
        >
          <img src="/icons/icon-512-white.png" alt="TLS Appointment Checker" className="w-24 h-24 rounded-2xl mx-auto mb-4 shadow-lg shadow-primary-500/20" />
          <h3 className="font-display font-bold text-xl">TLS Appointment Checker</h3>
          <p className="text-gray-400 text-sm mt-1">Never Miss Your Appointment</p>
          <div className="flex items-center justify-center gap-4 mt-4 text-sm text-gray-500">
            <span>Free</span>
            <span>&middot;</span>
            <span>Works Offline</span>
            <span>&middot;</span>
            <span>Push Notifications</span>
          </div>
        </motion.div>

        {/* Installation Steps */}
        <div className="space-y-6">
          <h2 className="text-2xl font-display font-bold text-center">How to Install</h2>
          <div className="space-y-4">
            <StepCard
              number={1}
              icon={<Share className="w-5 h-5" />}
              title="Open in Safari"
              description="Open this website in Safari browser (not Chrome or other browsers). Safari is required for iOS PWA installation."
            />
            <StepCard
              number={2}
              icon={<Share className="w-5 h-5" />}
              title="Tap the Share Button"
              description='Tap the Share button (square with arrow pointing up) at the bottom of Safari.'
            />
            <StepCard
              number={3}
              icon={<Plus className="w-5 h-5" />}
              title='Select "Add to Home Screen"'
              description='Scroll down in the share menu and tap "Add to Home Screen". You may need to scroll to find this option.'
            />
            <StepCard
              number={4}
              icon={<Download className="w-5 h-5" />}
              title='Tap "Add"'
              description="Confirm the name and tap Add. The app icon will appear on your home screen just like a native app."
            />
          </div>
        </div>

        {/* Benefits */}
        <div className="glass-card p-6 space-y-4">
          <h3 className="font-semibold text-lg">What You Get</h3>
          <div className="grid sm:grid-cols-2 gap-3">
            {[
              "Full-screen app experience",
              "Push notifications for appointments",
              "Works even with poor connection",
              "Home screen icon like native apps",
              "No App Store needed",
              "Always up-to-date automatically",
            ].map((feature) => (
              <div key={feature} className="flex items-center gap-2 text-sm text-gray-300">
                <div className="w-1.5 h-1.5 rounded-full bg-accent-green" />
                {feature}
              </div>
            ))}
          </div>
        </div>

        {/* CTA */}
        <div className="text-center space-y-4">
          <Link href="/register" className="btn-gradient inline-flex items-center gap-2 text-lg !px-8 !py-3">
            Get Started <ArrowRight className="w-5 h-5" />
          </Link>
          <p className="text-gray-500 text-sm">
            Already have an account? <Link href="/login" className="text-primary-400 hover:underline">Sign in</Link>
          </p>
        </div>
      </main>
    </div>
  );
}

function StepCard({ number, icon, title, description }: {
  number: number;
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <motion.div
      initial={fadeUp.hidden}
      animate={fadeUp.visible}
      transition={{ delay: number * 0.1 }}
      className="glass-card p-5 flex items-start gap-4"
    >
      <div className="w-10 h-10 rounded-xl bg-primary-500/10 flex items-center justify-center flex-shrink-0 text-primary-400 font-bold">
        {number}
      </div>
      <div>
        <h4 className="font-semibold flex items-center gap-2">{icon} {title}</h4>
        <p className="text-sm text-gray-400 mt-1">{description}</p>
      </div>
    </motion.div>
  );
}
