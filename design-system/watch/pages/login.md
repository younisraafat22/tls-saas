# Login Page Overrides

> **PROJECT:** WATCH
> **Generated:** 2026-08-28 04:11:55
> **Page Type:** Authentication

> ⚠️ **IMPORTANT:** Rules in this file **override** the Master file (`design-system/MASTER.md`).
> Only deviations from the Master are documented here. For all other rules, refer to the Master.

---

## Page-Specific Rules

### Layout Overrides

- **Max Width:** 1200px (standard)
- **Layout:** Full-width sections, centered content

### Spacing Overrides

- No overrides — use Master spacing

### Typography Overrides

- No overrides — use Master typography

### Color Overrides

- No overrides — use Master colors

### Component Overrides

- Avoid: Block paste or require manual OTP transcription with no alternative
- Avoid: No feedback after submit
- Avoid: Placeholder-only inputs

---

## Page-Specific Components

- No unique components for this page

---

## Recommendations

- Effects: transform: translateY(scroll), position: fixed/sticky, perspective: 1px, scroll-triggered animations
- Security / Accessibility: Allow password managers and paste; offer passkeys OAuth or another non-cognitive method
- Forms: Show loading then success/error state
- Accessibility: Use label with for attribute or wrap input
