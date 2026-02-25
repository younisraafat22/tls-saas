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
          <span>Â·</span>
          <Link href="/" className="hover:text-gray-300 transition-colors">{tr.footerHome}</Link>
        </div>
      </div>
    </div>
  );
}
