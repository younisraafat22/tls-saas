import re

with open('frontend/src/app/page.tsx', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''      }}\n    >'''
replacement = '''      }}\n    >\n      <div className="bg-amber-500/10 border-b border-amber-500/20 py-2 px-4 text-center text-xs sm:text-sm text-amber-200">\n        <p><strong>⚠️ IMPORTANT NOTICE:</strong> TLS Appointment Checker is <strong>monitoring only</strong>. No auto-booking, and it does not guarantee appointments. It is a tool to help you find open slots by checking the TLS website automatically.</p>\n      </div>'''

if target in text:
    text = text.replace(target, replacement, 1) # Only replace the first occurrence which is in Navbar
    print("Replaced safely")

with open('frontend/src/app/page.tsx', 'w', encoding='utf-8') as f:
    f.write(text)
