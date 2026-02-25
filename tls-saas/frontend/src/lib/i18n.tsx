"use client";

import React, { createContext, useContext, useState, useEffect } from "react";

export type Locale = "en" | "ar" | "de";

export const translations = {
  en: {
    dir: "ltr" as const,
    nav: {
      features: "Features",
      howItWorks: "How It Works",
      pricing: "Pricing",
      faq: "FAQ",
      logIn: "Log In",
      getStarted: "Get Started",
      dashboard: "Dashboard",
    },
    hero: {
      badge: "Live Monitoring Active",
      headline1: "Never Miss Your",
      headline2: "TLS Appointment",
      headline3: "Again",
      sub: "24/7 automated monitoring for German document legalization appointments in Egypt.",
      cta: "Start Monitoring",
      learnMore: "Learn More",
      emailAlerts: "Email Alerts",
      mobileReady: "Works on Phone",
      monitoringActive: "Monitoring Active",
      live: "Live",
      checking: "Checking...",
      noSlots: "No slots",
      slotsOpen: "🎉 Slots Open!",
    },
    stats: {
      branches: "Branches Monitored",
      monitoring: "Monitoring",
      checkInterval: "Check Interval",
      alertChannels: "Alert Channels",
    },
    features: {
      title: "Why Choose",
      titleHighlight: "TLS Appointment Checker",
      titleEnd: "?",
      sub: "Stop refreshing the TLS website manually. Let our server do the work while you live your life.",
      items: [
        { title: "Instant Notifications", desc: "Email and browser push — get alerted the second a slot opens, even on your phone." },
        { title: "Secure & Private", desc: "Your data stays safe. Encrypted credentials, secure auth, and no data sharing. Ever." },
        { title: "Both Branches", desc: "Monitor Sheikh Zayed & Hurghada legalization branches — both covered under one subscription." },
        { title: "Lightning Fast", desc: "Our server checks every 30 minutes. When slots appear, you know within seconds." },
        { title: "24/7 Monitoring", desc: "Our server never sleeps. It checks around the clock so you don't have to." },
        { title: "Mobile Friendly", desc: "Check your dashboard from any device. Your phone, tablet, or computer." },
      ],
    },
    howItWorks: {
      title: "How It",
      titleHighlight: "Works",
      sub: "Get started in under 2 minutes. No software to install — everything runs in your browser.",
      steps: [
        { title: "Create Account", desc: "Sign up in seconds with just your email. No downloads, no installations." },
        { title: "Subscribe", desc: "One simple plan for document legalization monitoring. Pay via Vodafone Cash or Instapay." },
        { title: "Select Branches", desc: "Choose which TLS branches to monitor. Our server handles the rest." },
        { title: "Get Notified", desc: "Receive instant alerts via email or push notification when slots open." },
      ],
    },
    pricing: {
      title: "Simple,",
      titleHighlight: "Transparent",
      titleEnd: "Pricing",
      sub: "Choose the plan that fits your needs. No hidden fees, cancel anytime.",
      perMonth: "/mo",
      getStarted: "Get Started",
      footer: "Pay via Vodafone Cash or Instapay. Subscription activated within a few hours.",
    },
    faq: {
      title: "Frequently Asked",
      titleHighlight: "Questions",
      items: [
        { q: "How does monitoring work?", a: "Our server checks TLS appointment availability every 30 minutes for all branches. When a slot opens, all subscribers monitoring that branch are instantly notified via email and web push." },
        { q: "Do I need to keep my computer on?", a: "No! Everything runs on our server 24/7. You just need an internet connection to receive notifications — on your phone, tablet, or any device." },
        { q: "How fast will I be notified?", a: "Within seconds of detecting available slots. Our system sends notifications via multiple channels simultaneously to maximize your chances of booking." },
        { q: "What payment methods do you accept?", a: "We currently accept Vodafone Cash and Instapay. After payment, our team verifies and activates your subscription, usually within a few hours." },
        { q: "Can I monitor multiple branches?", a: "Yes! Your legalization subscription covers both Sheikh Zayed and Hurghada branches simultaneously." },
        { q: "What happens when my subscription expires?", a: "Monitoring stops and you won't receive notifications. You can renew at any time to resume monitoring." },
        { q: "Is this an early access service?", a: "Yes — this is an early access release. While we strive for reliability, we cannot guarantee 100% uptime or uninterrupted monitoring. By using the service you agree to our Terms & Conditions." },
      ],
    },
    cta: {
      title: "Ready to Stop Refreshing?",
      sub: "Join others who are getting instant notifications when TLS appointment slots open.",
      button: "Get Started Now",
    },
    footer: {
      desc: "Automated appointment monitoring for German document legalization services in Egypt.",
      quickLinks: "Quick Links",
      legal: "Legal",
      features: "Features",
      pricing: "Pricing",
      faq: "FAQ",
      logIn: "Log In",
      terms: "Terms & Conditions",
      privacy: "Privacy Policy",
      contact: "Contact Form",
      rights: "All rights reserved.",
    },
    payment: {
      earlyAccessTitle: "⚠️ Early Access — Please Read",
      earlyAccessBody: "This is a service under trial. While we do our absolute best to keep monitoring running, the TLS website may occasionally block automated access. We cannot guarantee uninterrupted service. Appointments must still be booked by you once notified.",
    },
  },

  ar: {
    dir: "rtl" as const,
    nav: {
      features: "المميزات",
      howItWorks: "كيف يعمل",
      pricing: "الأسعار",
      faq: "الأسئلة الشائعة",
      logIn: "تسجيل الدخول",
      getStarted: "ابدأ الآن",
      dashboard: "لوحة التحكم",
    },
    hero: {
      badge: "المراقبة نشطة الآن",
      headline1: "لا تفوّت موعدك",
      headline2: "في TLS",
      headline3: "أبدًا",
      sub: "مراقبة آلية على مدار الساعة لمواعيد توثيق الوثائق الألمانية في مصر.",
      cta: "ابدأ المراقبة",
      learnMore: "اعرف أكثر",
      emailAlerts: "تنبيهات بريد إلكتروني",
      mobileReady: "يعمل على الهاتف",
      monitoringActive: "المراقبة نشطة",
      live: "مباشر",
      checking: "جارٍ الفحص...",
      noSlots: "لا توجد مواعيد",
      slotsOpen: "🎉 مواعيد متاحة!",
    },
    stats: {
      branches: "فروع مُراقَبة",
      monitoring: "مراقبة",
      checkInterval: "فترة الفحص",
      alertChannels: "قنوات التنبيه",
    },
    features: {
      title: "لماذا تختار",
      titleHighlight: "TLS Appointment Checker",
      titleEnd: "؟",
      sub: "توقف عن تحديث موقع TLS يدويًا. دعنا نتولى الأمر بينما تعيش حياتك.",
      items: [
        { title: "تنبيهات فورية", desc: "بريد إلكتروني ونوتيفيكيشن — تعرف في اللحظة التي يُفتح فيها موعد، حتى على هاتفك." },
        { title: "آمن وخاص", desc: "بياناتك في أمان. بيانات اعتماد مشفرة، مصادقة آمنة، وبدون مشاركة البيانات أبدًا." },
        { title: "جميع الفروع", desc: "راقب فروع التوثيق في الشيخ زايد والغردقة — كلاهما ضمن اشتراك واحد." },
        { title: "سرعة فائقة", desc: "يفحص سيرفرنا كل 30 دقيقة. حين تظهر المواعيد، تعلم خلال ثوانٍ." },
        { title: "مراقبة 24/7", desc: "سيرفرنا لا ينام. يعمل على مدار الساعة حتى لا تضطر للسهر." },
        { title: "متوافق مع الجوال", desc: "تابع لوحة التحكم من أي جهاز — هاتفك أو تابلت أو كمبيوتر." },
      ],
    },
    howItWorks: {
      title: "كيف",
      titleHighlight: "يعمل",
      sub: "ابدأ في أقل من دقيقتين. لا برامج تثبيت — كل شيء في المتصفح.",
      steps: [
        { title: "أنشئ حسابك", desc: "سجّل في ثوانٍ بإيميلك فقط. بدون تنزيلات أو تثبيت." },
        { title: "اشترك", desc: "خطة واحدة بسيطة لمراقبة توثيق الوثائق. ادفع عبر فودافون كاش أو إنستاباي." },
        { title: "اختر الفروع", desc: "حدّد فروع TLS التي تريد مراقبتها. السيرفر يتولى الباقي." },
        { title: "استقبل التنبيهات", desc: "تلقّ تنبيهات فورية عبر البريد الإلكتروني أو الإشعارات حين تفتح المواعيد." },
      ],
    },
    pricing: {
      title: "أسعار",
      titleHighlight: "شفافة",
      titleEnd: "وبسيطة",
      sub: "اختر الخطة المناسبة لك. لا رسوم خفية، يمكن الإلغاء في أي وقت.",
      perMonth: "/شهر",
      getStarted: "ابدأ الآن",
      footer: "الدفع عبر فودافون كاش أو إنستاباي. يُفعَّل الاشتراك خلال ساعات قليلة.",
    },
    faq: {
      title: "الأسئلة",
      titleHighlight: "الشائعة",
      items: [
        { q: "كيف تعمل المراقبة؟", a: "سيرفرنا يفحص مواعيد TLS كل 30 دقيقة لجميع الفروع. حين يُفتح موعد، يُخطَر جميع المشتركين فورًا عبر البريد الإلكتروني والإشعارات." },
        { q: "هل أحتاج لإبقاء جهازي شغّالًا؟", a: "لا! كل شيء يعمل على سيرفرنا 24/7. تحتاج فقط لاتصال إنترنت لاستقبال التنبيهات — على هاتفك أو أي جهاز." },
        { q: "كم سرعة وصول التنبيه؟", a: "خلال ثوانٍ من اكتشاف المواعيد. نحن نرسل التنبيهات عبر قنوات متعددة في نفس الوقت." },
        { q: "ما وسائل الدفع المقبولة؟", a: "نقبل حاليًا فودافون كاش وإنستاباي. بعد الدفع، يتحقق فريقنا ويفعّل اشتراكك عادةً خلال ساعات قليلة." },
        { q: "هل يمكنني مراقبة عدة فروع؟", a: "نعم! اشتراك التوثيق يغطي فرعَي الشيخ زايد والغردقة في نفس الوقت." },
        { q: "ماذا يحدث عند انتهاء الاشتراك؟", a: "تتوقف المراقبة ولن تصلك تنبيهات. يمكنك التجديد في أي وقت لاستئناف المراقبة." },
        { q: "هل هذه خدمة وصول مبكر؟", a: "نعم — هذا إصدار وصول مبكر. نسعى جاهدين للموثوقية، لكن لا نضمن تشغيلًا مستمرًا 100%. باستخدام الخدمة توافق على شروط الاستخدام." },
      ],
    },
    cta: {
      title: "هل أنت مستعد لتوقف عن التحديث اليدوي؟",
      sub: "انضم لمن يتلقون تنبيهات فورية حين تُفتح مواعيد TLS.",
      button: "ابدأ الآن",
    },
    footer: {
      desc: "مراقبة آلية لمواعيد توثيق الوثائق الألمانية في مصر.",
      quickLinks: "روابط سريعة",
      legal: "قانوني",
      features: "المميزات",
      pricing: "الأسعار",
      faq: "الأسئلة الشائعة",
      logIn: "تسجيل الدخول",
      terms: "الشروط والأحكام",
      privacy: "سياسة الخصوصية",
      contact: "نموذج التواصل",
      rights: "جميع الحقوق محفوظة.",
    },
    payment: {
      earlyAccessTitle: "⚠️ وصول مبكر — يرجى القراءة",
      earlyAccessBody: "هذه خدمة قيد التجربة. نبذل قصارى جهدنا للحفاظ على المراقبة نشطة، لكن موقع TLS قد يحجب في بعض الأحيان الوصول الآلي. لا يمكننا ضمان خدمة مستمرة دون انقطاع. يجب عليك حجز الموعد بنفسك بعد تلقي التنبيه.",
    },
  },

  de: {
    dir: "ltr" as const,
    nav: {
      features: "Funktionen",
      howItWorks: "So funktioniert es",
      pricing: "Preise",
      faq: "FAQ",
      logIn: "Anmelden",
      getStarted: "Loslegen",
      dashboard: "Dashboard",
    },
    hero: {
      badge: "Live-Überwachung aktiv",
      headline1: "Verpasse nie deinen",
      headline2: "TLS-Termin",
      headline3: "wieder",
      sub: "24/7 automatische Überwachung von Terminen für die Beglaubigung deutscher Dokumente in Ägypten.",
      cta: "Überwachung starten",
      learnMore: "Mehr erfahren",
      emailAlerts: "E-Mail-Benachrichtigungen",
      mobileReady: "Funktioniert auf dem Handy",
      monitoringActive: "Überwachung aktiv",
      live: "Live",
      checking: "Prüfe...",
      noSlots: "Keine Termine",
      slotsOpen: "🎉 Termine frei!",
    },
    stats: {
      branches: "Überwachte Filialen",
      monitoring: "Überwachung",
      checkInterval: "Prüfintervall",
      alertChannels: "Benachrichtigungskanäle",
    },
    features: {
      title: "Warum",
      titleHighlight: "TLS Appointment Checker",
      titleEnd: "wählen?",
      sub: "Hör auf, die TLS-Website manuell zu aktualisieren. Lass unseren Server arbeiten, während du dein Leben lebst.",
      items: [
        { title: "Sofortige Benachrichtigungen", desc: "E-Mail und Browser-Push — du wirst sofort benachrichtigt, sobald ein Termin frei wird, auch auf deinem Handy." },
        { title: "Sicher & Privat", desc: "Deine Daten sind sicher. Verschlüsselte Zugangsdaten, sichere Authentifizierung, keine Datenweitergabe. Niemals." },
        { title: "Alle Filialen", desc: "Überwache die Legalisierungsfilialen in Sheikh Zayed & Hurghada — beide unter einem Abonnement." },
        { title: "Blitzschnell", desc: "Unser Server prüft alle 30 Minuten. Wenn Termine erscheinen, weißt du es innerhalb von Sekunden." },
        { title: "24/7 Überwachung", desc: "Unser Server schläft nie. Er überprüft rund um die Uhr, damit du das nicht musst." },
        { title: "Mobil-freundlich", desc: "Überprüfe dein Dashboard von jedem Gerät aus — Handy, Tablet oder Computer." },
      ],
    },
    howItWorks: {
      title: "So funktioniert",
      titleHighlight: "es",
      sub: "In unter 2 Minuten starten. Keine Software zu installieren — alles läuft in deinem Browser.",
      steps: [
        { title: "Konto erstellen", desc: "Registriere dich in Sekunden nur mit deiner E-Mail. Keine Downloads, keine Installationen." },
        { title: "Abonnieren", desc: "Ein einfacher Plan für die Überwachung der Dokumentenbeglaubigung. Zahle per Vodafone Cash oder Instapay." },
        { title: "Filialen auswählen", desc: "Wähle aus, welche TLS-Filialen überwacht werden sollen. Unser Server erledigt den Rest." },
        { title: "Benachrichtigt werden", desc: "Erhalte sofortige Benachrichtigungen per E-Mail oder Push-Notification, wenn Termine verfügbar sind." },
      ],
    },
    pricing: {
      title: "Einfache,",
      titleHighlight: "transparente",
      titleEnd: "Preise",
      sub: "Wähle den Plan, der zu dir passt. Keine versteckten Kosten, jederzeit kündbar.",
      perMonth: "/Monat",
      getStarted: "Loslegen",
      footer: "Zahlung per Vodafone Cash oder Instapay. Abonnement wird innerhalb weniger Stunden aktiviert.",
    },
    faq: {
      title: "Häufig gestellte",
      titleHighlight: "Fragen",
      items: [
        { q: "Wie funktioniert die Überwachung?", a: "Unser Server prüft alle 30 Minuten die Terminverfügbarkeit bei TLS für alle Filialen. Wenn ein Termin frei wird, werden alle Abonnenten sofort per E-Mail und Web-Push benachrichtigt." },
        { q: "Muss ich meinen Computer eingeschaltet lassen?", a: "Nein! Alles läuft auf unserem Server 24/7. Du brauchst nur eine Internetverbindung, um Benachrichtigungen zu empfangen — auf deinem Handy, Tablet oder jedem anderen Gerät." },
        { q: "Wie schnell werde ich benachrichtigt?", a: "Innerhalb von Sekunden nach der Erkennung freier Termine. Unser System sendet Benachrichtigungen über mehrere Kanäle gleichzeitig." },
        { q: "Welche Zahlungsmethoden werden akzeptiert?", a: "Wir akzeptieren derzeit Vodafone Cash und Instapay. Nach der Zahlung verifiziert unser Team und aktiviert dein Abonnement in der Regel innerhalb weniger Stunden." },
        { q: "Kann ich mehrere Filialen überwachen?", a: "Ja! Dein Legalisierungsabonnement umfasst gleichzeitig beide Filialen: Sheikh Zayed und Hurghada." },
        { q: "Was passiert, wenn mein Abonnement abläuft?", a: "Die Überwachung stoppt und du erhältst keine Benachrichtigungen mehr. Du kannst jederzeit verlängern, um die Überwachung fortzusetzen." },
        { q: "Ist dies ein Early-Access-Dienst?", a: "Ja — dies ist eine Early-Access-Version. Wir streben nach Zuverlässigkeit, können jedoch keine 100%ige Betriebszeit garantieren. Mit der Nutzung des Dienstes stimmst du unseren AGB zu." },
      ],
    },
    cta: {
      title: "Bereit, mit dem manuellen Aktualisieren aufzuhören?",
      sub: "Schließ dich anderen an, die sofortige Benachrichtigungen erhalten, wenn TLS-Termine verfügbar werden.",
      button: "Jetzt loslegen",
    },
    footer: {
      desc: "Automatische Terminüberwachung für Dienstleistungen zur Beglaubigung deutscher Dokumente in Ägypten.",
      quickLinks: "Schnelllinks",
      legal: "Rechtliches",
      features: "Funktionen",
      pricing: "Preise",
      faq: "FAQ",
      logIn: "Anmelden",
      terms: "AGB",
      privacy: "Datenschutz",
      contact: "Kontaktformular",
      rights: "Alle Rechte vorbehalten.",
    },
    payment: {
      earlyAccessTitle: "⚠️ Early Access — Bitte lesen",
      earlyAccessBody: "Dies ist ein Dienst in der Testphase. Obwohl wir unser Bestes tun, um die Überwachung aufrechtzuerhalten, kann die TLS-Website gelegentlich automatisierten Zugriff blockieren. Wir können keinen unterbrechungsfreien Service garantieren. Termine müssen nach der Benachrichtigung von dir selbst gebucht werden.",
    },
  },
} as const;

export type TranslationKey = typeof translations.en;

interface LanguageContextType {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: TranslationKey;
}

const LanguageContext = createContext<LanguageContextType>({
  locale: "en",
  setLocale: () => {},
  t: translations.en,
});

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");

  useEffect(() => {
    const saved = localStorage.getItem("tls_locale") as Locale | null;
    if (saved && translations[saved]) setLocaleState(saved);
  }, []);

  // Apply dir + lang to <html> whenever locale changes
  useEffect(() => {
    const t = translations[locale];
    document.documentElement.setAttribute("dir", t.dir);
    document.documentElement.setAttribute("lang", locale);
  }, [locale]);

  const setLocale = (l: Locale) => {
    setLocaleState(l);
    localStorage.setItem("tls_locale", l);
  };

  return (
    <LanguageContext.Provider value={{ locale, setLocale, t: translations[locale] as TranslationKey }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  return useContext(LanguageContext);
}

export const localeLabels: Record<Locale, string> = {
  en: "EN",
  ar: "عربي",
  de: "DE",
};
