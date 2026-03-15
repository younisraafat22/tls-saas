import sys
content = open('frontend/src/lib/i18n.tsx', encoding='utf-8').read()

en_add = '''    rating: {
      title: "Rate Your Experience",
      sub: "Let us know how the service works for you!",
      placeholder: "Optional feedback...",
      submit: "Submit Rating",
      thanks: "Thank you for your feedback!",
    },
    cta: {'''
content = content.replace('    cta: {', en_add, 1)

ar_add = '''    rating: {
      title: "قيّم تجربتك",
      sub: "أخبرنا برأيك في الخدمة!",
      placeholder: "تعليق اختياري...",
      submit: "إرسال التقييم",
      thanks: "شكراً على ملاحظاتك!",
    },
    cta: {'''
content = content.replace('    cta: {', ar_add, 1)

de_add = '''    rating: {
      title: "Bewerten Sie Ihre Erfahrung",
      sub: "Lassen Sie uns wissen, wie der Service für Sie funktioniert!",
      placeholder: "Optionales Feedback...",
      submit: "Bewertung abgeben",
      thanks: "Vielen Dank für Ihr Feedback!",
    },
    cta: {'''
content = content.replace('    cta: {', de_add, 1)

open('frontend/src/lib/i18n.tsx', 'w', encoding='utf-8').write(content)
