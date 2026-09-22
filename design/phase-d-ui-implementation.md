# Phase D — UI redesign: implementation guide (LibreChat v0.8.8-rc2)

Design canvas: https://claude.ai/artifact/RgFDMNpi5gMNgVY7BugKnn · Brand source: `clarisync-design-system.md`

**Update:** sections 3 and 4 are now built from your real `.env`, real `docker-compose.override.yaml`, and your actual built `index.html` (not the repo source — yours has the real hashed asset filenames), plus a full source audit of the rc2 client. Section 2 (`librechat.yaml`) is still checked only against what's in project knowledge, not a live instance. **Ready-to-mount files are attached below:** `branding/index.html` (patched), `branding/logo.svg`, `branding/favicon-32x32.png`, `branding/favicon-16x16.png`, `branding/apple-touch-icon-180x180.png`, `branding/clarisync-theme.css`, `branding/docker-compose.override.yaml`. Poppins/Inter font files still need to be added (self-host — see 4.2).

---

## 1. Model naming (decision)

Users never see raw IDs. The gateway ignores the dropdown and auto-routes text vs. image, so **`quick-vision` must not be user-visible** — showing it implies a choice that doesn't exist.

| Internal ID (unchanged) | User-facing label | Description shown in picker | When |
|---|---|---|---|
| `quick-text` (+ auto vision) | **Quick** | Fast answers for everyday writing, rephrasing and short summaries. Reads attached images automatically. | Dev box now |
| future `general-text` (GPT-OSS 20B) | **Standard** | Longer documents, comparisons and careful analysis. A little slower. | Pilot |
| future `deep-text` (R1 Distill 32B) | **Deep Think** | Works through hard problems step by step before answering. Noticeably slower. | Pilot |

Do **not** rename the IDs (`model_registry.py` keys) — only labels change, via `modelSpecs`.

**Gateway blocker for the pilot:** `routing.py` ignores `req.model`, so a user picking Standard/Deep Think would be silently overridden. Before exposing more than one tier, either (a) make the gateway honour the selected tier, or (b) expose a single "Clarisync Assistant" entry and let the cascade pick. Recommendation: (a), with vision still auto-switched.

---

## 2. `librechat.yaml` — hide developer features

Add/replace these top-level blocks. `modelSpecs` with `enforce: true` removes the endpoint/model dropdown; `interface` hides the rest.

```yaml
interface:
  customWelcome: 'Welcome back, {{user.name}}'   # {{user.name}} may render the full name — check
  modelSelect: false          # no raw endpoint/model dropdown (modelSpecs picker replaces it)
  parameters: false           # hides temperature/top_p/etc.
  presets: false
  multiConvo: false           # side-by-side model comparison
  agents: false
  prompts: false              # prompt library — re-enable later if users ask
  memories: false             # memory isn't configured
  runCode: false
  webSearch: false            # no search configured; also a data-egress risk
  fileSearch: false           # our gateway handles files, not rag_api's tool
  fileCitations: false
  mcpServers:
    use: false
    create: false
  skills: false
  marketplace:
    use: false
  remoteAgents:
    use: false
  contextUsage: false         # token gauge
  contextCost: false
  feedback: true              # KEEP — pilot success metric depends on thumbs up/down
  bookmarks: true
  temporaryChat: false        # conflicts with the planned deleted-conversation archival; decide explicitly
  sharedLinks:
    create: false             # confidential data — no share links for the pilot
    share: false
    public: false
  autoSubmitFromUrl: false    # blocks one-click prompt-injection links
  privacyPolicy:
    externalUrl: '[CLARISYNC PRIVACY URL — from IT/legal]'
    openNewTab: true
  termsOfService:
    externalUrl: '[CLARISYNC TERMS URL — from IT/legal]'
    openNewTab: true
    modalAcceptance: true
    modalTitle: 'Clarisync Assistant — terms of use'
    modalContent: |
      [COMPANY-SUPPLIED TEXT]

modelSpecs:
  enforce: true
  prioritize: true
  list:
    - name: 'quick'
      label: 'Quick'
      description: 'Fast answers for everyday writing, rephrasing and short summaries. Reads attached images automatically.'
      default: true
      hideBadgeRow: true
      iconURL: '/assets/clarisync-mark.svg'
      conversation_starters:          # max 4 shown
        - 'Rephrase this email to sound clearer and more professional'
        - 'Summarise the document I attach, grouped by urgency'
        - 'Explain this clause in plain English'
        - 'Turn my rough notes into a short status update'
      preset:
        endpoint: 'Clarisync Gateway'   # must match the custom endpoint name exactly
        model: 'quick-text'
        modelLabel: 'Clarisync Assistant'
    # --- pilot only, once the gateway honours req.model ---
    # - name: 'standard'
    #   label: 'Standard'
    #   description: 'Longer documents, comparisons and careful analysis. A little slower.'
    #   hideBadgeRow: true
    #   preset: { endpoint: 'Clarisync Gateway', model: 'general-text', modelLabel: 'Clarisync Assistant' }
    # - name: 'deep-think'
    #   label: 'Deep Think'
    #   description: 'Works through hard problems step by step before answering. Noticeably slower.'
    #   hideBadgeRow: true
    #   preset: { endpoint: 'Clarisync Gateway', model: 'deep-text', modelLabel: 'Clarisync Assistant' }
```

Also in the existing custom endpoint block: `models.default: ['quick-text']` (drop `quick-vision` from the UI list; the gateway registry keeps it) and `modelDisplayLabel: 'Clarisync Assistant'`.

**Permissions caveat (from LibreChat docs):** `prompts`, `agents`, `memories`, `multiConvo`, `runCode`, `webSearch`, `fileSearch`, `mcpServers`, `skills`, `sharedLinks`, `temporaryChat`, `marketplace` seed role permissions for the `USER` role at startup. After restart, confirm in the Admin Panel (`:3000`) that the USER role actually reflects them; the Admin Panel is the preferred place to manage them going forward.

---

## 3. `.env` changes — checked against your actual file

Current relevant state, confirmed: `APP_TITLE=LibreChat`, `HELP_AND_FAQ_URL=https://librechat.ai`, `CUSTOM_FOOTER` and `ENDPOINTS` both commented out (unset). `CREDS_KEY`/`CREDS_IV`/`JWT_SECRET`/`JWT_REFRESH_SECRET` are already real generated values, not placeholders — matches the Phase A hardening claim in the handoff docs. The full `SAML_*` block already exists as empty keys (`SAML_ENTRY_POINT=`, `SAML_ISSUER=`, `SAML_CERT=`, `SAML_CALLBACK_URL=/oauth/saml/callback`, `SAML_SESSION_SECRET=`, plus claim-mapping and button-label keys) — ready to fill once Amir replies, nothing to add there. `OPENID_CLIENT_ID`/`OPENID_CLIENT_SECRET`/`OPENID_ISSUER` are also present but empty — harmless now, but **the file itself warns "If OpenID is enabled, SAML authentication will be automatically disabled"**, so when Amir's values arrive, fill only the `SAML_*` keys and leave the `OPENID_*` ones empty.

```diff
- APP_TITLE=LibreChat
+ APP_TITLE=Clarisync Assistant

- HELP_AND_FAQ_URL=https://librechat.ai
+ HELP_AND_FAQ_URL=          # empty disables the help link outright (check on rc2 — untested); or point it at an internal IT support page

- # ENDPOINTS=openAI,assistants,azureOpenAI,google,anthropic
+ ENDPOINTS=custom            # hides OpenAI/Anthropic/Google/Assistants/Agents/Bedrock — only your Clarisync Gateway shows

- # CUSTOM_FOOTER="My custom footer"
+ CUSTOM_FOOTER="The assistant can make mistakes — check anything important."
```

**Open question, not urgent:** `ALLOW_SOCIAL_LOGIN=false` is currently set. LibreChat's `registration.socialLogins` list (in your `librechat.yaml`, per project knowledge) already includes `'saml'`, but it's unconfirmed from source whether `ALLOW_SOCIAL_LOGIN=false` also suppresses the SAML button specifically, or only the OAuth-provider buttons (Google/GitHub/etc). Check this when SAML values actually arrive — don't flip it blind now.

**Leave alone for now:** `ALLOW_REGISTRATION=true` — per Ryef's notes, don't disable local email login until SAML is confirmed working, to avoid a lockout.

---

## 4. Theme — no client rebuild needed

LibreChat's colours are CSS variables holding RGB triplets (`--white: 255 255 255`). A stylesheet loaded after the app's overrides them. Mapped in rc2 source (full client audit): chat area = `--presentation`, sidebar and popovers = `--surface-primary-alt`, composer = `--surface-chat` (via `packages/client/src/utils/composer.ts`; code blocks share it), message rows mostly `--surface-secondary`/`--surface-tertiary`, text = `--text-primary`/`--text-secondary` (1,500+ uses), send button = `[data-testid="send-button"]` (painted with `bg-text-primary`, so it needs its own rule). Tailwind hardcodes `Inter` as the sans font, so the Poppins rule is a CSS override too — the earlier "font needs a rebuild" assumption doesn't hold.

### 4.1 `LibreChat/branding/clarisync-theme.css`

```css
/* clarisync-theme.css — overrides LibreChat v0.8.8-rc2 CSS variables (space-separated RGB).
   Loaded AFTER the app stylesheet via a <link> in the mounted index.html. */
html:root {
  --presentation: 247 248 248; /* #F7F8F8 */
  --surface-primary: 247 248 248; /* #F7F8F8 */
  --surface-primary-alt: 238 242 242; /* #EEF2F2 */
  --surface-secondary: 238 242 242; /* #EEF2F2 */
  --surface-tertiary: 228 235 236; /* #E4EBEC */
  --surface-chat: 255 255 255; /* #FFFFFF */
  --surface-dialog: 255 255 255; /* #FFFFFF */
  --surface-hover: 228 235 236; /* #E4EBEC */
  --surface-active: 220 227 228; /* #DCE3E4 */
  --surface-active-alt: 220 227 228; /* #DCE3E4 */
  --header-primary: 247 248 248; /* #F7F8F8 */
  --text-primary: 20 38 44; /* #14262C */
  --text-secondary: 74 94 101; /* #4A5E65 */
  --text-secondary-alt: 95 113 119; /* #5F7177 */
  --text-tertiary: 95 113 119; /* #5F7177 */
  --border-light: 220 227 228; /* #DCE3E4 */
  --border-medium: 201 211 213; /* #C9D3D5 */
  --border-medium-alt: 201 211 213; /* #C9D3D5 */
  --border-heavy: 169 183 186; /* #A9B7BA */
  --ring-primary: 0 121 128; /* #007980 */
  --surface-submit: 31 71 86; /* #1F4756 */
  --surface-submit-hover: 22 50 60; /* #16323C */
  --surface-destructive: 198 40 40; /* #C62828 */
  --text-destructive: 198 40 40; /* #C62828 */
  --theme-font-family: Inter, system-ui, sans-serif;
}
html.dark:root {
  --presentation: 15 22 24; /* #0F1618 */
  --surface-primary: 15 22 24; /* #0F1618 */
  --surface-primary-alt: 20 29 32; /* #141D20 */
  --surface-secondary: 26 36 39; /* #1A2427 */
  --surface-tertiary: 34 47 52; /* #222F34 */
  --surface-chat: 26 36 39; /* #1A2427 */
  --surface-dialog: 26 36 39; /* #1A2427 */
  --surface-hover: 34 47 52; /* #222F34 */
  --surface-active: 38 52 58; /* #26343A */
  --surface-active-alt: 38 52 58; /* #26343A */
  --header-primary: 15 22 24; /* #0F1618 */
  --text-primary: 231 237 238; /* #E7EDEE */
  --text-secondary: 166 182 186; /* #A6B6BA */
  --text-secondary-alt: 138 156 160; /* #8A9CA0 */
  --text-tertiary: 138 156 160; /* #8A9CA0 */
  --border-light: 38 52 58; /* #26343A */
  --border-medium: 51 68 74; /* #33444A */
  --border-medium-alt: 51 68 74; /* #33444A */
  --border-heavy: 70 89 95; /* #46595F */
  --ring-primary: 77 198 205; /* #4DC6CD */
  --surface-submit: 77 198 205; /* #4DC6CD */
  --surface-submit-hover: 115 210 215; /* #73D2D7 */
  --surface-destructive: 179 38 30; /* #B3261E */
  --text-destructive: 255 138 138; /* #FF8A8A */
}
/* Fonts: Inter for reading, Poppins for headings and UI labels */
body, .font-sans { font-family: Inter, system-ui, sans-serif; }
h1, h2, h3, button, [role="menuitem"], [role="option"] { font-family: Poppins, Inter, system-ui, sans-serif; }
/* Send button: brand colour instead of LibreChat's bg-text-primary */
[data-testid="send-button"]:not(:disabled) { background-color: #1F4756 !important; color: #FFFFFF !important; }
html.dark [data-testid="send-button"]:not(:disabled) { background-color: #4DC6CD !important; color: #0F1618 !important; }
/* Links and focus */
.markdown a, .prose a { color: #007980; }
html.dark .markdown a, html.dark .prose a { color: #4DC6CD; }
:focus-visible { outline-color: #007980; }
```

### 4.2 Fonts — self-host, don't use Google Fonts

Internal confidential tool → don't make every page load call Google. Download Poppins (400/500/600) and Inter (400/500/600) woff2 files (both SIL OFL, free for web use), put them in `LibreChat/branding/fonts/`, and add `@font-face` rules to the top of the theme CSS pointing at `/assets/fonts/<file>.woff2`. (rc2 already bundles Inter, so Poppins is the only must-add.)

### 4.3 Custom `index.html` — already built from your real file

`branding/index.html` (attached) is your uploaded, actually-built file (real hashed asset names — `index.B6ZW-LhR.js` etc.) with these changes applied, nothing else touched:

- `<title>` → `Clarisync Assistant`; `description` meta → an internal-tool description instead of LibreChat's.
- `theme-color` → `#F7F8F8`.
- Loading-screen script: the two brand-relevant background colors changed, `'#0d0d0d'` → `'#0F1618'` (normal dark) and the light-mode `'#ffffff'` → `'#F7F8F8'`. The **high-contrast** branches (`'#000000'` / `'#ffffff'` for Windows Contrast Theme / `prefers-contrast: more`) are deliberately left untouched — those exist for accessibility and should stay true black/white regardless of brand.
- Added `<link rel="stylesheet" href="./assets/clarisync-theme.css">` right after the app's own compiled stylesheet link, so it loads after and can override.

**Re-do this whenever LibreChat's image updates** — new hashed filenames mean this exact patch won't apply to the next build's `index.html`; pull the new one the same way (`docker cp LibreChat:/app/client/dist/index.html ./index.html`) and re-apply the same edits (title, description, theme-color, the two background colors, the stylesheet link).

### 4.4 Logo and favicons — already generated from your Figma export

From `Brand_Logo.svg` (the full 277×42 lockup you exported): the icon mark is the first `<g>` group (two `<path>`s, `#1F4756`, natural size ~38×42) — I extracted it and rendered:
- `branding/favicon-32x32.png`, `branding/favicon-16x16.png` — transparent background.
- `branding/apple-touch-icon-180x180.png` — `#F7F8F8` background (iOS doesn't handle transparency well on this icon), mark scaled to 132px and centered.
- `branding/logo.svg` — your original file, unchanged, for the `logo.svg` asset slot.

### 4.5 `docker-compose.override.yaml` — real before / after

Your actual file (uploaded) only mounted `librechat.yaml` plus the Mongo/Postgres credential passthrough — matches Ryef's handover exactly, nothing drifted. `branding/docker-compose.override.yaml` (attached) is your file with the branding mounts added:

```diff
     volumes:
       - ./librechat.yaml:/app/librechat.yaml
+      - ./branding/index.html:/app/client/dist/index.html
+      - ./branding/clarisync-theme.css:/app/client/dist/assets/clarisync-theme.css
+      - ./branding/fonts:/app/client/dist/assets/fonts
+      - ./branding/logo.svg:/app/client/dist/assets/logo.svg
+      - ./branding/favicon-32x32.png:/app/client/dist/assets/favicon-32x32.png
+      - ./branding/favicon-16x16.png:/app/client/dist/assets/favicon-16x16.png
+      - ./branding/apple-touch-icon-180x180.png:/app/client/dist/assets/apple-touch-icon-180x180.png
```
`environment:` and the `vectordb` block are untouched. Put the attached files in a `branding/` folder next to your `docker-compose.override.yaml`, then `docker compose up -d api`.

**Still missing before this actually works:** `branding/fonts/` (Poppins + Inter woff2 files — see 4.2) and `branding/clarisync-theme.css` needs the `@font-face` rules pointing at them added to the top (I generated the color-variable part of this file already; see the attached `clarisync-theme.css` — the font-face block isn't in it yet since I don't have the font files).

### 4.6 Verify

Hard-refresh (Ctrl+Shift+R), then in DevTools → Elements → `<html>` → Computed, check `--presentation` shows `247 248 248`. If a surface didn't change, inspect it, read its `bg-*` class, and add that variable to the theme file.

---

## 5. What still needs a rebuild (unchanged from Phase D scope)

- LibreChat's error wrapper text. Source (rc2): `client/src/components/Messages/Content/Error.tsx`, line 163:
  `const defaultResponse = \`Something went wrong. Here's the specific error message we encountered: ${errorMessage}\`;`
  It's used whenever the error text isn't JSON with a known LibreChat error `code`/`type` — our gateway's 400s always land here. There's no config or translation override for it (locales are bundled), so it's a patch + rebuild. Minimal patch: make `defaultResponse` just `errorMessage` with the `An error occurred while processing the request: <status> ` prefix stripped by regex. Bundle this with any other client patch, since every rebuild means maintaining a fork of the image.
- The error box styling itself uses `--status-error-subtle` / `--status-error-border` variables, so its colours can still be themed from the CSS file without a rebuild.
- The "Private · stays on Clarisync servers" header badge — not a config option; either a small client patch or put it in `customWelcome`/footer text instead.

---

## 6. Palette rationale (short)

Brand teal `#00ADB7` is 2.74:1 against white — fails WCAG for text and for white-on-teal buttons, so it can't be the working UI accent. It's darkened to `#007980` (5.19:1) for links/icons/focus in light mode; the lighter `#4DC6CD` works in dark mode (8.95:1). Surfaces are neutrals with a faint teal tint so the product reads as Clarisync without large blocks of colour — the same approach Claude, ChatGPT and Gemini use (brand colour in 1–3 places, everything else neutral). Brand primary `#1F4756` is kept for the send button and avatar.
