# TLS Appointment Checker - Pre-Publishing Testing Checklist

## 🎯 Testing Before Publishing to Website

Complete all tests below before uploading the installer to the website. Mark each item as you test it.

---

## 1. 📦 Installation & Uninstallation

### First Installation
- [X] Download installer from `installer_output/TLS_Appointment_Checker_v1.0.0_Setup.exe`
- [X] Right-click installer → Properties → Check file size (should be ~127 MB)
- [ ] Run installer as Administrator
- [ ] Verify installer shows "TLS Appointment Checker" (no personal name "Younis")
- [ ] Check license agreement shows:
  - Copyright: "TLS Appointment Checker" (not personal name)
  - Support email: tlsappointmentchecker@gmail.com
- [ ] Complete installation to default location: `C:\Program Files\TLS Appointment Checker`
- [ ] Verify desktop shortcut created (if selected)
- [ ] Verify Start Menu shortcut created
- [ ] Right-click shortcut → Properties → Check icon displays correctly (not "file not found")

### Uninstallation
- [ ] Go to Settings → Apps → Find "TLS Appointment Checker"
- [ ] Click Uninstall
- [ ] Verify app closes gracefully
- [ ] Verify `C:\Program Files\TLS Appointment Checker` folder deleted
- [ ] Verify desktop shortcut removed
- [ ] Verify Start Menu entry removed

### Reinstallation
- [ ] Install again after uninstallation
- [ ] Verify app launches successfully
- [ ] Verify trial status persists (can't activate trial again)

---

## 2. 🎨 UI & Visual Elements

### Window & Title Bar
- [ ] App opens at center of screen
- [ ] Window size: 1400x990
- [ ] Title bar is hidden (clean look)
- [ ] Window controls (minimize, maximize, close) still work
- [ ] App background color is dark blue (#0A0E27)
- [ ] Custom icon appears in taskbar

### Welcome Page
- [ ] Logo displays correctly at top
- [ ] "Welcome to TLS Appointment Checker" heading visible
- [ ] 4 feature cards display properly (Real-Time Monitoring, Instant Email Alerts, Secure & Private, All Egypt Branches)
- [ ] "Important - Please Read" yellow warning box shows
- [ ] "Read Terms & Disclaimer" button works → opens modal with terms
- [ ] **"Get Started" button** (blue, filled) is visible and centered
- [ ] **"Visit Our Website" button** (blue, outlined) is visible below Get Started
- [ ] Version number shows at bottom
- [ ] Click "Visit Our Website" → opens https://tls-appointment-checker.netlify.app in browser

### All Pages - Website Icon
- [ ] **Welcome Page**: "Visit Our Website" button present
- [ ] **Service Selection Page**: Globe icon (🌐) visible in top-right corner
- [ ] **Pricing Page**: Globe icon (🌐) visible in top-right corner
- [ ] **Activation Page**: Globe icon (🌐) visible in top-right corner  
- [ ] **Monitoring Dashboard**: Globe icon (🌐) visible in header next to Support/Screenshots/Change License
- [ ] Click any globe icon → opens website in browser
- [ ] Hover over globe icon → shows "Visit Website" tooltip

---

## 3. 🎫 Licensing & Plans

### Trial Plan (Free 1-Day)
- [ ] Select "Legalization" or "Visa" service
- [ ] On pricing page, see 2 plan cards: "Free Trial" and "Lifetime Plan"
- [ ] Trial card shows: "Free", "1 day", "Start Free Trial" button (green)
- [ ] Click "Start Free Trial"
- [ ] If first time on this PC → trial activates successfully
- [ ] If trial already used → see error: "Trial already activated on this device"
- [ ] Trial persists even after uninstall/reinstall (Windows Registry check)

### Lifetime Plan Purchase
- [ ] Lifetime card shows: "1,500 EGP", "one-time", **"Buy Now"** button (amber/gold)
- [ ] Click **"Buy Now"** → opens payment dialog **inside the app** (not browser)
- [ ] Payment dialog shows:
  - Header: "Payment Instructions" with money bag icon
  - Text: "Send 1,500 EGP via one of these methods:"
  - **Vodafone Cash**: 01065080242 with "Copy Number" button (cyan)
  - **InstaPay**: 01060263887 with "Copy Number" button (cyan)
  - **After Payment** section (amber box) with 4 steps
  - **Green "Contact via WhatsApp" button** at bottom
  - "Close" button (gray outlined)
- [ ] Click "Copy Number" for Vodafone → shows "Vodafone Cash number copied!" snackbar
- [ ] Click "Copy Number" for InstaPay → shows "InstaPay number copied!" snackbar
- [ ] Click "Contact via WhatsApp" → opens WhatsApp to +20 10 60263887 (correct number!)
- [ ] Click "Close" → dialog closes

### License Activation
- [ ] Click "Already have a license key? Activate here →" on pricing page
- [ ] Activation page shows:
  - Globe icon (🌐) in top-right
  - "← Back to Pricing" button in top-left
  - "Activate Your License" heading
  - Device ID displayed with "Copy" button
  - License key input field
  - "Activate License" button (cyan)
- [ ] Try empty key → see error "Please enter a license key"
- [ ] Try invalid key → see error message
- [ ] Try valid key → activates successfully → redirects to monitoring dashboard
- [ ] Device ID copies correctly when "Copy" clicked

---

## 4. 📋 Service Selection & Configuration

### Service Selection
- [ ] See "Choose your service" page after welcome
- [ ] 2 cards: "Legalization" and "Visa Process"
- [ ] Globe icon (🌐) in top-right corner
- [ ] Yellow info box: "You must have an existing account on the TLS website..."
- [ ] Click "Legalization" → goes to pricing page with service type saved
- [ ] Go back → click "Visa" → goes to pricing page with service type saved

### Configuration (Once Activated)
- [ ] On monitoring dashboard, see "Configuration" card
- [ ] Fields visible:
  - TLS Email
  - TLS Password (masked)
  - Service Type dropdown (Legalization / Visa)
  - Branch dropdown (changes based on service type)
  - Check Interval dropdown (30-180 min for trial, 5-30 min for lifetime)
  - Notification Email
  - **Developer mode only**: "Run browser in background (Dev)" toggle
- [ ] Try saving with empty email → error
- [ ] Try saving with invalid email format → error
- [ ] Fill all fields correctly → click "Save Configuration" → success message
- [ ] Verify branch dropdown updates correctly when switching service type

### Developer Mode (Ctrl+Shift+D)
- [ ] Press **Ctrl+Shift+D** → see "Developer mode enabled" snackbar
- [ ] Configuration card refreshes, "Run browser in background (Dev)" toggle appears
- [ ] Press **Ctrl+Shift+D** again → see "Developer mode disabled" snackbar
- [ ] Toggle disappears from regular users

---

## 5. 🔍 Monitoring & Checking

### Start Monitoring
- [ ] Configure TLS credentials (email, password, branch)
- [ ] Click "Start Monitoring" button (green)
- [ ] Button changes to "Stop Monitoring" (red)
- [ ] Countdown timer starts (e.g., "29:45")
- [ ] Status log shows messages:
  - "Monitoring started..."
  - Chrome browser activity (if visible mode)
  - "Checking appointments..."
  - Results (appointments found/not found)
- [ ] Verify countdown decreases every second

### Stop Monitoring
- [ ] Click "Stop Monitoring" button
- [ ] Countdown stops
- [ ] Button changes back to "Start Monitoring"
- [ ] Status log shows "Monitoring stopped by user"

### Background Mode
- [ ] **Default behavior**: Browser runs in background (hidden), no Chrome window visible
- [ ] **Developer mode**: Toggle "Run browser in background" OFF → Chrome window visible during checks
- [ ] **Developer mode**: Toggle "Run browser in background" ON → Chrome hidden again

### Statistics Cards
- [ ] **Next Check**: Countdown timer updates every second
- [ ] **Total Checks**: Increments after each successful check
- [ ] **Checks Today**: Shows X/Y format (e.g., "5/10" or "5/∞" for unlimited)
- [ ] **Last Check**: Shows date and time of last completed check (MM/DD, HH:MM)

---

## 6. 📧 Notifications & Alerts

### Email Notifications
- [ ] Configure valid notification email in settings
- [ ] Start monitoring with correct TLS credentials
- [ ] Wait for a check to complete
- [ ] If appointments found → check notification email inbox:
  - Subject: "TLS Appointment Found!"
  - Body contains branch, date, appointment details
  - Sender: configured email service

### Windows Notifications
- [ ] When appointments found → Windows notification appears:
  - Title: "Appointment Available!"
  - Message: Brief details
  - App icon visible in notification

### TLS Email Change Limits
- [ ] Try changing TLS email during trial → allowed once
- [ ] Try changing TLS email again during trial → blocked (max 1 change for trial)
- [ ] With lifetime license → allowed up to 2 changes total
- [ ] After limit reached → see error message

---

## 7. 📸 Screenshots & Evidence

### Screenshots Gallery
- [ ] On monitoring dashboard header, click "View Screenshots" button (📷 icon)
- [ ] Screenshots gallery opens showing all captured screenshots
- [ ] If no screenshots yet → see "No screenshots available" message
- [ ] After check completes → new screenshots appear with timestamps
- [ ] Click screenshot → opens full-size in modal view
- [ ] Click "← Back to Dashboard" → returns to monitoring page

### Screenshot Filtering
- [ ] Screenshots show TLS website pages only (login, dashboard, appointment selection)
- [ ] Random browser screenshots (chrome://settings, blank pages, errors) are filtered out
- [ ] Verify no URLs like "chrome://", "about:blank", "data:" appear in gallery

---

## 8. 📞 Support & Help

### Contact Support Dialog
- [ ] On monitoring dashboard, click "Contact Support" button (🎧 icon)
- [ ] Dialog opens with fields:
  - Your Email (pre-filled if configured)
  - Subject
  - Message
- [ ] Try sending empty message → validation error
- [ ] Fill all fields → click "Send"
- [ ] See "Message sent successfully!" or appropriate message
- [ ] Click "Cancel" → dialog closes without sending

---

## 9. 🔄 Change License / Service

### Change Service Type
- [ ] On monitoring dashboard, hover over plan badge (top-right)
- [ ] Click badge or "Change Service" button
- [ ] Returns to service selection page
- [ ] Can select different service (Legalization ↔ Visa)
- [ ] License remains active

### Change Plan
- [ ] On monitoring dashboard, click "Change License" button (🔄 icon)
- [ ] Returns to pricing page
- [ ] Can activate new trial (if not used) or activate different license
- [ ] Current license deactivated when activating new one

---

## 10. 🐛 Error Handling

### Network Errors
- [ ] Disconnect internet
- [ ] Try starting monitoring → see network error in status log
- [ ] Reconnect internet → monitoring resumes

### Invalid Credentials
- [ ] Configure with wrong TLS email/password
- [ ] Start monitoring
- [ ] See error in status log: "Login failed" or similar
- [ ] Verify app doesn't crash

### Missing Configuration
- [ ] Don't configure TLS credentials
- [ ] Try starting monitoring → see error "Please configure TLS credentials first"

### Browser Issues
- [ ] Delete Chrome/Chromedriver files from `%APPDATA%\undetected_chromedriver`
- [ ] Start monitoring → verify app downloads fresh chromedriver
- [ ] No "[WinError 183]" errors appear

---

## 11. 💾 Data Persistence

### Database
- [ ] App creates `tls_checker.db` in app directory
- [ ] Configuration saved persists after restart
- [ ] Total checks count persists after restart
- [ ] License activation persists after restart
- [ ] TLS email change history tracked correctly

### Windows Registry (Trial)
- [ ] Activate trial
- [ ] Check registry: `HKEY_CURRENT_USER\SOFTWARE\TLSAppointmentChecker`
- [ ] Key exists with hardware ID and activation timestamp
- [ ] Uninstall app → registry key remains
- [ ] Reinstall → trial still blocked (can't reactivate)

### Log Files
- [ ] Check if app creates log files (if implemented)
- [ ] Verify no sensitive data (passwords) in plain text

---

## 12. 🚀 Performance & Stability

### Resource Usage
- [ ] Check Task Manager while app running:
  - CPU usage < 5% when idle
  - Memory usage < 200 MB when idle
  - During check: CPU spikes acceptable, returns to idle after
- [ ] No memory leaks after 10+ checks

### Long-Running Stability
- [ ] Let app run for 2+ hours with monitoring active
- [ ] Verify countdown continues correctly
- [ ] Verify checks execute on schedule
- [ ] No crashes or freezes

### Multiple Checks
- [ ] Complete at least 5 consecutive checks
- [ ] Verify each check completes successfully
- [ ] Total checks count increases correctly
- [ ] No errors accumulate in status log

---

## 13. 🔒 Security & Privacy

### Password Encryption
- [ ] Configure TLS password
- [ ] Open `tls_checker.db` with SQLite browser
- [ ] Check `user_settings` table → password column is encrypted (not plain text)
- [ ] Verify password decrypts correctly when starting check

### Local Storage Only
- [ ] Verify no network requests except:
  - TLS website (tlscontact.com)
  - License server (if checking license)
  - Update checks (if enabled)
- [ ] No user data sent to third parties

---

## 14. 🌐 Website Integration

### Download Link
- [ ] Upload installer to website hosting
- [ ] Update website download link to point to installer
- [ ] Click download link → installer downloads (127 MB file)
- [ ] Filename: `TLS_Appointment_Checker_v1.0.0_Setup.exe`

### Payment Flow
- [ ] User clicks "Buy Now" on website pricing section
- [ ] Payment modal appears with Vodafone/InstaPay numbers
- [ ] User can copy numbers and contact via WhatsApp
- [ ] After payment, user receives license key via email
- [ ] User activates key in app → works correctly

---

## 15. ✅ Final Checks Before Publishing

### Documentation
- [ ] README.md is up to date
- [ ] Privacy policy and terms updated on website
- [ ] User guide on website matches app features

### Version & Branding
- [ ] App shows correct version: 1.0.0
- [ ] No "Younis" or personal names anywhere:
  - LICENSE.txt
  - Installer screens
  - About/support sections
  - Error messages
- [ ] All emails reference: tlsappointmentchecker@gmail.com
- [ ] Copyright: "TLS Appointment Checker" (not personal name)

### File Integrity
- [ ] Installer is not corrupted (run hash check if needed)
- [ ] Installer size is reasonable (~127 MB)
- [ ] All dependencies bundled (no "missing DLL" errors on fresh Windows)

### Clean Install Testing
- [ ] Test on a **fresh Windows PC** (or VM) that has never had the app installed
- [ ] No Python/Chrome/dependencies pre-installed
- [ ] App installs and runs completely standalone
- [ ] No errors on first launch

---

## 📝 Testing Notes

**Tester Name**: ___________________  
**Test Date**: ___________________  
**Windows Version**: ___________________  
**Installer Version**: ___________________

### Issues Found:
```
(List any bugs, errors, or problems discovered during testing)




```

### Recommendations:
```
(Suggestions for improvements before publishing)




```

---

## ✨ Publishing Checklist

After ALL tests pass:

- [ ] Upload installer to website hosting (with HTTPS)
- [ ] Update website download link
- [ ] Verify payment numbers on website match app (Vodafone: 01065080242, InstaPay: 01060263887)
- [ ] Update website to mention:
  - Silent background monitoring (no Chrome window)
  - One-time trial per device
  - Registry-based trial tracking
  - Developer mode (Ctrl+Shift+D)
- [ ] Test complete workflow: Download → Install → Activate → Monitor
- [ ] Monitor user feedback and support requests

---

**Status**: ⏳ Testing in Progress

**Publishing Ready**: ❌ NO / ✅ YES (circle one)

---

*Last Updated: February 14, 2026*
