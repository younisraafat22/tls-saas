import re

with open('frontend/src/app/page.tsx', 'r', encoding='utf-8') as f:
    text = f.read()

# Make sure Hero padding is updated
text = text.replace('pt-20 overflow-hidden', 'pt-32 overflow-hidden')

# Find the exact motion.nav div for Navbar
import re
nav_start_regex = r'(className=\{ixed top-0 left-0 right-0 z-50 transition-all duration-300 \$\{\n.*?\}\\}\n\s*>\n\s*)<div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">'

replacement = r'''\1<div className="bg-amber-500/10 border-b border-amber-500/20 py-2 px-4 text-center text-xs md:text-sm text-amber-200">
        <p><strong>⚠️ IMPORTANT NOTICE:</strong> TLS Appointment Checker is <strong>monitoring only</strong>. No auto-booking, and it does not guarantee appointments. It is a tool to help you find open slots by checking the TLS website automatically.</p>
      </div>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">'''

if re.search(nav_start_regex, text, re.DOTALL):
    text = re.sub(nav_start_regex, replacement, text, flags=re.DOTALL)
    print("Injected banner into Navbar")
else:
    print("Could not find matching Navbar div")

# Also let's check pricing button alignment
with open('frontend/src/app/page.tsx', 'w', encoding='utf-8') as f:
    f.write(text)
