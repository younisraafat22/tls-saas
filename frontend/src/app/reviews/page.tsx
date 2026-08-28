"use client";
import { useEffect, useState } from "react";
import { Star } from "lucide-react";
import Link from "next/link";
import { useLanguage } from "../../lib/i18n";

export default function ReviewsPage() {
  const [reviews, setReviews] = useState<any[]>([]);
  const { locale } = useLanguage();

  useEffect(() => {
    fetch("/api/ratings")
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) setReviews(data);
      })
      .catch(console.error);
  }, []);

  return (
    <div className="min-h-screen bg-[#070b19] text-white p-8 pt-24" dir={locale === 'ar' ? 'rtl' : 'ltr'}>
      <div className="max-w-4xl mx-auto">
        <Link href="/" className="text-cyan-400 hover:underline mb-8 inline-flex items-center gap-2">
          {locale === 'ar' ? "→ العودة للرئيسية" : locale === 'de' ? "← Zurück zur Startseite" : "← Back to Home"}
        </Link>
        <h1 className="text-4xl font-bold mb-8">
          {locale === 'ar' ? "جميع التقييمات" : locale === 'de' ? "Alle Bewertungen" : "All Reviews"}
        </h1>
        <div className="grid gap-6 md:grid-cols-2">
          {reviews.length === 0 ? (
            <p className="text-gray-400">
               {locale === 'ar' ? "لا توجد تقييمات بعد." : locale === 'de' ? "Noch keine Bewertungen." : "No reviews yet."}
            </p>
          ) : (
            reviews.map((r: any) => (
              <div key={r.id} className="glass-card p-6 border border-white/10 rounded-xl bg-white/5 backdrop-blur-md">
                <div className="flex text-[#FFD700] mb-3">
                  {[...Array(5)].map((_, i) => (
                    <Star key={i} className="w-5 h-5" fill={i < r.rating ? "currentColor" : "none"} />
                  ))}
                </div>
                <p className="text-gray-200 mb-4">{r.comment}</p>
                <div className="text-xs text-gray-500 flex justify-between items-center">
                  <span>{r.source === "desktop" ? "🖥️ Desktop App" : "🌐 Website"}</span>
                  <span>{new Date(r.created_at).toLocaleDateString(locale === 'ar' ? 'ar-EG' : locale === 'de' ? 'de-DE' : 'en-US')}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
