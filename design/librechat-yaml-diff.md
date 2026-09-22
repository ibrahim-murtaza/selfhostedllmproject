# librechat.yaml changes — model rename/hide + privacy policy

Apply, then `docker compose restart api` (bind-mounted, no rebuild).

## 1. Remove the privacy policy link and the (generic, wrong-company) ToS modal

Your current file has this, verbatim (this is LibreChat's own sample text, not Clarisync's — every user currently has to click through it):

```yaml
interface:
  customWelcome: 'Welcome to LibreChat! Enjoy your experience.'
  privacyPolicy:
    externalUrl: 'https://librechat.ai/privacy-policy'
    openNewTab: true
  termsOfService:
    externalUrl: 'https://librechat.ai/tos'
    openNewTab: true
    modalAcceptance: true
    modalTitle: 'Terms of Service for LibreChat'
    modalContent: |
      # Terms and Conditions for LibreChat
      ...
  modelSelect: true
  parameters: true
  presets: true
  ...
```

**Delete the `privacyPolicy:` and `termsOfService:` blocks entirely** (don't leave them with empty/placeholder URLs — confirmed from source, `client/src/components/Auth/Footer.tsx` and `Chat/Footer.tsx` only render the link when `externalUrl != null`, so omitting the key is what actually hides it). You flagged privacy policy specifically; I'm pulling terms of service too since it's the same problem one level worse — right now every user has to click through a modal agreeing to LibreChat's own generic legal text, not Clarisync's. Flag me if you'd rather keep a placeholder ToS modal live instead of removing it — easy to put back once real text exists.

## 2. Model rename + hide — add `modelSpecs`, single "Quick" entry

```yaml
modelSpecs:
  enforce: true
  prioritize: true
  list:
    - name: 'quick'
      label: 'Quick'
      description: 'Fast answers for everyday writing, rephrasing and short summaries. Reads attached images automatically.'
      default: true
      hideBadgeRow: true
      conversation_starters:
        - 'Rephrase this email to sound clearer and more professional'
        - 'Summarise the document I attach, grouped by urgency'
        - 'Explain this clause in plain English'
        - 'Turn my rough notes into a short status update'
      preset:
        endpoint: 'Clarisync Gateway'
        model: 'quick-text'
        modelLabel: 'Clarisync Assistant'
```

`enforce: true` on its own hides the raw endpoint/model dropdown, parameter sliders, and presets (confirmed from LibreChat's docs — model specs disable those three unless `interface` says otherwise). So this single block covers "hide the other models" and "rename to just Quick" together — you don't need to touch `interface.modelSelect`/`parameters`/`presets` separately.

`quick-vision` stays in `model_registry.py` and the custom endpoint's `models.default` list — the gateway still auto-routes to it on image upload, it's just never a user-visible choice. Leave `endpoints.custom` as-is.

**Not applying yet (unrelated to what you asked, still just drafted in `phase-d-ui-implementation.md`):** `webSearch`, `agents`, `mcpServers`, etc. Say the word if you want those in the same restart.
