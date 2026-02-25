"use client";

import Link from "next/link";
import { ArrowLeft, Shield } from "lucide-react";
import { useLanguage } from "@/lib/i18n";

export default function PrivacyPage() {
  const { t } = useLanguage();
  const tr = t.privacy;

  return (
    <div className="min-h-screen bg-dark-950 text-white">
      <div className="max-w-3xl mx-auto px-6 py-16">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm text-gray-400 hover:text-white mb-10 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> {tr.backToHome}
        </Link>

        <h1 className="text-3xl font-display font-bold mb-2">{tr.title}</h1>
        <p className="text-gray-500 text-sm mb-10">{tr.effectiveDate}</p>

        {/* Summary Banner */}
        <div className="flex items-start gap-3 bg-primary-500/10 border border-primary-500/20 rounded-xl p-4 mb-10">
          <Shield className="w-5 h-5 text-primary-400 mt-0.5 shrink-0" />
          <div>
            <p className="text-primary-300 font-semibold text-sm">{tr.summaryTitle}</p>
            <p className="text-primary-200/70 text-sm mt-0.5">{tr.summaryBody}</p>
          </div>
        </div>

        <div className="space-y-8 text-gray-300 text-sm leading-relaxed">
          {tr.sections.map((s) => (
            <section key={s.heading}>
              <h2 className="text-white font-semibold text-base mb-3">{s.heading}</h2>
              {s.paras.map((p, i) => (
                <p key={i} className={i > 0 ? "mt-3" : ""}>{p}</p>
              ))}
              {s.list.length > 0 && (
                <ul className="list-disc ml-5 mt-2 space-y-1">
                  {s.list.map((item, i) => <li key={i}>{item}</li>)}
                </ul>
              )}
              {s.paras2.map((p, i) => (
                <p key={i} className="mt-3">{p}</p>
              ))}
            </section>
          ))}
        </div>

        <div className="mt-12 pt-8 border-t border-white/10 flex gap-4 text-sm text-gray-500">
          <Link href="/terms" className="hover:text-gray-300 transition-colors">{tr.footerTerms}</Link>
          <span>·</span>
          <Link href="/" className="hover:text-gray-300 transition-colors">{tr.footerHome}</Link>
        </div>
      </div>
    </div>
  );
}

    <div className="min-h-screen bg-dark-950 text-white">
      <div className="max-w-3xl mx-auto px-6 py-16">
        {/* Back */}
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm text-gray-400 hover:text-white mb-10 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Home
        </Link>

        <h1 className="text-3xl font-display font-bold mb-2">Privacy Policy</h1>
        <p className="text-gray-500 text-sm mb-10">Effective date: June 2025 &nbsp;·&nbsp; Last updated: June 2025</p>

        {/* Brief Summary */}
        <div className="flex items-start gap-3 bg-primary-500/10 border border-primary-500/20 rounded-xl p-4 mb-10">
          <Shield className="w-5 h-5 text-primary-400 mt-0.5 shrink-0" />
          <div>
            <p className="text-primary-300 font-semibold text-sm">Privacy Summary</p>
            <p className="text-primary-200/70 text-sm mt-0.5">
              We collect only what is necessary to run the Service. We do not sell your data, share it with advertisers,
              or use it for any purpose other than operating TLS Appointment Checker.
            </p>
          </div>
        </div>

        <div className="space-y-8 text-gray-300 text-sm leading-relaxed">
          <section>
            <h2 className="text-white font-semibold text-base mb-3">1. Who We Are</h2>
            <p>
              TLS Appointment Checker ("we", "us", "our") is an independent appointment monitoring service for
              legalization appointments at TLS Contact branches in Egypt. We are not affiliated with TLS Contact or any
              embassy or government authority.
            </p>
          </section>

          <section>
            <h2 className="text-white font-semibold text-base mb-3">2. Information We Collect</h2>

            <h3 className="text-gray-200 font-medium mt-4 mb-2">a) Account Information</h3>
            <ul className="list-disc ml-5 space-y-1">
              <li><strong className="text-white">Email address</strong> — used for login, account communication, and appointment notifications</li>
              <li><strong className="text-white">Password</strong> — stored as a bcrypt hash; we never store your plain-text password</li>
            </ul>

            <h3 className="text-gray-200 font-medium mt-4 mb-2">b) Payment Information</h3>
            <p>
              Payments are made manually via <strong className="text-white">InstaPay</strong> or{" "}
              <strong className="text-white">Vodafone Cash</strong>. We do not collect or store any card numbers, bank
              account details, or financial credentials. We only retain proof of payment (screenshot/reference) and
              payment status for subscription management.
            </p>

            <h3 className="text-gray-200 font-medium mt-4 mb-2">c) Notification Preferences</h3>
            <p>
              Your notification delivery preferences (email, WhatsApp, browser push) and any contact handles you
              provide for these channels.
            </p>

            <h3 className="text-gray-200 font-medium mt-4 mb-2">d) Usage Data</h3>
            <p>
              Basic technical logs including appointment check results associated with your subscription branch. These
              logs are used for debugging and Service improvement only.
            </p>
          </section>

          <section>
            <h2 className="text-white font-semibold text-base mb-3">3. How We Use Your Information</h2>
            <ul className="list-disc ml-5 space-y-1">
              <li>To create and manage your account</li>
              <li>To process your subscription payment</li>
              <li>To send you appointment availability notifications</li>
              <li>To respond to your support requests</li>
              <li>To improve the reliability and accuracy of the Service</li>
            </ul>
            <p className="mt-3">
              We do <strong className="text-white">not</strong> use your information for targeted advertising, profiling,
              or any purpose unrelated to operating the Service.
            </p>
          </section>

          <section>
            <h2 className="text-white font-semibold text-base mb-3">4. Data Sharing</h2>
            <p>
              We do not sell, rent, or share your personal data with third parties except as strictly necessary to
              operate the Service:
            </p>
            <ul className="list-disc ml-5 mt-2 space-y-1">
              <li><strong className="text-white">InstaPay / Vodafone Cash</strong> — payment references are kept for subscription verification only</li>
              <li><strong className="text-white">WhatsApp</strong> — only if you opt in and provide your number; used solely to deliver your notifications</li>
              <li><strong className="text-white">Hosting providers</strong> — our server infrastructure providers may have access to data stored on their servers, subject to their own privacy policies</li>
            </ul>
            <p className="mt-3">
              We may disclose your information if required by law or to protect the rights and safety of the Service
              and its users.
            </p>
          </section>

          <section>
            <h2 className="text-white font-semibold text-base mb-3">5. Data Retention</h2>
            <p>
              We retain your account data for as long as your account is active. Check result logs are retained for up
              to 30 days for debugging purposes, after which they are deleted automatically. If you cancel your
              subscription, your account data may be retained for up to 90 days before permanent deletion.
            </p>
          </section>

          <section>
            <h2 className="text-white font-semibold text-base mb-3">6. Your Rights</h2>
            <p>You have the right to:</p>
            <ul className="list-disc ml-5 mt-2 space-y-1">
              <li><strong className="text-white">Access</strong> the personal data we hold about you</li>
              <li><strong className="text-white">Correct</strong> inaccurate data</li>
              <li><strong className="text-white">Delete</strong> your account and associated data</li>
              <li><strong className="text-white">Withdraw consent</strong> for notification channels at any time from Settings</li>
            </ul>
            <p className="mt-3">
              To exercise any of these rights, contact us at{" "}
              <a href="mailto:support@tlschecker.com" className="text-primary-400 hover:underline">
                support@tlschecker.com
              </a>
              . We will respond within 14 days.
            </p>
          </section>

          <section>
            <h2 className="text-white font-semibold text-base mb-3">7. Security</h2>
            <p>
              We take reasonable technical measures to protect your data, including encrypted storage, hashed passwords,
              and HTTPS connections. However, no system is completely secure, and we cannot guarantee absolute security.
            </p>
          </section>

          <section>
            <h2 className="text-white font-semibold text-base mb-3">8. Cookies</h2>
            <p>
              The Service uses a minimal session cookie to keep you logged in. We do not use tracking cookies,
              analytics cookies, or advertising cookies.
            </p>
          </section>

          <section>
            <h2 className="text-white font-semibold text-base mb-3">9. Children's Privacy</h2>
            <p>
              The Service is not directed at children under 18. We do not knowingly collect personal data from minors.
              If you believe a minor has created an account, please contact us to have it removed.
            </p>
          </section>

          <section>
            <h2 className="text-white font-semibold text-base mb-3">10. Changes to This Policy</h2>
            <p>
              We may update this Privacy Policy at any time. We will notify you of significant changes via email or a
              prominent notice on the Service. Continued use after changes means you accept the updated policy.
            </p>
          </section>

          <section>
            <h2 className="text-white font-semibold text-base mb-3">11. Contact</h2>
            <p>
              If you have questions or concerns about this Privacy Policy, please email us at{" "}
              <a href="mailto:support@tlschecker.com" className="text-primary-400 hover:underline">
                support@tlschecker.com
              </a>
              .
            </p>
          </section>
        </div>

        <div className="mt-12 pt-8 border-t border-white/10 flex gap-4 text-sm text-gray-500">
          <Link href="/terms" className="hover:text-gray-300 transition-colors">Terms &amp; Conditions</Link>
          <span>·</span>
          <Link href="/" className="hover:text-gray-300 transition-colors">Home</Link>
        </div>
      </div>
    </div>
  );
}
