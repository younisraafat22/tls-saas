import re

with open('frontend/src/app/page.tsx', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Remove Top Disclaimer from LandingPage
old_landing = """export default function LandingPage() {
  return (
    <main>
      <Navbar />
      <div className="pt-24 pb-3 px-4 bg-red-500/10 border-b border-red-500/20 text-center text-sm md:text-base text-red-200">
        <p><strong>⚠️ IMPORTANT NOTICE:</strong> TLS Appointment Checker is <strong>monitoring only</strong>. No auto-booking, and it does not guarantee appointments. It is a tool to help you find open slots by checking the TLS website automatically.</p>
      </div>
      <Hero />"""

new_landing = """export default function LandingPage() {
  return (
    <main>
      <Navbar />
      <Hero />"""

if old_landing in text:
    text = text.replace(old_landing, new_landing)

# 2. Add Top Disclaimer inside Navbar
old_nav_start = """  return (
    <motion.nav
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      transition={{ duration: 0.6, ease: "easeOut" }}
      className={ixed top-0 left-0 right-0 z-50 transition-all duration-300 }
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 sm:h-20">"""

new_nav_start = """  return (
    <motion.nav
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      transition={{ duration: 0.6, ease: "easeOut" }}
      className={ixed top-0 left-0 right-0 z-50 flex flex-col transition-all duration-300 }
    >
      <div className="bg-amber-500/10 border-b border-amber-500/20 py-2 px-4 text-center text-xs md:text-sm text-amber-200">
        <p><strong>⚠️ IMPORTANT NOTICE:</strong> TLS Appointment Checker is <strong>monitoring only</strong>. No auto-booking, and it does not guarantee appointments. It is a tool to help you find open slots by checking the TLS website automatically.</p>
      </div>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
        <div className="flex items-center justify-between h-16 sm:h-20">"""

if old_nav_start in text:
    text = text.replace(old_nav_start, new_nav_start)

# 3. Clean up the ?  emojis
text = text.replace('? SERVER MONITORED', 'SERVER MONITORED')
text = text.replace('? BEST VALUE', 'BEST VALUE')
text = text.replace('? FREE TRIAL', 'FREE TRIAL')
text = text.replace(' SERVER MONITORED', 'SERVER MONITORED')
text = text.replace(' BEST VALUE', 'BEST VALUE')
text = text.replace(' FREE TRIAL', 'FREE TRIAL')

# 4. Flex layout for pricing cards
old_card_class = '''className={glass-card p-8 relative }'''
new_card_class = '''className={glass-card p-8 flex flex-col h-full relative }'''

text = text.replace(old_card_class, new_card_class)

old_ul_class = '''<ul className="space-y-3 mb-8">'''
new_ul_class = '''<ul className="space-y-3 mb-8 flex-1">'''

text = text.replace(old_ul_class, new_ul_class)

# 5. Make Hero padding larger to accommodate the top banner
text = text.replace('className="relative min-h-screen flex items-center pt-20 overflow-hidden"', 'className="relative min-h-screen flex items-center pt-32 overflow-hidden"')

with open('frontend/src/app/page.tsx', 'w', encoding='utf-8') as f:
    f.write(text)

print("Formatting applied.")
