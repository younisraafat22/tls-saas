"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Smartphone, Download, Plus, ArrowRight } from "lucide-react";

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
};

export default function AndroidInstallPage() {
  return (
    <div className="min-h-screen bg-dark-900 text-white">
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
        <motion.div initial={fadeUp.hidden} animate={fadeUp.visible} className="text-center space-y-4">
          <div className="inline-flex items-center gap-2 bg-white/5 border border-white/10 rounded-full px-4 py-1.5 text-sm text-gray-300">
            <Smartphone className="w-4 h-4" /> Android App
          </div>
          <h1 className="text-4xl font-display font-bold">Install on Your Android</h1>
          <p className="text-gray-400 text-lg max-w-lg mx-auto">
            Get TLS Appointment Checker as a native-like app on your Android device. No Play Store download required.
          </p>
        </motion.div>

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
            <span>&#183;</span>
            <span>Works Offline</span>
            <span>&#183;</span>
            <span>Push Notifications</span>
          </div>
        </motion.div>

        <div className="space-y-6">
          <h2 className="text-2xl font-display font-bold text-center">How to Install</h2>
          <div className="space-y-4">
            <StepCard
              number={1}
              title="Open in Chrome"
              description="Open this website in Google Chrome on your Android device."
            />
            <StepCard
              number={2}
              title="Look for the Install Banner"
              description="Chrome will show an Install app or Add to Home screen banner at the bottom. Tap it!"
            />
            <StepCard
              number={3}
              title="Tap Install"
              description="Confirm the installation. The app will be added to your home screen and app drawer."
            />
          </div>

          <div className="space-y-4 pt-4 border-t border-white/5">
            <h3 className="text-lg font-semibold text-gray-300">Alternative: Via Chrome Menu</h3>
            <StepCard
              number={1}
              title="Open Chrome Menu"
              description="Tap the three dots in the top-right corner of Chrome."
            />
            <StepCard
              number={2}
              title="Select Add to Home screen"
              description="Find this option in the menu and tap it to proceed."
            />
            <StepCard
              number={3}
              title="Confirm"
              description="Tap Add or Install. The app icon will appear on your home screen."
            />
          </div>
        </div>

        <div className="glass-card p-6 space-y-4">
          <h3 className="font-semibold text-lg">What You Get</h3>
          <div className="grid sm:grid-cols-2 gap-3">
            {[
              "Full-screen app experience",
              "Push notifications for appointments",
              "Works even with poor connection",
              "Home screen icon like native apps",
              "Shows in your app drawer",
              "Always up-to-date automatically",
            ].map((feature) => (
              <div key={feature} className="flex items-center gap-2 text-sm text-gray-300">
                <div className="w-1.5 h-1.5 rounded-full bg-accent-green" />
                {feature}
              </div>
            ))}
          </div>
        </div>

        <div className="text-center space-y-4">
          <Link href="/register" className="btn-gradient inline-flex items-center gap-2 text-lg !px-8 !py-3">
            Get Started <ArrowRight className="w-5 h-5" />
          </Link>
          <p className="text-gray-500 text-sm">
            Already have an account?{" "}
            <Link href="/login" className="text-primary-400 hover:underline">Sign in</Link>
          </p>
        </div>
      </main>
    </div>
  );
}

function StepCard({ number, title, description }: {
  number: number;
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
        <h4 className="font-semibold">{title}</h4>
        <p className="text-sm text-gray-400 mt-1">{description}</p>
      </div>
    </motion.div>
  );
}
