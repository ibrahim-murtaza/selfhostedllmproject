# Clarisync Design System — Reference (pulled from Figma)

**Source:** Clarisync-Website Figma file (original, view-only): `https://www.figma.com/design/6bZBWigmCw3Un5cSqODAHt/Clarisync-Website`
**Working copy (editor access, used to pull this data):** `https://www.figma.com/design/AohGw6WmSKU8pXpYpsYC8g/Untitled`
**Pulled:** 2026-09-22, for Phase D (branding) — welcome text/logo/favicon/font/error-wrapper work.

Frames on the board: Cover Image, Brand Logo, Colors, Typography, Iconography, Buttons. Cover Image is just a hero graphic (no tokens). Iconography is a large generic UI/payment/social/flag icon kit, not Clarisync-specific — not itemized here; pull individual icons from the board only if a specific one is needed later.

---

## 1. Brand Logo

- Component: icon mark + "CLARISYNC" wordmark, `276.82 × 42` px at 1x.
- Wordmark/icon color: Primary `#1F4756`.
- Already exported as SVG (via Figma's Export panel, downloaded locally) — re-export from the "Brand Logo" layer in the working copy above if you need another format/size (PNG, higher scale, or the icon mark / wordmark as separate files — they're separate sub-layers: `Layer_1` = icon mark, `Isolation_Mode` = wordmark).
- For the LibreChat logo/favicon mount (`docker-compose.override.yaml` → `/app/client/dist/assets/`), export at whatever sizes LibreChat's default asset filenames need, keeping those exact filenames (`logo.svg`, favicon PNGs, apple-touch icon).

---

## 2. Colors

### Core / semantic
| Role | Hex |
|---|---|
| Primary | `#1F4756` |
| Secondary | `#00ADB7` |
| Danger | `#F64040` |
| Success | `#36B933` |
| Warning | `#F6BB21` |
| Grey 300 Border | `#DEDEE4` |
| Black | `#000000` |
| White | `#FFFFFF` |

### Primary ramp (teal-navy)
| Step | Hex |
|---|---|
| 900 | `#0C1C22` |
| 800 | `#11272F` |
| 700 | `#16323C` |
| 600 | `#1A3C49` |
| **500 (base)** | **`#1F4756`** |
| 400 | `#41636F` |
| 300 | `#627E89` |
| 200 | `#849AA2` |
| 100 | `#A5B5BB` |
| 50 | `#C7D1D5` |

### Secondary ramp (teal-cyan)
| Step | Hex |
|---|---|
| 900 | `#004549` |
| 800 | `#005F65` |
| 700 | `#007980` |
| 600 | `#00939C` |
| **500 (base)** | **`#00ADB7`** |
| 400 | `#26B9C2` |
| 300 | `#4DC6CD` |
| 200 | `#73D2D7` |
| 100 | `#99DEE2` |
| 50 | `#BFEAED` |

### Grey scale
| Step | Hex |
|---|---|
| 900 | `#818288` |
| 800 | `#93949A` |
| 700 | `#A4A5AA` |
| 600 | `#B5B5BB` |
| 500 | `#C5C5CA` |
| Base | `#6E7077` |
| 400 | `#D2D2D8` |
| 300 Border | `#DEDEE4` |
| 200 | `#F2F2F4` |
| 100 Light | `#F9F9F9` |

### Opacity variants
Primary, Secondary, Grey, White, and Dark (black) each also have opacity steps (5/10/20/30/40/50/60/70/80/90%) defined in Figma — same base hex above, just apply the opacity value in CSS (`rgba()` or an alpha channel) rather than a separate hex.

---

## 3. Typography

**Font families:** **Poppins** (primary — used for nearly everything) and **Inter** (used only for two specific body sizes: P2/14px regular, Caption 2/10px regular). Both need to be actual licensed font files/web-font links (Google Fonts has both) — not pulled from Figma, still needed from you.

All heading/body text uses Primary `#1F4756` as its color.

| Style | Family | Weight | Size | Line height | Letter spacing |
|---|---|---|---|---|---|
| H1 | Poppins | Regular (400) | 75px | 90px | -3px |
| H1 Bold | Poppins | Bold (700) | 75px | 90px | -3px |
| H2 | Poppins | Regular (400) | 52px | 72px | -2px |
| H2 Bold | Poppins | Bold (700) | 52px | 72px | -2px |
| H3 | Poppins | Regular (400) | 36px | 48px | 0 |
| H3 Bold | Poppins | Bold (700) | 36px | 48px | 0 |
| H4 | Poppins | Regular (400) | 28px | 40px | 0 |
| H4 Bold | Poppins | Bold (700) | 28px | 40px | 0 |
| H5 | Poppins | Regular (400) | 24px | 36px | 0 |
| H5 Bold | Poppins | Bold (700) | 24px | 36px | 0 |
| H6 | Poppins | Regular (400) | 20px | 28px | 0 |
| H6 Bold | Poppins | Bold (700) | 20px | 28px | 0 |
| Headlines | Poppins | Regular (400) | 18px | 26px | 0 |
| Headlines Bold | Poppins | Bold (700) | 18px | 26px | 0 |
| P1 (body) | Poppins | Regular (400) | 16px | 24px | 0 |
| P1 Bold | Poppins | SemiBold (600) | 16px | 24px | 0 |
| P2 | **Inter** | Regular (400) | 14px | 22px | 0 |
| P2 Bold | Poppins | SemiBold (600) | 14px | 22px | 0 |
| Subheadline | Poppins | Regular (400) | 13px | 22px | 0 |
| Subheadline Bold | Poppins | SemiBold (600) | 13px | 22px | 0 |
| Footnote | Poppins | Regular (400) | 12px | 20px | 0 |
| Footnote Bold | Poppins | SemiBold (600) | 12px | 20px | 0 |
| Caption 1 | Poppins | Regular (400) | 11px | 18px | 0 |
| Caption 1 Bold | Poppins | SemiBold (600) | 11px | 18px | 0 |
| Caption 2 | **Inter** | Regular (400) | 10px | 12px | 0 |
| Caption 2 Bold | Poppins | Bold (700) | 10px | 12px | 0 |
| Button | Poppins | Medium (500) | 12px | 24px | 0 |
| Small Button | Poppins | Medium (500) | 10px | 14px | 0 |

Note: Poppins font style naming in Figma uses "Semi Bold"/"Extra Bold" (with a space), not "SemiBold"/"ExtraBold" — matters if referencing font files directly.

---

## 4. Buttons

Two main variants — **Primary** (bg `#1F4756`) and **Secondary** (bg `#00ADB7`) — each available at four heights, plus a couple of special-purpose variants.

| Height | Corner radius | Typical padding | Text style |
|---|---|---|---|
| 25px | 5px | px 13–20, py 5 | Poppins Medium 10px (capitalize) |
| 30px | 5px | px 15, py 5–8 | Poppins Medium 12px (capitalize) |
| 35px | 5px | px 20, py 5–8 | Inter Bold 12px (uppercase) |
| 50px | 10px | px 30, py 5–15 | Inter Bold 14px (uppercase) |

Icon-only buttons: 25/30/50px square, same radius/color rules as above, icon sized ~13/15/20px respectively.

**Special variants:**
- **Cancel (secondary/destructive):** bg `#F64040`, white text, 30px height, 5px radius, "Cancel" label, Poppins Medium 12px.
- **Cancel (primary/muted):** bg `#EAEAEA`, text `#313131`, same shape as above.
- **Continue with Google / Microsoft (OAuth buttons):** white bg, 8px radius, 30px height, 224px width, `16px` padding, `8px` gap, text color uses a literal `#1570EF` blue (not in the main palette — looks like it may be a template default rather than a real Clarisync token; confirm with Ryef/design before using it anywhere).

---

## 5. Iconography (reference only, not itemized)

A large generic icon library lives in the "Iconography" frame: UI/action icons (arrows, chevrons, file/folder icons, etc.), payment-method logos (Visa, PayPal, Stripe, etc.), social-media icons (in both "Original" and "Negative"/white variants), and a full country-flag set. None of it is Clarisync-branded — it's a standard UI kit bundled with the template. Pull specific icons from the working Figma copy only if/when a specific one is actually needed (e.g. for a custom error/empty state).

---

## 6. Still needed from you/company (not in Figma)

- Poppins + Inter font files or confirmed Google Fonts usage, licensed for web use.
- App title, welcome message copy.
- Privacy policy / Terms of Service text or URLs (from IT/legal).
- Footer text and help-link text/URL, if wanted.
- Confirmation on the OAuth-button blue (`#1570EF`) — real token or template leftover.
