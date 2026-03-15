import sys

en_add = '''    rating: {
      title: "Rate Your Experience",
      sub: "Let us know how the service works for you!",
      placeholder: "Optional feedback...",
      submit: "Submit Rating",
      thanks: "Thank you for your feedback!",
    },'''

ar_add = '''    rating: {
      title: "قيّم تجربتك",
      sub: "أخبرنا برأيك في الخدمة!",
      placeholder: "تعليق اختياري...",
      submit: "إرسال التقييم",
      thanks: "شكراً على ملاحظاتك!",
    },'''

de_add = '''    rating: {
      title: "Bewerten Sie Ihre Erfahrung",
      sub: "Lassen Sie uns wissen, wie der Service für Sie funktioniert!",
      placeholder: "Optionales Feedback...",
      submit: "Bewertung abgeben",
      thanks: "Vielen Dank für Ihr Feedback!",
    },'''

lines = open('frontend/src/lib/i18n.tsx', 'r', encoding='utf-8').readlines()

# find cta index for en (between 7 and 461)
en_cta_idx = next(i for i, line in enumerate(lines) if '    cta: {' in line and 7 < i < 461)
# insert
lines.insert(en_cta_idx, en_add + '\n')

# ar is offset
ar_cta_idx = next(i for i, line in enumerate(lines) if '    cta: {' in line and 461 < i < 917)
lines.insert(ar_cta_idx, ar_add + '\n')

# de is offset
de_cta_idx = next(i for i, line in enumerate(lines) if '    cta: {' in line and 917 < i)
lines.insert(de_cta_idx, de_add + '\n')

# Wait, before that, I need to adjust the auto-stop terms inside this script!
for i, line in enumerate(lines):
    if 'The Service notifies subscribers when appointment slots are detected.", "The Service is available' in line:
        lines[i] = line.replace('The Service notifies subscribers when appointment slots are detected.", "The Service is available', 'The Service notifies subscribers when appointment slots are detected. To avoid rate-limiting, monitoring will automatically pause once a valid appointment is found. You must manually restart it if needed.", "The Service is available')
    if 'يقوم الخدمة بإشعار المشتركين عند اكتشاف مواعيد متاحة.", "الخدمة متاحة' in line:
        lines[i] = line.replace('يقوم الخدمة بإشعار المشتركين عند اكتشاف مواعيد متاحة.", "الخدمة متاحة', 'يقوم الخدمة بإشعار المشتركين عند اكتشاف مواعيد متاحة. لتجنب حظر الاتصال، سيتوقف الفحص تلقائيًا بمجرد العثور على موعد. يجب عليك إعادة تشغيله يدويًا إذا لزم الأمر.", "الخدمة متاحة')
    if 'Der Dienst benachrichtigt Abonnenten, wenn Termine erkannt werden.", "Der Dienst ist' in line:
        lines[i] = line.replace('Der Dienst benachrichtigt Abonnenten, wenn Termine erkannt werden.", "Der Dienst ist', 'Der Dienst benachrichtigt Abonnenten, wenn Termine erkannt werden. Um Ratenlimitierungen zu vermeiden, wird die Überwachung automatisch angehalten, sobald ein Termin gefunden wird. Sie müssen sie bei Bedarf manuell neu starten.", "Der Dienst ist')

open('frontend/src/lib/i18n.tsx', 'w', encoding='utf-8').writelines(lines)
