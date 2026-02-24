"use client";

import Link from "next/link";
import { ArrowLeft, AlertTriangle } from "lucide-react";

export default function TermsPage() {
  return (
    <div className="min-h-screen bg-dark-950 text-white">
      <div className="max-w-3xl mx-auto px-6 py-16">
        {/* Back */}
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm text-gray-400 hover:text-white mb-10 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Home
        </Link>

        <h1 className="text-3xl font-display font-bold mb-2">Terms &amp; Conditions</h1>
        <p className="text-gray-500 text-sm mb-10">Effective date: June 2025 &nbsp;·&nbsp; Last updated: June 2025</p>

        {/* Early Access Banner */}
        <div className="flex items-start gap-3 bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 mb-10">
          <AlertTriangle className="w-5 h-5 text-amber-400 mt-0.5 shrink-0" />
          <div>
            <p className="text-amber-300 font-semibold text-sm">Early Access Service</p>
            <p className="text-amber-200/70 text-sm mt-0.5">
              TLS Appointment Checker is currently in <strong>early access</strong>. The service is provided as-is,
              with no guarantees of uptime, availability, or accuracy. Features may change or be discontinued at any
              time without prior notice.
            </p>
          </div>
        </div>

        <div className="space-y-8 text-gray-300 text-sm leading-relaxed">
          <section>
            <h2 className="text-white font-semibold text-base mb-3">1. Acceptance of Terms</h2>
            <p>
              By accessing or using TLS Appointment Checker ("the Service"), you agree to be bound by these Terms &amp;
              Conditions. If you do not agree, please do not use the Service.
            </p>
          </section>

          <section>
            <h2 className="text-white font-semibold text-base mb-3">2. Service Description</h2>
            <p>
              TLS Appointment Checker is an automated monitoring tool that checks the TLS Contact website for
              legalization appointment availability at supported branches in Egypt (currently Sheikh Zayed and Hurghada).
              The Service notifies subscribers when appointment slots are detected.
            </p>
            <p className="mt-3">
              The Service does <strong className="text-white">not</strong> book appointments on your behalf, guarantee
              that detected slots will still be available when you attempt to book, or have any affiliation with TLS
              Contact or any embassy.
            </p>
          </section>

          <section>
            <h2 className="text-white font-semibold text-base mb-3">3. No Guarantee of Service</h2>
            <p>
              The Service is provided <strong className="text-white">"as is"</strong> and
              <strong className="text-white"> "as available"</strong> without warranties of any kind, either express or
              implied. We do not guarantee:
            </p>
            <ul className="list-disc ml-5 mt-2 space-y-1">
              <li>Continuous, uninterrupted, or error-free operation</li>
              <li>That monitoring checks will run on a fixed schedule</li>
              <li>Accuracy or completeness of appointment availability data</li>
              <li>That you will receive a notification before an appointment slot disappears</li>
              <li>Any specific response or detection time</li>
            </ul>
          </section>

          <section>
            <h2 className="text-white font-semibold text-base mb-3">4. Subscription &amp; Payments</h2>
            <p>
              The Service is offered on a monthly subscription basis. Payment is made manually via{" "}
              <strong className="text-white">InstaPay</strong> or{" "}
              <strong className="text-white">Vodafone Cash</strong>. Subscriptions are activated upon confirmation of
              payment.
            </p>
            <p className="mt-3">
              <strong className="text-white">All payments are non-refundable.</strong> We do not offer refunds for
              partial months, unused periods, missed notifications, or dissatisfaction with the Service.
            </p>
            <p className="mt-3">
              Subscription fees are subject to change. We will notify active subscribers at least 14 days before any
              price change takes effect.
            </p>
          </section>

          <section>
            <h2 className="text-white font-semibold text-base mb-3">5. User Responsibilities</h2>
            <p>You agree to:</p>
            <ul className="list-disc ml-5 mt-2 space-y-1">
              <li>Provide accurate information when registering</li>
              <li>Keep your account credentials confidential</li>
              <li>Use the Service solely for your own personal, non-commercial appointment needs</li>
              <li>Not attempt to reverse-engineer, scrape, abuse, or overload the Service</li>
              <li>Not use the Service in any way that violates applicable law</li>
            </ul>
          </section>

          <section>
            <h2 className="text-white font-semibold text-base mb-3">6. Limitation of Liability</h2>
            <p>
              To the fullest extent permitted by law, TLS Appointment Checker and its operators shall not be liable for
              any indirect, incidental, special, consequential, or punitive damages, including but not limited to:
            </p>
            <ul className="list-disc ml-5 mt-2 space-y-1">
              <li>Missed appointment slots due to delayed or failed notifications</li>
              <li>Financial losses resulting from inability to book an appointment</li>
              <li>Service downtime or data loss</li>
              <li>Changes to the TLS Contact website that affect the Service's functionality</li>
            </ul>
            <p className="mt-3">
              Our total liability to you for any claim arising from the use of the Service shall not exceed the amount
              you paid for the current billing month.
            </p>
          </section>

          <section>
            <h2 className="text-white font-semibold text-base mb-3">7. Termination</h2>
            <p>
              We reserve the right to suspend or terminate your account at any time, without notice, if we determine
              that you have violated these Terms or if continued operation of your account poses a risk to the Service
              or other users. No refund will be issued upon termination for breach.
            </p>
          </section>

          <section>
            <h2 className="text-white font-semibold text-base mb-3">8. Changes to These Terms</h2>
            <p>
              We may update these Terms at any time. Continued use of the Service after changes are posted constitutes
              acceptance of the new Terms. For significant changes, we will attempt to notify you via email.
            </p>
          </section>

          <section>
            <h2 className="text-white font-semibold text-base mb-3">9. Governing Law</h2>
            <p>
              These Terms are governed by and construed in accordance with the laws of the Arab Republic of Egypt.
              Any disputes shall be subject to the exclusive jurisdiction of the courts of Egypt.
            </p>
          </section>

          <section>
            <h2 className="text-white font-semibold text-base mb-3">10. Contact</h2>
            <p>
              For questions about these Terms, please contact us at{" "}
              <a href="mailto:support@tlschecker.com" className="text-primary-400 hover:underline">
                support@tlschecker.com
              </a>
              .
            </p>
          </section>
        </div>

        <div className="mt-12 pt-8 border-t border-white/10 flex gap-4 text-sm text-gray-500">
          <Link href="/privacy" className="hover:text-gray-300 transition-colors">Privacy Policy</Link>
          <span>·</span>
          <Link href="/" className="hover:text-gray-300 transition-colors">Home</Link>
        </div>
      </div>
    </div>
  );
}
